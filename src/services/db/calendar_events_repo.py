# src/services/db/calendar_events_repo.py
"""
Репозиторий для работы с событиями календаря.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from src.services.db.pool import get_pool


async def get_events_by_user(
    user_id: int,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> list[dict]:
    """
    Получить события пользователя за период.
    Если start/end не указаны — возвращает все события.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        if start and end:
            rows = await conn.fetch(
                """
                SELECT id, user_id, title, start_date_time, end_date_time, all_day,
                       type, culture_code, plot_id, status, description, tags, color,
                       created_at, updated_at
                FROM calendar_events
                WHERE user_id = $1
                  AND start_date_time >= $2
                  AND start_date_time < $3
                ORDER BY start_date_time
                """,
                user_id,
                start,
                end,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, user_id, title, start_date_time, end_date_time, all_day,
                       type, culture_code, plot_id, status, description, tags, color,
                       created_at, updated_at
                FROM calendar_events
                WHERE user_id = $1
                ORDER BY start_date_time
                """,
                user_id,
            )

        return [_row_to_dict(row) for row in rows]


async def get_event_by_id(event_id: str, user_id: int) -> Optional[dict]:
    """
    Получить событие по ID (только если принадлежит пользователю).
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, user_id, title, start_date_time, end_date_time, all_day,
                   type, culture_code, plot_id, status, description, tags, color,
                   created_at, updated_at
            FROM calendar_events
            WHERE id = $1 AND user_id = $2
            """,
            UUID(event_id),
            user_id,
        )

        if row is None:
            return None

        return _row_to_dict(row)


async def create_event(user_id: int, data: dict) -> dict:
    """
    Создать новое событие.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO calendar_events (
                user_id, title, start_date_time, end_date_time, all_day,
                type, culture_code, plot_id, status, description, tags, color
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING id, user_id, title, start_date_time, end_date_time, all_day,
                      type, culture_code, plot_id, status, description, tags, color,
                      created_at, updated_at
            """,
            user_id,
            data["title"],
            data["startDateTime"],
            data.get("endDateTime"),
            data.get("allDay", False),
            data["type"],
            data.get("cultureCode"),
            data.get("plotId"),
            data.get("status", "planned"),
            data.get("description"),
            data.get("tags"),
            data.get("color"),
        )

        return _row_to_dict(row)


async def update_event(event_id: str, user_id: int, data: dict) -> Optional[dict]:
    """
    Обновить событие (только если принадлежит пользователю).
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE calendar_events
            SET title = COALESCE($3, title),
                start_date_time = COALESCE($4, start_date_time),
                end_date_time = $5,
                all_day = COALESCE($6, all_day),
                type = COALESCE($7, type),
                culture_code = $8,
                plot_id = $9,
                status = COALESCE($10, status),
                description = $11,
                tags = $12,
                color = $13,
                updated_at = NOW()
            WHERE id = $1 AND user_id = $2
            RETURNING id, user_id, title, start_date_time, end_date_time, all_day,
                      type, culture_code, plot_id, status, description, tags, color,
                      created_at, updated_at
            """,
            UUID(event_id),
            user_id,
            data.get("title"),
            data.get("startDateTime"),
            data.get("endDateTime"),
            data.get("allDay"),
            data.get("type"),
            data.get("cultureCode"),
            data.get("plotId"),
            data.get("status"),
            data.get("description"),
            data.get("tags"),
            data.get("color"),
        )

        if row is None:
            return None

        return _row_to_dict(row)


async def delete_event(event_id: str, user_id: int) -> bool:
    """
    Удалить событие (только если принадлежит пользователю).
    Возвращает True если событие было удалено.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM calendar_events
            WHERE id = $1 AND user_id = $2
            """,
            UUID(event_id),
            user_id,
        )

        # result = "DELETE 1" или "DELETE 0"
        return result == "DELETE 1"


async def update_event_status(event_id: str, user_id: int, status: str) -> Optional[dict]:
    """
    Изменить статус события.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE calendar_events
            SET status = $3, updated_at = NOW()
            WHERE id = $1 AND user_id = $2
            RETURNING id, user_id, title, start_date_time, end_date_time, all_day,
                      type, culture_code, plot_id, status, description, tags, color,
                      created_at, updated_at
            """,
            UUID(event_id),
            user_id,
            status,
        )

        if row is None:
            return None

        return _row_to_dict(row)


def _row_to_dict(row) -> dict:
    """
    Преобразовать asyncpg.Record в dict с правильными именами полей для API.
    """
    return {
        "id": str(row["id"]),
        "userId": row["user_id"],
        "title": row["title"],
        "startDateTime": row["start_date_time"].isoformat() if row["start_date_time"] else None,
        "endDateTime": row["end_date_time"].isoformat() if row["end_date_time"] else None,
        "allDay": row["all_day"],
        "type": row["type"],
        "cultureCode": row["culture_code"],
        "plotId": row["plot_id"],
        "status": row["status"],
        "description": row["description"],
        "tags": row["tags"],
        "color": row["color"],
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
    }
