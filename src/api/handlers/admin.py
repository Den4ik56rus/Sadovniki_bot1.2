# src/api/handlers/admin.py
"""
API handlers для админ-панели мониторинга консультаций.
"""

import logging
from aiohttp import web

from src.services.db import consultation_logs_repo

logger = logging.getLogger(__name__)


async def get_users_list(request: web.Request) -> web.Response:
    """
    GET /api/admin/users
    Получить список пользователей со статистикой консультаций.

    Query params:
        limit: int (default 50)
        offset: int (default 0)
        search: str (поиск по username/first_name)
    """
    try:
        limit = int(request.query.get("limit", 50))
        offset = int(request.query.get("offset", 0))
        search = request.query.get("search", "")

        result = await consultation_logs_repo.get_users_with_stats(
            limit=limit,
            offset=offset,
            search=search,
        )

        return web.json_response(result)

    except Exception as e:
        logger.error(f"Error getting users list: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_user_topics(request: web.Request) -> web.Response:
    """
    GET /api/admin/users/{id}/topics
    Получить топики пользователя.

    Path params:
        id: int (user_id)

    Query params:
        limit: int (default 50)
        offset: int (default 0)
    """
    try:
        user_id = int(request.match_info["id"])
        limit = int(request.query.get("limit", 50))
        offset = int(request.query.get("offset", 0))

        topics = await consultation_logs_repo.get_topics_by_user(
            user_id=user_id,
            limit=limit,
            offset=offset,
        )

        return web.json_response(topics)

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid user ID")
    except Exception as e:
        logger.error(f"Error getting user topics: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_topic_logs(request: web.Request) -> web.Response:
    """
    GET /api/admin/topics/{id}/logs
    Получить полный лог консультации по топику.

    Path params:
        id: int (topic_id)
    """
    try:
        topic_id = int(request.match_info["id"])

        result = await consultation_logs_repo.get_logs_by_topic(topic_id)

        return web.json_response(result)

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid topic ID")
    except Exception as e:
        logger.error(f"Error getting topic logs: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_recent_logs(request: web.Request) -> web.Response:
    """
    GET /api/admin/logs/recent
    Получить последние логи консультаций (для live feed).

    Query params:
        limit: int (default 50)
        since_id: int (вернуть только записи с id > since_id)
    """
    try:
        limit = int(request.query.get("limit", 50))
        since_id_str = request.query.get("since_id")
        since_id = int(since_id_str) if since_id_str else None

        logs = await consultation_logs_repo.get_recent_logs(
            limit=limit,
            since_id=since_id,
        )

        return web.json_response(logs)

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid parameter")
    except Exception as e:
        logger.error(f"Error getting recent logs: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_stats(request: web.Request) -> web.Response:
    """
    GET /api/admin/stats
    Получить общую статистику по консультациям.

    Query params:
        period: str ('day' | 'week' | 'month' | 'all', default 'all')
    """
    try:
        period = request.query.get("period", "all")

        if period not in ("day", "week", "month", "all"):
            raise web.HTTPBadRequest(text="Invalid period. Use: day, week, month, all")

        stats = await consultation_logs_repo.get_stats_summary(period=period)

        return web.json_response(stats)

    except web.HTTPBadRequest:
        raise
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_embedding_stats(request: web.Request) -> web.Response:
    """
    GET /api/admin/stats/embeddings
    Получить статистику по embeddings (документы + консультации).

    Query params:
        period: str ('day' | 'week' | 'month' | 'all', default 'all')
    """
    try:
        period = request.query.get("period", "all")

        if period not in ("day", "week", "month", "all"):
            raise web.HTTPBadRequest(text="Invalid period. Use: day, week, month, all")

        stats = await consultation_logs_repo.get_embedding_stats(period=period)

        return web.json_response(stats)

    except web.HTTPBadRequest:
        raise
    except Exception as e:
        logger.error(f"Error getting embedding stats: {e}")
        raise web.HTTPInternalServerError(text="Database error")
