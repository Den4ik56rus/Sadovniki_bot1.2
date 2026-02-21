# src/services/broadcast_sender.py

"""
Асинхронная отправка рассылок через Telegram с rate limiting и SSE прогрессом.
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

from src.api.sse_manager import sse_manager
from src.services.db.broadcast_repo import (
    get_broadcast,
    update_broadcast_status,
    increment_broadcast_counters,
    get_broadcast_recipients,
    save_recipient_result,
    save_recipient_poll_id,
)

logger = logging.getLogger(__name__)

# Rate limit: ~20 msg/sec (Telegram рекомендует не более 30)
SEND_DELAY = 0.05
# Частота SSE обновлений (каждые N отправок)
SSE_UPDATE_INTERVAL = 5

# Telegram поддерживает только эти HTML теги
TELEGRAM_ALLOWED_TAGS = frozenset({
    'b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del',
    'a', 'code', 'pre', 'tg-spoiler', 'blockquote',
})


def sanitize_html_for_telegram(html: str) -> str:
    """Конвертировать TipTap HTML в Telegram-совместимый HTML."""
    if not html:
        return html

    # <br> → \n
    text = re.sub(r'<br\s*/?>', '\n', html)
    # </p><p> → двойной перенос
    text = re.sub(r'</p>\s*<p[^>]*>', '\n\n', text)
    # <p> и </p> → убираем
    text = re.sub(r'</?p[^>]*>', '', text)

    # Убираем все HTML теги кроме разрешённых Telegram
    def replace_tag(m: re.Match) -> str:
        tag_name = m.group(2).lower()
        if tag_name in TELEGRAM_ALLOWED_TAGS:
            return m.group(0)
        return ''

    text = re.sub(r'<(/?)([\w-]+)([^>]*)>', replace_tag, text)

    # Нормализуем переносы
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def build_inline_keyboard(
    broadcast_id: int,
    buttons_json,
) -> Optional[InlineKeyboardMarkup]:
    """
    Построить InlineKeyboardMarkup из JSONB массива кнопок.

    Формат buttons_json: [{"row":0, "text":"Да!", "type":"quick_reply", "option_key":"opt_0"},
                           {"row":1, "text":"Сайт", "type":"url", "url":"https://..."}]
    """
    if not buttons_json:
        return None

    import json as _json
    if isinstance(buttons_json, str):
        buttons_json = _json.loads(buttons_json)

    if not buttons_json:
        return None

    # Группируем по row
    rows_dict: dict[int, list] = {}
    for btn in buttons_json:
        row_idx = btn.get('row', 0)
        rows_dict.setdefault(row_idx, []).append(btn)

    keyboard = []
    for row_idx in sorted(rows_dict.keys()):
        row_buttons = []
        for btn in rows_dict[row_idx]:
            if btn['type'] == 'url':
                row_buttons.append(InlineKeyboardButton(
                    text=btn['text'],
                    url=btn['url'],
                ))
            elif btn['type'] == 'quick_reply':
                callback_data = f"bcast:{broadcast_id}:{btn['option_key']}"
                row_buttons.append(InlineKeyboardButton(
                    text=btn['text'],
                    callback_data=callback_data,
                ))
        if row_buttons:
            keyboard.append(row_buttons)

    if not keyboard:
        return None

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def execute_broadcast(broadcast_id: int) -> None:
    """
    Отправить рассылку всем получателям.

    Вызывается как asyncio.create_task() из API handler или scheduler.
    Отправляет текст/фото/опрос, обновляет счётчики, шлёт SSE прогресс.
    """
    broadcast = await get_broadcast(broadcast_id)
    if not broadcast:
        logger.error(f"Broadcast {broadcast_id} not found")
        return

    now = datetime.now(timezone.utc)
    await update_broadcast_status(broadcast_id, 'sending', started_at=now)

    recipients = await get_broadcast_recipients(broadcast_id, status_filter='pending')
    if not recipients:
        logger.warning(f"Broadcast {broadcast_id}: no pending recipients")
        await update_broadcast_status(broadcast_id, 'completed', completed_at=now)
        return

    from src.bot import get_bot  # lazy import to avoid circular dependency
    bot = get_bot()

    # Конвертируем HTML в Telegram-совместимый формат
    message_text = sanitize_html_for_telegram(broadcast['message_text']) if broadcast['message_text'] else None

    # Если photo_path — только имя файла, строим полный путь
    photo_path = broadcast['photo_path']
    if photo_path and not os.path.isabs(photo_path):
        base_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "broadcast_photos"
        )
        photo_path = os.path.join(base_dir, photo_path)

    # JSONB поля могут вернуться как строки из asyncpg
    poll_options = broadcast['poll_options']
    if isinstance(poll_options, str):
        poll_options = json.loads(poll_options)

    # Построить inline keyboard из кнопок
    reply_markup = build_inline_keyboard(broadcast_id, broadcast.get('inline_buttons'))

    batch_sent = 0
    batch_failed = 0
    total_sent = 0
    total_failed = 0

    for recipient in recipients:
        # Проверяем отмену
        current = await get_broadcast(broadcast_id)
        if not current or current['status'] == 'cancelled':
            logger.info(f"Broadcast {broadcast_id} cancelled, stopping")
            break

        tg_id = recipient['telegram_user_id']
        user_id = recipient['user_id']

        try:
            # Отправляем контент
            if photo_path:
                photo = FSInputFile(photo_path)
                if message_text:
                    await bot.send_photo(
                        chat_id=tg_id,
                        photo=photo,
                        caption=message_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup,
                    )
                else:
                    await bot.send_photo(
                        chat_id=tg_id,
                        photo=photo,
                        reply_markup=reply_markup,
                    )
            elif message_text:
                await bot.send_message(
                    chat_id=tg_id,
                    text=message_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                )

            # Отправляем опрос (отдельно от текста/фото)
            if broadcast['poll_question'] and poll_options:
                poll_result = await bot.send_poll(
                    chat_id=tg_id,
                    question=broadcast['poll_question'],
                    options=poll_options,
                    is_anonymous=broadcast.get('poll_is_anonymous', True),
                    allows_multiple_answers=broadcast.get('poll_allows_multiple', False),
                )
                # Сохраняем poll_id для маппинга PollAnswer → broadcast
                if poll_result and poll_result.poll:
                    try:
                        await save_recipient_poll_id(
                            broadcast_id, user_id, poll_result.poll.id,
                        )
                    except Exception as poll_err:
                        logger.warning(f"Failed to save poll_id for user {user_id}: {poll_err}")

            await save_recipient_result(broadcast_id, user_id, 'sent')
            batch_sent += 1
            total_sent += 1

        except Exception as e:
            error_msg = str(e)[:500]
            await save_recipient_result(broadcast_id, user_id, 'failed', error_msg)
            batch_failed += 1
            total_failed += 1
            logger.warning(f"Broadcast {broadcast_id}: failed to send to user {user_id}: {error_msg}")

        # Обновляем счётчики и SSE каждые N отправок
        if (batch_sent + batch_failed) >= SSE_UPDATE_INTERVAL:
            await increment_broadcast_counters(broadcast_id, batch_sent, batch_failed)
            await _broadcast_progress_sse(broadcast_id, total_sent, total_failed, len(recipients))
            batch_sent = 0
            batch_failed = 0

        # Rate limit
        await asyncio.sleep(SEND_DELAY)

    # Финальное обновление оставшегося batch
    if batch_sent > 0 or batch_failed > 0:
        await increment_broadcast_counters(broadcast_id, batch_sent, batch_failed)

    # Завершаем рассылку
    completed_at = datetime.now(timezone.utc)
    current = await get_broadcast(broadcast_id)
    if current and current['status'] != 'cancelled':
        await update_broadcast_status(broadcast_id, 'completed', completed_at=completed_at)

    # Финальный SSE
    await sse_manager.broadcast(
        event_type='broadcast_completed',
        data={
            'broadcast_id': broadcast_id,
            'sent_count': total_sent,
            'failed_count': total_failed,
            'total_recipients': len(recipients),
        },
        endpoint_type='broadcast',
        entity_id=broadcast_id,
    )

    logger.info(
        f"Broadcast {broadcast_id} completed: "
        f"{total_sent} sent, {total_failed} failed out of {len(recipients)}"
    )


async def _broadcast_progress_sse(
    broadcast_id: int,
    sent: int,
    failed: int,
    total: int,
) -> None:
    """Отправить SSE событие прогресса рассылки."""
    await sse_manager.broadcast(
        event_type='broadcast_progress',
        data={
            'broadcast_id': broadcast_id,
            'sent_count': sent,
            'failed_count': failed,
            'total_recipients': total,
        },
        endpoint_type='broadcast',
        entity_id=broadcast_id,
    )
