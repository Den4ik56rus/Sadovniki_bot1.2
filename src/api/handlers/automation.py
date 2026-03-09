# src/api/handlers/automation.py

"""
API handlers для универсальных автоматических триггеров.
"""

import logging
from aiohttp import web

from src.services.db import automation_trigger_repo

logger = logging.getLogger(__name__)


async def get_triggers(request: web.Request) -> web.Response:
    """
    GET /api/admin/triggers
    Список триггеров с опциональными фильтрами.

    Query params:
        event_type: stage_transition|payment_success|tag_changed|subscription_expiring
        funnel_id: str (для stage_transition)
        stage_key: str (для stage_transition)
    """
    try:
        event_type = request.rel_url.query.get('event_type')
        funnel_id = request.rel_url.query.get('funnel_id')
        stage_key = request.rel_url.query.get('stage_key')

        triggers = await automation_trigger_repo.get_all_triggers(
            event_type=event_type,
            funnel_id=funnel_id,
            stage_key=stage_key,
        )
        return web.json_response({"triggers": triggers})
    except Exception as e:
        logger.error(f"Error getting automation triggers: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def create_trigger(request: web.Request) -> web.Response:
    """
    POST /api/admin/triggers
    Создать триггер.

    Body: {
        "name": "Отправка после оплаты",
        "description": "...",
        "event_type": "payment_success",
        "event_config": {"payment_type": "subscription"},
        "conditions": {...} | null,
        "actions": [{"type": "send_broadcast", "broadcast_id": 42}],
        "delay_minutes": 0
    }
    """
    try:
        data = await request.json()

        name = data.get('name')
        if not name:
            return web.json_response({"error": "name is required"}, status=400)

        event_type = data.get('event_type')
        if not event_type:
            return web.json_response({"error": "event_type is required"}, status=400)

        valid_types = ('stage_transition', 'payment_success', 'tag_changed', 'subscription_expiring')
        if event_type not in valid_types:
            return web.json_response({"error": f"event_type must be one of: {', '.join(valid_types)}"}, status=400)

        event_config = data.get('event_config') or {}
        actions = data.get('actions') or []
        if not actions:
            return web.json_response({"error": "actions must be a non-empty array"}, status=400)

        trigger = await automation_trigger_repo.create_trigger(
            name=name,
            event_type=event_type,
            event_config=event_config,
            actions=actions,
            conditions=data.get('conditions'),
            delay_minutes=int(data.get('delay_minutes', 0) or 0),
            description=data.get('description'),
        )
        return web.json_response({"trigger": trigger}, status=201)
    except Exception as e:
        logger.error(f"Error creating automation trigger: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def get_trigger(request: web.Request) -> web.Response:
    """
    GET /api/admin/triggers/{id}
    Получить триггер по ID.
    """
    try:
        trigger_id = int(request.match_info.get("id"))
        trigger = await automation_trigger_repo.get_trigger_by_id(trigger_id)
        if not trigger:
            return web.json_response({"error": "Trigger not found"}, status=404)
        return web.json_response({"trigger": trigger})
    except Exception as e:
        logger.error(f"Error getting automation trigger: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def update_trigger(request: web.Request) -> web.Response:
    """
    PUT /api/admin/triggers/{id}
    Обновить триггер.
    """
    try:
        trigger_id = int(request.match_info.get("id"))
        data = await request.json()

        clear_conditions = False
        conditions = data.get('conditions')
        if 'conditions' in data and conditions is None:
            clear_conditions = True

        trigger = await automation_trigger_repo.update_trigger(
            trigger_id,
            name=data.get('name'),
            description=data.get('description'),
            event_type=data.get('event_type'),
            event_config=data.get('event_config'),
            conditions=conditions,
            clear_conditions=clear_conditions,
            actions=data.get('actions'),
            delay_minutes=int(data['delay_minutes']) if 'delay_minutes' in data else None,
            is_active=data.get('is_active'),
        )
        if not trigger:
            return web.json_response({"error": "Trigger not found"}, status=404)
        return web.json_response({"trigger": trigger})
    except Exception as e:
        logger.error(f"Error updating automation trigger: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def delete_trigger(request: web.Request) -> web.Response:
    """
    DELETE /api/admin/triggers/{id}
    Удалить триггер (CASCADE удалит лог).
    """
    try:
        trigger_id = int(request.match_info.get("id"))
        deleted = await automation_trigger_repo.delete_trigger(trigger_id)
        if not deleted:
            return web.json_response({"error": "Trigger not found"}, status=404)
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error deleting automation trigger: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def toggle_trigger(request: web.Request) -> web.Response:
    """
    PATCH /api/admin/triggers/{id}/toggle
    Включить/выключить триггер.

    Body: { "is_active": true/false }
    """
    try:
        trigger_id = int(request.match_info.get("id"))
        data = await request.json()
        is_active = data.get('is_active')

        if is_active is None:
            return web.json_response({"error": "is_active is required"}, status=400)

        trigger = await automation_trigger_repo.toggle_trigger(trigger_id, bool(is_active))
        if not trigger:
            return web.json_response({"error": "Trigger not found"}, status=404)
        return web.json_response({"trigger": trigger})
    except Exception as e:
        logger.error(f"Error toggling automation trigger: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def get_trigger_log(request: web.Request) -> web.Response:
    """
    GET /api/admin/triggers/{id}/log
    Лог выполнений триггера.

    Query params:
        limit: int (default 50)
        offset: int (default 0)
    """
    try:
        trigger_id = int(request.match_info.get("id"))
        limit = int(request.rel_url.query.get('limit', 50))
        offset = int(request.rel_url.query.get('offset', 0))

        log_entries = await automation_trigger_repo.get_trigger_log(trigger_id, limit, offset)
        return web.json_response({"log": log_entries, "limit": limit, "offset": offset})
    except Exception as e:
        logger.error(f"Error getting trigger log: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def preview_users(request: web.Request) -> web.Response:
    """
    POST /api/admin/triggers/preview-users
    Превью количества пользователей, подходящих под условия.

    Body: { "conditions": {...} }
    """
    try:
        data = await request.json()
        conditions = data.get('conditions')

        if not conditions:
            # Без условий — все пользователи
            from src.services.db.pool import get_pool
            pool = get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow("SELECT COUNT(*) as cnt FROM users WHERE is_blocked = false")
            return web.json_response({"count": row['cnt']})

        # Проверяем каждого пользователя
        from src.services.db.pool import get_pool
        from src.services.automation.conditions import evaluate_conditions
        pool = get_pool()
        async with pool.acquire() as conn:
            users = await conn.fetch("SELECT id FROM users WHERE is_blocked = false")

        count = 0
        for user in users:
            matched = await evaluate_conditions(conditions, user['id'])
            if matched:
                count += 1

        return web.json_response({"count": count})
    except Exception as e:
        logger.error(f"Error previewing users: {e}")
        return web.json_response({"error": str(e)}, status=500)
