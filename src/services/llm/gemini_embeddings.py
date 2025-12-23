# src/services/llm/gemini_embeddings.py

"""
Модуль для работы с Google Gemini Embeddings через QueryRouter.

QueryRouter предоставляет OpenAI-совместимый API для доступа к моделям Gemini.
Используем модель google/gemini-embedding-001 — лучшую модель Google 2025:
- 3072 измерений
- 2048 токенов максимум
- 100+ языков включая русский

Base URL: https://api.queryrouter.ru/v1
"""

from typing import List, Tuple, Literal
from openai import AsyncOpenAI

from src.config import settings


# Размерности embeddings
OutputDimensionality = Literal[768, 1536, 3072]

# Модель через QueryRouter
DEFAULT_MODEL = "google/gemini-embedding-001"

# QueryRouter base URL
QUERYROUTER_BASE_URL = "https://api.queryrouter.ru/v1"

# Клиент (lazy initialization)
_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    """Возвращает AsyncOpenAI клиент для QueryRouter."""
    global _client
    if _client is None:
        api_key = settings.queryrouter_api_key
        if not api_key:
            raise ValueError(
                "QUERYROUTER_API_KEY не настроен. "
                "Добавьте QUERYROUTER_API_KEY в .env файл."
            )
        _client = AsyncOpenAI(
            base_url=QUERYROUTER_BASE_URL,
            api_key=api_key,
        )
    return _client


async def get_gemini_embedding(
    text: str,
    output_dimensionality: OutputDimensionality = 3072,
) -> List[float]:
    """
    Получает embedding для одного текста через QueryRouter/Gemini.

    Параметры:
        text: Текст для эмбеддинга
        output_dimensionality: Размерность выходного вектора (не используется в OpenAI API)

    Возвращает:
        List[float] — embedding вектор
    """
    client = _get_client()

    response = await client.embeddings.create(
        model=DEFAULT_MODEL,
        input=text,
    )

    return response.data[0].embedding


async def get_gemini_embedding_with_usage(
    text: str,
    output_dimensionality: OutputDimensionality = 3072,
) -> Tuple[List[float], int, str]:
    """
    Получает embedding для одного текста и возвращает информацию об использовании.

    Возвращает:
        Tuple[embedding, tokens, model_name]
    """
    client = _get_client()

    response = await client.embeddings.create(
        model=DEFAULT_MODEL,
        input=text,
    )

    embedding = response.data[0].embedding
    tokens = response.usage.total_tokens if response.usage else len(text) // 4
    model = response.model

    return embedding, tokens, model


async def get_gemini_batch_embeddings(
    texts: List[str],
    output_dimensionality: OutputDimensionality = 3072,
) -> List[List[float]]:
    """
    Получает embeddings для списка текстов через QueryRouter/Gemini.

    Параметры:
        texts: Список текстов
        output_dimensionality: Размерность (не используется в OpenAI API)

    Возвращает:
        List[List[float]] — список embedding векторов
    """
    if not texts:
        return []

    client = _get_client()

    response = await client.embeddings.create(
        model=DEFAULT_MODEL,
        input=texts,
    )

    # Сортируем по индексу, т.к. API может вернуть в другом порядке
    embeddings = [None] * len(texts)
    for item in response.data:
        embeddings[item.index] = item.embedding

    return embeddings


async def get_gemini_batch_embeddings_with_usage(
    texts: List[str],
    output_dimensionality: OutputDimensionality = 3072,
) -> Tuple[List[List[float]], int, str]:
    """
    Получает embeddings для списка текстов и возвращает информацию об использовании.

    Возвращает:
        Tuple[embeddings, tokens, model_name]
    """
    if not texts:
        return [], 0, DEFAULT_MODEL

    client = _get_client()

    response = await client.embeddings.create(
        model=DEFAULT_MODEL,
        input=texts,
    )

    # Сортируем по индексу
    embeddings = [None] * len(texts)
    for item in response.data:
        embeddings[item.index] = item.embedding

    tokens = response.usage.total_tokens if response.usage else sum(len(t) // 4 for t in texts)
    model = response.model

    return embeddings, tokens, model


# === Специализированные функции для конкретных задач ===

async def get_embedding_for_document(
    text: str,
    output_dimensionality: OutputDimensionality = 3072,
) -> List[float]:
    """
    Embedding для индексации документа в RAG.
    """
    return await get_gemini_embedding(text, output_dimensionality)


async def get_embedding_for_query(
    text: str,
    output_dimensionality: OutputDimensionality = 3072,
) -> List[float]:
    """
    Embedding для поискового запроса пользователя.
    """
    return await get_gemini_embedding(text, output_dimensionality)


async def get_embeddings_for_similarity(
    texts: List[str],
    output_dimensionality: OutputDimensionality = 768,
) -> List[List[float]]:
    """
    Embeddings для сравнения семантической близости текстов (semantic chunking).
    """
    return await get_gemini_batch_embeddings(texts, output_dimensionality)


async def get_embeddings_for_similarity_with_usage(
    texts: List[str],
    output_dimensionality: OutputDimensionality = 768,
) -> Tuple[List[List[float]], int, float]:
    """
    Embeddings для semantic chunking с возвратом статистики.

    Возвращает:
        Tuple[embeddings, tokens, cost_usd]

    Стоимость: $0.15 / 1M tokens (Gemini Embedding)
    """
    embeddings, tokens, _ = await get_gemini_batch_embeddings_with_usage(
        texts, output_dimensionality
    )
    # Gemini Embedding: $0.15 per 1M tokens
    cost_usd = tokens * 0.00000015
    return embeddings, tokens, cost_usd


async def get_batch_embeddings_for_documents(
    texts: List[str],
    output_dimensionality: OutputDimensionality = 3072,
) -> List[List[float]]:
    """
    Batch embeddings для индексации документов в RAG.
    """
    return await get_gemini_batch_embeddings(texts, output_dimensionality)
