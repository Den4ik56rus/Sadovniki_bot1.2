# src/middleware/activity_tracker.py

"""
Middleware для отслеживания последней активности пользователя.

Обновляет users.last_activity_at при каждом входящем update
(сообщение, нажатие кнопки, /start и т.д.).
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


class ActivityTrackerMiddleware(BaseMiddleware):
    """
    Outer middleware на уровне Update.
    Извлекает telegram_user_id из любого входящего update
    и обновляет last_activity_at в таблице users.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Извлекаем telegram_user_id из update
        if isinstance(event, Update):
            tg_user_id = self._extract_user_id(event)
            if tg_user_id:
                try:
                    pool = get_pool()
                    async with pool.acquire() as conn:
                        await conn.execute(
                            "UPDATE users SET last_activity_at = NOW() WHERE telegram_user_id = $1",
                            tg_user_id,
                        )
                except Exception:
                    # Не ломаем обработку update если не удалось обновить активность
                    logger.debug("Failed to update last_activity_at for user %s", tg_user_id, exc_info=True)

        return await handler(event, data)

    @staticmethod
    def _extract_user_id(update: Update) -> int | None:
        """Извлечь telegram user id из любого типа update."""
        if update.message and update.message.from_user:
            return update.message.from_user.id
        if update.callback_query and update.callback_query.from_user:
            return update.callback_query.from_user.id
        if update.inline_query and update.inline_query.from_user:
            return update.inline_query.from_user.id
        if update.chosen_inline_result and update.chosen_inline_result.from_user:
            return update.chosen_inline_result.from_user.id
        if update.pre_checkout_query and update.pre_checkout_query.from_user:
            return update.pre_checkout_query.from_user.id
        if update.poll_answer and update.poll_answer.user:
            return update.poll_answer.user.id
        return None
