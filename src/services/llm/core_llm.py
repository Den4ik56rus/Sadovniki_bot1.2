# src/services/llm/core_llm.py

from typing import List, Dict, Any  # Типы для аннотаций
from openai import AsyncOpenAI       # Асинхронный клиент OpenAI

from src.config import settings      # Берём настройки проекта (ключи, модели)


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
