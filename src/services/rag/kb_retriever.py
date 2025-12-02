# src/services/rag/kb_retriever.py

from typing import List, Dict, Any, Optional  # Типы для удобства

from src.services.db.kb_repo import kb_search  # Функция поиска по knowledge_base


async def retrieve_kb_snippets(
    *,
    category: str,                 # Тип консультации ('питание растений', 'посадка и уход' и т.п.)
    query_embedding: List[float],  # Эмбеддинг запроса пользователя
    subcategory: Optional[str] = None,         # Культура ('малина', 'голубика' и т.п.) или None
    limit: int = 3,                            # Максимальное количество фрагментов
    distance_threshold: float = 0.35,          # Порог схожести (чем меньше, тем ближе)
) -> List[Dict[str, Any]]:
    """
    Достаёт из базы знаний наиболее похожие фрагменты для заданной категории и, при наличии, культуры.

    Стратегия:
        1) Если subcategory передана:
            - сначала ищем внутри (category, subcategory),
            - если ничего не нашли — делаем fallback-поиск по всей category (subcategory=None).
        2) Если subcategory не передана:
            - ищем по всей category без учёта культуры.
    """
    # 1. Поиск с учётом subcategory (культуры)
    rows = await kb_search(
        category=category,
        subcategory=subcategory,
        query_embedding=query_embedding,
        limit=limit,
        distance_threshold=distance_threshold,
    )

    # Если по конкретной культуре ничего не нашли и культура была указана —
    # пробуем сделать fallback по всей категории (без фильтра по subcategory).
    if not rows and subcategory is not None:
        rows = await kb_search(
            category=category,
            subcategory=None,  # без фильтра по культуре
            query_embedding=query_embedding,
            limit=limit,
            distance_threshold=distance_threshold,
        )

    snippets: List[Dict[str, Any]] = []
    for row in rows:
        snippets.append(
            {
                "id": row["id"],                     # id записи в knowledge_base
                "category": row["category"],         # тип консультации
                "subcategory": row["subcategory"],   # культура
                "question": row["question"],         # пример вопроса
                "answer": row["answer"],             # текст ответа (главное поле)
                "distance": row["distance"],         # расстояние до эмбеддинга запроса
            }
        )

    return snippets
