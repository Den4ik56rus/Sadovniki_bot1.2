# src/api/handlers/events.py
"""
API handlers для событий календаря.
"""

import logging
from datetime import datetime
from typing import Optional

from aiohttp import web

from src.services.db import calendar_events_repo

logger = logging.getLogger(__name__)


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Парсит ISO datetime строку."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


async def get_events(request: web.Request) -> web.Response:
    """
    GET /api/events
    Получить список событий пользователя.
    Query params: start, end (ISO datetime)
    """
    user_id = request.get("db_user_id")
    if not user_id:
        raise web.HTTPUnauthorized(text="Not authenticated")

    # Парсим query параметры
    start_str = request.query.get("start")
    end_str = request.query.get("end")

    start = parse_datetime(start_str)
    end = parse_datetime(end_str)

    try:
        events = await calendar_events_repo.get_events_by_user(user_id, start, end)
        return web.json_response(events)
    except Exception as e:
        logger.error(f"Error getting events: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_event(request: web.Request) -> web.Response:
    """
    GET /api/events/{id}
    Получить одно событие.
    """
    user_id = request.get("db_user_id")
    if not user_id:
        raise web.HTTPUnauthorized(text="Not authenticated")

    event_id = request.match_info.get("id")
    if not event_id:
        raise web.HTTPBadRequest(text="Missing event ID")

    try:
        event = await calendar_events_repo.get_event_by_id(event_id, user_id)
        if not event:
            raise web.HTTPNotFound(text="Event not found")
        return web.json_response(event)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting event: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def create_event(request: web.Request) -> web.Response:
    """
    POST /api/events
    Создать новое событие.
    """
    user_id = request.get("db_user_id")
    if not user_id:
        raise web.HTTPUnauthorized(text="Not authenticated")

    try:
        data = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text="Invalid JSON")

    # Валидация обязательных полей
    if not data.get("title"):
        raise web.HTTPBadRequest(text="Missing title")
    if not data.get("startDateTime"):
        raise web.HTTPBadRequest(text="Missing startDateTime")
    if not data.get("type"):
        raise web.HTTPBadRequest(text="Missing type")

    # Преобразуем datetime строки
    data["startDateTime"] = parse_datetime(data["startDateTime"])
    if not data["startDateTime"]:
        raise web.HTTPBadRequest(text="Invalid startDateTime format")

    if data.get("endDateTime"):
        data["endDateTime"] = parse_datetime(data["endDateTime"])

    try:
        event = await calendar_events_repo.create_event(user_id, data)
        return web.json_response(event, status=201)
    except Exception as e:
        logger.error(f"Error creating event: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def update_event(request: web.Request) -> web.Response:
    """
    PUT /api/events/{id}
    Обновить событие.
    """
    user_id = request.get("db_user_id")
    if not user_id:
        raise web.HTTPUnauthorized(text="Not authenticated")

    event_id = request.match_info.get("id")
    if not event_id:
        raise web.HTTPBadRequest(text="Missing event ID")

    try:
        data = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text="Invalid JSON")

    # Преобразуем datetime строки если они есть
    if data.get("startDateTime"):
        data["startDateTime"] = parse_datetime(data["startDateTime"])
    if data.get("endDateTime"):
        data["endDateTime"] = parse_datetime(data["endDateTime"])

    try:
        event = await calendar_events_repo.update_event(event_id, user_id, data)
        if not event:
            raise web.HTTPNotFound(text="Event not found")
        return web.json_response(event)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating event: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def delete_event(request: web.Request) -> web.Response:
    """
    DELETE /api/events/{id}
    Удалить событие.
    """
    user_id = request.get("db_user_id")
    if not user_id:
        raise web.HTTPUnauthorized(text="Not authenticated")

    event_id = request.match_info.get("id")
    if not event_id:
        raise web.HTTPBadRequest(text="Missing event ID")

    try:
        deleted = await calendar_events_repo.delete_event(event_id, user_id)
        if not deleted:
            raise web.HTTPNotFound(text="Event not found")
        return web.Response(status=204)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting event: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def update_event_status(request: web.Request) -> web.Response:
    """
    PATCH /api/events/{id}/status
    Изменить статус события.
    """
    user_id = request.get("db_user_id")
    if not user_id:
        raise web.HTTPUnauthorized(text="Not authenticated")

    event_id = request.match_info.get("id")
    if not event_id:
        raise web.HTTPBadRequest(text="Missing event ID")

    try:
        data = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text="Invalid JSON")

    status = data.get("status")
    if status not in ("planned", "done", "skipped"):
        raise web.HTTPBadRequest(text="Invalid status. Must be: planned, done, skipped")

    try:
        event = await calendar_events_repo.update_event_status(event_id, user_id, status)
        if not event:
            raise web.HTTPNotFound(text="Event not found")
        return web.json_response(event)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating event status: {e}")
        raise web.HTTPInternalServerError(text="Database error")
