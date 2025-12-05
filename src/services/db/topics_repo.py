# src/services/db/topics_repo.py

from typing import Optional  # topic_id может быть Optional в других местах

from src.services.db.pool import get_pool  # Пул подключений


async def get_or_create_open_topic(user_id: int, session_id: str, force_new: bool = False) -> int:
    """
    Ищет последнюю ОТКРЫТУЮ тему (topics.status='open') для пользователя.
    Если нашёл — возвращает её id.
    Если нет — создаёт новую запись в topics и возвращает её id.

    Args:
        user_id: ID пользователя
        session_id: Идентификатор сессии
        force_new: Если True, закрывает все открытые темы и создает новую
    """
    # Берём пул
    pool = get_pool()

    # Работаем с БД
    async with pool.acquire() as conn:
        # Если force_new=True, закрываем все открытые темы
        if force_new:
            await conn.execute(
                """
                UPDATE topics
                SET status = 'closed', updated_at = CURRENT_TIMESTAMP
                WHERE user_id = $1 AND status = 'open'
                """,
                user_id,
            )
            print(f"[get_or_create_open_topic] force_new=True, закрыты все открытые топики для user_id={user_id}")
        else:
            # Ищем последнюю открытую тему у пользователя
            row = await conn.fetchrow(
                """
                SELECT id, status
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
                print(f"[get_or_create_open_topic] Найден открытый топик: topic_id={row['id']}, status={row['status']}, user_id={user_id}")
                return row["id"]
            else:
                print(f"[get_or_create_open_topic] Открытый топик НЕ найден для user_id={user_id}, создаём новый")

        # Если не нашли или force_new=True — создаём новую тему
        row = await conn.fetchrow(
            """
            INSERT INTO topics (user_id, session_id, status, follow_up_questions_left)
            VALUES ($1, $2, 'open', 3)
            RETURNING id
            """,
            user_id,     # $1 — пользователь
            session_id,  # $2 — идентификатор сессии
        )

        print(f"[get_or_create_open_topic] Создан НОВЫЙ топик: topic_id={row['id']}, user_id={user_id}, follow_up_questions_left=3")
        # Возвращаем id новой темы
        return row["id"]


async def get_topic_culture(topic_id: int) -> Optional[str]:
    """Получить культуру для темы."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT culture FROM topics WHERE id = $1",
            topic_id,
        )
        return row["culture"] if row else None


async def get_topic_category(topic_id: int) -> Optional[str]:
    """Получить категорию для темы."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT category FROM topics WHERE id = $1",
            topic_id,
        )
        return row["category"] if row else None


async def set_topic_culture(topic_id: int, culture: str) -> None:
    """Установить культуру для темы."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE topics SET culture = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2",
            culture,
            topic_id,
        )


async def set_topic_category(topic_id: int, category: str) -> None:
    """Установить категорию для темы."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE topics SET category = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2",
            category,
            topic_id,
        )


async def get_topic_message_count(topic_id: int) -> int:
    """Получить количество сообщений пользователя в теме."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT COUNT(*) as count
            FROM messages
            WHERE topic_id = $1 AND direction = 'user'
            """,
            topic_id,
        )
        return row["count"] if row else 0


async def get_topic_status(topic_id: int) -> Optional[str]:
    """Получить статус темы."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status FROM topics WHERE id = $1",
            topic_id,
        )
        return row["status"] if row else None


async def close_open_topics(user_id: int) -> None:
    """
    Закрывает все открытые топики пользователя.
    Используется при нажатии кнопки "Новая тема" или возврате в главное меню.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        # Сначала проверим, сколько топиков открыто
        count_before = await conn.fetchval(
            "SELECT COUNT(*) FROM topics WHERE user_id = $1 AND status = 'open'",
            user_id,
        )
        print(f"[close_open_topics] До закрытия: {count_before} открытых топиков для user_id={user_id}")

        # Закрываем
        result = await conn.execute(
            """
            UPDATE topics
            SET status = 'closed', updated_at = CURRENT_TIMESTAMP
            WHERE user_id = $1 AND status = 'open'
            """,
            user_id,
        )
        print(f"[close_open_topics] Закрыто топиков: {result}, user_id={user_id}")

        # Проверяем после
        count_after = await conn.fetchval(
            "SELECT COUNT(*) FROM topics WHERE user_id = $1 AND status = 'open'",
            user_id,
        )
        print(f"[close_open_topics] После закрытия: {count_after} открытых топиков для user_id={user_id}")


async def get_follow_up_questions_left(topic_id: int) -> int:
    """Получить количество оставшихся уточняющих вопросов."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT follow_up_questions_left FROM topics WHERE id = $1",
            topic_id,
        )
        return row["follow_up_questions_left"] if row else 0


async def decrement_follow_up_questions(topic_id: int) -> int:
    """Уменьшить количество уточняющих вопросов на 1. Возвращает новое значение."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE topics
            SET follow_up_questions_left = GREATEST(follow_up_questions_left - 1, 0),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
            RETURNING follow_up_questions_left
            """,
            topic_id,
        )
        return row["follow_up_questions_left"] if row else 0


async def reset_follow_up_questions(topic_id: int) -> None:
    """Сбросить счётчик уточняющих вопросов на 3."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE topics
            SET follow_up_questions_left = 3,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
            """,
            topic_id,
        )
        print(f"[reset_follow_up_questions] Reset counter to 3 for topic_id={topic_id}")


async def get_topic_info(topic_id: int) -> Optional[dict]:
    """Получить полную информацию о теме."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, status, culture, follow_up_questions_left
            FROM topics WHERE id = $1
            """,
            topic_id,
        )
        return dict(row) if row else None
