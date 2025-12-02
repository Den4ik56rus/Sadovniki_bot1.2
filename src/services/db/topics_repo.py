# src/services/db/topics_repo.py

from typing import Optional  # topic_id может быть Optional в других местах

from src.services.db.pool import get_pool  # Пул подключений


async def get_or_create_open_topic(user_id: int, session_id: str) -> int:
    """
    Ищет последнюю ОТКРЫТУЮ тему (topics.status='open') для пользователя.
    Если нашёл — возвращает её id.
    Если нет — создаёт новую запись в topics и возвращает её id.
    """
    # Берём пул
    pool = get_pool()

    # Работаем с БД
    async with pool.acquire() as conn:
        # Ищем последнюю открытую тему у пользователя
        row = await conn.fetchrow(
            """
            SELECT id
            FROM topics
            WHERE user_id = $1
              AND status = 'open'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id,  # $1
        )

        # Если нашли — возвращаем id
        if row is not None:
            return row["id"]

        # Если не нашли — создаём новую тему
        row = await conn.fetchrow(
            """
            INSERT INTO topics (user_id, session_id, status)
            VALUES ($1, $2, 'open')
            RETURNING id
            """,
            user_id,     # $1 — пользователь
            session_id,  # $2 — идентификатор сессии
        )

        # Возвращаем id новой темы
        return row["id"]
