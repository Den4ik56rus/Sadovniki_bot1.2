# src/handlers/broadcast_callbacks.py

"""
Обработчик inline-кнопок рассылок и ответов на опросы (PollAnswer).

- bcast:{broadcast_id}:{option_key} — клик по quick_reply кнопке (трекается)
- URL-кнопки — отправляются как прямые ссылки Telegram (url=), не трекаются
- PollAnswer — ответ на неанонимный опрос рассылки
"""

import json
import logging

from aiogram import Router, F
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery, PollAnswer

from src.services.db.broadcast_repo import (
    get_broadcast,
    record_button_click,
    record_poll_answer,
    resolve_broadcast_from_poll_id,
    resolve_run_id_from_recipient,
    resolve_run_id_from_poll,
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

        # Получаем данные кнопки из broadcast.inline_buttons
        broadcast = await get_broadcast(broadcast_id)
        button_text = option_key  # fallback
        reply_text = None
        ask_for_response = False
        if broadcast and broadcast.get('inline_buttons'):
            buttons = broadcast['inline_buttons']
            if isinstance(buttons, str):
                buttons = json.loads(buttons)
            for btn in buttons:
                if btn.get('option_key') == option_key:
                    button_text = btn.get('text', option_key)
                    reply_text = btn.get('reply_text')
                    ask_for_response = btn.get('ask_for_response', False)
                    break

        # Определяем run_id (последний запуск, в котором участвовал юзер)
        run_id = await resolve_run_id_from_recipient(broadcast_id, user_id)

        await record_button_click(
            broadcast_id=broadcast_id,
            user_id=user_id,
            telegram_user_id=callback.from_user.id,
            option_key=option_key,
            button_text=button_text,
            run_id=run_id,
        )

        # Если есть reply_text — отправляем как полноценное сообщение
        if reply_text and reply_text.strip():
            from src.services.broadcast_sender import sanitize_html_for_telegram
            sanitized = sanitize_html_for_telegram(reply_text)
            if sanitized:
                try:
                    await callback.message.answer(
                        text=sanitized,
                        parse_mode=ParseMode.HTML,
                    )
                    await callback.answer()  # убрать spinner
                except Exception as reply_err:
                    logger.warning(f"Failed to send reply_text for bcast:{broadcast_id}:{option_key}: {reply_err}")
                    await callback.answer("Ваш ответ записан!")
            else:
                await callback.answer("Ваш ответ записан!")
        else:
            await callback.answer("Ваш ответ записан!")

        # Если кнопка запрашивает текстовый ответ — устанавливаем состояние
        if ask_for_response:
            from src.handlers.common import set_consultation_state
            await set_consultation_state(
                callback.from_user.id,
                f"waiting_broadcast_response",
                context={
                    "broadcast_id": broadcast_id,
                    "option_key": option_key,
                    "run_id": run_id,
                    "button_text": button_text,
                },
            )
            prompt = "Расскажите подробнее — мы обязательно прочитаем ваш ответ:"
            await callback.message.answer(prompt)

    except Exception as e:
        logger.error(f"Error handling broadcast button click: {e}", exc_info=True)
        await callback.answer("Произошла ошибка")


@router.callback_query(F.data.startswith("bcast_discount:"))
async def handle_broadcast_discount_click(callback: CallbackQuery) -> None:
    """Обработка клика по discount-кнопке рассылки. Сохраняет скидку и открывает меню тарифов."""
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

        # Получаем конфиг кнопки из broadcast.inline_buttons
        broadcast = await get_broadcast(broadcast_id)
        btn_config = None
        button_text = option_key
        if broadcast and broadcast.get('inline_buttons'):
            buttons = broadcast['inline_buttons']
            if isinstance(buttons, str):
                buttons = json.loads(buttons)
            for btn in buttons:
                if btn.get('option_key') == option_key and btn.get('type') == 'discount':
                    btn_config = btn
                    button_text = btn.get('text', option_key)
                    break

        if not btn_config:
            await callback.answer()
            return

        # Сохраняем скидку в БД
        from src.services.db.discount_repo import upsert_broadcast_discount
        await upsert_broadcast_discount(
            user_id=user_id,
            broadcast_id=broadcast_id,
            option_key=option_key,
            discount_percent=btn_config['discount_percent'],
            bonus_tokens=btn_config.get('discount_bonus_tokens') or 0,
            duration_hours=btn_config['discount_duration_hours'],
        )

        # Трекируем клик (та же инфраструктура что и у quick_reply)
        run_id = await resolve_run_id_from_recipient(broadcast_id, user_id)
        await record_button_click(
            broadcast_id=broadcast_id,
            user_id=user_id,
            telegram_user_id=callback.from_user.id,
            option_key=option_key,
            button_text=button_text,
            run_id=run_id,
        )

        await callback.answer()

        # Показываем меню подписок со скидкой
        from src.handlers.payments.discount_menu import show_discount_subscription_menu
        await show_discount_subscription_menu(callback, user_id)

    except Exception as e:
        logger.error(f"Error handling broadcast discount click: {e}", exc_info=True)
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

        # Определяем run_id по poll_id
        run_id = await resolve_run_id_from_poll(telegram_poll_id)

        await record_poll_answer(
            broadcast_id=broadcast_id,
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            telegram_poll_id=telegram_poll_id,
            option_ids=list(option_ids),
            run_id=run_id,
        )

        logger.info(
            f"Poll answer recorded: broadcast={broadcast_id}, "
            f"user_tg={telegram_user_id}, options={option_ids}"
        )

    except Exception as e:
        logger.error(f"Error handling poll answer: {e}", exc_info=True)
