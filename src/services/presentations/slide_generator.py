# src/services/presentations/slide_generator.py

"""
Генерация изображений слайдов через Google Vertex AI (Gemini Flash Image).

Модель: gemini-2.5-flash-image-preview (Nano Banana Pro)
Также доступна: gemini-3.1-flash-image-preview (Nano Banana 2)
API: Google GenAI SDK через Vertex AI

Rate limits (free trial):
- ~10 RPM для image generation
- Retry с exponential backoff при 429
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional, TypedDict

from google import genai
from google.genai.types import GenerateContentConfig
from google.genai.errors import ClientError

from src.config import settings

logger = logging.getLogger(__name__)

# Доступные модели для генерации изображений
AVAILABLE_IMAGE_MODELS = {
    "gemini-2.5-flash-image-preview": {
        "name": "Nano Banana (Gemini 2.5 Flash Image)",
        "input_price_per_1m": 0.30,
        "output_price_per_1m": 30.0,
        "image_tokens": 1290,
    },
    "gemini-3.1-flash-image-preview": {
        "name": "Nano Banana 2 (Gemini 3.1 Flash Image)",
        "input_price_per_1m": 0.50,
        "output_price_per_1m": 60.0,
        "image_tokens": 1290,
    },
}

# Модель по умолчанию
DEFAULT_IMAGE_MODEL = "gemini-2.5-flash-image-preview"

# Retry config
MAX_RETRIES = 5
INITIAL_BACKOFF = 10  # секунд — начальная пауза при 429

# Lazy client
_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        project = settings.google_cloud_project
        location = settings.google_cloud_location or "global"
        if not project:
            raise ValueError("GOOGLE_CLOUD_PROJECT не настроен для генерации изображений")

        creds_path = settings.google_application_credentials
        if creds_path and os.path.exists(creds_path):
            os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", creds_path)

        _client = genai.Client(
            vertexai=True,
            project=project,
            location=location,
        )
    return _client


class SlideGenerationResult(TypedDict):
    image_path: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


def calculate_nbp_cost(input_tokens: int, output_tokens: int, model: str = DEFAULT_IMAGE_MODEL) -> float:
    """Рассчитывает стоимость запроса в USD по ценам Vertex AI."""
    pricing = AVAILABLE_IMAGE_MODELS.get(model, AVAILABLE_IMAGE_MODELS[DEFAULT_IMAGE_MODEL])
    input_cost = (input_tokens / 1_000_000) * pricing["input_price_per_1m"]
    output_cost = (output_tokens / 1_000_000) * pricing["output_price_per_1m"]
    return input_cost + output_cost


def get_image_models_info() -> list[dict]:
    """Возвращает список доступных моделей с ценами для фронтенда."""
    result = []
    for model_id, info in AVAILABLE_IMAGE_MODELS.items():
        cost_per_image = (info["image_tokens"] / 1_000_000) * info["output_price_per_1m"]
        result.append({
            "id": model_id,
            "name": info["name"],
            "input_price_per_1m": info["input_price_per_1m"],
            "output_price_per_1m": info["output_price_per_1m"],
            "cost_per_image": round(cost_per_image, 4),
        })
    return result


async def _call_with_retry(func, *args, **kwargs):
    """Вызывает функцию с retry при 429 (rate limit)."""
    for attempt in range(MAX_RETRIES):
        try:
            return await func(*args, **kwargs)
        except ClientError as e:
            if e.code == 429 and attempt < MAX_RETRIES - 1:
                wait = INITIAL_BACKOFF * (2 ** attempt)
                logger.warning(
                    f"[slide_generator] Rate limit (429), retry {attempt + 1}/{MAX_RETRIES} "
                    f"через {wait}с..."
                )
                await asyncio.sleep(wait)
            else:
                raise


async def generate_slide_image(
    prompt: str,
    output_path: str,
    model: str = DEFAULT_IMAGE_MODEL,
) -> SlideGenerationResult:
    """
    Генерирует изображение слайда через Vertex AI.

    Args:
        prompt: Промпт для генерации (от GPT)
        output_path: Путь для сохранения PNG
        model: ID модели для генерации

    Returns:
        SlideGenerationResult с путём и статистикой токенов
    """
    client = _get_client()

    logger.info(f"[slide_generator] Генерация слайда: model={model}, prompt='{prompt[:80]}...', output={output_path}")

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
                logger.warning(
                    f"[slide_generator] Rate limit (429), retry {attempt + 1}/{MAX_RETRIES} "
                    f"через {wait}с..."
                )
                await asyncio.sleep(wait)
            else:
                raise

    # Извлекаем изображение из ответа
    image_bytes = None
    for part in response.candidates[0].content.parts:
        if hasattr(part, 'inline_data') and part.inline_data and part.inline_data.data:
            image_bytes = part.inline_data.data
            break

    if not image_bytes:
        raise RuntimeError(f"Vertex AI не вернул изображение для модели {model}")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_bytes(image_bytes)

    # Token usage
    usage = response.usage_metadata
    input_tokens = usage.prompt_token_count if usage else 0
    output_tokens = usage.candidates_token_count if usage else 0
    cost = calculate_nbp_cost(input_tokens, output_tokens, model)

    logger.info(
        f"[slide_generator] Слайд сгенерирован: {output_path}, "
        f"tokens={input_tokens}+{output_tokens}, cost=${cost:.4f}"
    )

    return {
        "image_path": output_path,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost,
    }


async def edit_slide_image(
    image_path: str,
    instruction: str,
    output_path: str,
    model: str = DEFAULT_IMAGE_MODEL,
) -> SlideGenerationResult:
    """
    Редактирует изображение слайда через Vertex AI (отправка картинки + текст правок).

    Args:
        image_path: Путь к текущему изображению
        instruction: Инструкция по редактированию
        output_path: Путь для сохранения нового PNG
        model: ID модели для генерации

    Returns:
        SlideGenerationResult с путём и статистикой
    """
    client = _get_client()

    # Читаем текущее изображение
    img_bytes = Path(image_path).read_bytes()

    logger.info(f"[slide_generator] Редактирование слайда: model={model}, instruction='{instruction[:80]}...'")

    from google.genai.types import Part, Blob

    response = None
    for attempt in range(MAX_RETRIES):
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=[
                    Part(inline_data=Blob(mime_type="image/png", data=img_bytes)),
                    instruction,
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
                logger.warning(
                    f"[slide_generator] Rate limit (429) edit, retry {attempt + 1}/{MAX_RETRIES} "
                    f"через {wait}с..."
                )
                await asyncio.sleep(wait)
            else:
                raise

    # Извлекаем изображение
    new_image_bytes = None
    for part in response.candidates[0].content.parts:
        if hasattr(part, 'inline_data') and part.inline_data and part.inline_data.data:
            new_image_bytes = part.inline_data.data
            break

    if not new_image_bytes:
        raise RuntimeError(f"Vertex AI не вернул изображение при редактировании (модель {model})")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_bytes(new_image_bytes)

    usage = response.usage_metadata
    input_tokens = usage.prompt_token_count if usage else 0
    output_tokens = usage.candidates_token_count if usage else 0
    cost = calculate_nbp_cost(input_tokens, output_tokens, model)

    logger.info(
        f"[slide_generator] Слайд отредактирован: {output_path}, "
        f"tokens={input_tokens}+{output_tokens}, cost=${cost:.4f}"
    )

    return {
        "image_path": output_path,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost,
    }
