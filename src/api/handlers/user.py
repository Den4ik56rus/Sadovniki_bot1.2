# src/api/handlers/user.py
"""
API handlers для пользовательских настроек.
"""

import logging

from aiohttp import web

from src.services.db import user_plantings_repo

logger = logging.getLogger(__name__)

VALID_REGIONS = {"south", "central", "north"}


async def get_region(request: web.Request) -> web.Response:
    """
    GET /api/user/region
    Получить регион пользователя.
    """
    user_id = request.get("db_user_id")
    if not user_id:
        raise web.HTTPUnauthorized(text="Not authenticated")

    try:
        region = await user_plantings_repo.get_user_region(user_id)
        return web.json_response({"region": region})
    except Exception as e:
        logger.error(f"Error getting user region: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def update_region(request: web.Request) -> web.Response:
    """
    PUT /api/user/region
    Установить регион пользователя.
    """
    user_id = request.get("db_user_id")
    if not user_id:
        raise web.HTTPUnauthorized(text="Not authenticated")

    try:
        data = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text="Invalid JSON")

    region = data.get("region")
    if region not in VALID_REGIONS:
        raise web.HTTPBadRequest(text=f"Invalid region. Must be one of: {', '.join(VALID_REGIONS)}")

    try:
        updated_region = await user_plantings_repo.update_user_region(user_id, region)
        return web.json_response({"region": updated_region})
    except Exception as e:
        logger.error(f"Error updating user region: {e}")
        raise web.HTTPInternalServerError(text="Database error")
