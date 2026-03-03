# src/api/handlers/presentations.py

"""
API handlers для презентаций.

Endpoints:
    POST   /api/admin/presentations                          — создать
    POST   /api/admin/presentations/{id}/generate             — запустить генерацию
    GET    /api/admin/presentations                           — список
    GET    /api/admin/presentations/{id}                      — деталь + слайды + версии
    DELETE /api/admin/presentations/{id}                      — удалить
    POST   /api/admin/presentations/slides/{id}/edit          — редактировать слайд
    GET    /api/admin/presentations/{id}/pdf                  — скачать PDF
    GET    /api/admin/presentations/slides/versions/{id}/image — скачать PNG
    POST   /api/admin/presentations/{id}/pdf/rebuild          — пересобрать PDF

    GET    /api/admin/presentations/styles                    — список стилей
    POST   /api/admin/presentations/styles                    — создать стиль
    PUT    /api/admin/presentations/styles/{id}               — обновить стиль
    DELETE /api/admin/presentations/styles/{id}               — удалить стиль

    GET    /api/admin/presentations/templates                 — список шаблонов
    POST   /api/admin/presentations/templates                 — создать шаблон
    PUT    /api/admin/presentations/templates/{id}            — обновить шаблон
    DELETE /api/admin/presentations/templates/{id}            — удалить шаблон
"""

import asyncio
import logging
import os
from decimal import Decimal
from pathlib import Path

from aiohttp import web

from src.services.db import presentation_repo
from src.services.presentations.presentation_service import (
    generate_presentation,
    edit_slide,
    rebuild_pdf,
)
from src.services.presentations.slide_generator import get_image_models_info
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


# =============================================================================
# Presentations CRUD
# =============================================================================

async def create_presentation_api(request: web.Request) -> web.Response:
    """Создать презентацию (draft)."""
    try:
        data = await request.json()

        generation_mode = data.get("generation_mode", "article")

        if generation_mode == "problem":
            # Режим «По проблеме»: culture_key + problem_key обязательны
            culture_key = (data.get("culture_key") or "").strip()
            problem_key = (data.get("problem_key") or "").strip()
            if not culture_key or not problem_key:
                return web.json_response({"error": "culture_key and problem_key are required for problem mode"}, status=400)

            variety_key = (data.get("variety_key") or "").strip() or None

            # Авто-генерация title если не указан
            title = (data.get("title") or "").strip()
            if not title:
                from src.data.funnel_b_problems import get_culture_label, get_problem_label
                title = f"{get_culture_label(culture_key, variety_key)}: {get_problem_label(problem_key)}"

            source_text = ""  # Будет заполнен после генерации статьи
        else:
            # Режим «Текст статьи» (текущий)
            title = (data.get("title") or "").strip()
            if not title:
                return web.json_response({"error": "title is required"}, status=400)

            source_text = (data.get("source_text") or "").strip()
            if not source_text:
                return web.json_response({"error": "source_text is required"}, status=400)

            culture_key = None
            variety_key = None
            problem_key = None

        # test_slide_index: если передан, генерируем только этот слайд
        test_slide_index = data.get("test_slide_index")
        if test_slide_index is not None:
            test_slide_index = int(test_slide_index)

        # Custom system prompt (если пустая строка — не сохраняем)
        custom_system_prompt = (data.get("custom_system_prompt") or "").strip() or None

        pres_id = await presentation_repo.create_presentation(
            title=title,
            source_text=source_text,
            style_id=data.get("style_id"),
            template_id=data.get("template_id"),
            llm_model=data.get("llm_model"),
            reasoning_effort=data.get("reasoning_effort"),
            image_model=data.get("image_model") or None,
            test_slide_index=test_slide_index,
            generation_mode=generation_mode,
            culture_key=culture_key,
            variety_key=variety_key,
            problem_key=problem_key,
            custom_system_prompt=custom_system_prompt,
        )

        pres = await presentation_repo.get_presentation_by_id(pres_id)
        return web.json_response({"id": pres_id, "presentation": _serialize(pres)})

    except Exception as e:
        logger.error(f"Error creating presentation: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def generate_presentation_api(request: web.Request) -> web.Response:
    """Запустить генерацию презентации (background task)."""
    presentation_id = int(request.match_info["id"])

    try:
        pres = await presentation_repo.get_presentation_by_id(presentation_id)
        if not pres:
            return web.json_response({"error": "Presentation not found"}, status=404)

        if pres["status"] == "generating":
            return web.json_response({"error": "Already generating"}, status=409)

        # SSE progress callback
        async def on_progress(event: dict):
            await sse_manager.broadcast(
                event_type=event.get("type", "progress"),
                data=event,
                endpoint_type="presentation",
                entity_id=presentation_id,
            )

        # Start generation in background
        asyncio.create_task(
            generate_presentation(presentation_id, on_progress=on_progress)
        )

        return web.json_response({"status": "started", "presentation_id": presentation_id})

    except Exception as e:
        logger.error(f"Error starting generation for {presentation_id}: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def get_presentations(request: web.Request) -> web.Response:
    """Список презентаций с пагинацией."""
    try:
        limit = int(request.query.get("limit", "50"))
        offset = int(request.query.get("offset", "0"))
        status = request.query.get("status")

        presentations = await presentation_repo.get_presentations_list(
            limit=limit, offset=offset, status=status
        )
        total = await presentation_repo.get_presentations_count(status)

        return web.json_response({
            "presentations": [_serialize(p) for p in presentations],
            "total": total,
            "limit": limit,
            "offset": offset,
        })

    except Exception as e:
        logger.error(f"Error getting presentations: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def get_presentation(request: web.Request) -> web.Response:
    """Получить презентацию с полными слайдами и версиями."""
    presentation_id = int(request.match_info["id"])

    try:
        pres = await presentation_repo.get_presentation_full(presentation_id)
        if not pres:
            return web.json_response({"error": "Presentation not found"}, status=404)

        return web.json_response(_serialize(pres))

    except Exception as e:
        logger.error(f"Error getting presentation {presentation_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def delete_presentation_api(request: web.Request) -> web.Response:
    """Удалить презентацию и все её файлы."""
    presentation_id = int(request.match_info["id"])

    try:
        pres = await presentation_repo.get_presentation_by_id(presentation_id)
        if not pres:
            return web.json_response({"error": "Presentation not found"}, status=404)

        # Delete files
        pres_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "data", "presentations", str(presentation_id)
        )
        if os.path.exists(pres_dir):
            import shutil
            shutil.rmtree(pres_dir)

        # Delete from DB (CASCADE deletes slides + versions)
        await presentation_repo.delete_presentation(presentation_id)

        return web.json_response({"success": True})

    except Exception as e:
        logger.error(f"Error deleting presentation {presentation_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)


# =============================================================================
# Slide editing
# =============================================================================

async def edit_slide_api(request: web.Request) -> web.Response:
    """Редактировать слайд — создать новую версию."""
    slide_id = int(request.match_info["id"])

    try:
        data = await request.json()
        instruction = (data.get("instruction") or "").strip()
        if not instruction:
            return web.json_response({"error": "instruction is required"}, status=400)

        version = await edit_slide(slide_id, instruction)
        return web.json_response(_serialize(version))

    except ValueError as e:
        return web.json_response({"error": str(e)}, status=404)
    except Exception as e:
        logger.error(f"Error editing slide {slide_id}: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


# =============================================================================
# File downloads
# =============================================================================

async def download_pdf(request: web.Request) -> web.Response:
    """Скачать PDF презентации."""
    presentation_id = int(request.match_info["id"])

    try:
        pres = await presentation_repo.get_presentation_by_id(presentation_id)
        if not pres:
            return web.json_response({"error": "Presentation not found"}, status=404)

        pdf_path = pres.get("pdf_path")
        if not pdf_path or not Path(pdf_path).exists():
            return web.json_response({"error": "PDF not found"}, status=404)

        return web.FileResponse(
            pdf_path,
            headers={
                "Content-Disposition": f'attachment; filename="{pres["title"]}.pdf"',
            },
        )

    except Exception as e:
        logger.error(f"Error downloading PDF for {presentation_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def get_slide_image(request: web.Request) -> web.Response:
    """Скачать PNG слайда (конкретная версия)."""
    version_id = int(request.match_info["id"])

    try:
        version = await presentation_repo.get_version_by_id(version_id)
        if not version:
            return web.json_response({"error": "Version not found"}, status=404)

        image_path = version.get("image_path")
        if not image_path or not Path(image_path).exists():
            return web.json_response({"error": "Image not found"}, status=404)

        return web.FileResponse(image_path)

    except Exception as e:
        logger.error(f"Error getting slide image {version_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def rebuild_pdf_api(request: web.Request) -> web.Response:
    """Пересобрать PDF из текущих версий слайдов."""
    presentation_id = int(request.match_info["id"])

    try:
        pdf_path = await rebuild_pdf(presentation_id)
        return web.json_response({"success": True, "pdf_path": pdf_path})

    except ValueError as e:
        return web.json_response({"error": str(e)}, status=404)
    except Exception as e:
        logger.error(f"Error rebuilding PDF for {presentation_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)


# =============================================================================
# Styles CRUD
# =============================================================================

async def get_styles(request: web.Request) -> web.Response:
    """Список стилей."""
    try:
        styles = await presentation_repo.get_styles_list()
        return web.json_response({"styles": [_serialize(s) for s in styles]})
    except Exception as e:
        logger.error(f"Error getting styles: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def create_style_api(request: web.Request) -> web.Response:
    """Создать стиль."""
    try:
        data = await request.json()

        name = (data.get("name") or "").strip()
        if not name:
            return web.json_response({"error": "name is required"}, status=400)

        style_xml = (data.get("style_xml") or "").strip()
        if not style_xml:
            return web.json_response({"error": "style_xml is required"}, status=400)

        style_id = await presentation_repo.create_style(
            name=name,
            description=data.get("description"),
            style_xml=style_xml,
        )

        style = await presentation_repo.get_style_by_id(style_id)
        return web.json_response(_serialize(style))

    except Exception as e:
        logger.error(f"Error creating style: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def update_style_api(request: web.Request) -> web.Response:
    """Обновить стиль."""
    style_id = int(request.match_info["id"])

    try:
        data = await request.json()
        style = await presentation_repo.update_style(
            style_id,
            name=data.get("name"),
            description=data.get("description"),
            style_xml=data.get("style_xml"),
        )

        if not style:
            return web.json_response({"error": "Style not found"}, status=404)

        return web.json_response(_serialize(style))

    except Exception as e:
        logger.error(f"Error updating style {style_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def delete_style_api(request: web.Request) -> web.Response:
    """Удалить стиль."""
    style_id = int(request.match_info["id"])

    try:
        deleted = await presentation_repo.delete_style(style_id)
        if not deleted:
            return web.json_response({"error": "Style not found"}, status=404)
        return web.json_response({"success": True})

    except Exception as e:
        logger.error(f"Error deleting style {style_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)


# =============================================================================
# Templates CRUD
# =============================================================================

async def get_templates(request: web.Request) -> web.Response:
    """Список шаблонов структуры."""
    try:
        templates = await presentation_repo.get_templates_list()
        return web.json_response({"templates": [_serialize(t) for t in templates]})
    except Exception as e:
        logger.error(f"Error getting templates: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def create_template_api(request: web.Request) -> web.Response:
    """Создать шаблон."""
    try:
        data = await request.json()

        name = (data.get("name") or "").strip()
        if not name:
            return web.json_response({"error": "name is required"}, status=400)

        template_text = (data.get("template_text") or "").strip()
        if not template_text:
            return web.json_response({"error": "template_text is required"}, status=400)

        template_id = await presentation_repo.create_template(
            name=name,
            description=data.get("description"),
            template_text=template_text,
        )

        template = await presentation_repo.get_template_by_id(template_id)
        return web.json_response(_serialize(template))

    except Exception as e:
        logger.error(f"Error creating template: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def update_template_api(request: web.Request) -> web.Response:
    """Обновить шаблон."""
    template_id = int(request.match_info["id"])

    try:
        data = await request.json()
        template = await presentation_repo.update_template(
            template_id,
            name=data.get("name"),
            description=data.get("description"),
            template_text=data.get("template_text"),
        )

        if not template:
            return web.json_response({"error": "Template not found"}, status=404)

        return web.json_response(_serialize(template))

    except Exception as e:
        logger.error(f"Error updating template {template_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def delete_template_api(request: web.Request) -> web.Response:
    """Удалить шаблон."""
    template_id = int(request.match_info["id"])

    try:
        deleted = await presentation_repo.delete_template(template_id)
        if not deleted:
            return web.json_response({"error": "Template not found"}, status=404)
        return web.json_response({"success": True})

    except Exception as e:
        logger.error(f"Error deleting template {template_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)


# =============================================================================
# Image models info
# =============================================================================

async def get_image_models(request: web.Request) -> web.Response:
    """Список доступных моделей для генерации изображений с ценами."""
    try:
        models = get_image_models_info()
        return web.json_response({"models": models})
    except Exception as e:
        logger.error(f"Error getting image models: {e}")
        return web.json_response({"error": str(e)}, status=500)


# =============================================================================
# Problem definitions (for "By Problem" presentation mode)
# =============================================================================

async def get_problem_definitions(request: web.Request) -> web.Response:
    """Список культур и проблем из Funnel B для режима «По проблеме»."""
    try:
        from src.data.funnel_b_problems import get_all_structured
        return web.json_response({"cultures": get_all_structured()})
    except Exception as e:
        logger.error(f"Error getting problem definitions: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def get_default_system_prompt(request: web.Request) -> web.Response:
    """Возвращает дефолтный system prompt для GPT разбивки на слайды."""
    from src.services.presentations.prompt_builder import SLIDE_SPLIT_SYSTEM_PROMPT
    return web.json_response({"system_prompt": SLIDE_SPLIT_SYSTEM_PROMPT})
