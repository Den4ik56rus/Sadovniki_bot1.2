# src/services/llm/core_llm.py

from typing import List, Dict, Any, TypedDict  # Типы для аннотаций
from openai import AsyncOpenAI                  # Асинхронный клиент OpenAI

from src.config import settings                 # Берём настройки проекта (ключи, модели)


# Создаём один экземпляр клиента OpenAI.
# Он будет переиспользоваться во всех запросах.
_client = AsyncOpenAI(
    api_key=settings.openai_api_key  # Секретный API-ключ OpenAI из конфига
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
    temperature: float = 0.3,        # "Креативность" ответа (0–1)
) -> str:
    """
    Выполняет чат-комплишн (диалоговый запрос к модели) и возвращает только текст ответа.

    Параметры:
        messages   — список сообщений (system + user + assistant)
        model      — имя модели (по умолчанию settings.openai_model)
        temperature — параметр "креативности"

    Возвращает:
        Строку с ответом ассистента.
    """
    # Выбираем модель: либо явно заданную, либо из настроек
    model_name = model or settings.openai_model

    # Получаем клиента
    client = get_client()

    # Отправляем запрос к OpenAI
    response = await client.chat.completions.create(
        model=model_name,         # Имя модели
        messages=messages,        # Контекст диалога
        temperature=temperature,  # Насколько вариативный ответ
    )

    # Берём первый вариант ответа (choices[0]) и оттуда сам текст
    content = response.choices[0].message.content

    # На всякий случай, если content может быть None — подставим пустую строку
    return content or ""


async def create_chat_completion_with_usage(
    messages: List[Dict[str, Any]],
    model: str | None = None,
    temperature: float = 0.3,
) -> ChatCompletionResult:
    """
    Выполняет чат-комплишн и возвращает результат с информацией об использовании токенов.

    Используется для логирования в admin-панели.

    Параметры:
        messages    — список сообщений (system + user + assistant)
        model       — имя модели (по умолчанию settings.openai_model)
        temperature — параметр "креативности"

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

    response = await client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=temperature,
    )

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
