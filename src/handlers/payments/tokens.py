"""
Обработчики покупки пакетов токенов.

Обработчики:
    - buy_tokens_{package_id} — инициировать покупку пакета
    - payment_cancel — отменить платеж
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from src.services.db import token_package_repo
from src.services.payments import payment_service
from src.config import settings

logger = logging.getLogger(__name__)
router = Router(name="payments_tokens")


@router.callback_query(F.data.startswith("buy_tokens_"))
async def buy_tokens_handler(callback: CallbackQuery):
    """
    Обработка покупки пакета токенов.

    Callback data format: buy_tokens_{package_id}
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
        # Извлечь package_id из callback_data
        package_id = int(callback.data.split("_")[-1])

        # Получить пакет из БД
        package = await token_package_repo.get_by_id(package_id)

        if not package:
            await callback.message.edit_text(
                "❌ Пакет токенов не найден.\n"
                "Попробуйте выбрать другой или свяжитесь с поддержкой.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="◀️ Назад к покупкам",
                        callback_data="show_payment_menu"
                    )]
                ])
            )
            return

        if not package.get("is_active"):
            await callback.message.edit_text(
                "⚠️ Этот пакет токенов временно недоступен.\n"
                "Выберите другой вариант или попробуйте позже.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="◀️ Назад к покупкам",
                        callback_data="show_payment_menu"
                    )]
                ])
            )
            return

        # Проверить активную подписку — допы только для подписчиков
        from src.services.payments.subscription_service import check_subscription_status
        if not await check_subscription_status(user_id):
            await callback.message.edit_text(
                "⚠️ Покупка дополнительных токенов доступна только подписчикам.\n\n"
                "Оформите подписку, чтобы получить токены и возможность покупать дополнительные.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="📅 Смотреть подписки",
                        callback_data="show_payment_menu"
                    )]
                ])
            )
            return

        # Создать платеж (скидка применяется внутри payment_service)
        payment = await payment_service.create_token_payment(
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            package_id=package_id,
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

        # Текст с учётом скидки
        if payment.get("discount_percent"):
            original = int(payment['original_amount'])
            purchase_text = (
                f"🛒 Покупка: {package['name']}\n"
                f"💰 Цена: <s>{original}₽</s> → <b>{pay_amount}₽</b> (скидка {payment['discount_percent']}%)\n"
                f"🎁 Вы получите: {package['tokens_amount']} токенов\n\n"
                f"Нажмите кнопку ниже для оплаты.\n"
                f"После успешной оплаты токены будут автоматически начислены на ваш баланс.\n\n"
                f"{'⚠️ Тестовый режим' if settings.YOOKASSA_TEST_MODE else ''}"
            )
        else:
            purchase_text = (
                f"🛒 Покупка: {package['name']}\n"
                f"💰 Сумма: {pay_amount}₽\n"
                f"🎁 Вы получите: {package['tokens_amount']} токенов\n\n"
                f"Нажмите кнопку ниже для оплаты.\n"
                f"После успешной оплаты токены будут автоматически начислены на ваш баланс.\n\n"
                f"{'⚠️ Тестовый режим' if settings.YOOKASSA_TEST_MODE else ''}"
            )
        await callback.message.edit_text(purchase_text, reply_markup=keyboard, parse_mode="HTML")

        # Логируем действие пользователя + ответ бота
        try:
            from src.services.db.messages_repo import log_message
            await log_message(user_id=user_id, direction="user", text=f"[Кнопка] Купить: {package['name']}", session_id=f"tg:{telegram_user_id}", meta={"type": "callback", "callback_data": callback.data})
            await log_message(user_id=user_id, direction="bot", text=purchase_text, session_id=f"tg:{telegram_user_id}")
        except Exception:
            pass

        logger.info(
            f"Token payment created: user={user_id}, package={package['name']}, "
            f"amount={pay_amount}, payment_id={payment['payment_id']}"
        )

    except Exception as e:
        logger.error(f"Error creating token payment for user {user_id}: {e}", exc_info=True)
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


@router.callback_query(F.data.startswith("payment_cancel_"))
async def payment_cancel_handler(callback: CallbackQuery):
    """
    Обработка отмены платежа.

    Callback data format: payment_cancel_{payment_id}

    Note: Фактически платеж не отменяется в YooKassa, просто возвращаемся в меню.
    Платеж истечет автоматически через время, установленное в YooKassa.
    """
    await callback.answer("Платеж отменен")

    try:
        await callback.message.edit_text(
            "❌ Платеж отменен.\n\n"
            "Вы можете вернуться к покупкам в любое время.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="◀️ Назад к покупкам",
                    callback_data="show_payment_menu"
                )]
            ])
        )

        logger.info(f"User {callback.from_user.id} canceled payment {callback.data.split('_')[-1]}")

    except Exception as e:
        logger.error(f"Error handling payment cancel: {e}", exc_info=True)
