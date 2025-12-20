"""
Обработчики покупки подписки.

Обработчики:
    - buy_subscription_{plan_id} — инициировать покупку подписки
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from src.services.db import subscription_plan_repo
from src.services.payments import payment_service
from src.config import settings

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

        # Создать платеж
        payment = await payment_service.create_subscription_payment(
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            plan_id=plan_id,
            return_url=settings.YOOKASSA_RETURN_URL,
        )

        # Отправить ссылку на оплату
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"💳 Оплатить {int(plan['price_rub'])}₽",
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

        await callback.message.edit_text(
            f"📅 Подписка: {plan['name']}\n"
            f"💰 Сумма: {int(plan['price_rub'])}₽\n"
            f"⏱ Срок: {plan['duration_days']} дней\n"
            f"🎁 Включено токенов: {plan['tokens_included']} вопросов\n\n"
            f"Нажмите кнопку ниже для оплаты.\n"
            f"После успешной оплаты подписка будет активирована автоматически.\n\n"
            f"{'⚠️ Тестовый режим' if settings.YOOKASSA_TEST_MODE else ''}",
            reply_markup=keyboard
        )

        logger.info(
            f"Subscription payment created: user={user_id}, plan={plan['name']}, "
            f"amount={plan['price_rub']}, payment_id={payment['payment_id']}"
        )

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
