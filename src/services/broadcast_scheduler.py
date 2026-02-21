# src/services/broadcast_scheduler.py

"""
Фоновая задача для отправки запланированных рассылок.

Проверяет каждые 30 секунд, есть ли рассылки со статусом 'scheduled'
и scheduled_at <= NOW(). Если есть — запускает отправку.
"""

import asyncio
import logging

from src.services.db.broadcast_repo import get_scheduled_broadcasts, resolve_recipients
from src.services.broadcast_sender import execute_broadcast

logger = logging.getLogger(__name__)

# Интервал проверки (30 сек)
CHECK_INTERVAL = 30


async def broadcast_scheduler_loop() -> None:
    """
    Фоновый цикл — проверяет запланированные рассылки и запускает отправку.
    Запускается через asyncio.create_task() при старте бота.
    """
    logger.info("Broadcast scheduler started")

    while True:
        try:
            broadcasts = await get_scheduled_broadcasts()
            for b in broadcasts:
                broadcast_id = b['id']
                logger.info(f"Scheduled broadcast {broadcast_id} is ready, launching...")

                # Собираем получателей
                count = await resolve_recipients(broadcast_id)
                logger.info(f"Broadcast {broadcast_id}: resolved {count} recipients")

                # Запускаем отправку в фоне
                asyncio.create_task(execute_broadcast(broadcast_id))

        except Exception as e:
            logger.error(f"Error in broadcast scheduler: {e}", exc_info=True)

        await asyncio.sleep(CHECK_INTERVAL)
