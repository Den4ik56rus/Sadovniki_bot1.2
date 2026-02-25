# src/services/db/broadcast_repo.py

"""
Репозиторий для рассылок (broadcasts).

Функции:
    - create_broadcast — создать черновик рассылки
    - get_broadcasts — список рассылок с пагинацией
    - get_broadcast — одна рассылка по ID
    - update_broadcast — обновить черновик
    - delete_broadcast — удалить черновик/запланированную
    - update_broadcast_status — изменить статус
    - increment_broadcast_counters — атомарно обновить счётчики sent/failed
    - resolve_recipients — собрать список получателей по target_type
    - save_recipient_result — сохранить результат отправки получателю
    - get_broadcast_recipients — получатели со статусами
    - get_recipient_count_preview — превью количества для UI
    - get_scheduled_broadcasts — рассылки, готовые к отправке
    - get_all_users_short — все пользователи для ручного выбора
    - save_recipient_poll_id — привязать poll_id к получателю
    - resolve_broadcast_from_poll_id — найти broadcast по poll_id
    - record_button_click — записать клик по quick_reply кнопке
    - save_button_text_response — сохранить текстовый ответ на кнопку
    - record_poll_answer — записать ответ на опрос
    - get_button_click_stats — статистика кликов по кнопкам
    - get_button_click_users — список юзеров, нажавших кнопку
    - get_poll_answer_stats — статистика ответов на опрос
    - get_poll_answer_users — список юзеров, выбравших вариант
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


def _clean_user_ids(raw) -> Optional[List[int]]:
    """Нормализовать target_user_ids из JSONB: распарсить строки, оставить только int."""
    if raw is None:
        return None
    while isinstance(raw, str):
        raw = json.loads(raw)
    if isinstance(raw, list):
        seen = set()
        result = []
        for x in raw:
            val = None
            if isinstance(x, (int, float)):
                val = int(x)
            elif isinstance(x, str) and x.isdigit():
                val = int(x)
            if val is not None and val not in seen:
                seen.add(val)
                result.append(val)
        return result if result else None
    return None


async def create_broadcast(
    title: str,
    message_text: Optional[str] = None,
    photo_path: Optional[str] = None,
    poll_question: Optional[str] = None,
    poll_options: Optional[List[str]] = None,
    poll_is_anonymous: bool = True,
    poll_allows_multiple: bool = False,
    target_type: str = 'all',
    target_invite_link_id: Optional[int] = None,
    target_funnel_id: Optional[str] = None,
    target_stage_key: Optional[str] = None,
    target_user_ids: Optional[List[int]] = None,
    scheduled_at: Optional[str] = None,
    inline_buttons: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Создать черновик рассылки."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO broadcasts (
                title, message_text, photo_path,
                poll_question, poll_options, poll_is_anonymous, poll_allows_multiple,
                target_type, target_invite_link_id, target_funnel_id, target_stage_key, target_user_ids,
                scheduled_at, inline_buttons, status
            )
            VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, $9, $10, $11, $12::jsonb, $13::timestamptz, $14::jsonb, 'draft')
            RETURNING *
            """,
            title, message_text, photo_path,
            poll_question,
            json.dumps(poll_options) if poll_options else None,
            poll_is_anonymous, poll_allows_multiple,
            target_type, target_invite_link_id, target_funnel_id, target_stage_key,
            json.dumps(target_user_ids) if target_user_ids else None,
            scheduled_at,
            json.dumps(inline_buttons) if inline_buttons else None,
        )
    return _row_to_dict(row)


async def get_broadcasts(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Список рассылок, отсортированных по дате создания (без напоминалок)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM broadcasts
            WHERE parent_broadcast_id IS NULL
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset,
        )
    return [_row_to_dict(row) for row in rows]


async def get_broadcast(broadcast_id: int) -> Optional[Dict[str, Any]]:
    """Получить рассылку по ID."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM broadcasts WHERE id = $1",
            broadcast_id,
        )
    if not row:
        return None
    return _row_to_dict(row)


async def update_broadcast(
    broadcast_id: int,
    title: Optional[str] = None,
    message_text: Optional[str] = None,
    photo_path: Optional[str] = None,
    poll_question: Optional[str] = None,
    poll_options: Optional[List[str]] = None,
    poll_is_anonymous: Optional[bool] = None,
    poll_allows_multiple: Optional[bool] = None,
    target_type: Optional[str] = None,
    target_invite_link_id: Optional[int] = None,
    target_funnel_id: Optional[str] = None,
    target_stage_key: Optional[str] = None,
    target_user_ids: Optional[List[int]] = None,
    scheduled_at: Optional[str] = None,
    inline_buttons: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """Обновить рассылку. Все статусы кроме 'sending'."""
    pool = get_pool()
    async with pool.acquire() as conn:
        # Собираем SET-клаузы динамически
        sets = []
        params = []
        idx = 1

        fields = {
            'title': title,
            'message_text': message_text,
            'photo_path': photo_path,
            'poll_question': poll_question,
            'poll_is_anonymous': poll_is_anonymous,
            'poll_allows_multiple': poll_allows_multiple,
            'target_type': target_type,
            'target_invite_link_id': target_invite_link_id,
            'target_funnel_id': target_funnel_id,
            'target_stage_key': target_stage_key,
        }

        for field, value in fields.items():
            if value is not None:
                sets.append(f"{field} = ${idx}")
                params.append(value)
                idx += 1

        # JSON-поля требуют явной сериализации
        if poll_options is not None:
            sets.append(f"poll_options = ${idx}::jsonb")
            params.append(json.dumps(poll_options))
            idx += 1

        if target_user_ids is not None:
            sets.append(f"target_user_ids = ${idx}::jsonb")
            params.append(json.dumps(target_user_ids))
            idx += 1

        if inline_buttons is not None:
            sets.append(f"inline_buttons = ${idx}::jsonb")
            params.append(json.dumps(inline_buttons))
            idx += 1

        if scheduled_at is not None:
            sets.append(f"scheduled_at = ${idx}::timestamptz")
            params.append(scheduled_at)
            idx += 1

        if not sets:
            return await get_broadcast(broadcast_id)

        params.append(broadcast_id)
        query = f"""
            UPDATE broadcasts SET {', '.join(sets)}
            WHERE id = ${idx} AND status != 'sending'
            RETURNING *
        """
        row = await conn.fetchrow(query, *params)

    if not row:
        return None
    return _row_to_dict(row)


async def delete_broadcast(broadcast_id: int) -> bool:
    """Удалить рассылку. Все статусы кроме 'sending'."""
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM broadcasts WHERE id = $1 AND status != 'sending'",
            broadcast_id,
        )
    return result == "DELETE 1"


async def delete_broadcasts_bulk(broadcast_ids: List[int]) -> int:
    """Удалить несколько рассылок. Пропускает статус 'sending'. Возвращает количество удалённых."""
    if not broadcast_ids:
        return 0
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM broadcasts WHERE id = ANY($1) AND status != 'sending'",
            broadcast_ids,
        )
    # result = "DELETE N"
    return int(result.split()[-1])


async def update_broadcast_status(
    broadcast_id: int,
    status: str,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
) -> None:
    """Обновить статус рассылки."""
    pool = get_pool()
    async with pool.acquire() as conn:
        if started_at and completed_at:
            await conn.execute(
                "UPDATE broadcasts SET status = $1, started_at = $2, completed_at = $3 WHERE id = $4",
                status, started_at, completed_at, broadcast_id,
            )
        elif started_at:
            await conn.execute(
                "UPDATE broadcasts SET status = $1, started_at = $2 WHERE id = $3",
                status, started_at, broadcast_id,
            )
        elif completed_at:
            await conn.execute(
                "UPDATE broadcasts SET status = $1, completed_at = $2 WHERE id = $3",
                status, completed_at, broadcast_id,
            )
        else:
            await conn.execute(
                "UPDATE broadcasts SET status = $1 WHERE id = $2",
                status, broadcast_id,
            )


async def increment_broadcast_counters(
    broadcast_id: int,
    sent_delta: int = 0,
    failed_delta: int = 0,
) -> None:
    """Атомарно увеличить счётчики sent_count и failed_count."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE broadcasts
            SET sent_count = sent_count + $1, failed_count = failed_count + $2
            WHERE id = $3
            """,
            sent_delta, failed_delta, broadcast_id,
        )


async def resolve_recipients(broadcast_id: int) -> int:
    """
    Собрать получателей по target_type и записать в broadcast_recipients.
    Возвращает количество добавленных получателей.
    """
    pool = get_pool()
    broadcast = await get_broadcast(broadcast_id)
    if not broadcast:
        return 0

    target_type = broadcast['target_type']

    # Исключаем бота
    bot_tg_id = None
    try:
        from src.config import get_settings
        bot_tg_id = int(get_settings().telegram_bot_token.split(":")[0])
    except Exception:
        pass

    async with pool.acquire() as conn:
        if target_type == 'all':
            query = """
                INSERT INTO broadcast_recipients (broadcast_id, user_id, telegram_user_id)
                SELECT $1, u.id, u.telegram_user_id
                FROM users u
                WHERE u.telegram_user_id != $2
                ON CONFLICT (broadcast_id, run_id, user_id) DO NOTHING
            """
            await conn.execute(query, broadcast_id, bot_tg_id or 0)

        elif target_type == 'invite_link':
            link_id = broadcast['target_invite_link_id']
            if not link_id:
                return 0
            query = """
                INSERT INTO broadcast_recipients (broadcast_id, user_id, telegram_user_id)
                SELECT $1, u.id, u.telegram_user_id
                FROM users u
                JOIN invite_link_users ilu ON ilu.user_id = u.id
                WHERE ilu.invite_link_id = $2
                  AND u.telegram_user_id != $3
                ON CONFLICT (broadcast_id, run_id, user_id) DO NOTHING
            """
            await conn.execute(query, broadcast_id, link_id, bot_tg_id or 0)

        elif target_type == 'funnel_stage':
            funnel_id = broadcast['target_funnel_id']
            stage_key = broadcast['target_stage_key']
            if not funnel_id or not stage_key:
                return 0
            query = """
                INSERT INTO broadcast_recipients (broadcast_id, user_id, telegram_user_id)
                SELECT $1, u.id, u.telegram_user_id
                FROM users u
                JOIN client_funnel_position cfp ON cfp.user_id = u.id
                WHERE cfp.funnel_id = $2 AND cfp.stage_key = $3
                  AND u.telegram_user_id != $4
                ON CONFLICT (broadcast_id, run_id, user_id) DO NOTHING
            """
            await conn.execute(query, broadcast_id, funnel_id, stage_key, bot_tg_id or 0)

        elif target_type == 'manual':
            user_ids = _clean_user_ids(broadcast['target_user_ids'])
            if not user_ids:
                return 0
            query = """
                INSERT INTO broadcast_recipients (broadcast_id, user_id, telegram_user_id)
                SELECT $1, u.id, u.telegram_user_id
                FROM users u
                WHERE u.id = ANY($2::int[])
                  AND u.telegram_user_id != $3
                ON CONFLICT (broadcast_id, run_id, user_id) DO NOTHING
            """
            await conn.execute(query, broadcast_id, user_ids, bot_tg_id or 0)

        # Обновляем total_recipients
        count_row = await conn.fetchrow(
            "SELECT COUNT(*) AS cnt FROM broadcast_recipients WHERE broadcast_id = $1",
            broadcast_id,
        )
        total = count_row['cnt'] if count_row else 0
        await conn.execute(
            "UPDATE broadcasts SET total_recipients = $1 WHERE id = $2",
            total, broadcast_id,
        )

    return total


async def save_recipient_result(
    broadcast_id: int,
    user_id: int,
    status: str,
    error_message: Optional[str] = None,
    run_id: Optional[int] = None,
) -> None:
    """Сохранить результат отправки для получателя."""
    pool = get_pool()
    now = datetime.now(timezone.utc) if status == 'sent' else None
    async with pool.acquire() as conn:
        if run_id:
            await conn.execute(
                """
                UPDATE broadcast_recipients
                SET status = $1, error_message = $2, sent_at = $3
                WHERE broadcast_id = $4 AND user_id = $5 AND run_id = $6
                """,
                status, error_message, now, broadcast_id, user_id, run_id,
            )
        else:
            await conn.execute(
                """
                UPDATE broadcast_recipients
                SET status = $1, error_message = $2, sent_at = $3
                WHERE broadcast_id = $4 AND user_id = $5 AND run_id IS NULL
                """,
                status, error_message, now, broadcast_id, user_id,
            )


async def get_broadcast_recipients(
    broadcast_id: int,
    status_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Получатели рассылки со статусами. Опционально фильтр по статусу."""
    pool = get_pool()
    async with pool.acquire() as conn:
        if status_filter:
            rows = await conn.fetch(
                """
                SELECT br.*, u.username, u.first_name, u.last_name
                FROM broadcast_recipients br
                JOIN users u ON u.id = br.user_id
                WHERE br.broadcast_id = $1 AND br.status = $2
                ORDER BY br.id
                """,
                broadcast_id, status_filter,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT br.*, u.username, u.first_name, u.last_name
                FROM broadcast_recipients br
                JOIN users u ON u.id = br.user_id
                WHERE br.broadcast_id = $1
                ORDER BY br.id
                """,
                broadcast_id,
            )
    return [dict(row) for row in rows]


async def get_recipient_count_preview(
    target_type: str,
    target_invite_link_id: Optional[int] = None,
    target_funnel_id: Optional[str] = None,
    target_stage_key: Optional[str] = None,
    target_user_ids: Optional[List[int]] = None,
) -> int:
    """Превью количества получателей без создания рассылки."""
    pool = get_pool()

    bot_tg_id = None
    try:
        from src.config import get_settings
        bot_tg_id = int(get_settings().telegram_bot_token.split(":")[0])
    except Exception:
        pass

    async with pool.acquire() as conn:
        if target_type == 'all':
            row = await conn.fetchrow(
                "SELECT COUNT(*) AS cnt FROM users WHERE telegram_user_id != $1",
                bot_tg_id or 0,
            )
        elif target_type == 'invite_link' and target_invite_link_id:
            row = await conn.fetchrow(
                """
                SELECT COUNT(*) AS cnt FROM users u
                JOIN invite_link_users ilu ON ilu.user_id = u.id
                WHERE ilu.invite_link_id = $1 AND u.telegram_user_id != $2
                """,
                target_invite_link_id, bot_tg_id or 0,
            )
        elif target_type == 'funnel_stage' and target_funnel_id and target_stage_key:
            row = await conn.fetchrow(
                """
                SELECT COUNT(*) AS cnt FROM users u
                JOIN client_funnel_position cfp ON cfp.user_id = u.id
                WHERE cfp.funnel_id = $1 AND cfp.stage_key = $2
                  AND u.telegram_user_id != $3
                """,
                target_funnel_id, target_stage_key, bot_tg_id or 0,
            )
        elif target_type == 'manual' and target_user_ids:
            clean_ids = _clean_user_ids(target_user_ids)
            if not clean_ids:
                return 0
            row = await conn.fetchrow(
                """
                SELECT COUNT(*) AS cnt FROM users
                WHERE id = ANY($1::int[]) AND telegram_user_id != $2
                """,
                clean_ids, bot_tg_id or 0,
            )
        else:
            return 0

    return row['cnt'] if row else 0


async def get_scheduled_broadcasts() -> List[Dict[str, Any]]:
    """Получить рассылки, готовые к отправке (scheduled_at <= NOW()). Без напоминалок."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM broadcasts
            WHERE status = 'scheduled' AND scheduled_at <= NOW()
              AND parent_broadcast_id IS NULL
            ORDER BY scheduled_at
            """
        )
    return [_row_to_dict(row) for row in rows]


async def get_all_users_short() -> List[Dict[str, Any]]:
    """Все пользователи (краткая инфо для ручного выбора получателей)."""
    bot_tg_id = None
    try:
        from src.config import get_settings
        bot_tg_id = int(get_settings().telegram_bot_token.split(":")[0])
    except Exception:
        pass

    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, telegram_user_id, username, first_name, last_name
            FROM users
            WHERE telegram_user_id != $1
            ORDER BY id
            """,
            bot_tg_id or 0,
        )
    return [dict(row) for row in rows]


async def save_recipient_poll_id(
    broadcast_id: int,
    user_id: int,
    telegram_poll_id: str,
    run_id: Optional[int] = None,
) -> None:
    """Привязать telegram poll_id к получателю (для маппинга PollAnswer → broadcast)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        if run_id:
            await conn.execute(
                """
                UPDATE broadcast_recipients
                SET telegram_poll_id = $1
                WHERE broadcast_id = $2 AND user_id = $3 AND run_id = $4
                """,
                telegram_poll_id, broadcast_id, user_id, run_id,
            )
        else:
            await conn.execute(
                """
                UPDATE broadcast_recipients
                SET telegram_poll_id = $1
                WHERE broadcast_id = $2 AND user_id = $3 AND run_id IS NULL
                """,
                telegram_poll_id, broadcast_id, user_id,
            )


async def resolve_broadcast_from_poll_id(telegram_poll_id: str) -> Optional[int]:
    """Найти broadcast_id по telegram poll_id."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT broadcast_id FROM broadcast_recipients
            WHERE telegram_poll_id = $1
            LIMIT 1
            """,
            telegram_poll_id,
        )
    return row['broadcast_id'] if row else None


async def record_button_click(
    broadcast_id: int,
    user_id: int,
    telegram_user_id: int,
    option_key: str,
    button_text: str,
    run_id: Optional[int] = None,
) -> None:
    """Записать клик по кнопке рассылки. При повторном клике по той же кнопке — обновить время."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO broadcast_button_clicks
                (broadcast_id, run_id, user_id, telegram_user_id, option_key, button_text, clicked_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            ON CONFLICT (broadcast_id, run_id, user_id, option_key) DO UPDATE
            SET button_text = $6, clicked_at = NOW()
            """,
            broadcast_id, run_id, user_id, telegram_user_id, option_key, button_text,
        )


async def save_button_text_response(
    broadcast_id: int,
    user_id: int,
    option_key: str,
    text_response: str,
    run_id: Optional[int] = None,
) -> None:
    """Сохранить текстовый ответ пользователя на кнопку рассылки."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE broadcast_button_clicks
            SET text_response = $1, response_at = NOW()
            WHERE broadcast_id = $2 AND user_id = $3 AND option_key = $4
              AND (run_id = $5 OR ($5::int IS NULL AND run_id IS NULL))
            """,
            text_response, broadcast_id, user_id, option_key, run_id,
        )


async def record_poll_answer(
    broadcast_id: int,
    user_id: Optional[int],
    telegram_user_id: int,
    telegram_poll_id: str,
    option_ids: List[int],
    run_id: Optional[int] = None,
) -> None:
    """Записать ответ на опрос. Пустые option_ids = отзыв голоса."""
    pool = get_pool()
    async with pool.acquire() as conn:
        if not option_ids:
            # Отзыв голоса — удаляем запись
            if run_id:
                await conn.execute(
                    "DELETE FROM broadcast_poll_answers WHERE broadcast_id = $1 AND telegram_user_id = $2 AND run_id = $3",
                    broadcast_id, telegram_user_id, run_id,
                )
            else:
                await conn.execute(
                    "DELETE FROM broadcast_poll_answers WHERE broadcast_id = $1 AND telegram_user_id = $2 AND run_id IS NULL",
                    broadcast_id, telegram_user_id,
                )
        else:
            await conn.execute(
                """
                INSERT INTO broadcast_poll_answers
                    (broadcast_id, run_id, user_id, telegram_user_id, telegram_poll_id, option_ids, answered_at)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, NOW())
                ON CONFLICT (broadcast_id, run_id, telegram_user_id) DO UPDATE
                SET option_ids = $6::jsonb, answered_at = NOW()
                """,
                broadcast_id, run_id, user_id, telegram_user_id, telegram_poll_id,
                json.dumps(option_ids),
            )


async def get_button_click_stats(broadcast_id: int) -> List[Dict[str, Any]]:
    """Статистика кликов по кнопкам: [{option_key, button_text, click_count}]."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT option_key, button_text, COUNT(*) AS click_count
            FROM broadcast_button_clicks
            WHERE broadcast_id = $1
            GROUP BY option_key, button_text
            ORDER BY option_key
            """,
            broadcast_id,
        )
    return [dict(row) for row in rows]


async def get_button_click_users(
    broadcast_id: int,
    option_key: str,
) -> List[Dict[str, Any]]:
    """Список пользователей, нажавших конкретную кнопку."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT bbc.user_id, u.first_name, u.last_name, u.username,
                   bbc.clicked_at, bbc.text_response, bbc.response_at
            FROM broadcast_button_clicks bbc
            JOIN users u ON u.id = bbc.user_id
            WHERE bbc.broadcast_id = $1 AND bbc.option_key = $2
            ORDER BY bbc.clicked_at DESC
            """,
            broadcast_id, option_key,
        )
    result = []
    for row in rows:
        d = dict(row)
        if d.get('clicked_at'):
            d['clicked_at'] = d['clicked_at'].isoformat()
        if d.get('response_at'):
            d['response_at'] = d['response_at'].isoformat()
        result.append(d)
    return result


async def get_poll_answer_stats(broadcast_id: int) -> List[Dict[str, Any]]:
    """
    Статистика ответов на опрос: [{option_index, answer_count}].
    Разворачивает JSONB массив option_ids в отдельные строки.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT (opt#>>'{}')::int AS option_index, COUNT(*) AS answer_count
            FROM broadcast_poll_answers,
                 jsonb_array_elements(
                     CASE jsonb_typeof(option_ids)
                         WHEN 'array' THEN option_ids
                         WHEN 'string' THEN (option_ids#>>'{}')::jsonb
                         ELSE jsonb_build_array(option_ids)
                     END
                 ) AS opt
            WHERE broadcast_id = $1
            GROUP BY (opt#>>'{}')::int
            ORDER BY (opt#>>'{}')::int
            """,
            broadcast_id,
        )
    return [dict(row) for row in rows]


async def get_poll_answer_users(
    broadcast_id: int,
    option_index: int,
) -> List[Dict[str, Any]]:
    """Список пользователей, выбравших конкретный вариант опроса."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT bpa.user_id, u.first_name, u.last_name, u.username, bpa.answered_at
            FROM broadcast_poll_answers bpa
            JOIN users u ON u.id = bpa.user_id
            WHERE bpa.broadcast_id = $1 AND bpa.option_ids @> $2::jsonb
            ORDER BY bpa.answered_at DESC
            """,
            broadcast_id, json.dumps([option_index]),
        )
    result = []
    for row in rows:
        d = dict(row)
        if d.get('answered_at'):
            d['answered_at'] = d['answered_at'].isoformat()
        result.append(d)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# BROADCAST RUNS — повторные запуски рассылок
# ═══════════════════════════════════════════════════════════════════════════════

async def create_run(
    broadcast_id: int,
    target_type: str = 'all',
    target_invite_link_id: Optional[int] = None,
    target_funnel_id: Optional[str] = None,
    target_stage_key: Optional[str] = None,
    target_user_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Создать новый запуск рассылки (run)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        # Определяем номер запуска
        max_run = await conn.fetchval(
            "SELECT COALESCE(MAX(run_number), 0) FROM broadcast_runs WHERE broadcast_id = $1",
            broadcast_id,
        )
        run_number = max_run + 1

        row = await conn.fetchrow(
            """
            INSERT INTO broadcast_runs (
                broadcast_id, run_number, target_type,
                target_invite_link_id, target_funnel_id, target_stage_key, target_user_ids,
                status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, 'pending')
            RETURNING *
            """,
            broadcast_id, run_number, target_type,
            target_invite_link_id, target_funnel_id, target_stage_key,
            json.dumps(target_user_ids) if target_user_ids else None,
        )
    return _row_to_dict(row)


async def get_runs(broadcast_id: int) -> List[Dict[str, Any]]:
    """Список запусков рассылки."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM broadcast_runs
            WHERE broadcast_id = $1
            ORDER BY run_number ASC
            """,
            broadcast_id,
        )
    return [_row_to_dict(row) for row in rows]


async def get_run(run_id: int) -> Optional[Dict[str, Any]]:
    """Получить запуск по ID."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM broadcast_runs WHERE id = $1",
            run_id,
        )
    return _row_to_dict(row) if row else None


async def update_run_status(
    run_id: int,
    status: str,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
) -> None:
    """Обновить статус запуска."""
    pool = get_pool()
    async with pool.acquire() as conn:
        if started_at and completed_at:
            await conn.execute(
                "UPDATE broadcast_runs SET status = $1, started_at = $2, completed_at = $3 WHERE id = $4",
                status, started_at, completed_at, run_id,
            )
        elif started_at:
            await conn.execute(
                "UPDATE broadcast_runs SET status = $1, started_at = $2 WHERE id = $3",
                status, started_at, run_id,
            )
        elif completed_at:
            await conn.execute(
                "UPDATE broadcast_runs SET status = $1, completed_at = $2 WHERE id = $3",
                status, completed_at, run_id,
            )
        else:
            await conn.execute(
                "UPDATE broadcast_runs SET status = $1 WHERE id = $2",
                status, run_id,
            )


async def increment_run_counters(
    run_id: int,
    sent_delta: int = 0,
    failed_delta: int = 0,
) -> None:
    """Атомарно увеличить счётчики sent_count и failed_count запуска."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE broadcast_runs
            SET sent_count = sent_count + $1, failed_count = failed_count + $2
            WHERE id = $3
            """,
            sent_delta, failed_delta, run_id,
        )


async def resolve_recipients_for_run(run_id: int) -> int:
    """
    Собрать получателей для конкретного запуска по target_type из run.
    Записывает в broadcast_recipients с привязкой к run_id.
    """
    pool = get_pool()
    run = await get_run(run_id)
    if not run:
        return 0

    broadcast_id = run['broadcast_id']
    target_type = run['target_type']

    # Исключаем бота
    bot_tg_id = None
    try:
        from src.config import get_settings
        bot_tg_id = int(get_settings().telegram_bot_token.split(":")[0])
    except Exception:
        pass

    async with pool.acquire() as conn:
        if target_type == 'all':
            query = """
                INSERT INTO broadcast_recipients (broadcast_id, run_id, user_id, telegram_user_id)
                SELECT $1, $2, u.id, u.telegram_user_id
                FROM users u
                WHERE u.telegram_user_id != $3
                ON CONFLICT (broadcast_id, run_id, user_id) DO NOTHING
            """
            await conn.execute(query, broadcast_id, run_id, bot_tg_id or 0)

        elif target_type == 'invite_link':
            link_id = run['target_invite_link_id']
            if not link_id:
                return 0
            query = """
                INSERT INTO broadcast_recipients (broadcast_id, run_id, user_id, telegram_user_id)
                SELECT $1, $2, u.id, u.telegram_user_id
                FROM users u
                JOIN invite_link_users ilu ON ilu.user_id = u.id
                WHERE ilu.invite_link_id = $3 AND u.telegram_user_id != $4
                ON CONFLICT (broadcast_id, run_id, user_id) DO NOTHING
            """
            await conn.execute(query, broadcast_id, run_id, link_id, bot_tg_id or 0)

        elif target_type == 'funnel_stage':
            funnel_id = run['target_funnel_id']
            stage_key = run['target_stage_key']
            if not funnel_id or not stage_key:
                return 0
            query = """
                INSERT INTO broadcast_recipients (broadcast_id, run_id, user_id, telegram_user_id)
                SELECT $1, $2, u.id, u.telegram_user_id
                FROM users u
                JOIN client_funnel_position cfp ON cfp.user_id = u.id
                WHERE cfp.funnel_id = $3 AND cfp.stage_key = $4 AND u.telegram_user_id != $5
                ON CONFLICT (broadcast_id, run_id, user_id) DO NOTHING
            """
            await conn.execute(query, broadcast_id, run_id, funnel_id, stage_key, bot_tg_id or 0)

        elif target_type == 'manual':
            user_ids = _clean_user_ids(run['target_user_ids'])
            if not user_ids:
                return 0
            query = """
                INSERT INTO broadcast_recipients (broadcast_id, run_id, user_id, telegram_user_id)
                SELECT $1, $2, u.id, u.telegram_user_id
                FROM users u
                WHERE u.id = ANY($3::int[]) AND u.telegram_user_id != $4
                ON CONFLICT (broadcast_id, run_id, user_id) DO NOTHING
            """
            await conn.execute(query, broadcast_id, run_id, user_ids, bot_tg_id or 0)

        # Обновляем total_recipients на run
        count_row = await conn.fetchrow(
            "SELECT COUNT(*) AS cnt FROM broadcast_recipients WHERE run_id = $1",
            run_id,
        )
        total = count_row['cnt'] if count_row else 0
        await conn.execute(
            "UPDATE broadcast_runs SET total_recipients = $1 WHERE id = $2",
            total, run_id,
        )

    return total


async def get_run_recipients(
    run_id: int,
    status_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Получатели конкретного запуска."""
    pool = get_pool()
    async with pool.acquire() as conn:
        if status_filter:
            rows = await conn.fetch(
                """
                SELECT br.*, u.username, u.first_name, u.last_name
                FROM broadcast_recipients br
                JOIN users u ON u.id = br.user_id
                WHERE br.run_id = $1 AND br.status = $2
                ORDER BY br.id
                """,
                run_id, status_filter,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT br.*, u.username, u.first_name, u.last_name
                FROM broadcast_recipients br
                JOIN users u ON u.id = br.user_id
                WHERE br.run_id = $1
                ORDER BY br.id
                """,
                run_id,
            )
    return [dict(row) for row in rows]


async def get_button_click_stats_by_run(
    broadcast_id: int,
    run_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Статистика кликов по кнопкам с опциональным фильтром по run_id."""
    pool = get_pool()
    async with pool.acquire() as conn:
        if run_id:
            rows = await conn.fetch(
                """
                SELECT option_key, button_text, COUNT(*) AS click_count
                FROM broadcast_button_clicks
                WHERE broadcast_id = $1 AND run_id = $2
                GROUP BY option_key, button_text
                ORDER BY option_key
                """,
                broadcast_id, run_id,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT option_key, button_text, COUNT(*) AS click_count
                FROM broadcast_button_clicks
                WHERE broadcast_id = $1
                GROUP BY option_key, button_text
                ORDER BY option_key
                """,
                broadcast_id,
            )
    return [dict(row) for row in rows]


async def get_poll_answer_stats_by_run(
    broadcast_id: int,
    run_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Статистика ответов на опрос с опциональным фильтром по run_id."""
    pool = get_pool()
    async with pool.acquire() as conn:
        if run_id:
            rows = await conn.fetch(
                """
                SELECT (opt#>>'{}')::int AS option_index, COUNT(*) AS answer_count
                FROM broadcast_poll_answers,
                     jsonb_array_elements(
                         CASE jsonb_typeof(option_ids)
                             WHEN 'array' THEN option_ids
                             WHEN 'string' THEN (option_ids#>>'{}')::jsonb
                             ELSE jsonb_build_array(option_ids)
                         END
                     ) AS opt
                WHERE broadcast_id = $1 AND run_id = $2
                GROUP BY (opt#>>'{}')::int
                ORDER BY (opt#>>'{}')::int
                """,
                broadcast_id, run_id,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT (opt#>>'{}')::int AS option_index, COUNT(*) AS answer_count
                FROM broadcast_poll_answers,
                     jsonb_array_elements(
                         CASE jsonb_typeof(option_ids)
                             WHEN 'array' THEN option_ids
                             WHEN 'string' THEN (option_ids#>>'{}')::jsonb
                             ELSE jsonb_build_array(option_ids)
                         END
                     ) AS opt
                WHERE broadcast_id = $1
                GROUP BY (opt#>>'{}')::int
                ORDER BY (opt#>>'{}')::int
                """,
                broadcast_id,
            )
    return [dict(row) for row in rows]


async def get_button_click_users_by_run(
    broadcast_id: int,
    option_key: str,
    run_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Список пользователей, нажавших кнопку, с опциональным фильтром по run."""
    pool = get_pool()
    async with pool.acquire() as conn:
        if run_id:
            rows = await conn.fetch(
                """
                SELECT bbc.user_id, u.first_name, u.last_name, u.username,
                       bbc.clicked_at, bbc.text_response, bbc.response_at
                FROM broadcast_button_clicks bbc
                JOIN users u ON u.id = bbc.user_id
                WHERE bbc.broadcast_id = $1 AND bbc.option_key = $2 AND bbc.run_id = $3
                ORDER BY bbc.clicked_at DESC
                """,
                broadcast_id, option_key, run_id,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT bbc.user_id, u.first_name, u.last_name, u.username,
                       bbc.clicked_at, bbc.text_response, bbc.response_at
                FROM broadcast_button_clicks bbc
                JOIN users u ON u.id = bbc.user_id
                WHERE bbc.broadcast_id = $1 AND bbc.option_key = $2
                ORDER BY bbc.clicked_at DESC
                """,
                broadcast_id, option_key,
            )
    result = []
    for row in rows:
        d = dict(row)
        if d.get('clicked_at'):
            d['clicked_at'] = d['clicked_at'].isoformat()
        if d.get('response_at'):
            d['response_at'] = d['response_at'].isoformat()
        result.append(d)
    return result


async def get_poll_answer_users_by_run(
    broadcast_id: int,
    option_index: int,
    run_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Список пользователей, выбравших вариант опроса, с опциональным фильтром по run."""
    pool = get_pool()
    async with pool.acquire() as conn:
        if run_id:
            rows = await conn.fetch(
                """
                SELECT bpa.user_id, u.first_name, u.last_name, u.username, bpa.answered_at
                FROM broadcast_poll_answers bpa
                JOIN users u ON u.id = bpa.user_id
                WHERE bpa.broadcast_id = $1 AND bpa.option_ids @> $2::jsonb AND bpa.run_id = $3
                ORDER BY bpa.answered_at DESC
                """,
                broadcast_id, json.dumps([option_index]), run_id,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT bpa.user_id, u.first_name, u.last_name, u.username, bpa.answered_at
                FROM broadcast_poll_answers bpa
                JOIN users u ON u.id = bpa.user_id
                WHERE bpa.broadcast_id = $1 AND bpa.option_ids @> $2::jsonb
                ORDER BY bpa.answered_at DESC
                """,
                broadcast_id, json.dumps([option_index]),
            )
    result = []
    for row in rows:
        d = dict(row)
        if d.get('answered_at'):
            d['answered_at'] = d['answered_at'].isoformat()
        result.append(d)
    return result


async def resolve_run_id_from_recipient(broadcast_id: int, user_id: int) -> Optional[int]:
    """Найти run_id по получателю (для маппинга button_click/poll_answer)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT run_id FROM broadcast_recipients
            WHERE broadcast_id = $1 AND user_id = $2
            ORDER BY run_id DESC
            LIMIT 1
            """,
            broadcast_id, user_id,
        )
    return row['run_id'] if row else None


async def resolve_run_id_from_poll(telegram_poll_id: str) -> Optional[int]:
    """Найти run_id по telegram poll_id."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT run_id FROM broadcast_recipients
            WHERE telegram_poll_id = $1
            LIMIT 1
            """,
            telegram_poll_id,
        )
    return row['run_id'] if row else None


# ═══════════════════════════════════════════════════════════════════════════════
# REMINDER BROADCASTS — напоминалки (дочерние рассылки)
# ═══════════════════════════════════════════════════════════════════════════════


async def get_reminders_for_broadcast(broadcast_id: int) -> List[Dict[str, Any]]:
    """Получить все напоминалки для рассылки, отсортированные по sort_order."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM broadcasts
            WHERE parent_broadcast_id = $1
            ORDER BY reminder_sort_order
            """,
            broadcast_id,
        )
    return [_row_to_dict(row) for row in rows]


async def create_reminder(
    parent_id: int,
    sort_order: int = 0,
    message_text: Optional[str] = None,
    photo_path: Optional[str] = None,
    inline_buttons: Optional[List[Dict[str, Any]]] = None,
    poll_question: Optional[str] = None,
    poll_options: Optional[List[str]] = None,
    poll_is_anonymous: bool = True,
    poll_allows_multiple: bool = False,
    offset_hours: float = 2.0,
    trigger_type: str = 'after_send',
    exclude_bought: bool = False,
    exclude_clicked: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Создать напоминалку как дочернюю запись в broadcasts."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO broadcasts (
                title, message_text, photo_path,
                inline_buttons,
                poll_question, poll_options, poll_is_anonymous, poll_allows_multiple,
                target_type, status,
                parent_broadcast_id, reminder_sort_order,
                reminder_offset_hours, reminder_trigger_type,
                reminder_exclude_bought, reminder_exclude_clicked,
                reminder_status
            )
            VALUES (
                $1, $2, $3,
                $4::jsonb,
                $5, $6::jsonb, $7, $8,
                'all', 'draft',
                $9, $10,
                $11, $12,
                $13, $14::jsonb,
                'pending'
            )
            RETURNING *
            """,
            f"Напоминание #{sort_order + 1}",
            message_text, photo_path,
            json.dumps(inline_buttons) if inline_buttons else None,
            poll_question,
            json.dumps(poll_options) if poll_options else None,
            poll_is_anonymous, poll_allows_multiple,
            parent_id, sort_order,
            offset_hours, trigger_type,
            exclude_bought,
            json.dumps(exclude_clicked) if exclude_clicked else None,
        )
    return _row_to_dict(row)


async def update_reminder(
    reminder_id: int,
    data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Обновить напоминалку. Только если parent_broadcast_id IS NOT NULL."""
    pool = get_pool()
    async with pool.acquire() as conn:
        sets = []
        params = []
        idx = 1

        simple_fields = {
            'message_text': data.get('message_text'),
            'photo_path': data.get('photo_path'),
            'poll_question': data.get('poll_question'),
            'poll_is_anonymous': data.get('poll_is_anonymous'),
            'poll_allows_multiple': data.get('poll_allows_multiple'),
            'reminder_sort_order': data.get('sort_order'),
            'reminder_offset_hours': data.get('offset_hours'),
            'reminder_trigger_type': data.get('trigger_type'),
            'reminder_exclude_bought': data.get('exclude_bought'),
        }

        for field, value in simple_fields.items():
            if value is not None:
                sets.append(f"{field} = ${idx}")
                params.append(value)
                idx += 1

        # JSON-поля
        if 'inline_buttons' in data:
            sets.append(f"inline_buttons = ${idx}::jsonb")
            params.append(json.dumps(data['inline_buttons']) if data['inline_buttons'] else None)
            idx += 1

        if 'poll_options' in data:
            sets.append(f"poll_options = ${idx}::jsonb")
            params.append(json.dumps(data['poll_options']) if data['poll_options'] else None)
            idx += 1

        if 'exclude_clicked_buttons' in data:
            sets.append(f"reminder_exclude_clicked = ${idx}::jsonb")
            params.append(json.dumps(data['exclude_clicked_buttons']) if data['exclude_clicked_buttons'] else None)
            idx += 1

        if not sets:
            return await get_broadcast(reminder_id)

        params.append(reminder_id)
        query = f"""
            UPDATE broadcasts SET {', '.join(sets)}
            WHERE id = ${idx} AND parent_broadcast_id IS NOT NULL
            RETURNING *
        """
        row = await conn.fetchrow(query, *params)

    if not row:
        return None
    return _row_to_dict(row)


async def delete_reminder(reminder_id: int) -> bool:
    """Удалить напоминалку."""
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM broadcasts WHERE id = $1 AND parent_broadcast_id IS NOT NULL",
            reminder_id,
        )
    return result == "DELETE 1"


async def sync_reminders(broadcast_id: int, reminders_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Синхронизировать напоминалки: создать новые, обновить существующие, удалить лишние.
    Вызывается при сохранении рассылки (create/update).
    """
    existing = await get_reminders_for_broadcast(broadcast_id)
    existing_ids = {r['id'] for r in existing}
    incoming_ids = {r['id'] for r in reminders_data if r.get('id')}

    # Удалить те, что больше не в списке
    for eid in existing_ids - incoming_ids:
        await delete_reminder(eid)

    result = []
    for i, rdata in enumerate(reminders_data):
        rdata['sort_order'] = i
        if rdata.get('id') and rdata['id'] in existing_ids:
            # Обновить
            updated = await update_reminder(rdata['id'], rdata)
            if updated:
                result.append(updated)
        else:
            # Создать
            created = await create_reminder(
                parent_id=broadcast_id,
                sort_order=i,
                message_text=rdata.get('message_text'),
                photo_path=rdata.get('photo_path'),
                inline_buttons=rdata.get('inline_buttons'),
                poll_question=rdata.get('poll_question'),
                poll_options=rdata.get('poll_options'),
                poll_is_anonymous=rdata.get('poll_is_anonymous', True),
                poll_allows_multiple=rdata.get('poll_allows_multiple', False),
                offset_hours=float(rdata.get('offset_hours', 2)),
                trigger_type=rdata.get('trigger_type', 'after_send'),
                exclude_bought=rdata.get('exclude_bought', False),
                exclude_clicked=rdata.get('exclude_clicked_buttons'),
            )
            result.append(created)

    return result


async def get_due_reminders() -> List[Dict[str, Any]]:
    """Получить напоминалки, готовые к отправке (reminder_scheduled_at <= NOW())."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM broadcasts
            WHERE parent_broadcast_id IS NOT NULL
              AND reminder_status = 'scheduled'
              AND reminder_scheduled_at <= NOW()
            ORDER BY reminder_scheduled_at
            """
        )
    return [_row_to_dict(row) for row in rows]


async def update_reminder_status(
    reminder_id: int,
    status: str,
    scheduled_at=None,
) -> None:
    """Обновить статус напоминалки."""
    pool = get_pool()
    async with pool.acquire() as conn:
        if scheduled_at:
            await conn.execute(
                """
                UPDATE broadcasts
                SET reminder_status = $1, reminder_scheduled_at = $2
                WHERE id = $3 AND parent_broadcast_id IS NOT NULL
                """,
                status, scheduled_at, reminder_id,
            )
        else:
            await conn.execute(
                """
                UPDATE broadcasts SET reminder_status = $1
                WHERE id = $2 AND parent_broadcast_id IS NOT NULL
                """,
                status, reminder_id,
            )


async def cancel_broadcast_reminders(broadcast_id: int) -> None:
    """Отменить все pending/scheduled напоминалки при отмене родительской рассылки."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE broadcasts SET reminder_status = 'cancelled'
            WHERE parent_broadcast_id = $1
              AND reminder_status IN ('pending', 'scheduled')
            """,
            broadcast_id,
        )


async def resolve_reminder_recipients(
    reminder_id: int,
    parent_id: int,
    exclude_bought: bool = False,
    exclude_clicked: Optional[List[str]] = None,
) -> int:
    """
    Собрать получателей для напоминалки:
    1. Все кто получил родительскую рассылку (status='sent')
    2. Исключить купивших (если exclude_bought)
    3. Исключить кликнувших определённые кнопки (если exclude_clicked)
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        # Базовый запрос: получатели родителя со статусом 'sent'
        query = """
            INSERT INTO broadcast_recipients (broadcast_id, user_id, telegram_user_id)
            SELECT $1, br.user_id, br.telegram_user_id
            FROM broadcast_recipients br
            WHERE br.broadcast_id = $2 AND br.status = 'sent'
        """
        params = [reminder_id, parent_id]
        idx = 3

        # Исключить купивших (есть оплата после начала родительской рассылки)
        if exclude_bought:
            query += f"""
                AND br.user_id NOT IN (
                    SELECT p.user_id FROM payments p
                    WHERE p.status = 'succeeded'
                      AND p.created_at >= (SELECT started_at FROM broadcasts WHERE id = ${idx})
                )
            """
            params.append(parent_id)
            idx += 1

        # Исключить кликнувших определённые кнопки
        if exclude_clicked and len(exclude_clicked) > 0:
            query += f"""
                AND br.user_id NOT IN (
                    SELECT bbc.user_id FROM broadcast_button_clicks bbc
                    WHERE bbc.broadcast_id = ${idx} AND bbc.option_key = ANY(${idx + 1}::text[])
                )
            """
            params.extend([parent_id, exclude_clicked])
            idx += 2

        query += " ON CONFLICT (broadcast_id, run_id, user_id) DO NOTHING"

        await conn.execute(query, *params)

        # Посчитать и обновить total_recipients
        count_row = await conn.fetchrow(
            "SELECT COUNT(*) AS cnt FROM broadcast_recipients WHERE broadcast_id = $1",
            reminder_id,
        )
        total = count_row['cnt'] if count_row else 0
        await conn.execute(
            "UPDATE broadcasts SET total_recipients = $1 WHERE id = $2",
            total, reminder_id,
        )
        return total


def _row_to_dict(row) -> Dict[str, Any]:
    """Конвертация asyncpg.Record в dict с сериализацией datetime и JSON."""
    d = dict(row)
    for key in ('created_at', 'started_at', 'completed_at', 'scheduled_at', 'reminder_scheduled_at'):
        if key in d and d[key] is not None:
            d[key] = d[key].isoformat()
    return d
