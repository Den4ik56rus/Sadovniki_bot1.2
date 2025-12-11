# src/services/llm/embeddings_llm.py

from typing import List, Tuple, Dict, Any

from src.services.llm.core_llm import get_client  # Берём клиента OpenAI
from src.config import settings                   # Настройки (модель эмбеддингов)


async def get_text_embedding(text: str) -> List[float]:
    """
    Считает эмбеддинг для текста с помощью OpenAI.

    Параметры:
        text — произвольная строка (вопрос пользователя, ответ, фрагмент базы знаний).

    Возвращает:
        Список чисел (List[float]) — эмбеддинг.
    """
    # Получаем клиента
    client = get_client()

    # Делаем запрос на получение эмбеддинга
    response = await client.embeddings.create(
        model=settings.openai_embeddings_model,  # Имя модели эмбеддингов
        input=text,                              # Текст, для которого считаем эмбеддинг
    )

    # В ответе может быть несколько эмбеддингов (если подали список),
    # но мы отправляем один текст, значит берём первый элемент.
    embedding = response.data[0].embedding

    # Возвращаем список чисел
    return embedding


async def get_text_embedding_with_usage(text: str) -> Tuple[List[float], int, str]:
    """
    Считает эмбеддинг для текста и возвращает количество токенов и модель.

    Параметры:
        text — произвольная строка.

    Возвращает:
        Tuple[List[float], int, str] — (эмбеддинг, количество токенов, модель).
    """
    client = get_client()

    response = await client.embeddings.create(
        model=settings.openai_embeddings_model,
        input=text,
    )

    embedding = response.data[0].embedding
    tokens = response.usage.total_tokens if response.usage else 0
    model = response.model  # Реальная модель из API

    return embedding, tokens, model


async def get_batch_embeddings_with_usage(texts: List[str]) -> Tuple[List[List[float]], int, str]:
    """
    Считает эмбеддинги для списка текстов за один запрос и возвращает общее количество токенов и модель.

    Параметры:
        texts — список строк.

    Возвращает:
        Tuple[List[List[float]], int, str] — (список эмбеддингов, общее количество токенов, модель).
    """
    if not texts:
        return [], 0, settings.openai_embeddings_model

    client = get_client()

    response = await client.embeddings.create(
        model=settings.openai_embeddings_model,
        input=texts,
    )

    # Сортируем по индексу, т.к. API может вернуть в другом порядке
    embeddings = [None] * len(texts)
    for item in response.data:
        embeddings[item.index] = item.embedding

    tokens = response.usage.total_tokens if response.usage else 0
    model = response.model  # Реальная модель из API

    return embeddings, tokens, model
