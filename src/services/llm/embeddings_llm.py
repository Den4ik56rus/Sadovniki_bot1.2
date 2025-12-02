# src/services/llm/embeddings_llm.py

from typing import List  # Для аннотации списка чисел (float)

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
