# src/api/handlers/batch_articles.py

"""
API handlers для пакетной генерации статей.

Endpoints:
    POST   /api/admin/articles/batches             — создать пакет + запустить
    GET    /api/admin/articles/batches              — список пакетов
    GET    /api/admin/articles/batches/{id}         — детали пакета + items
    POST   /api/admin/articles/batches/{id}/cancel  — отменить пакет
    DELETE /api/admin/articles/batches/{id}         — удалить пакет
    GET    /api/admin/articles/definitions          — категории + культуры для UI
"""

import asyncio
import logging
from decimal import Decimal

from aiohttp import web

from src.services.db import article_batch_repo
from src.services.articles.article_batch_processor import run_article_batch
from src.data.article_categories import (
    get_all_article_definitions,
    get_category_label,
    get_culture_label_for_batch,
    build_article_topic,
)
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


async def get_definitions(request: web.Request) -> web.Response:
    """Возвращает категории и культуры для UI."""
    try:
        definitions = get_all_article_definitions()
        return web.json_response(definitions)
    except Exception as e:
        logger.error(f"Error getting article definitions: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def create_batch_api(request: web.Request) -> web.Response:
    """Создать пакет и запустить генерацию."""
    try:
        data = await request.json()

        items = data.get("items", [])
        if not items:
            return web.json_response({"error": "items is required (non-empty array)"}, status=400)

        # Валидация элементов
        for item in items:
            if not item.get("culture_key") or not item.get("category_key"):
                return web.json_response(
                    {"error": "Each item must have culture_key and category_key"},
                    status=400,
                )

        # Авто-генерация topic и labels
        enriched_items = []
        for item in items:
            category_label = get_category_label(item["category_key"]) or item["category_key"]
            culture_label = get_culture_label_for_batch(
                item["culture_key"], item.get("variety_key")
            ) or item["culture_key"]
            topic = build_article_topic(category_label, culture_label)

            enriched_items.append({
                **item,
                "topic": topic,
                "culture_label": culture_label,
                "category_label": category_label,
            })

        # Создаём пакет
        batch_id = await article_batch_repo.create_batch(
            llm_model=data.get("llm_model"),
            total_items=len(enriched_items),
            reasoning_effort=data.get("reasoning_effort"),
        )

        # Добавляем элементы
        await article_batch_repo.add_batch_items(batch_id, enriched_items)

        # Запускаем генерацию в фоне
        from src.bot import get_bot
        bot = get_bot()
        asyncio.create_task(run_article_batch(batch_id, bot))

        batch = await article_batch_repo.get_batch(batch_id)
        return web.json_response({
            "id": batch_id,
            "batch": _serialize(batch) if batch else None,
        })

    except Exception as e:
        logger.error(f"Error creating article batch: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def get_batches(request: web.Request) -> web.Response:
    """Список всех пакетов."""
    try:
        limit = int(request.query.get("limit", "50"))
        offset = int(request.query.get("offset", "0"))

        batches = await article_batch_repo.get_batches(limit=limit, offset=offset)
        total = await article_batch_repo.get_batches_count()

        return web.json_response({
            "batches": [_serialize(b) for b in batches],
            "total": total,
            "limit": limit,
            "offset": offset,
        })

    except Exception as e:
        logger.error(f"Error getting article batches: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def get_batch(request: web.Request) -> web.Response:
    """Детали пакета с элементами."""
    try:
        batch_id = int(request.match_info["id"])
        batch = await article_batch_repo.get_batch(batch_id)
        if not batch:
            return web.json_response({"error": "Batch not found"}, status=404)

        return web.json_response(_serialize(batch))

    except Exception as e:
        logger.error(f"Error getting article batch: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def cancel_batch_api(request: web.Request) -> web.Response:
    """Отменить пакет."""
    try:
        batch_id = int(request.match_info["id"])
        success = await article_batch_repo.cancel_batch(batch_id)
        if not success:
            return web.json_response(
                {"error": "Batch not found or already finished"},
                status=404,
            )

        await sse_manager.broadcast(
            "article_batch_cancelled",
            {"batch_id": batch_id},
            "article_batch",
            batch_id,
        )

        return web.json_response({"success": True, "batch_id": batch_id})

    except Exception as e:
        logger.error(f"Error cancelling article batch: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def delete_batch_api(request: web.Request) -> web.Response:
    """Удалить пакет."""
    try:
        batch_id = int(request.match_info["id"])
        success = await article_batch_repo.delete_batch(batch_id)
        if not success:
            return web.json_response({"error": "Batch not found"}, status=404)

        return web.json_response({"success": True})

    except Exception as e:
        logger.error(f"Error deleting article batch: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)
