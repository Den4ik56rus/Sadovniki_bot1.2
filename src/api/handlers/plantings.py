# src/api/handlers/plantings.py
"""
API handlers для посадок пользователя.
"""

import logging
from datetime import date

from aiohttp import web

from src.services.db import user_plantings_repo

logger = logging.getLogger(__name__)

# Допустимые значения
VALID_CULTURE_TYPES = {
    "strawberry", "raspberry", "blackberry",
    "currant", "blueberry", "honeysuckle", "gooseberry"
}

VALID_VARIETIES = {
    "strawberry": {"early", "mid", "late", "remontant"},
    "raspberry": {"summer", "remontant"},
    "blackberry": {"summer", "remontant"},
}


def parse_date(value: str | None) -> date | None:
    """Парсит дату в формате YYYY-MM-DD."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def validate_variety(culture_type: str, variety: str | None) -> bool:
    """Проверяет допустимость сорта для культуры."""
    if culture_type in VALID_VARIETIES:
        # Культуры с сортами должны иметь сорт
        return variety in VALID_VARIETIES[culture_type]
    else:
        # Культуры без сортов не должны иметь сорт
        return variety is None


async def get_plantings(request: web.Request) -> web.Response:
    """
    GET /api/plantings
    Получить список посадок пользователя.
    """
    user_id = request.get("db_user_id")
    if not user_id:
        raise web.HTTPUnauthorized(text="Not authenticated")

    try:
        plantings = await user_plantings_repo.get_plantings_by_user(user_id)
        return web.json_response(plantings)
    except Exception as e:
        logger.error(f"Error getting plantings: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_planting(request: web.Request) -> web.Response:
    """
    GET /api/plantings/{id}
    Получить одну посадку.
    """
    user_id = request.get("db_user_id")
    if not user_id:
        raise web.HTTPUnauthorized(text="Not authenticated")

    planting_id = request.match_info.get("id")
    if not planting_id:
        raise web.HTTPBadRequest(text="Missing planting ID")

    try:
        planting = await user_plantings_repo.get_planting_by_id(planting_id, user_id)
        if not planting:
            raise web.HTTPNotFound(text="Planting not found")
        return web.json_response(planting)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting planting: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def create_planting(request: web.Request) -> web.Response:
    """
    POST /api/plantings
    Создать новую посадку.
    """
    user_id = request.get("db_user_id")
    if not user_id:
        raise web.HTTPUnauthorized(text="Not authenticated")

    try:
        data = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text="Invalid JSON")

    # Валидация обязательных полей
    culture_type = data.get("cultureType")
    if not culture_type:
        raise web.HTTPBadRequest(text="Missing cultureType")
    if culture_type not in VALID_CULTURE_TYPES:
        raise web.HTTPBadRequest(text=f"Invalid cultureType. Must be one of: {', '.join(VALID_CULTURE_TYPES)}")

    # Валидация сорта
    variety = data.get("variety")
    if not validate_variety(culture_type, variety):
        if culture_type in VALID_VARIETIES:
            raise web.HTTPBadRequest(
                text=f"Invalid variety for {culture_type}. Must be one of: {', '.join(VALID_VARIETIES[culture_type])}"
            )
        else:
            raise web.HTTPBadRequest(text=f"Culture {culture_type} should not have variety")

    # Парсим даты
    data["fruitingStart"] = parse_date(data.get("fruitingStart"))
    data["fruitingEnd"] = parse_date(data.get("fruitingEnd"))

    try:
        planting = await user_plantings_repo.create_planting(user_id, data)
        return web.json_response(planting, status=201)
    except Exception as e:
        logger.error(f"Error creating planting: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def update_planting(request: web.Request) -> web.Response:
    """
    PUT /api/plantings/{id}
    Обновить посадку.
    """
    user_id = request.get("db_user_id")
    if not user_id:
        raise web.HTTPUnauthorized(text="Not authenticated")

    planting_id = request.match_info.get("id")
    if not planting_id:
        raise web.HTTPBadRequest(text="Missing planting ID")

    try:
        data = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text="Invalid JSON")

    # Валидация типа культуры если передан
    culture_type = data.get("cultureType")
    if culture_type and culture_type not in VALID_CULTURE_TYPES:
        raise web.HTTPBadRequest(text=f"Invalid cultureType. Must be one of: {', '.join(VALID_CULTURE_TYPES)}")

    # Валидация сорта если передан
    variety = data.get("variety")
    if culture_type and not validate_variety(culture_type, variety):
        if culture_type in VALID_VARIETIES:
            raise web.HTTPBadRequest(
                text=f"Invalid variety for {culture_type}. Must be one of: {', '.join(VALID_VARIETIES[culture_type])}"
            )
        else:
            raise web.HTTPBadRequest(text=f"Culture {culture_type} should not have variety")

    # Парсим даты если переданы
    if "fruitingStart" in data:
        data["fruitingStart"] = parse_date(data.get("fruitingStart"))
    if "fruitingEnd" in data:
        data["fruitingEnd"] = parse_date(data.get("fruitingEnd"))

    try:
        planting = await user_plantings_repo.update_planting(planting_id, user_id, data)
        if not planting:
            raise web.HTTPNotFound(text="Planting not found")
        return web.json_response(planting)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating planting: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def delete_planting(request: web.Request) -> web.Response:
    """
    DELETE /api/plantings/{id}
    Удалить посадку.
    """
    user_id = request.get("db_user_id")
    if not user_id:
        raise web.HTTPUnauthorized(text="Not authenticated")

    planting_id = request.match_info.get("id")
    if not planting_id:
        raise web.HTTPBadRequest(text="Missing planting ID")

    try:
        deleted = await user_plantings_repo.delete_planting(planting_id, user_id)
        if not deleted:
            raise web.HTTPNotFound(text="Planting not found")
        return web.Response(status=204)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting planting: {e}")
        raise web.HTTPInternalServerError(text="Database error")
