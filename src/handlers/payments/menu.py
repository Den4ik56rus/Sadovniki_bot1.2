"""
Главное меню покупок токенов и подписок.

Обработчики:
    - /buy — открыть меню покупок
    - Кнопка "💰 Пополнить баланс" из главного меню
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from src.services.db import subscription_plan_repo, token_package_repo
from src.pricing import pluralize_questions

logger = logging.getLogger(__name__)
router = Router(name="payments_menu")


_RU_MONTHS = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}


def _fmt_date(dt) -> str:
    if not dt:
        return "—"
    return f"{dt.day} {_RU_MONTHS[dt.month]} {dt.year}"


def get_payment_menu_keyboard(
    subscription_plans: list,
    token_packages: list,
    has_subscription: bool = False,
    token_discount_percent: int = 0,
    invite_discount_percent: int = 0,
    auto_renew: bool = False,
) -> InlineKeyboardMarkup:
    buttons = []

    # Продлить / оформить подписку
    if has_subscription:
        buttons.append([InlineKeyboardButton(
            text="🔄 Продлить подписку",
            callback_data="show_subscription_plans"
        )])
    else:
        buttons.append([InlineKeyboardButton(
            text="📋 Оформить подписку",
            callback_data="show_subscription_plans"
        )])

    # Отменить автопродление — только если включено
    if has_subscription and auto_renew:
        buttons.append([InlineKeyboardButton(
            text="❌ Отменить автопродление",
            callback_data="cancel_auto_renew"
        )])

    # Купить доп. токены
    if token_packages:
        buttons.append([InlineKeyboardButton(
            text="➕ Купить доп. токены",
            callback_data="show_token_packages" if has_subscription else "buy_tokens_no_subscription"
        )])

    buttons.append([InlineKeyboardButton(
        text="◀️ Назад в меню",
        callback_data="main_menu"
    )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _build_menu_text(
    token_packages: list,
    subscription_plans: list,
    has_subscription: bool = False,
    token_discount_percent: int = 0,
    invite_discount_percent: int = 0,
    active_subscription: dict = None,
) -> str:
    """Формирует текст меню управления подпиской."""
    text_parts = ["⚙️ <b>Управлять подпиской</b>\n"]

    # Блок текущей подписки
    if active_subscription:
        plan = active_subscription.get("plan", {})
        plan_name = plan.get("name", "—")
        expires_at = active_subscription.get("expires_at")
        auto_renew = active_subscription.get("auto_renew", False)
        auto_renew_str = "✅ активно" if auto_renew else "❌ не активно"
        text_parts.append(
            f"📋 <b>Тариф:</b>\n"
            f"<b>{plan_name}</b>  ✅\n"
            f"Подписка до: {_fmt_date(expires_at)}\n"
            f"Автопродление: {auto_renew_str}\n"
        )
    else:
        text_parts.append("📋 <b>Тариф:</b>\n<b>Пробный</b>  |  Без подписки\n")

    # Тарифные планы
    if subscription_plans:
        text_parts.append("\n📅 <b>Тарифные планы:</b>")
        for plan in subscription_plans:
            qty = plan.get('tokens_included', 0)
            carryover = plan.get('max_carryover', 0)
            price = int(plan['price_rub'])
            carryover_info = f"\n  ↩️ Перенос: до {carryover} токенов" if carryover else ""
            if invite_discount_percent > 0:
                discounted = int(price * (100 - invite_discount_percent) / 100)
                price_str = f"<s>{price}₽</s> → <b>{discounted}₽</b>/мес  (скидка {invite_discount_percent}%)"
            else:
                price_str = f"{price}₽/мес"
            text_parts.append(
                f"\nПодписка: <b>{plan['name']}</b>\n"
                f"Цена: {price_str}\n"
                f"Срок: {plan.get('duration_days', 30)} дней\n"
                f"<b>Лимит: {qty} токенов в месяц</b>"
                f"{carryover_info}"
            )

    # Доп. токены
    if token_packages and has_subscription:
        best_discount = max(token_discount_percent, invite_discount_percent)
        text_parts.append("\n\n➕ <b>Дополнительные токены:</b>")
        for package in token_packages:
            price = int(package['price_rub'])
            if best_discount > 0:
                discounted = int(price * (100 - best_discount) / 100)
                text_parts.append(
                    f"  • {package['name']} — <s>{price}₽</s> <b>{discounted}₽</b>"
                )
            else:
                text_parts.append(f"  • {package['name']} — {price}₽")
    elif token_packages and not has_subscription:
        text_parts.append("\n\n➕ <b>Дополнительные токены</b>\n  Доступны только при активной подписке")

    return "\n".join(text_parts)


async def _get_subscription_info(user_id: int) -> tuple:
    """Получает информацию о подписке пользователя.

    Returns:
        (has_subscription, token_discount_percent, active_subscription_or_None)
    """
    from src.services.payments.subscription_service import get_active_subscription
    active_sub = await get_active_subscription(user_id)
    if active_sub:
        plan = active_sub.get("plan", {})
        return True, plan.get("token_discount_percent", 0) or 0, active_sub
    return False, 0, None


@router.message(Command("buy"))
@router.message(F.text == "💰 Пополнить баланс")
async def show_payment_menu(message: Message):
    """Показать меню покупок."""
    telegram_user_id = message.from_user.id

    # Получаем внутренний user_id
    from src.services.db.users_repo import get_or_create_user
    from src.services.db.messages_repo import log_message
    internal_user_id = await get_or_create_user(
        telegram_user_id=telegram_user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )

    # Логируем нажатие кнопки пользователем
    btn_text = message.text or "/buy"
    try:
        await log_message(
            user_id=internal_user_id,
            direction="user",
            text=btn_text,
            session_id=f"tg:{telegram_user_id}",
            meta={"type": "callback", "callback_data": "payment_menu"},
        )
    except Exception:
        pass

    try:
        # Получить активные планы и пакеты
        subscription_plans = await subscription_plan_repo.get_all_active()
        token_packages = await token_package_repo.get_all_active()

        if not subscription_plans and not token_packages:
            no_plans_text = "⚠️ В данный момент нет доступных тарифов.\nПопробуйте позже или свяжитесь с поддержкой."
            await message.answer(no_plans_text)
            try:
                await log_message(user_id=internal_user_id, direction="bot", text=no_plans_text, session_id=f"tg:{telegram_user_id}")
            except Exception:
                pass
            return

        # Проверить скидку по инвайт-ссылке
        from src.services.db.invite_link_repo import get_user_active_discount
        _inv = await get_user_active_discount(internal_user_id)
        invite_discount = _inv["discount_percent"] if _inv else 0

        # Проверить подписку и скидку от неё
        has_subscription, token_discount, active_sub = await _get_subscription_info(internal_user_id)

        menu_text = _build_menu_text(
            token_packages, subscription_plans,
            has_subscription=has_subscription,
            token_discount_percent=token_discount,
            invite_discount_percent=invite_discount,
            active_subscription=active_sub,
        )
        auto_renew = active_sub.get("auto_renew", False) if active_sub else False
        keyboard = get_payment_menu_keyboard(
            subscription_plans, token_packages,
            has_subscription=has_subscription,
            token_discount_percent=token_discount,
            invite_discount_percent=invite_discount,
            auto_renew=auto_renew,
        )

        await message.answer(menu_text, reply_markup=keyboard, parse_mode="HTML")

        # Логируем ответ бота
        try:
            await log_message(user_id=internal_user_id, direction="bot", text=menu_text, session_id=f"tg:{telegram_user_id}")
        except Exception:
            pass

        logger.info(f"Payment menu shown to user {telegram_user_id}")

    except Exception as e:
        logger.error(f"Error showing payment menu for user {telegram_user_id}: {e}", exc_info=True)
        await message.answer(
            "❌ Произошла ошибка при загрузке меню покупок.\n"
            "Попробуйте позже или свяжитесь с поддержкой."
        )


@router.callback_query(F.data == "show_payment_menu")
async def show_payment_menu_callback(callback: CallbackQuery):
    """Показать меню покупок (callback версия)."""
    await callback.answer()

    telegram_user_id = callback.from_user.id

    # Убедиться что пользователь существует в БД
    from src.services.db.users_repo import get_or_create_user
    user_id = await get_or_create_user(
        telegram_user_id=telegram_user_id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
    )

    try:
        # Получить активные планы и пакеты
        subscription_plans = await subscription_plan_repo.get_all_active()
        token_packages = await token_package_repo.get_all_active()

        if not subscription_plans and not token_packages:
            await callback.message.edit_text(
                "⚠️ В данный момент нет доступных тарифов.\n"
                "Попробуйте позже или свяжитесь с поддержкой."
            )
            return

        # Проверить скидку по инвайт-ссылке
        from src.services.db.invite_link_repo import get_user_active_discount
        _inv = await get_user_active_discount(user_id)
        invite_discount = _inv["discount_percent"] if _inv else 0

        # Проверить подписку и скидку от неё
        has_subscription, token_discount, active_sub = await _get_subscription_info(user_id)

        menu_text = _build_menu_text(
            token_packages, subscription_plans,
            has_subscription=has_subscription,
            token_discount_percent=token_discount,
            invite_discount_percent=invite_discount,
            active_subscription=active_sub,
        )
        auto_renew = active_sub.get("auto_renew", False) if active_sub else False
        keyboard = get_payment_menu_keyboard(
            subscription_plans, token_packages,
            has_subscription=has_subscription,
            token_discount_percent=token_discount,
            invite_discount_percent=invite_discount,
            auto_renew=auto_renew,
        )

        await callback.message.edit_text(
            menu_text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        logger.info(f"Payment menu shown to user {user_id} (callback)")

    except Exception as e:
        logger.error(f"Error showing payment menu callback for user {user_id}: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ Произошла ошибка при загрузке меню покупок.\n"
            "Попробуйте позже или свяжитесь с поддержкой."
        )


@router.callback_query(F.data.in_(["payment_menu_header_tokens", "payment_menu_header_subscription"]))
async def payment_menu_headers(callback: CallbackQuery):
    """Обработка кликов по заголовкам (они не активны, просто заглушка)."""
    await callback.answer()


@router.callback_query(F.data == "show_subscription_plans")
async def show_subscription_plans_handler(callback: CallbackQuery):
    """Показать список тарифных планов с кнопками для покупки."""
    await callback.answer()

    from src.services.db.users_repo import get_or_create_user
    from src.services.db.invite_link_repo import get_user_active_discount
    user_id = await get_or_create_user(
        telegram_user_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
    )

    subscription_plans = await subscription_plan_repo.get_all_active()
    _inv = await get_user_active_discount(user_id)
    invite_discount = _inv["discount_percent"] if _inv else 0

    buttons = []
    for plan in subscription_plans:
        price = int(plan['price_rub'])
        if invite_discount > 0:
            discounted = int(price * (100 - invite_discount) / 100)
            text = f"{plan['name']}  {price}₽ → {discounted}₽/мес"
        else:
            text = f"{plan['name']}  {price}₽/мес"
        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"buy_subscription_{plan['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="show_payment_menu")])

    await callback.message.edit_text(
        "📅 <b>Выберите тариф:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "show_token_packages")
async def show_token_packages_handler(callback: CallbackQuery):
    """Показать список пакетов доп. токенов с кнопками для покупки."""
    await callback.answer()

    from src.services.db.users_repo import get_or_create_user
    from src.services.db.invite_link_repo import get_user_active_discount
    user_id = await get_or_create_user(
        telegram_user_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
    )

    token_packages = await token_package_repo.get_all_active()
    _inv = await get_user_active_discount(user_id)
    invite_discount = _inv["discount_percent"] if _inv else 0
    _, token_discount, _ = await _get_subscription_info(user_id)
    best_discount = max(token_discount, invite_discount)

    buttons = []
    for package in token_packages:
        price = int(package['price_rub'])
        if best_discount > 0:
            discounted = int(price * (100 - best_discount) / 100)
            text = f"{package['name']}  {price}₽ → {discounted}₽"
        else:
            text = f"{package['name']}  {price}₽"
        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"buy_tokens_{package['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="show_payment_menu")])

    await callback.message.edit_text(
        "➕ <b>Выберите пакет токенов:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "buy_tokens_no_subscription")
async def buy_tokens_no_subscription(callback: CallbackQuery):
    """Попытка купить доп. токены без подписки."""
    await callback.answer(
        "Доп. токены доступны только при активной подписке. Сначала оформите подписку.",
        show_alert=True,
    )


@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery):
    """Вернуться в профиль."""
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass
    from src.handlers.menu import render_and_send_profile
    await render_and_send_profile(
        bot=callback.bot,
        chat_id=callback.from_user.id,
        telegram_user_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
    )


@router.callback_query(F.data == "cancel_auto_renew")
async def cancel_auto_renew_handler(callback: CallbackQuery):
    """Отменить автопродление подписки."""
    await callback.answer()

    from src.services.db.users_repo import get_or_create_user
    user_id = await get_or_create_user(
        telegram_user_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
    )

    from src.services.db.user_subscription_repo import get_active_subscription
    from src.services.db.pool import get_pool
    subscription = await get_active_subscription(user_id)

    if not subscription:
        await callback.answer("Активная подписка не найдена.", show_alert=True)
        return

    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE user_subscriptions SET auto_renew = false WHERE id = $1",
            subscription["id"],
        )

    await callback.answer("✅ Автопродление отключено.", show_alert=True)
    # Перезагружаем меню
    await show_payment_menu_callback(callback)
