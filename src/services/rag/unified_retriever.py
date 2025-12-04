# src/services/rag/unified_retriever.py

"""
Двухуровневый поиск по базе знаний с приоритизацией.

УРОВЕНЬ 1 (высший приоритет): Q&A пары из knowledge_base (управляется через админку)
УРОВЕНЬ 2 (средний приоритет): PDF-документы по культурам

Особенность: делаем ДВА отдельных запроса:
1. Поиск в knowledge_base (Q&A пары) - УРОВЕНЬ 1
2. Поиск в document_chunks по культуре (специфичные или общие) - УРОВЕНЬ 2

Затем объединяем результаты с приоритетом: 1 > 2
"""

from typing import List, Dict, Any, Optional

from src.services.db.kb_repo import kb_search
from src.services.db.document_chunks_repo import chunks_search


def get_general_subcategory(subcategory: Optional[str]) -> Optional[str]:
    """
    Преобразует специфичную подкатегорию в общую.

    Примеры:
        малина ремонтантная → малина общая
        малина летняя → малина общая
        малина общая → малина общая (без изменений)
        клубника ремонтантная → клубника общая
        клубника летняя → клубника общая
        клубника нейтрального дня → клубника общая
        голубика → голубика (без изменений)
        смородина → смородина (без изменений)

    Возвращает:
        Общую подкатегорию или None, если подкатегория не передана
    """
    if not subcategory:
        return None

    GENERAL_MAPPING = {
        # Малина - все типы приводим к "малина общая"
        "малина ремонтантная": "малина общая",
        "малина летняя": "малина общая",
        "малина общая": "малина общая",

        # Клубника - все типы приводим к "клубника общая"
        "клубника ремонтантная": "клубника общая",
        "клубника летняя": "клубника общая",
        "клубника общая": "клубника общая",

        # Остальные культуры - остаются без изменений
        "голубика": "голубика",
        "смородина": "смородина",
        "жимолость": "жимолость",
        "крыжовник": "крыжовник",
        "ежевика": "ежевика",

        # Общая информация
        "общая информация": "общая информация",
    }

    return GENERAL_MAPPING.get(subcategory, subcategory)


async def retrieve_unified_snippets(
    *,
    category: str,
    query_embedding: List[float],
    subcategory: Optional[str] = None,
    qa_limit: int = 2,
    doc_limit: int = 3,  # Документы (специфичные + общие)
    qa_distance_threshold: float = 0.4,
    doc_distance_threshold: float = 0.35,
) -> List[Dict[str, Any]]:
    """
    Двухуровневый поиск фрагментов с приоритизацией.

    Стратегия:
        1. УРОВЕНЬ 1: kb_search() для Q&A пар (высший приоритет)
        2. УРОВЕНЬ 2: chunks_search() для документов по культуре (средний приоритет)
            - Сначала ищем документы по точной культуре (малина ремонтантная)
            - Если не нашли, делаем fallback на общую культуру (малина общая)
        3. Объединяем результаты с сортировкой: уровень приоритета, затем distance

    Параметры:
        category: Тип консультации (СОХРАНЕНО для обратной совместимости, но не используется в chunks_search)
        query_embedding: Эмбеддинг запроса пользователя
        subcategory: Культура (опционально)
        qa_limit: Максимум Q&A фрагментов (УРОВЕНЬ 1, по умолчанию 2)
        doc_limit: Максимум фрагментов документов (УРОВЕНЬ 2, по умолчанию 3)
        qa_distance_threshold: Порог схожести для Q&A (по умолчанию 0.4)
        doc_distance_threshold: Порог схожести для документов (по умолчанию 0.35)

    Возвращает:
        Список словарей с полями:
            - source_type: 'qa' / 'document'
            - priority_level: 1 / 2
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
    # УРОВЕНЬ 2: Документы по культуре (средний приоритет)
    # ============================================================
    if subcategory:
        try:
            print(f"[УРОВЕНЬ 2] Поиск документов по культуре...")
            print(f"  subcategory={subcategory}, limit={doc_limit}, threshold={doc_distance_threshold}")

            # Ищем документы с точной subcategory (например, "малина ремонтантная")
            doc_rows = await chunks_search(
                subcategory=subcategory,
                query_embedding=query_embedding,
                limit=doc_limit,
                distance_threshold=doc_distance_threshold,
            )

            print(f"[УРОВЕНЬ 2] Найдено документов (точная культура): {len(doc_rows)}")

            # Fallback: если не нашли по точной культуре, ищем по общей
            if not doc_rows:
                general_subcategory = get_general_subcategory(subcategory)
                if general_subcategory and general_subcategory != subcategory:
                    print(f"[УРОВЕНЬ 2] Fallback на общую культуру: {general_subcategory}")
                    doc_rows = await chunks_search(
                        subcategory=general_subcategory,
                        query_embedding=query_embedding,
                        limit=doc_limit,
                        distance_threshold=doc_distance_threshold,
                    )
                    print(f"[УРОВЕНЬ 2] Найдено документов (общая культура): {len(doc_rows)}")

            # Преобразуем в единый формат с УРОВНЕМ 2
            for row in doc_rows:
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
    else:
        print(f"[УРОВЕНЬ 2] Пропущен (культура не указана)")

    # ============================================================
    # Сортировка: по priority_level, затем по distance
    # ============================================================
    # Сортируем: сначала по уровню приоритета (1, 2), внутри уровня по distance
    all_snippets.sort(key=lambda x: (x["priority_level"], x["distance"]))

    return all_snippets
