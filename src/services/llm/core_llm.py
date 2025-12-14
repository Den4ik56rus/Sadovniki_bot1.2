# src/services/llm/core_llm.py

import logging
from typing import List, Dict, Any, TypedDict  # Типы для аннотаций
from openai import AsyncOpenAI                  # Асинхронный клиент OpenAI
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
) -> str:
    """
    Выполняет чат-комплишн (диалоговый запрос к модели) и возвращает только текст ответа.

    Параметры:
        messages   — список сообщений (system + user + assistant)
        model      — имя модели (по умолчанию settings.openai_model)
        temperature — параметр "креативности" (None = берём из settings.openai_temperature)

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
    # Добавляем temperature только если он задан (для o1/gpt-5 моделей не передаём)
    if effective_temp is not None:
        kwargs["temperature"] = effective_temp

    # Отправляем запрос к OpenAI
    response = await client.chat.completions.create(**kwargs)

    # Берём первый вариант ответа (choices[0]) и оттуда сам текст
    content = response.choices[0].message.content

    # На всякий случай, если content может быть None — подставим пустую строку
    return content or ""


async def create_chat_completion_with_usage(
    messages: List[Dict[str, Any]],
    model: str | None = None,
    temperature: float | None = None,
) -> ChatCompletionResult:
    """
    Выполняет чат-комплишн и возвращает результат с информацией об использовании токенов.

    Используется для логирования в admin-панели.

    Параметры:
        messages    — список сообщений (system + user + assistant)
        model       — имя модели (по умолчанию settings.openai_model)
        temperature — параметр "креативности" (None = берём из settings.openai_temperature)

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
    # Добавляем temperature только если он задан (для o1/gpt-5 моделей не передаём)
    if effective_temp is not None:
        kwargs["temperature"] = effective_temp

    try:
        logger.info(f"[core_llm] Вызов OpenAI API: model={model_name}, temp={effective_temp}")
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
