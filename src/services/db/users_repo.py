# src/services/db/users_repo.py

import logging
from typing import Optional  # username / first_name / last_name могут быть None

from src.services.db.pool import get_pool  # Берём функцию, которая отдаёт пул подключений
from src.pricing import TRIAL_QUESTIONS, get_trial_questions

logger = logging.getLogger(__name__)


def _get_bot_telegram_id() -> Optional[int]:
    """Получить telegram_user_id бота из BOT_TOKEN (первая часть до ':')."""
    try:
        from src.config import get_settings
        token = get_settings().telegram_bot_token
        return int(token.split(":")[0])
    except Exception:
        return None


async def get_or_create_user(
    telegram_user_id: int,        # Telegram ID пользователя
    username: Optional[str],      # username (@ник), может быть None
    first_name: Optional[str],    # имя, может быть None
    last_name: Optional[str],     # фамилия, может быть None
) -> int:
    """
    Ищет пользователя по telegram_user_id, если нет — создаёт.
    Новым пользователям начисляет бесплатные токены (триал).
    Возвращает внутренний users.id.
    """
    # Не регистрируем самого бота как пользователя
    bot_id = _get_bot_telegram_id()
    if bot_id and telegram_user_id == bot_id:
        logger.warning(f"Попытка зарегистрировать бота (tg_id={telegram_user_id}) как пользователя — пропускаем")
        return -1

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

        # Если пользователь уже существует — обновляем данные профиля и возвращаем id
        if row is not None:
            await conn.execute(
                """
                UPDATE users
                SET username = COALESCE($2, username),
                    first_name = COALESCE($3, first_name),
                    last_name = COALESCE($4, last_name)
                WHERE telegram_user_id = $1
                """,
                telegram_user_id,
                username,
                first_name,
                last_name,
            )
            return row["id"]

        # Если не нашли — создаём нового пользователя и начисляем триал
        # Получаем количество триальных токенов из настроек (динамическое)
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

            # Начисляем бесплатные токены
            await conn.execute(
                """
                UPDATE users
                SET token_balance = token_balance + $1,
                    purchased_token_balance = COALESCE(purchased_token_balance, 0) + $1,
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
                "Бесплатные токены для новых пользователей",
            )

            # Добавляем в CRM-воронку и legacy client_funnel_status
            await conn.execute(
                """
                INSERT INTO client_funnel_position (user_id, funnel_id, stage_key)
                VALUES ($1, 'crm', 'new')
                ON CONFLICT (user_id, funnel_id) DO NOTHING
                """,
                new_user_id,
            )
            await conn.execute(
                """
                INSERT INTO client_funnel_status (user_id, status, auto_status)
                VALUES ($1, 'new', 'new')
                ON CONFLICT (user_id) DO NOTHING
                """,
                new_user_id,
            )

            return new_user_id


async def update_user_avatar(user_id: int, avatar_path: str) -> None:
    """Обновляет путь к аватару пользователя."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET avatar_path = $1 WHERE id = $2",
            avatar_path, user_id,
        )


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


async def delete_user_by_telegram_id(telegram_user_id: int) -> bool:
    """
    Удаляет пользователя по telegram_user_id.
    Все связанные записи удаляются каскадно (ON DELETE CASCADE).
    Возвращает True если пользователь был найден и удалён.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM users WHERE telegram_user_id = $1",
            telegram_user_id,
        )
        # result = "DELETE N" где N — количество удалённых строк
        return result == "DELETE 1"
