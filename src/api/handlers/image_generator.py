# src/api/handlers/image_generator.py

"""
API handlers для генератора картинок в админке.

Endpoints:
- POST /api/admin/image-generator/generate — создать генерацию + запустить фоновую задачу
- POST /api/admin/image-generator/generate-direct — генерация с отредактированным промптом
- POST /api/admin/image-generator/upload-reference — загрузить референс-фото
- GET  /api/admin/image-generator/history — список генераций
- GET  /api/admin/image-generator/image/{filename} — отдать файл картинки
- DELETE /api/admin/image-generator/{id} — удалить генерацию
- GET  /api/admin/image-generator/presets — список пресетов
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from decimal import Decimal

from aiohttp import web

from src.api.sse_manager import sse_manager
from src.services.db import image_generator_repo as repo
from src.services.image_generator.image_service import generate_image, IMAGES_DIR
from src.services.image_generator.prompt_optimizer import PRESET_DEFINITIONS

logger = logging.getLogger(__name__)


def _serialize(row: dict) -> dict:
    """Сериализует запись из БД для JSON-ответа."""
    result = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            result[k] = v.isoformat()
        elif isinstance(v, Decimal):
            result[k] = float(v)
        else:
            result[k] = v
    return result


async def generate_image_api(request: web.Request) -> web.Response:
    """
    POST /api/admin/image-generator/generate
    Body: { user_prompt, preset, image_model?, reference_image_path?, optimize_prompt? }
    """
    try:
        data = await request.json()
        user_prompt = data.get("user_prompt", "").strip()
        if not user_prompt:
            return web.json_response({"error": "user_prompt обязателен"}, status=400)

        preset = data.get("preset", "free")
        image_model = data.get("image_model")
        reference_image_path = data.get("reference_image_path")
        optimize_prompt = data.get("optimize_prompt", False)

        gen_id = await repo.create_generation(
            user_prompt=user_prompt,
            preset=preset,
            reference_image_path=reference_image_path,
            image_model=image_model,
        )

        # Если оптимизация не запрошена — ставим user_prompt как optimized_prompt,
        # чтобы image_service пропустил шаг оптимизации
        if not optimize_prompt:
            await repo.update_generation(gen_id, optimized_prompt=user_prompt)

        # SSE progress callback
        async def on_progress(event: dict):
            await sse_manager.broadcast(
                event_type=event.get("type", "progress"),
                data=event,
                endpoint_type="image_generator",
                entity_id=gen_id,
            )

        # Запускаем фоновую задачу
        asyncio.create_task(generate_image(gen_id, on_progress=on_progress))

        gen = await repo.get_generation(gen_id)
        return web.json_response({"id": gen_id, "generation": _serialize(gen)})

    except Exception as e:
        logger.error(f"Error in generate_image_api: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def generate_direct_api(request: web.Request) -> web.Response:
    """
    POST /api/admin/image-generator/generate-direct
    Body: { gen_id, edited_prompt }
    Генерация с вручную отредактированным промптом (пропуск GPT-4o).
    """
    try:
        data = await request.json()
        gen_id = data.get("gen_id")
        edited_prompt = data.get("edited_prompt", "").strip()

        if not gen_id or not edited_prompt:
            return web.json_response({"error": "gen_id и edited_prompt обязательны"}, status=400)

        gen = await repo.get_generation(gen_id)
        if not gen:
            return web.json_response({"error": "Генерация не найдена"}, status=404)

        # Обновляем оптимизированный промпт
        await repo.update_generation(gen_id, optimized_prompt=edited_prompt, status="pending")

        # SSE progress callback
        async def on_progress(event: dict):
            await sse_manager.broadcast(
                event_type=event.get("type", "progress"),
                data=event,
                endpoint_type="image_generator",
                entity_id=gen_id,
            )

        # Запускаем генерацию (prompt уже есть, GPT-4o пропустится)
        asyncio.create_task(generate_image(gen_id, on_progress=on_progress))

        return web.json_response({"id": gen_id, "status": "started"})

    except Exception as e:
        logger.error(f"Error in generate_direct_api: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def upload_reference_api(request: web.Request) -> web.Response:
    """
    POST /api/admin/image-generator/upload-reference
    Multipart upload референс-фото (≤10MB).
    """
    try:
        os.makedirs(IMAGES_DIR, exist_ok=True)

        reader = await request.multipart()
        field = await reader.next()

        if not field or field.name != 'image':
            raise web.HTTPBadRequest(text='Field "image" is required')

        filename = field.filename or 'reference.jpg'
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
            raise web.HTTPBadRequest(text='Допустимые форматы: jpg, jpeg, png, gif, webp')

        safe_name = f"ref_{int(time.time())}{ext}"
        filepath = os.path.join(IMAGES_DIR, safe_name)

        size = 0
        with open(filepath, 'wb') as f:
            while True:
                chunk = await field.read_chunk()
                if not chunk:
                    break
                size += len(chunk)
                if size > 10 * 1024 * 1024:
                    f.close()
                    os.remove(filepath)
                    raise web.HTTPBadRequest(text='Файл слишком большой (макс 10 МБ)')
                f.write(chunk)

        return web.json_response({'reference_path': safe_name})

    except web.HTTPBadRequest:
        raise
    except Exception as e:
        logger.error(f'Error uploading reference image: {e}', exc_info=True)
        raise web.HTTPInternalServerError(text='Upload failed')


async def get_history(request: web.Request) -> web.Response:
    """GET /api/admin/image-generator/history"""
    try:
        limit = int(request.query.get("limit", "50"))
        offset = int(request.query.get("offset", "0"))
        preset = request.query.get("preset")

        generations = await repo.get_generations(limit=limit, offset=offset, preset=preset)
        total = await repo.get_generations_count(preset)

        return web.json_response({
            "generations": [_serialize(g) for g in generations],
            "total": total,
            "limit": limit,
            "offset": offset,
        })

    except Exception as e:
        logger.error(f"Error getting image history: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def get_image_file(request: web.Request) -> web.Response:
    """GET /api/admin/image-generator/image/{filename}"""
    filename = request.match_info['filename']
    if '/' in filename or '..' in filename:
        raise web.HTTPBadRequest(text='Invalid filename')

    filepath = os.path.join(IMAGES_DIR, filename)
    if not os.path.isfile(filepath):
        raise web.HTTPNotFound(text='Image not found')

    return web.FileResponse(filepath)


async def delete_generation_api(request: web.Request) -> web.Response:
    """DELETE /api/admin/image-generator/{id}"""
    try:
        gen_id = int(request.match_info['id'])
        gen = await repo.get_generation(gen_id)
        if not gen:
            return web.json_response({"error": "Не найдено"}, status=404)

        # Удаляем файлы
        if gen.get("image_path"):
            path = os.path.join(IMAGES_DIR, gen["image_path"])
            if os.path.exists(path):
                os.remove(path)

        if gen.get("reference_image_path"):
            path = os.path.join(IMAGES_DIR, gen["reference_image_path"])
            if os.path.exists(path):
                os.remove(path)

        await repo.delete_generation(gen_id)
        return web.json_response({"success": True})

    except Exception as e:
        logger.error(f"Error deleting generation {request.match_info.get('id')}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def get_presets(request: web.Request) -> web.Response:
    """GET /api/admin/image-generator/presets"""
    return web.json_response({"presets": PRESET_DEFINITIONS})
