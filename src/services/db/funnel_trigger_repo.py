# src/services/db/funnel_trigger_repo.py

"""
Репозиторий для триггеров этапов воронки.

Триггер = привязка рассылки к этапу воронки.
Когда пользователь перемещается на этап — ему автоматически отправляется рассылка.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


def _serialize_row(row: dict) -> dict:
    """Convert datetime and Decimal objects for JSON serialization."""
    result = dict(row)
    for key, value in result.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, Decimal):
            result[key] = float(value)
    return result


async def get_triggers_for_stage(funnel_id: str, stage_key: str) -> List[Dict[str, Any]]:
    """Получить активные триггеры для конкретного этапа."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT fst.*, b.title AS broadcast_title, b.status AS broadcast_status
            FROM funnel_stage_triggers fst
            JOIN broadcasts b ON b.id = fst.broadcast_id
            WHERE fst.funnel_id = $1 AND fst.stage_key = $2
            ORDER BY fst.created_at ASC
            """,
            funnel_id, stage_key,
        )
    return [_serialize_row(row) for row in rows]


async def get_triggers_for_funnel(funnel_id: str) -> List[Dict[str, Any]]:
    """Получить все триггеры для воронки."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT fst.*, b.title AS broadcast_title, b.status AS broadcast_status
            FROM funnel_stage_triggers fst
            JOIN broadcasts b ON b.id = fst.broadcast_id
            WHERE fst.funnel_id = $1
            ORDER BY fst.stage_key, fst.created_at ASC
            """,
            funnel_id,
        )
    return [_serialize_row(row) for row in rows]


async def create_trigger(
    funnel_id: str,
    stage_key: str,
    broadcast_id: int,
) -> Optional[Dict[str, Any]]:
    """Создать триггер: привязать рассылку к этапу воронки."""
    pool = get_pool()
    async with pool.acquire() as conn:
        # Проверяем что этап существует
        stage = await conn.fetchrow(
            "SELECT 1 FROM funnel_stages WHERE funnel_id = $1 AND stage_key = $2",
            funnel_id, stage_key,
        )
        if not stage:
            logger.warning(f"Stage {funnel_id}/{stage_key} not found")
            return None

        # Проверяем что рассылка существует
        broadcast = await conn.fetchrow(
            "SELECT 1 FROM broadcasts WHERE id = $1",
            broadcast_id,
        )
        if not broadcast:
            logger.warning(f"Broadcast {broadcast_id} not found")
            return None

        row = await conn.fetchrow(
            """
            INSERT INTO funnel_stage_triggers (funnel_id, stage_key, broadcast_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (funnel_id, stage_key, broadcast_id) DO NOTHING
            RETURNING *
            """,
            funnel_id, stage_key, broadcast_id,
        )

    if not row:
        return None

    # Получаем с join на broadcast title
    return (await get_triggers_for_stage(funnel_id, stage_key))[-1] if row else None


async def delete_trigger(trigger_id: int) -> bool:
    """Удалить триггер."""
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM funnel_stage_triggers WHERE id = $1",
            trigger_id,
        )
    return result == "DELETE 1"


async def toggle_trigger(trigger_id: int, is_active: bool) -> Optional[Dict[str, Any]]:
    """Включить/выключить триггер."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE funnel_stage_triggers SET is_active = $1
            WHERE id = $2
            RETURNING *
            """,
            is_active, trigger_id,
        )
    return _serialize_row(row) if row else None


async def get_active_triggers_for_stage(funnel_id: str, stage_key: str) -> List[Dict[str, Any]]:
    """Получить только активные триггеры для этапа (для отправки)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT fst.*, b.title AS broadcast_title
            FROM funnel_stage_triggers fst
            JOIN broadcasts b ON b.id = fst.broadcast_id
            WHERE fst.funnel_id = $1 AND fst.stage_key = $2 AND fst.is_active = true
            ORDER BY fst.created_at ASC
            """,
            funnel_id, stage_key,
        )
    return [_serialize_row(row) for row in rows]


async def has_trigger_been_sent(trigger_id: int, user_id: int) -> bool:
    """Проверить, был ли триггер уже отправлен этому пользователю."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT 1 FROM funnel_trigger_log
            WHERE trigger_id = $1 AND user_id = $2 AND status = 'sent'
            """,
            trigger_id, user_id,
        )
    return row is not None


async def log_trigger_sent(
    trigger_id: int,
    user_id: int,
    status: str = 'sent',
    error_message: Optional[str] = None,
) -> None:
    """Записать результат отправки триггера."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO funnel_trigger_log (trigger_id, user_id, status, error_message)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (trigger_id, user_id) DO UPDATE
            SET status = $3, error_message = $4, sent_at = NOW()
            """,
            trigger_id, user_id, status, error_message,
        )
