# src/handlers/broadcast_callbacks.py

"""
Обработчик inline-кнопок рассылок и ответов на опросы (PollAnswer).

- bcast:{broadcast_id}:{option_key} — клик по quick_reply кнопке
- PollAnswer — ответ на неанонимный опрос рассылки
"""

import json
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, PollAnswer

from src.services.db.broadcast_repo import (
    get_broadcast,
    record_button_click,
    record_poll_answer,
    resolve_broadcast_from_poll_id,
)

logger = logging.getLogger(__name__)

router = Router(name="broadcast_callbacks")


@router.callback_query(F.data.startswith("bcast:"))
async def handle_broadcast_button_click(callback: CallbackQuery) -> None:
    """Обработка клика по inline quick_reply кнопке рассылки."""
    try:
        parts = callback.data.split(":", 2)
        if len(parts) != 3:
            await callback.answer("Ошибка формата")
            return

        broadcast_id = int(parts[1])
        option_key = parts[2]

        # Резолвим user_id из БД
        from src.services.db.pool import get_pool
        pool = get_pool()
        async with pool.acquire() as conn:
            user_row = await conn.fetchrow(
                "SELECT id FROM users WHERE telegram_user_id = $1",
                callback.from_user.id,
            )

        if not user_row:
            await callback.answer("Пользователь не найден")
            return

        user_id = user_row['id']

        # Получаем текст кнопки из broadcast.inline_buttons
        broadcast = await get_broadcast(broadcast_id)
        button_text = option_key  # fallback
        if broadcast and broadcast.get('inline_buttons'):
            buttons = broadcast['inline_buttons']
            if isinstance(buttons, str):
                buttons = json.loads(buttons)
            for btn in buttons:
                if btn.get('option_key') == option_key:
                    button_text = btn.get('text', option_key)
                    break

        await record_button_click(
            broadcast_id=broadcast_id,
            user_id=user_id,
            telegram_user_id=callback.from_user.id,
            option_key=option_key,
            button_text=button_text,
        )

        await callback.answer("Ваш ответ записан!")

    except Exception as e:
        logger.error(f"Error handling broadcast button click: {e}", exc_info=True)
        await callback.answer("Произошла ошибка")


@router.poll_answer()
async def handle_poll_answer(poll_answer: PollAnswer) -> None:
    """Обработка ответа на неанонимный опрос рассылки."""
    try:
        telegram_poll_id = poll_answer.poll_id
        telegram_user_id = poll_answer.user.id
        option_ids = poll_answer.option_ids  # list[int], пустой = отзыв голоса

        # Находим broadcast по poll_id
        broadcast_id = await resolve_broadcast_from_poll_id(telegram_poll_id)
        if not broadcast_id:
            # Это не наш опрос (или poll_id не был сохранён)
            return

        # Резолвим user_id
        from src.services.db.pool import get_pool
        pool = get_pool()
        async with pool.acquire() as conn:
            user_row = await conn.fetchrow(
                "SELECT id FROM users WHERE telegram_user_id = $1",
                telegram_user_id,
            )

        user_id = user_row['id'] if user_row else None

        await record_poll_answer(
            broadcast_id=broadcast_id,
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            telegram_poll_id=telegram_poll_id,
            option_ids=list(option_ids),
        )

        logger.info(
            f"Poll answer recorded: broadcast={broadcast_id}, "
            f"user_tg={telegram_user_id}, options={option_ids}"
        )

    except Exception as e:
        logger.error(f"Error handling poll answer: {e}", exc_info=True)
