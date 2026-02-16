"""
API handler для превью собранного промпта.

Endpoints:
    GET /api/admin/prompts/preview         — собранный промпт с аннотациями секций
    GET /api/admin/prompts/preview/options  — списки категорий и культур для дропдаунов
"""

import logging
from aiohttp import web

logger = logging.getLogger(__name__)

# Статические списки для дропдаунов
CATEGORIES = [
    {"value": "питание растений", "label": "Питание растений"},
    {"value": "посадка и уход", "label": "Посадка и уход"},
    {"value": "обрезка", "label": "Обрезка"},
    {"value": "защита растений", "label": "Защита растений"},
    {"value": "улучшение почвы", "label": "Улучшение почвы"},
    {"value": "подбор сортов", "label": "Подбор сортов"},
]

CULTURES = [
    {"value": "клубника летняя", "label": "Клубника летняя"},
    {"value": "клубника ремонтантная", "label": "Клубника ремонтантная"},
    {"value": "малина летняя", "label": "Малина летняя"},
    {"value": "малина ремонтантная", "label": "Малина ремонтантная"},
    {"value": "смородина", "label": "Смородина"},
    {"value": "голубика", "label": "Голубика"},
    {"value": "жимолость", "label": "Жимолость"},
    {"value": "крыжовник", "label": "Крыжовник"},
    {"value": "ежевика", "label": "Ежевика"},
    {"value": "общая информация", "label": "Общая информация"},
    {"value": "не определено", "label": "Не определено"},
]


async def get_preview_options(request: web.Request) -> web.Response:
    """
    GET /api/admin/prompts/preview/options

    Возвращает списки категорий и культур для дропдаунов.
    """
    return web.json_response({
        "categories": CATEGORIES,
        "cultures": CULTURES,
    })


async def get_prompt_preview(request: web.Request) -> web.Response:
    """
    GET /api/admin/prompts/preview?category=...&culture=...

    Возвращает собранный промпт с аннотированными секциями.
    """
    category = request.query.get("category", "")
    culture = request.query.get("culture", "")

    if not category or not culture:
        return web.json_response(
            {"error": "Параметры 'category' и 'culture' обязательны"},
            status=400,
        )

    try:
        from src.prompts.consultation_prompts import build_prompt_preview

        result = await build_prompt_preview(
            culture=culture,
            consultation_category=category,
        )
        return web.json_response(result)

    except Exception as e:
        logger.error(f"Error building prompt preview: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)
