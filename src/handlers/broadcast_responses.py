# src/handlers/broadcast_responses.py

"""
Обработчик текстовых ответов на кнопки рассылок.

Когда пользователь нажимает кнопку с ask_for_response=true,
broadcast_callbacks ставит состояние waiting_broadcast_response.
Этот хендлер ловит следующее текстовое сообщение и сохраняет его.
"""

import logging

from aiogram import Router, F
from aiogram.types import Message

from src.handlers.common import (
    CONSULTATION_STATE,
    CONSULTATION_CONTEXT,
    clear_consultation_state,
)
from src.services.db.broadcast_repo import save_button_text_response

logger = logging.getLogger(__name__)

router = Router(name="broadcast_responses")


@router.message(
    F.text,
    lambda m: m.from_user is not None
    and CONSULTATION_STATE.get(m.from_user.id) == "waiting_broadcast_response",
)
async def handle_broadcast_text_response(message: Message) -> None:
    """Сбор текстового ответа на кнопку рассылки."""
    telegram_user_id = message.from_user.id
    state = CONSULTATION_STATE.get(telegram_user_id)

    context = CONSULTATION_CONTEXT.get(telegram_user_id, {})
    broadcast_id = context.get("broadcast_id")
    option_key = context.get("option_key")
    run_id = context.get("run_id")

    if not broadcast_id or not option_key:
        logger.warning(f"Missing context for broadcast response from {telegram_user_id}")
        await clear_consultation_state(telegram_user_id)
        return

    text = message.text.strip()
    if not text:
        await message.answer("Пожалуйста, напишите ваш ответ текстом.")
        return

    try:
        # Резолвим user_id
        from src.services.db.pool import get_pool
        pool = get_pool()
        async with pool.acquire() as conn:
            user_row = await conn.fetchrow(
                "SELECT id FROM users WHERE telegram_user_id = $1",
                telegram_user_id,
            )

        if not user_row:
            await clear_consultation_state(telegram_user_id)
            return

        user_id = user_row['id']

        await save_button_text_response(
            broadcast_id=broadcast_id,
            user_id=user_id,
            option_key=option_key,
            text_response=text,
            run_id=run_id,
        )

        await clear_consultation_state(telegram_user_id)
        await message.answer("Спасибо за ваш ответ! Мы обязательно его прочитаем.")

    except Exception as e:
        logger.error(f"Error saving broadcast text response: {e}", exc_info=True)
        await clear_consultation_state(telegram_user_id)
        await message.answer("Спасибо, ваш ответ записан!")
