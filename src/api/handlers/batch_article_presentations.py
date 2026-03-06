# src/api/handlers/batch_article_presentations.py

"""
API handlers для пакетной генерации презентаций по статьям.

Endpoints:
    POST   /api/admin/presentations/article-batches             — создать пакет + запустить
    GET    /api/admin/presentations/article-batches              — список пакетов
    GET    /api/admin/presentations/article-batches/{id}         — детали пакета + items
    POST   /api/admin/presentations/article-batches/{id}/cancel  — отменить пакет
    DELETE /api/admin/presentations/article-batches/{id}         — удалить пакет
    GET    /api/admin/presentations/article-batches/definitions  — категории + культуры для UI
"""

import asyncio
import logging
from decimal import Decimal

from aiohttp import web

from src.services.db import batch_repo, article_repo
from src.services.presentations.article_batch_processor import run_article_presentation_batch
from src.data.article_categories import (
    ARTICLE_CATEGORIES,
    BATCH_CULTURES,
    get_category_label,
    get_culture_label_for_batch,
)

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
    """Возвращает категории и культуры для UI + информацию о доступных статьях."""
    try:
        # Для каждой культуры проверяем какие статьи существуют
        cultures_with_articles = []
        for culture in BATCH_CULTURES:
            articles = await article_repo.get_articles_by_culture(
                culture["culture_key"], culture.get("variety_key"),
            )
            # Собираем уникальные category_key существующих статей
            existing_categories = set()
            for art in articles:
                if art.get("category_key"):
                    existing_categories.add(art["category_key"])

            cultures_with_articles.append({
                **culture,
                "existing_categories": list(existing_categories),
                "article_count": len(existing_categories),
            })

        return web.json_response({
            "categories": ARTICLE_CATEGORIES,
            "cultures": cultures_with_articles,
        })
    except Exception as e:
        logger.error(f"Error getting article presentation definitions: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def create_batch_api(request: web.Request) -> web.Response:
    """Создать пакет и запустить генерацию."""
    try:
        data = await request.json()

        cultures = data.get("cultures", [])
        if not cultures:
            return web.json_response({"error": "cultures is required (non-empty array)"}, status=400)

        include_season_plan = data.get("include_season_plan", False)

        # Разворачиваем cultures → конкретные items
        items = []
        for culture in cultures:
            culture_key = culture["culture_key"]
            variety_key = culture.get("variety_key")

            # Добавляем 6 категорий (только если статья существует)
            for cat in ARTICLE_CATEGORIES:
                article = await article_repo.get_article_by_category_and_culture(
                    cat["key"], culture_key, variety_key,
                )
                if article:
                    items.append({
                        "culture_key": culture_key,
                        "variety_key": variety_key,
                        "category_key": cat["key"],
                        "is_season_plan": False,
                    })

            # Добавляем сезонный план
            if include_season_plan:
                items.append({
                    "culture_key": culture_key,
                    "variety_key": variety_key,
                    "category_key": None,
                    "is_season_plan": True,
                })

        if not items:
            return web.json_response(
                {"error": "Нет статей для выбранных культур"},
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
            batch_type="article",
        )

        # Добавляем элементы
        await batch_repo.add_article_batch_items(batch_id, items)

        # Запускаем генерацию в фоне
        from src.bot import get_bot
        bot = get_bot()
        asyncio.create_task(run_article_presentation_batch(batch_id, bot))

        batch = await batch_repo.get_batch(batch_id)
        return web.json_response({
            "id": batch_id,
            "batch": _serialize(batch) if batch else None,
        })

    except Exception as e:
        logger.error(f"Error creating article presentation batch: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def get_batches_api(request: web.Request) -> web.Response:
    """Список пакетов по статьям."""
    try:
        limit = int(request.query.get("limit", "50"))
        offset = int(request.query.get("offset", "0"))

        batches = await batch_repo.get_batches(limit=limit, offset=offset, batch_type="article")
        total = await batch_repo.get_batches_count(batch_type="article")

        return web.json_response({
            "batches": [_serialize(b) for b in batches],
            "total": total,
            "limit": limit,
            "offset": offset,
        })

    except Exception as e:
        logger.error(f"Error getting article presentation batches: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def get_batch_api(request: web.Request) -> web.Response:
    """Детали пакета с элементами."""
    try:
        batch_id = int(request.match_info["id"])
        batch = await batch_repo.get_batch(batch_id)
        if not batch:
            return web.json_response({"error": "Batch not found"}, status=404)

        return web.json_response(_serialize(batch))

    except Exception as e:
        logger.error(f"Error getting article presentation batch: {e}", exc_info=True)
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

        from src.api.sse_manager import sse_manager
        await sse_manager.broadcast(
            "batch_cancelled",
            {"batch_id": batch_id},
            "batch",
            batch_id,
        )

        return web.json_response({"success": True, "batch_id": batch_id})

    except Exception as e:
        logger.error(f"Error cancelling article presentation batch: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def run_batch_api(request: web.Request) -> web.Response:
    """Запустить существующий pending-пакет (для retry failed items)."""
    try:
        batch_id = int(request.match_info["id"])
        batch = await batch_repo.get_batch(batch_id)
        if not batch:
            return web.json_response({"error": "Batch not found"}, status=404)

        if batch["status"] not in ("pending",):
            return web.json_response(
                {"error": f"Batch status is '{batch['status']}', expected 'pending'"},
                status=400,
            )

        from src.bot import get_bot
        bot = get_bot()
        asyncio.create_task(run_article_presentation_batch(batch_id, bot))

        return web.json_response({"success": True, "batch_id": batch_id})

    except Exception as e:
        logger.error(f"Error running article presentation batch: {e}", exc_info=True)
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
        logger.error(f"Error deleting article presentation batch: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)
