"""
Webhook handlers для приема уведомлений от платежных систем.

Основные обработчики:
    - yookassa_webhook — прием уведомлений от YooKassa о статусе платежей
"""

import logging
from typing import Dict, Any
from aiohttp import web

from src.services.payments import payment_service

logger = logging.getLogger(__name__)


async def yookassa_webhook(request: web.Request) -> web.Response:
    """
    Обработка webhook от YooKassa.

    События:
        - payment.succeeded — платеж успешно завершен
        - payment.canceled — платеж отменен
        - payment.waiting_for_capture — ожидает подтверждения

    Security:
        - Идемпотентность через проверку статуса в БД
        - Верификация платежа через YooKassa API
        - Проверка суммы и владельца
        - Опционально: IP whitelist (для production)

    Returns:
        Всегда 200 OK для предотвращения повторной отправки
    """
    try:
        # Получить данные webhook
        payload = await request.json()
        event_type = payload.get("event")
        payment_object = payload.get("object")

        if not payment_object:
            logger.warning("Webhook received without payment object")
            return web.Response(status=400, text="Invalid payload")

        yookassa_payment_id = payment_object.get("id")
        status = payment_object.get("status")
        paid = payment_object.get("paid", False)

        logger.info(
            f"Webhook received: event={event_type}, "
            f"payment_id={yookassa_payment_id}, status={status}, paid={paid}"
        )

        # Обработка успешного платежа
        if event_type == "payment.succeeded" and paid and status == "succeeded":
            try:
                success = await payment_service.process_payment_success(
                    yookassa_payment_id=yookassa_payment_id,
                    yookassa_payment_object=payment_object,
                )

                if success:
                    logger.info(f"Payment {yookassa_payment_id} processed successfully")
                else:
                    logger.warning(f"Payment {yookassa_payment_id} could not be processed")

            except Exception as e:
                logger.error(
                    f"Error processing payment success for {yookassa_payment_id}: {e}",
                    exc_info=True,
                )
                # Все равно возвращаем 200 OK, чтобы YooKassa не повторял запрос
                # Ошибка записана в логи для дальнейшего расследования

        # Обработка отмены платежа
        elif event_type == "payment.canceled":
            try:
                await payment_service.process_payment_canceled(
                    yookassa_payment_id=yookassa_payment_id,
                    yookassa_payment_object=payment_object,
                )

                logger.info(f"Payment {yookassa_payment_id} canceled")

            except Exception as e:
                logger.error(
                    f"Error processing payment cancellation for {yookassa_payment_id}: {e}",
                    exc_info=True,
                )

        # Обработка ожидания подтверждения (двухстадийные платежи)
        elif event_type == "payment.waiting_for_capture":
            logger.info(
                f"Payment {yookassa_payment_id} waiting for capture "
                "(two-stage payment, auto-capture disabled)"
            )
            # В нашей реализации используется capture=True (одностадийные платежи)
            # Этот случай не должен происходить, но логируем для информации

        else:
            logger.info(
                f"Unhandled webhook event: {event_type}, "
                f"payment_id={yookassa_payment_id}, status={status}"
            )

        # Всегда возвращаем 200 OK
        return web.Response(status=200, text="OK")

    except Exception as e:
        logger.error(f"Webhook processing error: {e}", exc_info=True)
        # Все равно возвращаем 200 OK, чтобы не было повторных попыток
        # Ошибка уже залогирована для расследования
        return web.Response(status=200, text="OK")


async def yookassa_webhook_test(request: web.Request) -> web.Response:
    """
    Тестовый endpoint для локальной проверки webhook логики.

    Использование:
        curl -X POST http://localhost:8080/api/webhooks/yookassa/test \\
          -H "Content-Type: application/json" \\
          -d '{
            "event": "payment.succeeded",
            "object": {
              "id": "test_payment_id",
              "status": "succeeded",
              "paid": true,
              "amount": {"value": "200.00", "currency": "RUB"},
              "metadata": {"telegram_user_id": "123456789"}
            }
          }'
    """
    try:
        payload = await request.json()

        logger.info(f"TEST webhook received: {payload}")

        # Вызвать обычный обработчик
        response = await yookassa_webhook(request)

        return web.Response(
            status=200,
            text=f"Test webhook processed, response: {response.status}",
        )

    except Exception as e:
        logger.error(f"Test webhook error: {e}", exc_info=True)
        return web.Response(status=500, text=f"Error: {e}")
