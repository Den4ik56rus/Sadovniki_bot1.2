"""
Webhook handlers для приема уведомлений от платежных систем.

Архитектура надёжности:
    - Вебхук немедленно отвечает 200 OK (< 10ms)
    - Обработка ставится в asyncio.Queue
    - Consumer coroutine разгребает очередь в фоне
    - Если queue недоступна — fallback на синхронную обработку
"""

import asyncio
import logging
from typing import Dict, Any, Optional

from aiohttp import web

logger = logging.getLogger(__name__)

# Глобальная очередь задач обработки вебхуков.
# Инициализируется в main.py через set_webhook_queue().
_webhook_queue: Optional[asyncio.Queue] = None


def set_webhook_queue(queue: asyncio.Queue) -> None:
    """Устанавливает глобальную очередь вебхуков (вызывается из main.py при старте)."""
    global _webhook_queue
    _webhook_queue = queue


def get_webhook_queue() -> Optional[asyncio.Queue]:
    return _webhook_queue


async def yookassa_webhook(request: web.Request) -> web.Response:
    """
    Обработка webhook от YooKassa.

    Немедленно возвращает 200 OK, обработку ставит в очередь.
    YooKassa ждёт ответ не более ~5 сек — мы отвечаем за <10ms.
    """
    try:
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

        # Ставим обработку в очередь — отвечаем немедленно
        queue = get_webhook_queue()
        if queue is not None:
            await queue.put({
                "event_type": event_type,
                "payment_object": payment_object,
                "yookassa_payment_id": yookassa_payment_id,
                "status": status,
                "paid": paid,
            })
            logger.info(f"Webhook queued: {yookassa_payment_id}, queue size: {queue.qsize()}")
        else:
            # Fallback: синхронная обработка если очередь не инициализирована
            logger.warning("Webhook queue not initialized, processing synchronously")
            await _process_webhook_payload(event_type, payment_object, yookassa_payment_id, status, paid)

        return web.Response(status=200, text="OK")

    except Exception as e:
        logger.error(f"Webhook processing error: {e}", exc_info=True)
        # Всегда 200 чтобы YooKassa не повторяла
        return web.Response(status=200, text="OK")


async def _process_webhook_payload(
    event_type: str,
    payment_object: Dict[str, Any],
    yookassa_payment_id: str,
    status: str,
    paid: bool,
) -> None:
    """Обработка payload вебхука (используется consumer и fallback)."""
    from src.services.payments import payment_service

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
                await _send_payment_error_alert(yookassa_payment_id, "process_payment_success returned False")
        except Exception as e:
            logger.error(
                f"Error processing payment success for {yookassa_payment_id}: {e}",
                exc_info=True,
            )
            await _send_payment_error_alert(yookassa_payment_id, str(e))

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

    elif event_type == "payment.waiting_for_capture":
        logger.info(f"Payment {yookassa_payment_id} waiting for capture")

    else:
        logger.info(
            f"Unhandled webhook event: {event_type}, "
            f"payment_id={yookassa_payment_id}, status={status}"
        )


async def webhook_consumer(queue: asyncio.Queue) -> None:
    """
    Consumer coroutine для обработки вебхуков из очереди.
    Запускается как asyncio.create_task() в main.py.
    Работает вечно, обрабатывает по одному вебхуку за раз.
    """
    logger.info("Webhook consumer started")
    while True:
        try:
            item = await queue.get()
            try:
                await _process_webhook_payload(
                    event_type=item["event_type"],
                    payment_object=item["payment_object"],
                    yookassa_payment_id=item["yookassa_payment_id"],
                    status=item["status"],
                    paid=item["paid"],
                )
            except Exception as e:
                logger.error(f"Webhook consumer error for {item.get('yookassa_payment_id')}: {e}", exc_info=True)
            finally:
                queue.task_done()
        except asyncio.CancelledError:
            logger.info("Webhook consumer cancelled")
            break
        except Exception as e:
            logger.error(f"Unexpected error in webhook consumer: {e}", exc_info=True)
            await asyncio.sleep(1)


async def _send_payment_error_alert(yookassa_payment_id: str, error: str) -> None:
    """Алерт администратору при ошибке обработки платежа."""
    try:
        from src.bot import get_bot
        from src.config import settings

        bot = get_bot()
        if not settings.admin_ids:
            return

        admin_ids = [int(x.strip()) for x in settings.admin_ids.split(",") if x.strip()]
        if not admin_ids:
            return

        text = (
            "🚨 <b>Ошибка обработки платежа</b>\n\n"
            f"YooKassa ID: <code>{yookassa_payment_id}</code>\n"
            f"Ошибка: {error[:300]}\n\n"
            "Платёж будет восстановлен через periodic reconciliation (до 5 минут)."
        )

        for admin_id in admin_ids[:1]:
            await bot.send_message(chat_id=admin_id, text=text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Failed to send payment error alert: {e}")


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
        response = await yookassa_webhook(request)
        return web.Response(
            status=200,
            text=f"Test webhook processed, response: {response.status}",
        )
    except Exception as e:
        logger.error(f"Test webhook error: {e}", exc_info=True)
        return web.Response(status=500, text=f"Error: {e}")
