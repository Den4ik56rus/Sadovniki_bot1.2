# src/services/db/users_repo.py

from typing import Optional  # username / first_name / last_name могут быть None

from src.services.db.pool import get_pool  # Берём функцию, которая отдаёт пул подключений


async def get_or_create_user(
    telegram_user_id: int,        # Telegram ID пользователя
    username: Optional[str],      # username (@ник), может быть None
    first_name: Optional[str],    # имя, может быть None
    last_name: Optional[str],     # фамилия, может быть None
) -> int:
    """
    Ищет пользователя по telegram_user_id, если нет — создаёт.
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

        # Если не нашли — создаём нового пользователя
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

        # Возвращаем id только что созданной записи
        return row["id"]
