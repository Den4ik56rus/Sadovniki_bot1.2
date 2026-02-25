# src/services/broadcast_scheduler.py

"""
Фоновая задача для отправки запланированных рассылок и напоминалок.

Проверяет каждые 30 секунд:
1. Рассылки со статусом 'scheduled' и scheduled_at <= NOW()
2. Напоминалки со статусом 'scheduled' и reminder_scheduled_at <= NOW()
"""

import asyncio
import logging

from src.services.db.broadcast_repo import (
    get_scheduled_broadcasts,
    resolve_recipients,
    get_due_reminders,
    resolve_reminder_recipients,
    update_reminder_status,
)
from src.services.broadcast_sender import execute_broadcast

logger = logging.getLogger(__name__)

# Интервал проверки (30 сек)
CHECK_INTERVAL = 30


async def broadcast_scheduler_loop() -> None:
    """
    Фоновый цикл — проверяет запланированные рассылки и напоминалки.
    Запускается через asyncio.create_task() при старте бота.
    """
    logger.info("Broadcast scheduler started")

    while True:
        try:
            # 1. Запланированные рассылки
            broadcasts = await get_scheduled_broadcasts()
            for b in broadcasts:
                broadcast_id = b['id']
                logger.info(f"Scheduled broadcast {broadcast_id} is ready, launching...")

                # Собираем получателей
                count = await resolve_recipients(broadcast_id)
                logger.info(f"Broadcast {broadcast_id}: resolved {count} recipients")

                # Запускаем отправку в фоне
                asyncio.create_task(execute_broadcast(broadcast_id))

            # 2. Напоминалки (reminder broadcasts)
            reminders = await get_due_reminders()
            for r in reminders:
                reminder_id = r['id']
                parent_id = r['parent_broadcast_id']
                logger.info(f"Reminder {reminder_id} (parent={parent_id}) is due, launching...")

                # Обновляем статус на 'sending'
                await update_reminder_status(reminder_id, 'sending')

                # Собираем получателей с фильтрацией
                exclude_bought = r.get('reminder_exclude_bought', False)
                exclude_clicked = r.get('reminder_exclude_clicked')
                if isinstance(exclude_clicked, str):
                    import json
                    exclude_clicked = json.loads(exclude_clicked)

                count = await resolve_reminder_recipients(
                    reminder_id, parent_id, exclude_bought, exclude_clicked
                )
                logger.info(f"Reminder {reminder_id}: resolved {count} recipients")

                if count == 0:
                    logger.info(f"Reminder {reminder_id}: no recipients, marking as sent")
                    await update_reminder_status(reminder_id, 'sent')
                    continue

                # Запускаем отправку (execute_broadcast работает с любой строкой broadcasts)
                asyncio.create_task(_execute_reminder(reminder_id))

        except Exception as e:
            logger.error(f"Error in broadcast scheduler: {e}", exc_info=True)

        await asyncio.sleep(CHECK_INTERVAL)


async def _execute_reminder(reminder_id: int) -> None:
    """Обёртка для отправки напоминалки с обновлением reminder_status."""
    try:
        await execute_broadcast(reminder_id)
        await update_reminder_status(reminder_id, 'sent')
    except Exception as e:
        logger.error(f"Reminder {reminder_id} execution failed: {e}", exc_info=True)
        await update_reminder_status(reminder_id, 'failed')
