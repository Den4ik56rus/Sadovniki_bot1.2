# src/services/db/messages_repo.py

import logging
from typing import Optional, Dict, Any, List

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


async def log_message(
    user_id: int,                     # Внутренний id пользователя (users.id)
    direction: str,                   # Направление сообщения: 'user' или 'assistant'
    text: str,                        # Текст сообщения
    session_id: str,                  # Идентификатор сессии (например, aiogram/LLM)
    topic_id: Optional[int] = None,   # Текущая тема (topics.id) или None
    meta: Optional[Dict[str, Any]] = None,  # Дополнительные данные (JSON), например, промты/категория
) -> int:
    """
    Записывает сообщение в таблицу messages.
    Возвращает messages.id.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO messages (user_id, direction, text, session_id, topic_id, meta)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, created_at
            """,
            user_id,
            direction,
            text,
            session_id,
            topic_id,
            meta,
        )

        msg_id = row["id"]
        created_at = row["created_at"]

        # SSE broadcast для admin panel — topic-level (ConsultationView)
        if topic_id:
            try:
                from src.api.sse_manager import sse_manager
                await sse_manager.broadcast(
                    event_type='new_message',
                    data={
                        "id": msg_id,
                        "direction": direction,
                        "text": text,
                        "created_at": created_at.isoformat() if created_at else None,
                        "meta": meta,
                    },
                    endpoint_type='logs',
                    entity_id=topic_id,
                )
            except Exception as e:
                logger.warning(f"Failed to broadcast SSE message event: {e}")

        # SSE broadcast для карточки клиента — client-level (ChatHistory)
        try:
            from src.api.sse_manager import sse_manager
            await sse_manager.broadcast(
                event_type='new_message',
                data={
                    "id": msg_id,
                    "direction": direction,
                    "text": text,
                    "created_at": created_at.isoformat() if created_at else None,
                    "meta": meta,
                    "topic_id": topic_id,
                },
                endpoint_type='client',
                entity_id=user_id,
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast SSE client message event: {e}")

        return msg_id


async def attach_topic_to_message(message_id: int, topic_id: int) -> None:
    """
    Привязывает сообщение к топику (обновляет topic_id).
    Используется для привязки первого вопроса пользователя к топику,
    который создаётся после логирования вопроса.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE messages SET topic_id = $1 WHERE id = $2",
            topic_id,
            message_id,
        )


async def attach_pending_messages_to_topic(
    user_id: int,
    topic_id: int,
    since_msg_id: int | None = None,
) -> int:
    """
    Привязывает все сообщения пользователя без topic_id к указанному топику.
    Если since_msg_id указан — только сообщения начиная с этого id.
    Возвращает количество обновлённых записей.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        if since_msg_id:
            result = await conn.execute(
                """
                UPDATE messages
                SET topic_id = $1
                WHERE user_id = $2 AND topic_id IS NULL AND id >= $3
                """,
                topic_id, user_id, since_msg_id,
            )
        else:
            result = await conn.execute(
                """
                UPDATE messages
                SET topic_id = $1
                WHERE user_id = $2 AND topic_id IS NULL
                """,
                topic_id, user_id,
            )
        count = int(result.split()[-1]) if result else 0
        return count


async def get_last_messages(user_id: int, limit: int = 6) -> List[dict]:
    """
    Возвращает последние limit сообщений (user+bot) для пользователя,
    отсортированные от старых к новым.
    """
    # Берём пул
    pool = get_pool()

    # Делаем запрос к БД
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT direction, text, created_at
            FROM messages
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            user_id,  # $1
            limit,    # $2
        )

    # Сейчас rows отсортированы от новых к старым, а нам нужно наоборот.
    rows = list(reversed(rows))

    # Преобразуем результат в список обычных словарей (dict),
    # чтобы было удобно использовать в коде и передавать в LLM.
    result: List[dict] = []
    for row in rows:
        result.append(
            {
                "direction": row["direction"],  # 'user' или 'assistant'
                "text": row["text"],            # текст сообщения
                "created_at": row["created_at"] # время создания
            }
        )

    return result


async def get_recent_messages(topic_id: int, limit: int = 5) -> List[dict]:
    """
    Получить последние N сообщений для топика (для контекста классификации).

    Args:
        topic_id: ID топика
        limit: Количество сообщений

    Returns:
        Список словарей с полями: direction, text, created_at
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT direction, text, created_at
            FROM messages
            WHERE topic_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            topic_id,
            limit,
        )
        # Возвращаем в хронологическом порядке (старые → новые)
        return [dict(row) for row in reversed(rows)]


async def find_unanswered_user_messages(since_minutes: int = 30) -> List[dict]:
    """
    Находит пользователей, которые отправили вопрос но не получили ответа.

    Ищет direction='user' сообщения за последние since_minutes минут,
    для которых нет последующего direction='bot' сообщения в том же topic_id.

    Возвращает один результат на пользователя (самый последний неотвеченный вопрос).
    Используется при запуске бота для детектирования пропущенных ответов.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (m.user_id)
                u.telegram_user_id,
                m.user_id,
                m.id AS message_id,
                m.text,
                m.created_at,
                m.topic_id
            FROM messages m
            JOIN users u ON u.id = m.user_id
            WHERE m.direction = 'user'
              AND m.created_at >= NOW() - make_interval(mins => $1)
              AND NOT EXISTS (
                  SELECT 1 FROM messages bot_msg
                  WHERE bot_msg.user_id = m.user_id
                    AND bot_msg.direction = 'bot'
                    AND bot_msg.created_at > m.created_at
                    AND (
                        bot_msg.topic_id = m.topic_id
                        OR (m.topic_id IS NULL AND bot_msg.topic_id IS NULL)
                    )
              )
            ORDER BY m.user_id, m.created_at DESC
            """,
            since_minutes,
        )
    return [dict(r) for r in rows]


async def get_user_chat_history(user_id: int, limit: int = 500) -> Dict[str, Any]:
    """
    Возвращает полную историю чата пользователя со всех топиков + без топика.
    Также возвращает список топиков для группировки.

    Returns:
        {
            "messages": [{ id, direction, text, created_at, meta, topic_id }, ...],
            "topics": [{ id, culture, category, status, created_at }, ...]
        }
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        # Все сообщения пользователя
        msg_rows = await conn.fetch(
            """
            SELECT id, direction, text, created_at, meta, topic_id
            FROM messages
            WHERE user_id = $1
            ORDER BY created_at ASC
            LIMIT $2
            """,
            user_id,
            limit,
        )

        # Уникальные topic_id из сообщений
        topic_ids = list({r["topic_id"] for r in msg_rows if r["topic_id"] is not None})

        topics = []
        if topic_ids:
            topic_rows = await conn.fetch(
                """
                SELECT t.id, t.culture, t.status, t.created_at,
                       (SELECT cl.consultation_category
                        FROM consultation_logs cl
                        WHERE cl.topic_id = t.id
                        LIMIT 1) AS category
                FROM topics t
                WHERE t.id = ANY($1)
                ORDER BY t.created_at ASC
                """,
                topic_ids,
            )
            for row in topic_rows:
                topics.append({
                    "id": row["id"],
                    "culture": row["culture"],
                    "category": row["category"],
                    "status": row["status"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                })

        messages = []
        for row in msg_rows:
            messages.append({
                "id": row["id"],
                "direction": row["direction"],
                "text": row["text"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "meta": row["meta"],
                "topic_id": row["topic_id"],
            })

        return {"messages": messages, "topics": topics}
