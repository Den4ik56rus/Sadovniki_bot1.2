# src/services/rag/unified_retriever.py

"""
Трёхуровневый поиск по базе знаний с приоритизацией.

УРОВЕНЬ 1 (высший приоритет): Q&A пары из knowledge_base
УРОВЕНЬ 2 (средний приоритет): Специфичные документы (малина_ремонтантная, клубника_летняя и т.п.)
УРОВЕНЬ 3 (низкий приоритет): Общие документы (малина общая, клубника общая)

Особенность: делаем ТРИ отдельных запроса:
1. Поиск в knowledge_base (Q&A пары) - УРОВЕНЬ 1
2. Поиск в document_chunks с точной subcategory (специфичные документы) - УРОВЕНЬ 2
3. Поиск в document_chunks с общей subcategory (общие документы) - УРОВЕНЬ 3

Затем объединяем результаты с приоритетами: 1 > 2 > 3
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
    level2_limit: int = 2,  # Специфичные документы
    level3_limit: int = 2,  # Общие документы
    qa_distance_threshold: float = 0.4,
    doc_distance_threshold: float = 0.35,
) -> List[Dict[str, Any]]:
    """
    Трёхуровневый поиск фрагментов с приоритизацией.

    Стратегия:
        1. УРОВЕНЬ 1: kb_search() для Q&A пар (высший приоритет)
        2. УРОВЕНЬ 2: chunks_search() для специфичных документов (средний приоритет)
        3. УРОВЕНЬ 3: chunks_search() для общих документов (низкий приоритет)
        4. Объединяем результаты с сортировкой: уровень приоритета, затем distance
        5. Применяем two-tier fallback для Q&A

    Параметры:
        category: Тип консультации
        query_embedding: Эмбеддинг запроса пользователя
        subcategory: Культура (опционально)
        qa_limit: Максимум Q&A фрагментов (УРОВЕНЬ 1, по умолчанию 2)
        level2_limit: Максимум специфичных документов (УРОВЕНЬ 2, по умолчанию 2)
        level3_limit: Максимум общих документов (УРОВЕНЬ 3, по умолчанию 2)
        qa_distance_threshold: Порог схожести для Q&A (по умолчанию 0.4)
        doc_distance_threshold: Порог схожести для документов (по умолчанию 0.35)

    Возвращает:
        Список словарей с полями:
            - source_type: 'qa' / 'document_specific' / 'document_general'
            - priority_level: 1 / 2 / 3
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
    # УРОВЕНЬ 2: Специфичные документы (средний приоритет)
    # ============================================================
    if subcategory:
        try:
            print(f"[УРОВЕНЬ 2] Поиск специфичных документов...")
            print(f"  category={category}, subcategory={subcategory}, limit={level2_limit}, threshold={doc_distance_threshold}")

            # Ищем документы с точной subcategory (например, "малина ремонтантная")
            level2_rows = await chunks_search(
                category=category,
                subcategory=subcategory,
                query_embedding=query_embedding,
                limit=level2_limit,
                distance_threshold=doc_distance_threshold,
            )

            print(f"[УРОВЕНЬ 2] Найдено специфичных документов: {len(level2_rows)}")

            # Преобразуем в единый формат с УРОВНЕМ 2
            for row in level2_rows:
                all_snippets.append({
                    "source_type": "document_specific",
                    "priority_level": 2,  # СРЕДНИЙ ПРИОРИТЕТ
                    "content": row["chunk_text"],
                    "distance": row["distance"],
                    "id": row["id"],
                    "document_id": row["document_id"],
                    "page_number": row.get("page_number"),
                    "category": row["category"],
                    "subcategory": row["subcategory"],
                })

        except Exception as e:
            print(f"[retrieve_unified_snippets] УРОВЕНЬ 2 (специфичные документы) search error: {e}")
    else:
        print(f"[УРОВЕНЬ 2] Пропущен (subcategory не указана)")

    # ============================================================
    # УРОВЕНЬ 3: Общие документы (низкий приоритет)
    # ============================================================
    # Определяем общую подкатегорию
    general_subcategory = get_general_subcategory(subcategory)

    print(f"[УРОВЕНЬ 3] Специфичная подкатегория: {subcategory}")
    print(f"[УРОВЕНЬ 3] Общая подкатегория: {general_subcategory}")

    # Ищем только если общая подкатегория отличается от специфичной
    # (иначе получим дублирование с УРОВНЕМ 2)
    if general_subcategory and general_subcategory != subcategory:
        try:
            print(f"[УРОВЕНЬ 3] Поиск общих документов...")
            print(f"  category={category}, subcategory={general_subcategory}, limit={level3_limit}, threshold={doc_distance_threshold}")

            level3_rows = await chunks_search(
                category=category,
                subcategory=general_subcategory,
                query_embedding=query_embedding,
                limit=level3_limit,
                distance_threshold=doc_distance_threshold,
            )

            print(f"[УРОВЕНЬ 3] Найдено общих документов: {len(level3_rows)}")

            # Преобразуем в единый формат с УРОВНЕМ 3
            for row in level3_rows:
                all_snippets.append({
                    "source_type": "document_general",
                    "priority_level": 3,  # НИЗКИЙ ПРИОРИТЕТ
                    "content": row["chunk_text"],
                    "distance": row["distance"],
                    "id": row["id"],
                    "document_id": row["document_id"],
                    "page_number": row.get("page_number"),
                    "category": row["category"],
                    "subcategory": row["subcategory"],
                })

        except Exception as e:
            print(f"[retrieve_unified_snippets] УРОВЕНЬ 3 (общие документы) search error: {e}")
    else:
        print(f"[УРОВЕНЬ 3] Пропущен (общая подкатегория совпадает со специфичной или отсутствует)")

    # ============================================================
    # Сортировка: по priority_level, затем по distance
    # ============================================================
    # Сортируем: сначала по уровню приоритета (1, 2, 3), внутри уровня по distance
    all_snippets.sort(key=lambda x: (x["priority_level"], x["distance"]))

    return all_snippets
