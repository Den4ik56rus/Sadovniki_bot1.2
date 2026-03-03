# src/api/handlers/batch_presentations.py

"""
API handlers для пакетной генерации презентаций.

Endpoints:
    POST   /api/admin/presentations/batches             — создать пакет + запустить
    GET    /api/admin/presentations/batches              — список пакетов
    GET    /api/admin/presentations/batches/{id}         — детали пакета + items
    POST   /api/admin/presentations/batches/{id}/cancel  — отменить пакет
    DELETE /api/admin/presentations/batches/{id}         — удалить пакет
"""

import asyncio
import logging
from decimal import Decimal

from aiohttp import web

from src.services.db import batch_repo
from src.services.presentations.batch_processor import run_batch
from src.api.sse_manager import sse_manager

logger = logging.getLogger(__name__)


def _serialize(obj: dict) -> dict:
    """Конвертирует Decimal/datetime в JSON-совместимые типы."""
    result = {}
    for k, v in obj.items():
        if isinstance(v, Decimal):
            result[k] = float(v)
        elif hasattr(v, 'isoformat'):
            result[k] = v.isoformat()
        elif isinstance(v, list):
            result[k] = [_serialize(i) if isinstance(i, dict) else i for i in v]
        elif isinstance(v, dict):
            result[k] = _serialize(v)
        else:
            result[k] = v
    return result


async def create_batch_api(request: web.Request) -> web.Response:
    """Создать пакет и запустить генерацию."""
    try:
        data = await request.json()

        items = data.get("items", [])
        if not items:
            return web.json_response({"error": "items is required (non-empty array)"}, status=400)

        # Валидация элементов
        for item in items:
            if not item.get("culture_key") or not item.get("problem_key"):
                return web.json_response(
                    {"error": "Each item must have culture_key and problem_key"},
                    status=400,
                )

        # Создаём пакет
        batch_id = await batch_repo.create_batch(
            style_id=data.get("style_id"),
            template_id=data.get("template_id"),
            llm_model=data.get("llm_model"),
            reasoning_effort=data.get("reasoning_effort"),
            image_model=data.get("image_model"),
            custom_system_prompt=data.get("custom_system_prompt"),
            total_items=len(items),
        )

        # Добавляем элементы
        await batch_repo.add_batch_items(batch_id, items)

        # Запускаем генерацию в фоне
        from src.bot import get_bot
        bot = get_bot()
        asyncio.create_task(run_batch(batch_id, bot))

        batch = await batch_repo.get_batch(batch_id)
        return web.json_response({
            "id": batch_id,
            "batch": _serialize(batch) if batch else None,
        })

    except Exception as e:
        logger.error(f"Error creating batch: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def get_batches(request: web.Request) -> web.Response:
    """Список всех пакетов."""
    try:
        limit = int(request.query.get("limit", "50"))
        offset = int(request.query.get("offset", "0"))

        batches = await batch_repo.get_batches(limit=limit, offset=offset)
        total = await batch_repo.get_batches_count()

        return web.json_response({
            "batches": [_serialize(b) for b in batches],
            "total": total,
            "limit": limit,
            "offset": offset,
        })

    except Exception as e:
        logger.error(f"Error getting batches: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def get_batch(request: web.Request) -> web.Response:
    """Детали пакета с элементами."""
    try:
        batch_id = int(request.match_info["id"])
        batch = await batch_repo.get_batch(batch_id)
        if not batch:
            return web.json_response({"error": "Batch not found"}, status=404)

        return web.json_response(_serialize(batch))

    except Exception as e:
        logger.error(f"Error getting batch: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def cancel_batch_api(request: web.Request) -> web.Response:
    """Отменить пакет."""
    try:
        batch_id = int(request.match_info["id"])
        success = await batch_repo.cancel_batch(batch_id)
        if not success:
            return web.json_response(
                {"error": "Batch not found or already finished"},
                status=404,
            )

        await sse_manager.broadcast(
            "batch_cancelled",
            {"batch_id": batch_id},
            "batch",
            batch_id,
        )

        return web.json_response({"success": True, "batch_id": batch_id})

    except Exception as e:
        logger.error(f"Error cancelling batch: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def delete_batch_api(request: web.Request) -> web.Response:
    """Удалить пакет."""
    try:
        batch_id = int(request.match_info["id"])
        success = await batch_repo.delete_batch(batch_id)
        if not success:
            return web.json_response({"error": "Batch not found"}, status=404)

        return web.json_response({"success": True})

    except Exception as e:
        logger.error(f"Error deleting batch: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)
