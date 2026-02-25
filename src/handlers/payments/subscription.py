"""
Обработчики покупки подписки.

Обработчики:
    - buy_subscription_{plan_id} — инициировать покупку подписки
"""

import asyncio
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from src.services.db import subscription_plan_repo
from src.services.payments import payment_service
from src.config import settings
from src.pricing import pluralize_questions

logger = logging.getLogger(__name__)
router = Router(name="payments_subscription")


@router.callback_query(F.data.startswith("buy_subscription_"))
async def buy_subscription_handler(callback: CallbackQuery):
    """
    Обработка покупки подписки.

    Callback data format: buy_subscription_{plan_id}
    """
    await callback.answer()

    telegram_user_id = callback.from_user.id

    # Получить внутренний user_id из БД
    from src.services.db.users_repo import get_or_create_user
    user_id = await get_or_create_user(
        telegram_user_id=telegram_user_id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
    )

    try:
        # Извлечь plan_id из callback_data
        plan_id = int(callback.data.split("_")[-1])

        # Получить план из БД
        plan = await subscription_plan_repo.get_by_id(plan_id)

        if not plan:
            await callback.message.edit_text(
                "❌ План подписки не найден.\n"
                "Попробуйте выбрать другой или свяжитесь с поддержкой.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="◀️ Назад к покупкам",
                        callback_data="show_payment_menu"
                    )]
                ])
            )
            return

        if not plan.get("is_active"):
            await callback.message.edit_text(
                "⚠️ Эта подписка временно недоступна.\n"
                "Выберите другой вариант или попробуйте позже.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="◀️ Назад к покупкам",
                        callback_data="show_payment_menu"
                    )]
                ])
            )
            return

        # --- Проверяем бонусные токены из рассылки ---
        from src.services.db.discount_repo import get_user_active_broadcast_discount
        import math
        broadcast_disc = await get_user_active_broadcast_discount(user_id)
        bonus_tokens = 0
        if broadcast_disc:
            raw_bonus = broadcast_disc.get('bonus_tokens', 0) or 0
            bonus_mode = broadcast_disc.get('bonus_tokens_mode', 'absolute')
            if bonus_mode == 'percent' and raw_bonus > 0:
                bonus_tokens = math.ceil(plan.get('tokens_included', 0) * raw_bonus / 100)
            else:
                bonus_tokens = raw_bonus

        # --- Режим перенаправления на менеджера (тестовый запуск) ---
        if settings.PAYMENTS_REDIRECT_MODE:
            from urllib.parse import quote

            price = int(plan['price_rub'])
            qty = plan.get('tokens_included', 0)
            contact = settings.PAYMENTS_CONTACT_USERNAME

            pre_filled = f"Здравствуйте, хочу оформить подписку «{plan['name']}» ({price}₽/мес)"
            link = f"https://t.me/{contact}?text={quote(pre_filled)}"

            if bonus_tokens > 0:
                limit_line = f"🎁 Лимит: {qty} + {bonus_tokens} бонус = <b>{qty + bonus_tokens} токенов</b> в месяц"
            else:
                limit_line = f"🎁 Лимит: {pluralize_questions(qty)} в месяц"

            sub_text = (
                f"📅 Подписка: <b>{plan['name']}</b>\n"
                f"💰 Цена: {price}₽/мес\n"
                f"⏱ Срок: {plan['duration_days']} дней\n"
                f"{limit_line}\n\n"
                f"Для оформления подписки напишите нашему менеджеру — "
                f"нажмите кнопку ниже."
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="✉️ Написать менеджеру",
                    url=link,
                )],
                [InlineKeyboardButton(
                    text="◀️ Назад к покупкам",
                    callback_data="show_payment_menu",
                )],
            ])

            await callback.message.edit_text(sub_text, reply_markup=keyboard, parse_mode="HTML")

            try:
                from src.services.db.messages_repo import log_message
                await log_message(user_id=user_id, direction="user", text=f"[Кнопка] Подписка: {plan['name']}", session_id=f"tg:{telegram_user_id}", meta={"type": "callback", "callback_data": callback.data})
                await log_message(user_id=user_id, direction="bot", text=sub_text, session_id=f"tg:{telegram_user_id}")
            except Exception:
                pass

            logger.info(f"Subscription redirect shown: user={user_id}, plan={plan['name']}")

            # Авто-переход CRM: * → saw_pricing
            from src.services.db.funnel_repo import auto_move_client_in_crm
            asyncio.create_task(auto_move_client_in_crm(user_id, 'saw_pricing'))
            return

        # Создать платеж (скидка применяется внутри payment_service)
        payment = await payment_service.create_subscription_payment(
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            plan_id=plan_id,
            return_url=settings.YOOKASSA_RETURN_URL,
        )

        pay_amount = int(payment['amount'])

        # Отправить ссылку на оплату
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"💳 Оплатить {pay_amount}₽",
                url=payment["confirmation_url"]
            )],
            [InlineKeyboardButton(
                text="❌ Отмена",
                callback_data=f"payment_cancel_{payment['payment_id']}"
            )],
            [InlineKeyboardButton(
                text="◀️ Назад к покупкам",
                callback_data="show_payment_menu"
            )]
        ])

        qty = plan.get('tokens_included', 0)

        if bonus_tokens > 0:
            limit_line = f"🎁 Лимит: {qty} + {bonus_tokens} бонус = <b>{qty + bonus_tokens} токенов</b> в месяц"
        else:
            limit_line = f"🎁 Лимит: {pluralize_questions(qty)} в месяц"

        # Текст с учётом скидки
        if payment.get("discount_percent"):
            original = int(payment['original_amount'])
            sub_text = (
                f"📅 Подписка: {plan['name']}\n"
                f"💰 Цена: <s>{original}₽</s> → <b>{pay_amount}₽</b>/мес (скидка {payment['discount_percent']}%)\n"
                f"⏱ Срок: {plan['duration_days']} дней\n"
                f"{limit_line}\n\n"
                f"Нажмите кнопку ниже для оплаты.\n"
                f"После успешной оплаты подписка будет активирована автоматически.\n\n"
                f"{'⚠️ Тестовый режим' if settings.YOOKASSA_TEST_MODE else ''}"
            )
        else:
            sub_text = (
                f"📅 Подписка: {plan['name']}\n"
                f"💰 Сумма: {pay_amount}₽/мес\n"
                f"⏱ Срок: {plan['duration_days']} дней\n"
                f"{limit_line}\n\n"
                f"Нажмите кнопку ниже для оплаты.\n"
                f"После успешной оплаты подписка будет активирована автоматически.\n\n"
                f"{'⚠️ Тестовый режим' if settings.YOOKASSA_TEST_MODE else ''}"
            )
        await callback.message.edit_text(sub_text, reply_markup=keyboard, parse_mode="HTML")

        # Логируем действие пользователя + ответ бота
        try:
            from src.services.db.messages_repo import log_message
            await log_message(user_id=user_id, direction="user", text=f"[Кнопка] Подписка: {plan['name']}", session_id=f"tg:{telegram_user_id}", meta={"type": "callback", "callback_data": callback.data})
            await log_message(user_id=user_id, direction="bot", text=sub_text, session_id=f"tg:{telegram_user_id}")
        except Exception:
            pass

        logger.info(
            f"Subscription payment created: user={user_id}, plan={plan['name']}, "
            f"amount={pay_amount}, payment_id={payment['payment_id']}"
        )

        # Авто-переход CRM: * → saw_pricing
        from src.services.db.funnel_repo import auto_move_client_in_crm
        asyncio.create_task(auto_move_client_in_crm(user_id, 'saw_pricing'))

    except Exception as e:
        logger.error(f"Error creating subscription payment for user {user_id}: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ Произошла ошибка при создании платежа.\n"
            "Попробуйте еще раз или свяжитесь с поддержкой.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="◀️ Назад к покупкам",
                    callback_data="show_payment_menu"
                )]
            ])
        )
