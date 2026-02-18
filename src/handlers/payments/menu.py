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


def get_payment_menu_keyboard(
    subscription_plans: list,
    token_packages: list,
    discount_percent: int = 0,
) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру меню покупок.

    Args:
        subscription_plans: Список активных планов подписки
        token_packages: Список активных пакетов токенов
        discount_percent: Процент скидки (0 = без скидки)

    Returns:
        InlineKeyboardMarkup с кнопками покупки
    """
    buttons = []

    # Заголовок разовых покупок
    if token_packages:
        buttons.append([
            InlineKeyboardButton(
                text="📦 Разовая покупка",
                callback_data="payment_menu_header_tokens"
            )
        ])

        # Пакеты токенов
        for package in token_packages:
            price = int(package['price_rub'])
            if discount_percent > 0:
                discounted = int(package['price_rub'] * (100 - discount_percent) / 100)
                text = f"  {package['name']} — {discounted}₽ (было {price}₽)"
            else:
                text = f"  {package['name']} — {price}₽"
            buttons.append([
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"buy_tokens_{package['id']}"
                )
            ])

    # Заголовок подписок
    if subscription_plans:
        buttons.append([
            InlineKeyboardButton(
                text="📅 Подписка",
                callback_data="payment_menu_header_subscription"
            )
        ])

        # Планы подписки
        for plan in subscription_plans:
            qty = plan.get('tokens_included', 0)
            qty_text = f" ({pluralize_questions(qty)}/мес)" if qty else ""
            price = int(plan['price_rub'])
            if discount_percent > 0:
                discounted = int(plan['price_rub'] * (100 - discount_percent) / 100)
                text = f"  {plan['name']} — {discounted}₽/мес{qty_text} (было {price}₽)"
            else:
                text = f"  {plan['name']} — {price}₽/мес{qty_text}"
            buttons.append([
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"buy_subscription_{plan['id']}"
                )
            ])

    # Кнопка возврата
    buttons.append([
        InlineKeyboardButton(
            text="◀️ Назад в меню",
            callback_data="main_menu"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _build_menu_text(
    token_packages: list,
    subscription_plans: list,
    discount_percent: int = 0,
) -> str:
    """Формирует текст меню покупок с учётом скидки."""
    text_parts = ["💰 Пополнить баланс\n"]

    if discount_percent > 0:
        text_parts.append(f"\n🎉 У вас скидка <b>{discount_percent}%</b> по приглашению!\n")

    if token_packages:
        text_parts.append("\n📦 Разовая покупка:")
        for package in token_packages:
            price = int(package['price_rub'])
            if discount_percent > 0:
                discounted = int(package['price_rub'] * (100 - discount_percent) / 100)
                text_parts.append(
                    f"  • {package['name']} — <s>{price}₽</s> <b>{discounted}₽</b>"
                )
            else:
                text_parts.append(
                    f"  • {package['name']} — {price}₽"
                )

    if subscription_plans:
        text_parts.append("\n📅 Подписка:")
        for plan in subscription_plans:
            qty = plan.get('tokens_included', 0)
            tokens_info = f"({pluralize_questions(qty)}/мес)" if qty else ""
            price = int(plan['price_rub'])
            if discount_percent > 0:
                discounted = int(plan['price_rub'] * (100 - discount_percent) / 100)
                text_parts.append(
                    f"  • {plan['name']} — <s>{price}₽</s> <b>{discounted}₽</b>/мес {tokens_info}"
                )
            else:
                text_parts.append(
                    f"  • {plan['name']} — {price}₽/мес {tokens_info}"
                )

    text_parts.append("\nВыберите подходящий вариант:")
    return "\n".join(text_parts)


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
        discount_percent = await get_user_active_discount(internal_user_id) or 0

        menu_text = _build_menu_text(token_packages, subscription_plans, discount_percent)
        keyboard = get_payment_menu_keyboard(subscription_plans, token_packages, discount_percent)

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
        discount_percent = await get_user_active_discount(user_id) or 0

        menu_text = _build_menu_text(token_packages, subscription_plans, discount_percent)
        keyboard = get_payment_menu_keyboard(subscription_plans, token_packages, discount_percent)

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
