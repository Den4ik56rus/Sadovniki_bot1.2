# src/services/image_generator/image_service.py

"""
Сервис генерации изображений через Vertex AI (Nano Banana Pro).

Оркестрирует полный пайплайн:
1. Оптимизация промпта через GPT-4o
2. Генерация изображения через Vertex AI
3. Сохранение результата в БД и файловую систему
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Callable, Awaitable, Optional

from google.genai.types import GenerateContentConfig, Part, Blob
from google.genai.errors import ClientError

from src.services.presentations.slide_generator import (
    _get_client,
    calculate_nbp_cost,
    DEFAULT_IMAGE_MODEL,
    MAX_RETRIES,
    INITIAL_BACKOFF,
)
from src.services.db import image_generator_repo as repo
from src.services.image_generator.prompt_optimizer import optimize_prompt

logger = logging.getLogger(__name__)

# Директория для сохранения картинок
IMAGES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data", "generated_images",
)


def _ensure_images_dir():
    os.makedirs(IMAGES_DIR, exist_ok=True)


async def generate_image(
    gen_id: int,
    on_progress: Optional[Callable[[dict], Awaitable[None]]] = None,
) -> dict:
    """
    Полный пайплайн генерации изображения.

    1. Читаем запись из БД
    2. Оптимизируем промпт через GPT-4o (если optimized_prompt ещё нет)
    3. Генерируем изображение через Vertex AI
    4. Сохраняем результат

    Args:
        gen_id: ID записи в generated_images
        on_progress: Callback для SSE-событий

    Returns:
        dict с результатом генерации
    """
    _ensure_images_dir()

    async def emit(event_type: str, **data):
        if on_progress:
            await on_progress({"type": event_type, "gen_id": gen_id, **data})

    try:
        gen = await repo.get_generation(gen_id)
        if not gen:
            raise ValueError(f"Генерация {gen_id} не найдена")

        # Шаг 1: Оптимизация промпта (если нужно)
        if not gen.get("optimized_prompt"):
            await repo.update_generation(gen_id, status="optimizing")
            await emit("status", status="optimizing", message="Оптимизация промпта...")

            has_ref = bool(gen.get("reference_image_path"))
            opt_result = await optimize_prompt(
                user_description=gen["user_prompt"],
                preset=gen["preset"],
                has_reference_image=has_ref,
            )

            await repo.update_generation(
                gen_id,
                optimized_prompt=opt_result["optimized_prompt"],
                prompt_tokens=opt_result["prompt_tokens"],
                prompt_completion_tokens=opt_result["completion_tokens"],
            )

            await emit(
                "optimized",
                status="optimized",
                optimized_prompt=opt_result["optimized_prompt"],
                message="Промпт оптимизирован",
            )

            prompt = opt_result["optimized_prompt"]
            prompt_cost = opt_result["cost_usd"]
        else:
            prompt = gen["optimized_prompt"]
            prompt_cost = 0.0

        # Шаг 2: Генерация изображения
        await repo.update_generation(gen_id, status="generating")
        await emit("status", status="generating", message="Генерация изображения...")

        model = gen.get("image_model") or DEFAULT_IMAGE_MODEL
        timestamp = int(time.time())
        filename = f"{gen_id}_{timestamp}.png"
        output_path = os.path.join(IMAGES_DIR, filename)

        # Вызов Vertex AI
        ref_path = gen.get("reference_image_path")
        if ref_path:
            full_ref_path = os.path.join(IMAGES_DIR, ref_path)
            if os.path.exists(full_ref_path):
                result = await _generate_with_reference(prompt, full_ref_path, output_path, model)
            else:
                result = await _generate_image(prompt, output_path, model)
        else:
            result = await _generate_image(prompt, output_path, model)

        # Шаг 3: Сохраняем результат
        total_cost = prompt_cost + result["cost_usd"]

        await repo.update_generation(
            gen_id,
            status="completed",
            image_path=filename,
            input_tokens=result["input_tokens"],
            output_tokens=result["output_tokens"],
            cost_usd=total_cost,
        )

        await emit(
            "completed",
            status="completed",
            image_path=filename,
            cost_usd=total_cost,
            message="Готово!",
        )

        logger.info(f"[image_service] Генерация {gen_id} завершена: {filename}, cost=${total_cost:.4f}")
        return {"gen_id": gen_id, "image_path": filename, "cost_usd": total_cost}

    except Exception as e:
        logger.error(f"[image_service] Ошибка генерации {gen_id}: {e}", exc_info=True)
        await repo.update_generation(gen_id, status="failed", error_message=str(e))
        await emit("failed", status="failed", error=str(e), message=f"Ошибка: {e}")
        raise


async def _generate_image(
    prompt: str,
    output_path: str,
    model: str = DEFAULT_IMAGE_MODEL,
) -> dict:
    """Генерация изображения без референса."""
    client = _get_client()

    response = None
    for attempt in range(MAX_RETRIES):
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                    temperature=1.0,
                ),
            )
            break
        except ClientError as e:
            if e.code == 429 and attempt < MAX_RETRIES - 1:
                wait = INITIAL_BACKOFF * (2 ** attempt)
                logger.warning(f"[image_service] Rate limit (429), retry {attempt + 1}/{MAX_RETRIES} через {wait}с...")
                await asyncio.sleep(wait)
            else:
                raise

    image_bytes = _extract_image(response)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_bytes(image_bytes)

    usage = response.usage_metadata
    input_tokens = usage.prompt_token_count if usage else 0
    output_tokens = usage.candidates_token_count if usage else 0
    cost = calculate_nbp_cost(input_tokens, output_tokens, model)

    return {"input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": cost}


async def _generate_with_reference(
    prompt: str,
    reference_path: str,
    output_path: str,
    model: str = DEFAULT_IMAGE_MODEL,
) -> dict:
    """Генерация изображения с референсом (для редактирования или стиля)."""
    client = _get_client()

    img_bytes = Path(reference_path).read_bytes()
    # Определяем mime type
    ext = Path(reference_path).suffix.lower()
    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}
    mime_type = mime_map.get(ext, "image/png")

    response = None
    for attempt in range(MAX_RETRIES):
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=[
                    Part(inline_data=Blob(mime_type=mime_type, data=img_bytes)),
                    prompt,
                ],
                config=GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                    temperature=1.0,
                ),
            )
            break
        except ClientError as e:
            if e.code == 429 and attempt < MAX_RETRIES - 1:
                wait = INITIAL_BACKOFF * (2 ** attempt)
                logger.warning(f"[image_service] Rate limit (429) ref, retry {attempt + 1}/{MAX_RETRIES} через {wait}с...")
                await asyncio.sleep(wait)
            else:
                raise

    image_bytes = _extract_image(response)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_bytes(image_bytes)

    usage = response.usage_metadata
    input_tokens = usage.prompt_token_count if usage else 0
    output_tokens = usage.candidates_token_count if usage else 0
    cost = calculate_nbp_cost(input_tokens, output_tokens, model)

    return {"input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": cost}


def _extract_image(response) -> bytes:
    """Извлекает bytes изображения из Vertex AI response."""
    for part in response.candidates[0].content.parts:
        if hasattr(part, 'inline_data') and part.inline_data and part.inline_data.data:
            return part.inline_data.data
    raise RuntimeError("Vertex AI не вернул изображение")
