# src/services/db/automation_trigger_repo.py

"""
Репозиторий для универсальных автоматических триггеров.

4 типа событий: stage_transition, payment_success, tag_changed, subscription_expiring
AND/OR условия, множественные действия, отложенная отправка.
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
        elif isinstance(value, str) and key in ('event_config', 'conditions', 'actions', 'actions_result', 'event_snapshot'):
            try:
                result[key] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                pass
    return result


# ═══════════════════════════════════════════════════════════════════
# CRUD — ТРИГГЕРЫ
# ═══════════════════════════════════════════════════════════════════

async def get_all_triggers(
    event_type: Optional[str] = None,
    funnel_id: Optional[str] = None,
    stage_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Получить все триггеры с опциональными фильтрами."""
    pool = get_pool()
    conditions = []
    values: List[Any] = []
    idx = 1

    if event_type:
        conditions.append(f"event_type = ${idx}")
        values.append(event_type)
        idx += 1

    if funnel_id:
        conditions.append(f"event_config->>'funnel_id' = ${idx}")
        values.append(funnel_id)
        idx += 1

    if stage_key:
        conditions.append(f"event_config->>'stage_key' = ${idx}")
        values.append(stage_key)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT * FROM automation_triggers
            {where}
            ORDER BY created_at DESC
            """,
            *values,
        )
    return [_serialize_row(dict(row)) for row in rows]


async def get_trigger_by_id(trigger_id: int) -> Optional[Dict[str, Any]]:
    """Получить триггер по ID."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM automation_triggers WHERE id = $1",
            trigger_id,
        )
    return _serialize_row(dict(row)) if row else None


async def create_trigger(
    name: str,
    event_type: str,
    event_config: Dict[str, Any],
    actions: List[Dict[str, Any]],
    conditions: Optional[Dict[str, Any]] = None,
    delay_minutes: int = 0,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Создать новый триггер."""
    # Guard against double-encoding: ensure event_config is always a dict
    if isinstance(event_config, str):
        event_config = json.loads(event_config)
    if isinstance(conditions, str):
        conditions = json.loads(conditions)
    if isinstance(actions, str):
        actions = json.loads(actions)

    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO automation_triggers
                (name, description, event_type, event_config, conditions, actions, delay_minutes)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
            """,
            name,
            description,
            event_type,
            json.dumps(event_config),
            json.dumps(conditions) if conditions else None,
            json.dumps(actions),
            delay_minutes,
        )
    return _serialize_row(dict(row))


async def update_trigger(
    trigger_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
    event_type: Optional[str] = None,
    event_config: Optional[Dict[str, Any]] = None,
    conditions: Optional[Dict[str, Any]] = None,
    clear_conditions: bool = False,
    actions: Optional[List[Dict[str, Any]]] = None,
    delay_minutes: Optional[int] = None,
    is_active: Optional[bool] = None,
) -> Optional[Dict[str, Any]]:
    """Обновить параметры триггера."""
    pool = get_pool()
    set_parts = ["updated_at = NOW()"]
    values: List[Any] = [trigger_id]
    idx = 2

    if name is not None:
        set_parts.append(f"name = ${idx}")
        values.append(name)
        idx += 1

    if description is not None:
        set_parts.append(f"description = ${idx}")
        values.append(description)
        idx += 1

    if event_type is not None:
        set_parts.append(f"event_type = ${idx}")
        values.append(event_type)
        idx += 1

    if event_config is not None:
        if isinstance(event_config, str):
            event_config = json.loads(event_config)
        set_parts.append(f"event_config = ${idx}")
        values.append(json.dumps(event_config))
        idx += 1

    if clear_conditions:
        set_parts.append("conditions = NULL")
    elif conditions is not None:
        if isinstance(conditions, str):
            conditions = json.loads(conditions)
        set_parts.append(f"conditions = ${idx}")
        values.append(json.dumps(conditions))
        idx += 1

    if actions is not None:
        if isinstance(actions, str):
            actions = json.loads(actions)
        set_parts.append(f"actions = ${idx}")
        values.append(json.dumps(actions))
        idx += 1

    if delay_minutes is not None:
        set_parts.append(f"delay_minutes = ${idx}")
        values.append(delay_minutes)
        idx += 1

    if is_active is not None:
        set_parts.append(f"is_active = ${idx}")
        values.append(is_active)
        idx += 1

    sql = f"UPDATE automation_triggers SET {', '.join(set_parts)} WHERE id = $1 RETURNING *"
    print(f"[DEBUG update_trigger] sql={sql}", flush=True)
    print(f"[DEBUG update_trigger] values types={[type(v).__name__ for v in values]}", flush=True)
    print(f"[DEBUG update_trigger] values={values!r}", flush=True)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, *values)
        if row:
            async with pool.acquire() as conn2:
                chk = await conn2.fetchrow("SELECT jsonb_typeof(event_config) as t FROM automation_triggers WHERE id=$1", trigger_id)
                print(f"[DEBUG update_trigger] DB jsonb_typeof after update: {chk['t']}", flush=True)
    return _serialize_row(dict(row)) if row else None


async def delete_trigger(trigger_id: int) -> bool:
    """Удалить триггер (CASCADE удалит лог)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM automation_triggers WHERE id = $1",
            trigger_id,
        )
    return result == "DELETE 1"


async def toggle_trigger(trigger_id: int, is_active: bool) -> Optional[Dict[str, Any]]:
    """Включить/выключить триггер."""
    return await update_trigger(trigger_id, is_active=is_active)


# ═══════════════════════════════════════════════════════════════════
# ПОЛУЧЕНИЕ АКТИВНЫХ ТРИГГЕРОВ ДЛЯ ДВИЖКА
# ═══════════════════════════════════════════════════════════════════

async def get_active_triggers_by_event(event_type: str) -> List[Dict[str, Any]]:
    """Получить все активные триггеры для указанного типа события."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM automation_triggers
            WHERE event_type = $1 AND is_active = true
            ORDER BY created_at ASC
            """,
            event_type,
        )
    return [_serialize_row(dict(row)) for row in rows]


# ═══════════════════════════════════════════════════════════════════
# ЛОГ ВЫПОЛНЕНИЯ
# ═══════════════════════════════════════════════════════════════════

async def log_trigger_execution(
    trigger_id: int,
    user_id: int,
    status: str = 'pending',
    send_at_offset_minutes: int = 0,
    event_snapshot: Optional[Dict[str, Any]] = None,
    actions_result: Optional[List[Dict[str, Any]]] = None,
    error_message: Optional[str] = None,
) -> int:
    """Записать результат выполнения триггера. Возвращает log_id."""
    pool = get_pool()
    async with pool.acquire() as conn:
        if send_at_offset_minutes > 0:
            row = await conn.fetchrow(
                """
                INSERT INTO automation_trigger_log
                    (trigger_id, user_id, status, send_at, event_snapshot, actions_result, error_message)
                VALUES ($1, $2, $3, NOW() + ($4 * INTERVAL '1 minute'), $5, $6, $7)
                RETURNING id
                """,
                trigger_id, user_id, status, send_at_offset_minutes,
                json.dumps(event_snapshot) if event_snapshot else None,
                json.dumps(actions_result) if actions_result else None,
                error_message,
            )
        else:
            executed_at = "NOW()" if status in ('sent', 'failed', 'skipped') else "NULL"
            row = await conn.fetchrow(
                f"""
                INSERT INTO automation_trigger_log
                    (trigger_id, user_id, status, event_snapshot, actions_result, error_message, executed_at)
                VALUES ($1, $2, $3, $4, $5, $6, {executed_at})
                RETURNING id
                """,
                trigger_id, user_id, status,
                json.dumps(event_snapshot) if event_snapshot else None,
                json.dumps(actions_result) if actions_result else None,
                error_message,
            )
    return row['id']


async def get_pending_triggers_due(limit: int = 100) -> List[Dict[str, Any]]:
    """Получить pending-триггеры у которых пришло время выполнения."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                atl.id AS log_id,
                atl.trigger_id,
                atl.user_id,
                atl.event_snapshot,
                at.event_type,
                at.event_config,
                at.conditions,
                at.actions,
                at.is_active,
                u.telegram_user_id
            FROM automation_trigger_log atl
            JOIN automation_triggers at ON at.id = atl.trigger_id
            JOIN users u ON u.id = atl.user_id
            WHERE atl.status = 'pending' AND atl.send_at <= NOW()
            ORDER BY atl.send_at ASC
            LIMIT $1
            """,
            limit,
        )
    return [_serialize_row(dict(row)) for row in rows]


async def update_trigger_log_status(
    log_id: int,
    status: str,
    actions_result: Optional[List[Dict[str, Any]]] = None,
    error_message: Optional[str] = None,
) -> None:
    """Обновить статус записи в automation_trigger_log."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE automation_trigger_log
            SET status = $1, actions_result = $2, error_message = $3,
                executed_at = CASE WHEN $1 IN ('sent', 'failed', 'skipped') THEN NOW() ELSE executed_at END
            WHERE id = $4
            """,
            status,
            json.dumps(actions_result) if actions_result else None,
            error_message,
            log_id,
        )


async def delete_trigger_log_entry(log_id: int) -> None:
    """Удалить запись из automation_trigger_log по ID."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM automation_trigger_log WHERE id = $1",
            log_id,
        )


async def get_trigger_log(
    trigger_id: int,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Получить лог выполнения триггера."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT atl.*, u.telegram_user_id, u.first_name, u.last_name, u.username
            FROM automation_trigger_log atl
            JOIN users u ON u.id = atl.user_id
            WHERE atl.trigger_id = $1
            ORDER BY atl.created_at DESC
            LIMIT $2 OFFSET $3
            """,
            trigger_id, limit, offset,
        )
    return [_serialize_row(dict(row)) for row in rows]


async def has_been_triggered(
    trigger_id: int,
    user_id: int,
    event_snapshot: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Проверить, срабатывал ли триггер для пользователя.

    Для subscription_expiring: проверяем по subscription_id в event_snapshot.
    Для остальных: проверяем по trigger_id + user_id + status IN (sent, pending).
    skipped не блокирует повтор — условия могли измениться.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        if event_snapshot and 'subscription_id' in event_snapshot:
            row = await conn.fetchrow(
                """
                SELECT 1 FROM automation_trigger_log
                WHERE trigger_id = $1 AND user_id = $2
                  AND event_snapshot->>'subscription_id' = $3
                """,
                trigger_id, user_id, str(event_snapshot['subscription_id']),
            )
        else:
            row = await conn.fetchrow(
                """
                SELECT 1 FROM automation_trigger_log
                WHERE trigger_id = $1 AND user_id = $2
                  AND status IN ('sent', 'pending')
                """,
                trigger_id, user_id,
            )
    return row is not None


# ═══════════════════════════════════════════════════════════════════
# ОТМЕНА PENDING-ТРИГГЕРОВ
# ═══════════════════════════════════════════════════════════════════

async def delete_pending_for_stage(
    user_id: int,
    funnel_id: str,
    stage_key: str,
) -> int:
    """Удалить все pending-триггеры пользователя для этапа воронки (stage_transition)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM automation_trigger_log atl
            USING automation_triggers at
            WHERE atl.trigger_id = at.id
              AND atl.user_id = $1
              AND atl.status = 'pending'
              AND at.event_type = 'stage_transition'
              AND at.event_config->>'funnel_id' = $2
              AND at.event_config->>'stage_key' = $3
            """,
            user_id, funnel_id, stage_key,
        )
        count = int(result.split()[-1]) if result else 0
        if count > 0:
            logger.info(
                f"Deleted {count} pending automation triggers for user {user_id} "
                f"leaving stage {funnel_id}/{stage_key}"
            )
        return count


async def delete_pending_for_funnel(
    user_id: int,
    funnel_id: str,
) -> int:
    """Удалить ВСЕ pending-триггеры пользователя для воронки."""
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM automation_trigger_log atl
            USING automation_triggers at
            WHERE atl.trigger_id = at.id
              AND atl.user_id = $1
              AND atl.status = 'pending'
              AND at.event_type = 'stage_transition'
              AND at.event_config->>'funnel_id' = $2
            """,
            user_id, funnel_id,
        )
        count = int(result.split()[-1]) if result else 0
        if count > 0:
            logger.info(
                f"Deleted {count} pending automation triggers for user {user_id} "
                f"leaving funnel {funnel_id}"
            )
        return count
