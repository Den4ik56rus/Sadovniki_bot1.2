# src/services/db/user_plantings_repo.py
"""
Репозиторий для работы с посадками пользователя.
"""

from typing import Optional
from uuid import UUID

from src.services.db.pool import get_pool


async def get_plantings_by_user(user_id: int) -> list[dict]:
    """
    Получить все посадки пользователя.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, user_id, culture_type, variety,
                   fruiting_start, fruiting_end,
                   created_at, updated_at
            FROM user_plantings
            WHERE user_id = $1
            ORDER BY created_at
            """,
            user_id,
        )

        return [_row_to_dict(row) for row in rows]


async def get_planting_by_id(planting_id: str, user_id: int) -> Optional[dict]:
    """
    Получить посадку по ID (только если принадлежит пользователю).
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, user_id, culture_type, variety,
                   fruiting_start, fruiting_end,
                   created_at, updated_at
            FROM user_plantings
            WHERE id = $1 AND user_id = $2
            """,
            UUID(planting_id),
            user_id,
        )

        if row is None:
            return None

        return _row_to_dict(row)


async def create_planting(user_id: int, data: dict) -> dict:
    """
    Создать новую посадку.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO user_plantings (
                user_id, culture_type, variety,
                fruiting_start, fruiting_end
            )
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, user_id, culture_type, variety,
                      fruiting_start, fruiting_end,
                      created_at, updated_at
            """,
            user_id,
            data["cultureType"],
            data.get("variety"),
            data.get("fruitingStart"),
            data.get("fruitingEnd"),
        )

        return _row_to_dict(row)


async def update_planting(planting_id: str, user_id: int, data: dict) -> Optional[dict]:
    """
    Обновить посадку (только если принадлежит пользователю).
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE user_plantings
            SET culture_type = COALESCE($3, culture_type),
                variety = $4,
                fruiting_start = $5,
                fruiting_end = $6,
                updated_at = NOW()
            WHERE id = $1 AND user_id = $2
            RETURNING id, user_id, culture_type, variety,
                      fruiting_start, fruiting_end,
                      created_at, updated_at
            """,
            UUID(planting_id),
            user_id,
            data.get("cultureType"),
            data.get("variety"),
            data.get("fruitingStart"),
            data.get("fruitingEnd"),
        )

        if row is None:
            return None

        return _row_to_dict(row)


async def delete_planting(planting_id: str, user_id: int) -> bool:
    """
    Удалить посадку (только если принадлежит пользователю).
    Возвращает True если посадка была удалена.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM user_plantings
            WHERE id = $1 AND user_id = $2
            """,
            UUID(planting_id),
            user_id,
        )

        # result = "DELETE 1" или "DELETE 0"
        return result == "DELETE 1"


async def get_user_region(user_id: int) -> Optional[str]:
    """
    Получить регион пользователя.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT region FROM users WHERE id = $1
            """,
            user_id,
        )

        if row is None:
            return None

        return row["region"]


async def update_user_region(user_id: int, region: str) -> str:
    """
    Обновить регион пользователя.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users SET region = $2 WHERE id = $1
            """,
            user_id,
            region,
        )

        return region


def _row_to_dict(row) -> dict:
    """
    Преобразовать asyncpg.Record в dict с правильными именами полей для API.
    """
    return {
        "id": str(row["id"]),
        "userId": row["user_id"],
        "cultureType": row["culture_type"],
        "variety": row["variety"],
        "fruitingStart": row["fruiting_start"].isoformat() if row["fruiting_start"] else None,
        "fruitingEnd": row["fruiting_end"].isoformat() if row["fruiting_end"] else None,
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
    }
