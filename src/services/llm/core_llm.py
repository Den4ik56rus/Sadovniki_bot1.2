# src/services/llm/core_llm.py

import asyncio
import logging
from typing import List, Dict, Any, TypedDict, Optional, Callable, Awaitable  # Типы для аннотаций
from openai import AsyncOpenAI, APIConnectionError, APITimeoutError  # Асинхронный клиент OpenAI + ошибки
import httpx                                     # Для кастомного таймаута

from src.config import settings                 # Берём настройки проекта (ключи, модели)

logger = logging.getLogger(__name__)

# Увеличенный таймаут для reasoning моделей (gpt-5.x, o1, o3)
# Reasoning модели могут думать дольше обычных — особенно при генерации статей
REASONING_TIMEOUT = httpx.Timeout(
    connect=60.0,    # Таймаут на подключение (сек)
    read=600.0,      # Таймаут на чтение ответа (10 минут для reasoning статей)
    write=60.0,      # Таймаут на запись
    pool=60.0,       # Таймаут на получение соединения из пула
)

# Создаём один экземпляр клиента OpenAI.
# Он будет переиспользоваться во всех запросах.
_client = AsyncOpenAI(
    api_key=settings.openai_api_key,  # Секретный API-ключ OpenAI из конфига
    timeout=REASONING_TIMEOUT,         # Увеличенный таймаут для reasoning моделей
    max_retries=3,                     # Автоматический retry при connection errors (по умолчанию 2)
)


def get_client() -> AsyncOpenAI:
    """
    Возвращает асинхронного клиента OpenAI.

    Нужен, чтобы в других модулях не импортировать _client напрямую,
    а пользоваться функцией (легче потом подменять/тестировать).
    """
    return _client  # Просто отдаём уже созданный клиент


class ChatCompletionResult(TypedDict):
    """Результат вызова LLM с информацией об использовании токенов."""
    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str


async def create_chat_completion(
    messages: List[Dict[str, Any]],  # Список сообщений формата {'role': 'user'/'assistant'/'system', 'content': '...'}
    model: str | None = None,        # Какую модель использовать; если None — берём из настроек
    temperature: float | None = None,  # "Креативность" ответа (None = из settings или не передавать)
    reasoning_effort: str | None = None,  # Уровень reasoning: low/medium/high (None = обычный режим)
) -> str:
    """
    Выполняет чат-комплишн (диалоговый запрос к модели) и возвращает только текст ответа.

    Параметры:
        messages         — список сообщений (system + user + assistant)
        model            — имя модели (по умолчанию settings.openai_model)
        temperature      — параметр "креативности" (None = берём из settings.openai_temperature)
        reasoning_effort — уровень reasoning для gpt-5.1+ (None = обычный режим без reasoning)

    Возвращает:
        Строку с ответом ассистента.
    """
    # Выбираем модель: либо явно заданную, либо из настроек
    model_name = model or settings.openai_model

    # Получаем клиента
    client = get_client()

    # Определяем temperature: явно заданный > из settings > не передавать
    effective_temp = temperature if temperature is not None else settings.openai_temperature

    # Формируем параметры запроса
    kwargs: Dict[str, Any] = {
        "model": model_name,
        "messages": messages,
    }

    # reasoning_effort и temperature взаимоисключающие:
    # если включен reasoning (low/medium/high) — temperature не передаём
    if reasoning_effort and reasoning_effort in ("low", "medium", "high"):
        kwargs["reasoning_effort"] = reasoning_effort
    elif effective_temp is not None:
        kwargs["temperature"] = effective_temp

    # Отправляем запрос к OpenAI
    try:
        response = await client.chat.completions.create(**kwargs)
    except Exception as e:
        logger.error(f"[core_llm] Ошибка в create_chat_completion: {type(e).__name__}: {e}")
        raise

    # Берём первый вариант ответа (choices[0]) и оттуда сам текст
    content = response.choices[0].message.content

    # На всякий случай, если content может быть None — подставим пустую строку
    return content or ""


async def create_chat_completion_with_usage(
    messages: List[Dict[str, Any]],
    model: str | None = None,
    temperature: float | None = None,
    reasoning_effort: str | None = None,
) -> ChatCompletionResult:
    """
    Выполняет чат-комплишн и возвращает результат с информацией об использовании токенов.

    Используется для логирования в admin-панели.

    Параметры:
        messages         — список сообщений (system + user + assistant)
        model            — имя модели (по умолчанию settings.openai_model)
        temperature      — параметр "креативности" (None = берём из settings.openai_temperature)
        reasoning_effort — уровень reasoning для gpt-5.1+ (None = обычный режим без reasoning)

    Возвращает:
        ChatCompletionResult с полями:
            - content: текст ответа
            - prompt_tokens: токены промпта
            - completion_tokens: токены ответа
            - total_tokens: всего токенов
            - model: использованная модель
    """
    model_name = model or settings.openai_model
    client = get_client()

    # Определяем temperature: явно заданный > из settings > не передавать
    effective_temp = temperature if temperature is not None else settings.openai_temperature

    # Формируем параметры запроса
    kwargs: Dict[str, Any] = {
        "model": model_name,
        "messages": messages,
    }

    # reasoning_effort и temperature взаимоисключающие:
    # если включен reasoning (low/medium/high) — temperature не передаём
    if reasoning_effort and reasoning_effort in ("low", "medium", "high"):
        kwargs["reasoning_effort"] = reasoning_effort
    elif effective_temp is not None:
        kwargs["temperature"] = effective_temp

    try:
        logger.info(f"[core_llm] Вызов OpenAI API: model={model_name}, temp={effective_temp}, reasoning={reasoning_effort}")
        response = await client.chat.completions.create(**kwargs)
    except Exception as e:
        # Детальное логирование ошибки
        error_type = type(e).__name__
        error_msg = str(e)
        logger.error(f"[core_llm] Ошибка OpenAI API: {error_type}: {error_msg}")
        logger.error(f"[core_llm] Модель: {model_name}, Temperature: {effective_temp}")

        # Проверяем типичные ошибки
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            logger.error("[core_llm] Причина: Таймаут — модель думает слишком долго")
        elif "connection" in error_msg.lower():
            logger.error("[core_llm] Причина: Проблема с подключением к OpenAI API")
        elif "401" in error_msg or "unauthorized" in error_msg.lower():
            logger.error("[core_llm] Причина: Неверный API-ключ")
        elif "model" in error_msg.lower() and "not found" in error_msg.lower():
            logger.error(f"[core_llm] Причина: Модель {model_name} не найдена или недоступна")
        elif "temperature" in error_msg.lower():
            logger.error("[core_llm] Причина: Модель не поддерживает temperature (reasoning модель)")

        raise

    content = response.choices[0].message.content
    usage = response.usage

    return {
        "content": content or "",
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
        "total_tokens": usage.total_tokens if usage else 0,
        "model": model_name,
    }


async def create_chat_completion_with_retry(
    messages: List[Dict[str, Any]],
    model: str | None = None,
    temperature: float | None = None,
    reasoning_effort: str | None = None,
    max_attempts: int = 2,
    base_delay: float = 5.0,
) -> ChatCompletionResult:
    """
    Обёртка над create_chat_completion_with_usage с application-level retry.

    SDK уже делает max_retries=3 на уровне HTTP. Эта функция добавляет
    ещё один уровень retry с экспоненциальным backoff для критических путей
    (консультации пользователя).

    Повторяет только APIConnectionError и APITimeoutError.
    """
    last_exception = None
    for attempt in range(max_attempts):
        try:
            return await create_chat_completion_with_usage(
                messages=messages,
                model=model,
                temperature=temperature,
                reasoning_effort=reasoning_effort,
            )
        except (APIConnectionError, APITimeoutError) as e:
            last_exception = e
            if attempt < max_attempts - 1:
                delay = base_delay * (2 ** attempt)  # 5s, 10s
                logger.warning(
                    f"[core_llm] Retry {attempt + 1}/{max_attempts} после "
                    f"{type(e).__name__}, ожидание {delay}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"[core_llm] Все {max_attempts} попыток неудачны: "
                    f"{type(e).__name__}: {e}"
                )
    raise last_exception


async def create_chat_completion_streaming(
    messages: List[Dict[str, Any]],
    model: str | None = None,
    temperature: float | None = None,
    reasoning_effort: str | None = None,
    on_chunk: Optional[Callable[[str], Awaitable[None]]] = None,
    max_attempts: int = 2,
    base_delay: float = 5.0,
) -> ChatCompletionResult:
    """
    Стриминг чат-комплишн с callback на каждый чанк и retry-логикой.

    Параметры:
        on_chunk — callback, вызывается с накопленным текстом при каждом новом чанке.
        Остальные параметры — как в create_chat_completion_with_retry.

    Возвращает:
        ChatCompletionResult с полными данными о токенах (из финального чанка).
    """
    model_name = model or settings.openai_model
    client = get_client()

    effective_temp = temperature if temperature is not None else settings.openai_temperature

    kwargs: Dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    if reasoning_effort and reasoning_effort in ("low", "medium", "high"):
        kwargs["reasoning_effort"] = reasoning_effort
    elif effective_temp is not None:
        kwargs["temperature"] = effective_temp

    last_exception = None
    for attempt in range(max_attempts):
        try:
            logger.info(f"[core_llm] Streaming вызов OpenAI API: model={model_name}, attempt={attempt + 1}")
            accumulated = ""
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0

            stream = await client.chat.completions.create(**kwargs)

            async for chunk in stream:
                # Извлекаем usage из финального чанка
                if chunk.usage:
                    prompt_tokens = chunk.usage.prompt_tokens
                    completion_tokens = chunk.usage.completion_tokens
                    total_tokens = chunk.usage.total_tokens

                # Извлекаем дельту текста
                if chunk.choices and chunk.choices[0].delta.content:
                    accumulated += chunk.choices[0].delta.content
                    if on_chunk:
                        try:
                            await on_chunk(accumulated)
                        except Exception:
                            pass  # Ошибки callback не должны ломать стрим

            return {
                "content": accumulated or "",
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "model": model_name,
            }

        except (APIConnectionError, APITimeoutError) as e:
            last_exception = e
            if attempt < max_attempts - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    f"[core_llm] Streaming retry {attempt + 1}/{max_attempts} после "
                    f"{type(e).__name__}, ожидание {delay}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"[core_llm] Все {max_attempts} streaming попыток неудачны: "
                    f"{type(e).__name__}: {e}"
                )

    raise last_exception


def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """
    Рассчитывает стоимость запроса в USD по ценам OpenAI (декабрь 2025).

    Цены (за 1M токенов):
        - gpt-4o: $2.50 input, $10.00 output
        - gpt-4o-mini: $0.15 input, $0.60 output
        - gpt-4.1-mini: $0.15 input, $0.60 output (алиас для gpt-4o-mini)
        - gpt-5-mini: $0.25 input, $2.00 output
        - gpt-5.1: $1.25 input, $10.00 output
        - gpt-4-turbo: $10 input, $30 output
    """
    pricing = {
        # GPT-4o (актуальные цены декабрь 2025)
        "gpt-4o": {"input": 2.50, "output": 10.0},
        "gpt-4o-2024-11-20": {"input": 2.50, "output": 10.0},
        "gpt-4o-2024-08-06": {"input": 2.50, "output": 10.0},
        # GPT-4o-mini (самая дешёвая модель)
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o-mini-2024-07-18": {"input": 0.15, "output": 0.60},
        "gpt-4.1-mini": {"input": 0.15, "output": 0.60},  # Алиас
        # GPT-5 серия
        "gpt-5-mini": {"input": 0.25, "output": 2.0},
        "gpt-5.1": {"input": 1.25, "output": 10.0},
        # Старые модели
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "gpt-4": {"input": 30.0, "output": 60.0},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    }

    # Fallback на gpt-4o-mini если модель не найдена
    rates = pricing.get(model, pricing["gpt-4o-mini"])
    input_cost = (prompt_tokens / 1_000_000) * rates["input"]
    output_cost = (completion_tokens / 1_000_000) * rates["output"]

    return input_cost + output_cost


# Цены embeddings (USD за 1M токенов)
EMBEDDING_PRICING = {
    "text-embedding-3-small": 0.02,   # $0.02/1M tokens
    "text-embedding-3-large": 0.13,   # $0.13/1M tokens
    "text-embedding-ada-002": 0.10,   # $0.10/1M tokens
}


def calculate_embedding_cost(model: str, tokens: int) -> float:
    """
    Рассчитывает стоимость embeddings в USD.

    Параметры:
        model  — название модели embeddings (из response.model)
        tokens — количество токенов

    Возвращает:
        Стоимость в USD.
    """
    rate = EMBEDDING_PRICING.get(model, EMBEDDING_PRICING["text-embedding-3-small"])
    return (tokens / 1_000_000) * rate
