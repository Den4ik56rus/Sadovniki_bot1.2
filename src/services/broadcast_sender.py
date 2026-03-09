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
    # Run support
    get_run,
    update_run_status,
    increment_run_counters,
    get_run_recipients,
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

# ─── Template variable substitution ──────────────────────────────────────────

CULTURE_NAMES = {
    "strawberry": "Клубника", "raspberry": "Малина", "blueberry": "Голубика",
    "currant": "Смородина", "honeysuckle": "Жимолость", "blackberry": "Ежевика", "other": "Другое",
}
REGION_NAMES = {
    "central": "Центральный", "south": "Южный", "north": "Северный",
}
PROBLEM_NAMES = {
    "small_berries": "Мало ягод", "diseases": "Болезни", "low_yield": "Низкий урожай",
    "increase_yield": "Увеличить урожай", "check_care": "Проверить уход",
}
URGENCY_NAMES = {
    "early": "Только заметил", "progressing": "Уже прогрессирует", "urgent": "Срочно спасать",
}
GOAL_NAMES = {
    "save": "Спасти урожай", "restore": "Восстановить",
    "yield": "Увеличить урожай", "prevent": "Предотвратить",
}


def substitute_variables(text: str, user_vars: dict) -> str:
    """Заменить {{var}} токены на значения пользователя. Отсутствующие → пустая строка."""
    if not text or '{{' not in text:
        return text
    return re.sub(r'\{\{(\w+)\}\}', lambda m: user_vars.get(m.group(1).strip(), ''), text)


def _build_user_vars_from_row(row) -> dict:
    return {
        'first_name': row['first_name'] or '',
        'username':   f"@{row['username']}" if row['username'] else '',
        'culture':    CULTURE_NAMES.get(row['culture'] or '', row['culture'] or ''),
        'region':     REGION_NAMES.get(row['region'] or '', row['region'] or ''),
        'problem':    PROBLEM_NAMES.get(row['problem'] or '', row['problem'] or ''),
        'urgency':    URGENCY_NAMES.get(row['urgency'] or '', row['urgency'] or ''),
        'goal':       GOAL_NAMES.get(row['goal'] or '', row['goal'] or ''),
    }


_VARS_QUERY = """
    SELECT u.id, u.first_name, u.username,
           qa.culture, qa.region, qa.problem,
           qs.urgency, qs.goal
    FROM users u
    LEFT JOIN user_quiz_answers qa ON qa.user_id = u.id
    LEFT JOIN user_quiz_survey2  qs ON qs.user_id = u.id
"""


async def _fetch_user_vars_batch(user_ids: list) -> dict:
    """Пакетная загрузка переменных для списка user_id. Возвращает dict[user_id → vars]."""
    if not user_ids:
        return {}
    from src.services.db.pool import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(_VARS_QUERY + "WHERE u.id = ANY($1)", user_ids)
    return {row['id']: _build_user_vars_from_row(row) for row in rows}


async def _fetch_user_vars_single(user_id: int) -> dict:
    """Загрузка переменных для одного пользователя."""
    from src.services.db.pool import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_VARS_QUERY + "WHERE u.id = $1", user_id)
    return _build_user_vars_from_row(row) if row else {}


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


def _normalize_buttons(buttons_json) -> list:
    """
    Нормализовать кнопки: распарсить JSON, сгенерировать option_key для кнопок без него.
    Возвращает список dict-ов (мутирует на месте).
    """
    if not buttons_json:
        return []

    if isinstance(buttons_json, str):
        buttons_json = json.loads(buttons_json)

    if not buttons_json:
        return []

    auto_idx = 0
    for btn in buttons_json:
        if not btn.get('option_key'):
            btn['option_key'] = f"auto_{auto_idx}"
            auto_idx += 1

    return buttons_json


async def build_inline_keyboard(
    broadcast_id: int,
    buttons: list,
    telegram_user_id: int = 0,
    user_id: int = 0,
) -> Optional[InlineKeyboardMarkup]:
    """
    Построить InlineKeyboardMarkup из нормализованного массива кнопок.
    Кнопки должны быть предварительно обработаны через _normalize_buttons().

    URL-кнопки идут через redirect-трекер /api/r/{broadcast_id}/{option_key}?u={tg_id}
    для записи кликов. Если api_base_url не настроен — прямая ссылка без трекинга.
    Payment-кнопки генерируют персональную ссылку YooKassa для каждого получателя.
    """
    if not buttons:
        return None

    from src.config import settings
    # Telegram требует https:// для URL в inline-кнопках
    raw_base = settings.api_base_url.rstrip('/') if settings.api_base_url else ''
    base_url = raw_base if raw_base.startswith('https://') else ''

    # Группируем по row
    rows_dict: dict[int, list] = {}
    for btn in buttons:
        row_idx = btn.get('row', 0)
        rows_dict.setdefault(row_idx, []).append(btn)

    keyboard = []
    for row_idx in sorted(rows_dict.keys()):
        row_buttons = []
        for btn in rows_dict[row_idx]:
            if btn['type'] == 'url' and btn.get('url'):
                if base_url:
                    # Через redirect-трекер: стрелочка ↗ + запись клика
                    redirect_url = f"{base_url}/api/r/{broadcast_id}/{btn['option_key']}"
                    if telegram_user_id:
                        redirect_url += f"?u={telegram_user_id}"
                    row_buttons.append(InlineKeyboardButton(
                        text=btn['text'],
                        url=redirect_url,
                    ))
                else:
                    # Прямая ссылка без трекинга (api_base_url не настроен)
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
            elif btn['type'] == 'payment' and btn.get('payment_plan_id') and user_id and telegram_user_id:
                try:
                    from src.services.payments.payment_service import create_subscription_payment_custom
                    payment_result = await create_subscription_payment_custom(
                        user_id=user_id,
                        telegram_user_id=telegram_user_id,
                        plan_id=btn['payment_plan_id'],
                        custom_price=btn.get('payment_custom_price'),
                        bonus_tokens=btn.get('payment_bonus_tokens'),
                    )
                    payment_url = payment_result.get('confirmation_url')
                    if payment_url:
                        btn_text = btn.get('text', '').strip()
                        if not btn_text:
                            price = int(payment_result.get('amount', 0))
                            discount = payment_result.get('discount_percent', 0)
                            plan_name = payment_result.get('description', 'Подписка').replace('Подписка ', '')
                            if discount:
                                btn_text = f"💳 {plan_name} — {price}₽ (скидка {discount}%)"
                            else:
                                btn_text = f"💳 {plan_name} — {price}₽"
                        row_buttons.append(InlineKeyboardButton(
                            text=btn_text,
                            url=payment_url,
                        ))
                except Exception as e:
                    logger.warning(f"Failed to create subscription payment for broadcast button: {e}")
            elif btn['type'] == 'payment' and btn.get('payment_package_id') and int(btn.get('payment_package_id', 0)) > 0 and user_id and telegram_user_id:
                try:
                    from src.services.payments.payment_service import create_token_payment_custom
                    payment_result = await create_token_payment_custom(
                        user_id=user_id,
                        telegram_user_id=telegram_user_id,
                        package_id=btn['payment_package_id'],
                        custom_price=btn.get('payment_custom_price'),
                    )
                    payment_url = payment_result.get('confirmation_url')
                    if payment_url:
                        btn_text = btn.get('text', '').strip()
                        if not btn_text:
                            price = int(payment_result.get('amount', 0))
                            discount = payment_result.get('discount_percent', 0)
                            tokens = payment_result.get('tokens_amount', 0)
                            if discount:
                                btn_text = f"🎁 {tokens} токенов — {price}₽ (скидка {discount}%)"
                            else:
                                btn_text = f"🎁 {tokens} токенов — {price}₽"
                        row_buttons.append(InlineKeyboardButton(
                            text=btn_text,
                            url=payment_url,
                        ))
                except Exception as e:
                    logger.warning(f"Failed to create token payment for broadcast button: {e}")
            elif btn['type'] == 'discount':
                option_key = btn.get('option_key', f"discount_{row_idx}")
                callback_data = f"bcast_discount:{broadcast_id}:{option_key}"
                btn_text = btn.get('text', '').strip()
                if not btn_text:
                    pct = btn.get('discount_percent', 0)
                    hours = btn.get('discount_duration_hours', 24)
                    btn_text = f"🏷️ Скидка {pct}% на {hours}ч"
                row_buttons.append(InlineKeyboardButton(
                    text=btn_text,
                    callback_data=callback_data,
                ))
            elif btn['type'] == 'quiz_start':
                callback_data = f"bcast_quiz:{broadcast_id}"
                row_buttons.append(InlineKeyboardButton(
                    text=btn.get('text', 'START'),
                    callback_data=callback_data,
                ))
        if row_buttons:
            keyboard.append(row_buttons)

    if not keyboard:
        return None

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def execute_broadcast(broadcast_id: int, run_id: Optional[int] = None) -> None:
    """
    Отправить рассылку всем получателям.

    Вызывается как asyncio.create_task() из API handler или scheduler.
    Отправляет текст/фото/опрос, обновляет счётчики, шлёт SSE прогресс.

    Если run_id указан — работаем с recipients конкретного запуска и обновляем счётчики run.
    """
    broadcast = await get_broadcast(broadcast_id)
    if not broadcast:
        logger.error(f"Broadcast {broadcast_id} not found")
        return

    now = datetime.now(timezone.utc)
    await update_broadcast_status(broadcast_id, 'sending', started_at=now)
    if run_id:
        await update_run_status(run_id, 'sending', started_at=now)

    # Получаем получателей: из конкретного run или всех
    if run_id:
        recipients = await get_run_recipients(run_id, status_filter='pending')
    else:
        recipients = await get_broadcast_recipients(broadcast_id, status_filter='pending')

    if not recipients:
        logger.warning(f"Broadcast {broadcast_id} (run={run_id}): no pending recipients")
        await update_broadcast_status(broadcast_id, 'completed', completed_at=now)
        if run_id:
            await update_run_status(run_id, 'completed', completed_at=now)
        return

    from src.bot import get_bot  # lazy import to avoid circular dependency
    bot = get_bot()

    # Персонализация: если в тексте есть {{var}} — загружаем данные пользователей
    raw_message_text = broadcast['message_text']
    has_vars = bool(raw_message_text and '{{' in raw_message_text)
    user_vars_map: dict = {}
    if has_vars:
        all_user_ids = [r['user_id'] for r in recipients]
        user_vars_map = await _fetch_user_vars_batch(all_user_ids)

    # Статичный текст (без переменных) — вычисляем один раз
    static_message_text = sanitize_html_for_telegram(raw_message_text) if raw_message_text else None

    # Если photo_path — только имя файла, строим полный путь
    photo_path = broadcast['photo_path']
    if photo_path and not os.path.isabs(photo_path):
        # Убираем возможный префикс data/broadcast_photos/ чтобы не дублировать
        photo_path = photo_path.removeprefix('data/broadcast_photos/')
        base_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "broadcast_photos"
        )
        photo_path = os.path.join(base_dir, photo_path)

    # Проверяем существование файла фото, иначе отправляем без фото
    if photo_path and not os.path.isfile(photo_path):
        logger.warning(f"Broadcast {broadcast_id}: photo file not found: {photo_path}, sending without photo")
        photo_path = None

    # JSONB поля могут вернуться как строки из asyncpg
    poll_options = broadcast['poll_options']
    if isinstance(poll_options, str):
        poll_options = json.loads(poll_options)

    # Нормализуем кнопки (генерируем option_key если отсутствует) и сохраняем в БД
    inline_buttons = _normalize_buttons(broadcast.get('inline_buttons'))
    if inline_buttons:
        from src.services.db.pool import get_pool
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE broadcasts SET inline_buttons = $1::jsonb WHERE id = $2",
                json.dumps(inline_buttons), broadcast_id,
            )

    # Есть ли кнопки требующие персонализации (URL-трекер или payment URL)
    has_personal_buttons = any(b.get('type') in ('url', 'payment') for b in inline_buttons)

    # Если нет персональных кнопок — строим reply_markup один раз
    shared_reply_markup = None
    if not has_personal_buttons:
        shared_reply_markup = await build_inline_keyboard(broadcast_id, inline_buttons)

    batch_sent = 0
    batch_failed = 0
    total_sent = 0
    total_failed = 0

    for recipient in recipients:
        # Проверяем отмену
        current = await get_broadcast(broadcast_id)
        if not current or current['status'] == 'cancelled':
            logger.info(f"Broadcast {broadcast_id} cancelled, stopping")
            if run_id:
                await update_run_status(run_id, 'cancelled')
            break

        tg_id = recipient['telegram_user_id']
        user_id = recipient['user_id']

        # Персонализированный текст сообщения
        if has_vars:
            user_vars = user_vars_map.get(user_id, {})
            message_text = sanitize_html_for_telegram(substitute_variables(raw_message_text, user_vars))
        else:
            message_text = static_message_text

        # Персональный reply_markup для URL/payment кнопок
        reply_markup = shared_reply_markup
        if has_personal_buttons:
            reply_markup = await build_inline_keyboard(broadcast_id, inline_buttons, telegram_user_id=tg_id, user_id=user_id)

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
                    is_anonymous=False,
                    allows_multiple_answers=broadcast.get('poll_allows_multiple', False),
                )
                # Сохраняем poll_id для маппинга PollAnswer → broadcast
                if poll_result and poll_result.poll:
                    try:
                        await save_recipient_poll_id(
                            broadcast_id, user_id, poll_result.poll.id, run_id=run_id,
                        )
                    except Exception as poll_err:
                        logger.warning(f"Failed to save poll_id for user {user_id}: {poll_err}")

            await save_recipient_result(broadcast_id, user_id, 'sent', run_id=run_id)
            batch_sent += 1
            total_sent += 1

        except Exception as e:
            error_msg = str(e)[:500]
            await save_recipient_result(broadcast_id, user_id, 'failed', error_msg, run_id=run_id)
            batch_failed += 1
            total_failed += 1
            logger.warning(f"Broadcast {broadcast_id}: failed to send to user {user_id}: {error_msg}")

        # Обновляем счётчики и SSE каждые N отправок
        if (batch_sent + batch_failed) >= SSE_UPDATE_INTERVAL:
            await increment_broadcast_counters(broadcast_id, batch_sent, batch_failed)
            if run_id:
                await increment_run_counters(run_id, batch_sent, batch_failed)
            await _broadcast_progress_sse(broadcast_id, total_sent, total_failed, len(recipients))
            batch_sent = 0
            batch_failed = 0

        # Rate limit
        await asyncio.sleep(SEND_DELAY)

    # Финальное обновление оставшегося batch
    if batch_sent > 0 or batch_failed > 0:
        await increment_broadcast_counters(broadcast_id, batch_sent, batch_failed)
        if run_id:
            await increment_run_counters(run_id, batch_sent, batch_failed)

    # Завершаем рассылку
    completed_at = datetime.now(timezone.utc)
    current = await get_broadcast(broadcast_id)
    if current and current['status'] != 'cancelled':
        await update_broadcast_status(broadcast_id, 'completed', completed_at=completed_at)
    if run_id:
        run_data = await get_run(run_id)
        if run_data and run_data['status'] != 'cancelled':
            await update_run_status(run_id, 'completed', completed_at=completed_at)

    # Финальный SSE
    await sse_manager.broadcast(
        event_type='broadcast_completed',
        data={
            'broadcast_id': broadcast_id,
            'run_id': run_id,
            'sent_count': total_sent,
            'failed_count': total_failed,
            'total_recipients': len(recipients),
        },
        endpoint_type='broadcast',
        entity_id=broadcast_id,
    )

    logger.info(
        f"Broadcast {broadcast_id} (run={run_id}) completed: "
        f"{total_sent} sent, {total_failed} failed out of {len(recipients)}"
    )

    # Планируем напоминалки для родительских рассылок (не для run-ов и не для самих напоминалок)
    if not run_id and current and current['status'] != 'cancelled' and not current.get('parent_broadcast_id'):
        try:
            from src.services.reminder_scheduler import compute_reminder_schedules
            await compute_reminder_schedules(broadcast_id)
        except Exception as e:
            logger.error(f"Failed to compute reminder schedules for broadcast {broadcast_id}: {e}", exc_info=True)


async def send_to_single_user(broadcast_id: int, user_id: int, telegram_user_id: int) -> bool:
    """
    Отправить рассылку одному пользователю (для триггеров воронки).
    Возвращает True если успешно.
    """
    broadcast = await get_broadcast(broadcast_id)
    if not broadcast:
        return False

    from src.bot import get_bot
    bot = get_bot()

    raw_message = broadcast['message_text']
    if raw_message and '{{' in raw_message and user_id:
        user_vars = await _fetch_user_vars_single(user_id)
        raw_message = substitute_variables(raw_message, user_vars)
    message_text = sanitize_html_for_telegram(raw_message) if raw_message else None

    photo_path = broadcast['photo_path']
    if photo_path and not os.path.isabs(photo_path):
        photo_path = photo_path.removeprefix('data/broadcast_photos/')
        base_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "broadcast_photos"
        )
        photo_path = os.path.join(base_dir, photo_path)

    if photo_path and not os.path.isfile(photo_path):
        logger.warning(f"Broadcast {broadcast_id}: photo not found: {photo_path}, sending without photo")
        photo_path = None

    poll_options = broadcast['poll_options']
    if isinstance(poll_options, str):
        poll_options = json.loads(poll_options)

    inline_buttons = _normalize_buttons(broadcast.get('inline_buttons'))
    reply_markup = await build_inline_keyboard(broadcast_id, inline_buttons, telegram_user_id=telegram_user_id, user_id=user_id)

    try:
        if photo_path:
            photo = FSInputFile(photo_path)
            if message_text:
                await bot.send_photo(
                    chat_id=telegram_user_id,
                    photo=photo,
                    caption=message_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                )
            else:
                await bot.send_photo(
                    chat_id=telegram_user_id,
                    photo=photo,
                    reply_markup=reply_markup,
                )
        elif message_text:
            await bot.send_message(
                chat_id=telegram_user_id,
                text=message_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )

        if broadcast['poll_question'] and poll_options:
            await bot.send_poll(
                chat_id=telegram_user_id,
                question=broadcast['poll_question'],
                options=poll_options,
                is_anonymous=broadcast.get('poll_is_anonymous', True),
                allows_multiple_answers=broadcast.get('poll_allows_multiple', False),
            )

        return True

    except Exception as e:
        logger.warning(f"Trigger send to user {telegram_user_id} failed: {e}")
        return False


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
