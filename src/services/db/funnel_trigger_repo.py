# src/services/db/funnel_trigger_repo.py

"""
DEPRECATED: Используйте automation_trigger_repo.py вместо этого модуля.

Этот модуль (funnel_stage_triggers) заменён универсальной системой automation_triggers.
Оставлен для обратной совместимости — существующие триггеры продолжают работать.
Новые триггеры создавайте через automation_triggers API.

Старое описание:
Репозиторий для триггеров этапов воронки.
Триггер = привязка рассылки к этапу воронки.
"""

import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


def _serialize_row(row: dict) -> dict:
    """Convert datetime, Decimal and JSONB objects for JSON serialization."""
    result = dict(row)
    for key, value in result.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, Decimal):
            result[key] = float(value)
        elif isinstance(value, str) and key == 'payment_config':
            # asyncpg может вернуть JSONB как строку
            try:
                result[key] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                pass
    return result


async def get_triggers_for_stage(funnel_id: str, stage_key: str) -> List[Dict[str, Any]]:
    """Получить все триггеры для конкретного этапа."""
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
    return [_serialize_row(dict(row)) for row in rows]


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
    return [_serialize_row(dict(row)) for row in rows]


async def create_trigger(
    funnel_id: str,
    stage_key: str,
    broadcast_id: int,
    delay_minutes: int = 0,
    payment_config: Optional[Dict[str, Any]] = None,
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

        payment_config_json = json.dumps(payment_config) if payment_config else None

        row = await conn.fetchrow(
            """
            INSERT INTO funnel_stage_triggers (funnel_id, stage_key, broadcast_id, delay_minutes, payment_config)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            ON CONFLICT (funnel_id, stage_key, broadcast_id) DO NOTHING
            RETURNING *
            """,
            funnel_id, stage_key, broadcast_id, delay_minutes, payment_config_json,
        )

    if not row:
        return None

    # Получаем с join на broadcast title
    triggers = await get_triggers_for_stage(funnel_id, stage_key)
    return triggers[-1] if triggers else None


async def update_trigger(
    trigger_id: int,
    is_active: Optional[bool] = None,
    delay_minutes: Optional[int] = None,
    payment_config: Optional[Dict[str, Any]] = None,
    clear_payment_config: bool = False,
) -> Optional[Dict[str, Any]]:
    """Обновить параметры триггера (активность, задержка, платёжный конфиг)."""
    pool = get_pool()
    set_parts = []
    values: List[Any] = [trigger_id]
    idx = 2

    if is_active is not None:
        set_parts.append(f"is_active = ${idx}")
        values.append(is_active)
        idx += 1

    if delay_minutes is not None:
        set_parts.append(f"delay_minutes = ${idx}")
        values.append(delay_minutes)
        idx += 1

    if clear_payment_config:
        set_parts.append("payment_config = NULL")
    elif payment_config is not None:
        set_parts.append(f"payment_config = ${idx}::jsonb")
        values.append(json.dumps(payment_config))
        idx += 1

    if not set_parts:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM funnel_stage_triggers WHERE id = $1", trigger_id
            )
        return _serialize_row(dict(row)) if row else None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"UPDATE funnel_stage_triggers SET {', '.join(set_parts)} WHERE id = $1 RETURNING *",
            *values,
        )
    return _serialize_row(dict(row)) if row else None


# Оставляем старый toggle_trigger для обратной совместимости
async def toggle_trigger(trigger_id: int, is_active: bool) -> Optional[Dict[str, Any]]:
    """Включить/выключить триггер (deprecated — используй update_trigger)."""
    return await update_trigger(trigger_id, is_active=is_active)


async def delete_trigger(trigger_id: int) -> bool:
    """Удалить триггер."""
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM funnel_stage_triggers WHERE id = $1",
            trigger_id,
        )
    return result == "DELETE 1"


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
    return [_serialize_row(dict(row)) for row in rows]


async def has_trigger_been_sent(trigger_id: int, user_id: int) -> bool:
    """Проверить, был ли триггер уже отправлен или запланирован для этого пользователя."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT 1 FROM funnel_trigger_log
            WHERE trigger_id = $1 AND user_id = $2 AND status IN ('sent', 'pending')
            """,
            trigger_id, user_id,
        )
    return row is not None


async def log_trigger_sent(
    trigger_id: int,
    user_id: int,
    status: str = 'sent',
    error_message: Optional[str] = None,
    send_at_offset_minutes: int = 0,
) -> None:
    """Записать результат отправки триггера.

    Если send_at_offset_minutes > 0 — записываем как pending с будущим send_at.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        if send_at_offset_minutes > 0:
            await conn.execute(
                """
                INSERT INTO funnel_trigger_log (trigger_id, user_id, status, error_message, send_at)
                VALUES ($1, $2, $3, $4, NOW() + ($5 * INTERVAL '1 minute'))
                """,
                trigger_id, user_id, status, error_message, send_at_offset_minutes,
            )
        else:
            await conn.execute(
                """
                INSERT INTO funnel_trigger_log (trigger_id, user_id, status, error_message)
                VALUES ($1, $2, $3, $4)
                """,
                trigger_id, user_id, status, error_message,
            )


async def get_pending_triggers_due(limit: int = 100) -> List[Dict[str, Any]]:
    """Получить триггеры с status='pending' у которых send_at <= NOW() (пора отправлять)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                ftl.id AS log_id,
                ftl.trigger_id,
                ftl.user_id,
                fst.broadcast_id,
                fst.payment_config,
                fst.funnel_id,
                fst.stage_key,
                u.telegram_user_id
            FROM funnel_trigger_log ftl
            JOIN funnel_stage_triggers fst ON fst.id = ftl.trigger_id
            JOIN users u ON u.id = ftl.user_id
            WHERE ftl.status = 'pending' AND ftl.send_at <= NOW()
            ORDER BY ftl.send_at ASC
            LIMIT $1
            """,
            limit,
        )
    return [_serialize_row(dict(row)) for row in rows]


async def update_trigger_log_status(
    log_id: int,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    """Обновить статус записи в funnel_trigger_log."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE funnel_trigger_log
            SET status = $1, error_message = $2
            WHERE id = $3
            """,
            status, error_message, log_id,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ОТМЕНА PENDING-ТРИГГЕРОВ ПРИ СМЕНЕ ЭТАПА
# ═══════════════════════════════════════════════════════════════════════════════

async def delete_pending_triggers_for_stage(
    user_id: int,
    funnel_id: str,
    stage_key: str,
) -> int:
    """
    Удалить все pending-триггеры пользователя для конкретного этапа воронки.

    Вызывается при перемещении клиента с этапа (перед обновлением позиции).
    Удаление (а не cancel) гарантирует, что при возврате на этап таймер начнёт заново.
    Возвращает количество удалённых триггеров.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM funnel_trigger_log ftl
            USING funnel_stage_triggers fst
            WHERE ftl.trigger_id = fst.id
              AND ftl.user_id = $1
              AND fst.funnel_id = $2
              AND fst.stage_key = $3
            """,
            user_id, funnel_id, stage_key,
        )
        count = int(result.split()[-1]) if result else 0
        if count > 0:
            logger.info(
                f"Deleted {count} trigger log entries for user {user_id} "
                f"leaving stage {funnel_id}/{stage_key}"
            )
        return count


async def delete_all_pending_triggers_for_funnel(
    user_id: int,
    funnel_id: str,
) -> int:
    """
    Удалить ВСЕ записи триггеров пользователя во всей воронке.

    Вызывается при удалении клиента из воронки (transfer_client, remove_client_from_funnel).
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM funnel_trigger_log ftl
            USING funnel_stage_triggers fst
            WHERE ftl.trigger_id = fst.id
              AND ftl.user_id = $1
              AND fst.funnel_id = $2
            """,
            user_id, funnel_id,
        )
        count = int(result.split()[-1]) if result else 0
        if count > 0:
            logger.info(
                f"Deleted {count} trigger log entries for user {user_id} "
                f"leaving funnel {funnel_id}"
            )
        return count


async def delete_pending_triggers_for_deleted_stage(
    funnel_id: str,
    stage_key: str,
    conn=None,
) -> int:
    """
    Удалить все записи триггеров для удаляемого этапа (для всех пользователей).

    Принимает опциональный conn для использования внутри транзакции.
    """
    release = False
    if conn is None:
        pool = get_pool()
        conn = await pool.acquire()
        release = True

    try:
        result = await conn.execute(
            """
            DELETE FROM funnel_trigger_log ftl
            USING funnel_stage_triggers fst
            WHERE ftl.trigger_id = fst.id
              AND fst.funnel_id = $1
              AND fst.stage_key = $2
            """,
            funnel_id, stage_key,
        )
        count = int(result.split()[-1]) if result else 0
        if count > 0:
            logger.info(
                f"Deleted {count} trigger log entries for deleted stage {funnel_id}/{stage_key}"
            )
        return count
    finally:
        if release:
            await pool.release(conn)


async def delete_trigger_log_entry(log_id: int) -> None:
    """Удалить запись из funnel_trigger_log по ID."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM funnel_trigger_log WHERE id = $1",
            log_id,
        )


async def is_user_on_stage(user_id: int, funnel_id: str, stage_key: str) -> bool:
    """Проверить, находится ли пользователь на указанном этапе воронки."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT 1 FROM client_funnel_position
            WHERE user_id = $1 AND funnel_id = $2 AND stage_key = $3
            """,
            user_id, funnel_id, stage_key,
        )
    return row is not None
