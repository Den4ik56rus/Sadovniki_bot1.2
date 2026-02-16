# src/services/db/users_repo.py

from typing import Optional  # username / first_name / last_name могут быть None

from src.services.db.pool import get_pool  # Берём функцию, которая отдаёт пул подключений
from src.pricing import TRIAL_QUESTIONS, get_trial_questions


async def get_or_create_user(
    telegram_user_id: int,        # Telegram ID пользователя
    username: Optional[str],      # username (@ник), может быть None
    first_name: Optional[str],    # имя, может быть None
    last_name: Optional[str],     # фамилия, может быть None
) -> int:
    """
    Ищет пользователя по telegram_user_id, если нет — создаёт.
    Новым пользователям начисляет бесплатные вопросы (триал).
    Возвращает внутренний users.id.
    """
    # Получаем пул подключений
    pool = get_pool()

    # Через пул получаем соединение с БД (conn) и работаем внутри контекстного менеджера
    async with pool.acquire() as conn:
        # Пробуем найти пользователя по telegram_user_id
        row = await conn.fetchrow(
            """
            SELECT id
            FROM users
            WHERE telegram_user_id = $1
            """,
            telegram_user_id,  # Подставляем $1
        )

        # Если пользователь уже существует — возвращаем его id
        if row is not None:
            return row["id"]

        # Если не нашли — создаём нового пользователя и начисляем триал
        # Получаем количество триальных вопросов из настроек (динамическое)
        trial_qty = await get_trial_questions()

        async with conn.transaction():
            # Создаём пользователя
            row = await conn.fetchrow(
                """
                INSERT INTO users (telegram_user_id, username, first_name, last_name)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                telegram_user_id,  # $1 — telegram_user_id
                username,          # $2 — username
                first_name,        # $3 — first_name
                last_name,         # $4 — last_name
            )

            new_user_id = row["id"]

            # Начисляем бесплатные вопросы
            await conn.execute(
                """
                UPDATE users
                SET token_balance = token_balance + $1,
                    trial_questions_granted = true
                WHERE id = $2
                """,
                trial_qty,
                new_user_id,
            )

            # Логируем в token_transactions
            await conn.execute(
                """
                INSERT INTO token_transactions
                (user_id, amount, operation_type, description)
                VALUES ($1, $2, $3, $4)
                """,
                new_user_id,
                trial_qty,
                "trial_grant",
                "Бесплатные вопросы для новых пользователей",
            )

            return new_user_id


async def user_exists(telegram_user_id: int) -> bool:
    """Проверяет, существует ли пользователь с данным telegram_user_id."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM users WHERE telegram_user_id = $1",
            telegram_user_id,
        )
        return row is not None


async def count_all_users() -> int:
    """
    Возвращает общее количество пользователей в БД.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT COUNT(*) AS cnt FROM users;")
        return int(row["cnt"]) if row and row["cnt"] is not None else 0
