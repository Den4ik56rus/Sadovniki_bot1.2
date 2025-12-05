# src/services/db/messages_repo.py

from typing import Optional, Dict, Any, List  # Для типов параметров и возвращаемого значения

from src.services.db.pool import get_pool  # Пул подключений


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
    # Берём пул
    pool = get_pool()

    # Открываем соединение
    async with pool.acquire() as conn:
        # Выполняем INSERT и сразу получаем вставленную строку (RETURNING id)
        row = await conn.fetchrow(
            """
            INSERT INTO messages (user_id, direction, text, session_id, topic_id, meta)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            user_id,    # $1
            direction,  # $2
            text,       # $3
            session_id, # $4
            topic_id,   # $5
            meta,       # $6 (PostgreSQL принимает jsonb)
        )

        # Возвращаем id нового сообщения
        return row["id"]


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
