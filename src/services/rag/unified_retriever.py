# src/services/rag/unified_retriever.py

"""
Трёхуровневый поиск по базе знаний с приоритизацией.

УРОВЕНЬ 1 (высший приоритет): Q&A пары из knowledge_base (управляется через админку)
    - Фильтрация по category и subcategory
УРОВЕНЬ 1.5 (приоритетные документы): PDF-документы с subcategory='приоритет'
    - Всегда включаются в ответ при наличии релевантных фрагментов
УРОВЕНЬ 2 (средний приоритет): Остальные PDF-документы
    - БЕЗ фильтрации — поиск только по векторному сходству

Затем объединяем результаты с приоритетом: 1 > 1.5 > 2
"""

from typing import List, Dict, Any, Optional

from src.services.db.kb_repo import kb_search
from src.services.db.document_chunks_repo import chunks_search, chunks_search_priority


async def retrieve_unified_snippets(
    *,
    category: str,
    query_embedding: List[float],
    subcategory: Optional[str] = None,
    qa_limit: int = 2,
    doc_limit: int = 5,
    priority_doc_limit: int = 3,
    qa_distance_threshold: float = 0.4,
    doc_distance_threshold: float = 0.35,
) -> List[Dict[str, Any]]:
    """
    Трёхуровневый поиск фрагментов с приоритизацией.

    Стратегия:
        1. УРОВЕНЬ 1: kb_search() для Q&A пар (высший приоритет)
           - Фильтрация по category и subcategory
        2. УРОВЕНЬ 1.5: chunks_search_priority() для приоритетных документов
           - Только документы с subcategory='приоритет'
        3. УРОВЕНЬ 2: chunks_search() для остальных документов (средний приоритет)
           - БЕЗ фильтрации — только векторный поиск
        4. Объединяем результаты с сортировкой: уровень приоритета, затем distance

    Параметры:
        category: Тип консультации (используется для Q&A)
        query_embedding: Эмбеддинг запроса пользователя
        subcategory: Культура (используется для Q&A)
        qa_limit: Максимум Q&A фрагментов (УРОВЕНЬ 1, по умолчанию 2)
        doc_limit: Максимум фрагментов документов (УРОВЕНЬ 2, по умолчанию 5)
        priority_doc_limit: Максимум приоритетных документов (УРОВЕНЬ 1.5, по умолчанию 3)
        qa_distance_threshold: Порог схожести для Q&A (по умолчанию 0.4)
        doc_distance_threshold: Порог схожести для документов (по умолчанию 0.35)

    Возвращает:
        Список словарей с полями:
            - source_type: 'qa' / 'document'
            - priority_level: 1 / 1.5 / 2
            - content: текст фрагмента
            - distance: расстояние до эмбеддинга запроса
            - (другие поля зависят от источника)
    """
    all_snippets: List[Dict[str, Any]] = []

    # ============================================================
    # УРОВЕНЬ 1: Q&A пары из knowledge_base (высший приоритет)
    # ============================================================
    try:
        print(f"[УРОВЕНЬ 1] Поиск Q&A пар...")
        print(f"  category={category}, subcategory={subcategory}, limit={qa_limit}, threshold={qa_distance_threshold}")

        qa_rows = await kb_search(
            category=category,
            subcategory=subcategory,
            query_embedding=query_embedding,
            limit=qa_limit,
            distance_threshold=qa_distance_threshold,
        )

        print(f"[УРОВЕНЬ 1] Найдено Q&A: {len(qa_rows)}")

        # Fallback: если с subcategory ничего не нашли — ищем по всей категории
        if not qa_rows and subcategory is not None:
            print(f"[УРОВЕНЬ 1] Fallback: ищем Q&A без subcategory...")
            qa_rows = await kb_search(
                category=category,
                subcategory=None,
                query_embedding=query_embedding,
                limit=qa_limit,
                distance_threshold=qa_distance_threshold,
            )
            print(f"[УРОВЕНЬ 1] Найдено Q&A (fallback): {len(qa_rows)}")

        # Преобразуем в единый формат с УРОВНЕМ 1
        for row in qa_rows:
            all_snippets.append({
                "source_type": "qa",
                "priority_level": 1,  # ВЫСШИЙ ПРИОРИТЕТ
                "content": row["answer"],
                "distance": row["distance"],
                "id": row["id"],
                "category": row["category"],
                "subcategory": row["subcategory"],
                "question": row.get("question"),
            })

    except Exception as e:
        print(f"[retrieve_unified_snippets] УРОВЕНЬ 1 (Q&A) search error: {e}")

    # ============================================================
    # УРОВЕНЬ 1.5: Приоритетные документы (subcategory='приоритет')
    # ============================================================
    try:
        print(f"[УРОВЕНЬ 1.5] Поиск приоритетных документов...")
        print(f"  limit={priority_doc_limit}, threshold={doc_distance_threshold}")

        priority_rows = await chunks_search_priority(
            query_embedding=query_embedding,
            limit=priority_doc_limit,
            distance_threshold=doc_distance_threshold,
        )

        print(f"[УРОВЕНЬ 1.5] Найдено приоритетных документов: {len(priority_rows)}")

        # Преобразуем в единый формат с УРОВНЕМ 1.5
        for row in priority_rows:
            all_snippets.append({
                "source_type": "document",
                "priority_level": 1.5,  # ПРИОРИТЕТНЫЕ ДОКУМЕНТЫ
                "content": row["chunk_text"],
                "distance": row["distance"],
                "id": row["id"],
                "document_id": row["document_id"],
                "page_number": row.get("page_number"),
                "subcategory": row["subcategory"],
            })

    except Exception as e:
        print(f"[retrieve_unified_snippets] УРОВЕНЬ 1.5 (приоритетные документы) search error: {e}")

    # ============================================================
    # УРОВЕНЬ 2: Остальные документы (средний приоритет)
    # ============================================================
    try:
        print(f"[УРОВЕНЬ 2] Поиск документов по векторному сходству...")
        print(f"  limit={doc_limit}, threshold={doc_distance_threshold}")

        doc_rows = await chunks_search(
            query_embedding=query_embedding,
            limit=doc_limit,
            distance_threshold=doc_distance_threshold,
        )

        print(f"[УРОВЕНЬ 2] Найдено документов: {len(doc_rows)}")

        # Преобразуем в единый формат с УРОВНЕМ 2
        # Исключаем приоритетные документы (они уже добавлены в УРОВНЕ 1.5)
        for row in doc_rows:
            if row["subcategory"] == "приоритет":
                continue  # Уже добавлены на уровне 1.5

            all_snippets.append({
                "source_type": "document",
                "priority_level": 2,  # СРЕДНИЙ ПРИОРИТЕТ
                "content": row["chunk_text"],
                "distance": row["distance"],
                "id": row["id"],
                "document_id": row["document_id"],
                "page_number": row.get("page_number"),
                "subcategory": row["subcategory"],
            })

    except Exception as e:
        print(f"[retrieve_unified_snippets] УРОВЕНЬ 2 (документы) search error: {e}")

    # ============================================================
    # Сортировка: по priority_level, затем по distance
    # ============================================================
    # Сортируем: сначала по уровню приоритета (1, 1.5, 2), внутри уровня по distance
    all_snippets.sort(key=lambda x: (x["priority_level"], x["distance"]))

    return all_snippets
