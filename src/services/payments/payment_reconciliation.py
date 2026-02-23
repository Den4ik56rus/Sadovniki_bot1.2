"""
Периодическая сверка статусов платежей с YooKassa API.

Назначение: страховка от потерянных вебхуков.
Каждые 5 минут проверяет pending платежи старше 2 минут.
Если платёж succeeded в YooKassa — обрабатывает его.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)

# Интервал проверки (секунды)
RECONCILIATION_INTERVAL = 300  # 5 минут
# Минимальный возраст pending платежа для проверки
MIN_PAYMENT_AGE_MINUTES = 2


async def reconcile_pending_payments() -> int:
    """
    Проверяет все stale pending платежи через YooKassa API.
    Обрабатывает успешные, обновляет отменённые.

    Returns:
        Количество обработанных платежей.
    """
    from src.services.db import payment_repo
    from src.services.payments.yookassa_client import yookassa_client
    from src.services.payments import payment_service

    processed = 0

    try:
        stale_payments = await payment_repo.get_stale_pending_payments(MIN_PAYMENT_AGE_MINUTES)

        if not stale_payments:
            return 0

        logger.info(f"[reconciliation] Найдено {len(stale_payments)} stale pending платежей")

        for payment in stale_payments:
            yookassa_id = payment["yookassa_payment_id"]
            try:
                # Запросить актуальный статус у YooKassa
                yk_payment = await yookassa_client.get_payment(yookassa_id)
                yk_status = yk_payment.get("status")
                yk_paid = yk_payment.get("paid", False)

                if yk_status == "succeeded" and yk_paid:
                    logger.info(f"[reconciliation] Платёж {yookassa_id} succeeded — обрабатываем")
                    await payment_service.process_payment_success(
                        yookassa_payment_id=yookassa_id,
                        yookassa_payment_object=yk_payment,
                    )
                    processed += 1
                    # Алерт о восстановленном платеже
                    await _send_recovery_alert(payment, yk_payment)

                elif yk_status == "canceled":
                    logger.info(f"[reconciliation] Платёж {yookassa_id} canceled — обновляем")
                    await payment_service.process_payment_canceled(
                        yookassa_payment_id=yookassa_id,
                        yookassa_payment_object=yk_payment,
                    )
                    processed += 1

                else:
                    logger.debug(f"[reconciliation] Платёж {yookassa_id} всё ещё {yk_status} — пропускаем")

            except Exception as e:
                logger.error(f"[reconciliation] Ошибка проверки платежа {yookassa_id}: {e}", exc_info=True)
                # Не прерываем цикл — продолжаем следующий платёж
                continue

    except Exception as e:
        logger.error(f"[reconciliation] Ошибка получения stale платежей: {e}", exc_info=True)

    return processed


async def _send_recovery_alert(payment: dict, yk_payment: dict) -> None:
    """Алерт администратору о восстановленном платеже."""
    try:
        from src.bot import get_bot
        from src.config import settings
        from src.services.db.pool import get_pool

        bot = get_bot()
        if not settings.admin_ids:
            return

        admin_ids = [int(x.strip()) for x in settings.admin_ids.split(",") if x.strip()]
        if not admin_ids:
            return

        pool = get_pool()
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT telegram_user_id, username FROM users WHERE id = $1",
                payment["user_id"],
            )

        username = f"@{user['username']}" if user and user.get("username") else f"id={payment['user_id']}"
        amount = payment.get("amount_rub", "?")
        yookassa_id = payment["yookassa_payment_id"]

        text = (
            "⚠️ <b>Восстановлен потерянный платёж</b>\n\n"
            f"Пользователь: {username}\n"
            f"Сумма: {amount}₽\n"
            f"YooKassa ID: <code>{yookassa_id}</code>\n\n"
            "Платёж был в статусе pending, восстановлен через periodic reconciliation.\n"
            "Вебхук был потерян."
        )

        for admin_id in admin_ids[:1]:  # Отправляем первому администратору
            await bot.send_message(chat_id=admin_id, text=text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"[reconciliation] Ошибка отправки алерта: {e}", exc_info=True)


async def payment_reconciliation_loop() -> None:
    """
    Бесконечный цикл сверки платежей.
    Запускается как asyncio.create_task() в main.py.
    """
    logger.info("Payment reconciliation loop started")
    # Первая проверка через 1 минуту после старта (бот ещё инициализируется)
    await asyncio.sleep(60)

    while True:
        try:
            processed = await reconcile_pending_payments()
            if processed > 0:
                logger.info(f"[reconciliation] Обработано платежей: {processed}")
        except Exception as e:
            logger.error(f"[reconciliation] Ошибка в цикле: {e}", exc_info=True)

        await asyncio.sleep(RECONCILIATION_INTERVAL)
