# src/services/db/document_chunks_repo.py

from typing import List, Dict, Optional
from src.services.db.pool import get_pool


# Размерность вектора (фиксированная для OpenAI embeddings)
VECTOR_DIM = 1536  # text-embedding-3-small


def assemble_chunk_text(chunk: Dict) -> str:
    """
    Собирает полный текст чанка: prefix + context + chunk_text.

    Это единственная точка сборки — используется для:
    - генерации эмбеддингов (embed_document)
    - передачи контекста в LLM (RAG retrieval)
    - отображения в админке (API endpoint)
    """
    parts = []
    prefix = chunk.get("prefix")
    context = chunk.get("context")
    chunk_text = chunk.get("chunk_text", "")

    if prefix:
        parts.append(prefix)
    if context:
        parts.append(context)
    parts.append(chunk_text)
    return "\n".join(parts)


def _normalize_embedding(embedding: List[float]) -> List[float]:
    """
    Приводит эмбеддинг к размерности VECTOR_DIM.
    """
    if embedding is None:
        return [0.0] * VECTOR_DIM

    emb = list(embedding)
    n = len(emb)

    if n == VECTOR_DIM:
        return emb
    elif n > VECTOR_DIM:
        return emb[:VECTOR_DIM]
    else:
        return emb + [0.0] * (VECTOR_DIM - n)


async def chunks_bulk_insert(chunks: List[Dict]) -> None:
    """
    Массовая вставка чанков в таблицу document_chunks.

    Параметры:
        chunks: Список словарей с полями:
            - document_id: int
            - chunk_index: int
            - chunk_text: str
            - chunk_size: int
            - page_number: Optional[int]
            - embedding: List[float]
            - category: str
            - subcategory: Optional[str]
    """
    if not chunks:
        return

    pool = get_pool()

    # Подготовка данных для вставки
    records = []
    for chunk in chunks:
        norm_embedding = _normalize_embedding(chunk["embedding"])
        vector_str = "[" + ",".join(f"{x:.6f}" for x in norm_embedding) + "]"

        records.append((
            chunk["document_id"],
            chunk["chunk_index"],
            chunk["chunk_text"],
            chunk["chunk_size"],
            chunk.get("page_number"),
            vector_str,
            chunk["category"],
            chunk.get("subcategory"),
        ))

    async with pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO document_chunks (
                document_id,
                chunk_index,
                chunk_text,
                chunk_size,
                page_number,
                embedding,
                category,
                subcategory
            )
            VALUES ($1, $2, $3, $4, $5, $6::vector, $7, $8);
            """,
            records
        )


async def chunks_search(
    *,
    query_embedding: List[float],
    limit: int = 5,
    distance_threshold: Optional[float] = 0.35,
):
    """
    Поиск похожих фрагментов документов по эмбеддингу.

    Поиск по всем документам без фильтрации по категории/культуре.
    Релевантность определяется только векторным сходством.

    Возвращает список записей с полями:
        - id, document_id, chunk_text, page_number, distance, subcategory
    """
    pool = get_pool()

    norm_embedding = _normalize_embedding(query_embedding)
    vector_str = "[" + ",".join(f"{x:.6f}" for x in norm_embedding) + "]"

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                c.id,
                c.document_id,
                c.chunk_text,
                c.prefix,
                c.context,
                c.page_number,
                c.subcategory,
                c.embedding <=> $1::vector AS distance
            FROM document_chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE c.is_active = TRUE
              AND d.is_active = TRUE
            ORDER BY c.embedding <=> $1::vector
            LIMIT $2;
            """,
            vector_str,
            limit,
        )

    # Фильтрация по distance_threshold
    if distance_threshold is not None:
        rows = [r for r in rows if r["distance"] <= distance_threshold]

    return rows


async def chunks_search_priority(
    *,
    query_embedding: List[float],
    limit: int = 3,
    distance_threshold: Optional[float] = 0.35,
):
    """
    Поиск похожих фрагментов из ПРИОРИТЕТНЫХ документов (subcategory='приоритет').

    Возвращает список записей с полями:
        - id, document_id, chunk_text, page_number, distance, subcategory
    """
    pool = get_pool()

    norm_embedding = _normalize_embedding(query_embedding)
    vector_str = "[" + ",".join(f"{x:.6f}" for x in norm_embedding) + "]"

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                c.id,
                c.document_id,
                c.chunk_text,
                c.prefix,
                c.context,
                c.page_number,
                c.subcategory,
                c.embedding <=> $1::vector AS distance
            FROM document_chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE c.is_active = TRUE
              AND d.is_active = TRUE
              AND c.subcategory = 'приоритет'
            ORDER BY c.embedding <=> $1::vector
            LIMIT $2;
            """,
            vector_str,
            limit,
        )

    # Фильтрация по distance_threshold
    if distance_threshold is not None:
        rows = [r for r in rows if r["distance"] <= distance_threshold]

    return rows


async def chunks_search_all(
    *,
    query_embedding: List[float],
    limit: int = 5,
    distance_threshold: Optional[float] = 0.35,
):
    """
    Поиск похожих фрагментов документов БЕЗ фильтрации по subcategory.
    Используется в режиме написания статей для администратора.

    Идентичен chunks_search(), но явно указано назначение.

    Возвращает список записей с полями:
        - id, document_id, chunk_text, page_number, distance, subcategory
    """
    # Просто вызываем chunks_search, так как она уже ищет по всем документам
    return await chunks_search(
        query_embedding=query_embedding,
        limit=limit,
        distance_threshold=distance_threshold,
    )


async def chunks_search_priority_all(
    *,
    query_embedding: List[float],
    limit: int = 3,
    distance_threshold: Optional[float] = 0.35,
):
    """
    Поиск приоритетных chunks БЕЗ фильтрации (только subcategory='приоритет').
    Используется в режиме написания статей для администратора.

    Идентичен chunks_search_priority(), но явно указано назначение.

    Возвращает список записей с полями:
        - id, document_id, chunk_text, page_number, distance, subcategory
    """
    # Просто вызываем chunks_search_priority, так как она уже ищет без фильтрации
    return await chunks_search_priority(
        query_embedding=query_embedding,
        limit=limit,
        distance_threshold=distance_threshold,
    )


async def chunks_bulk_insert_without_embedding(chunks: List[Dict]) -> None:
    """
    Массовая вставка чанков БЕЗ embeddings (для двухэтапной обработки).

    Чанки вставляются с NULL embedding — embeddings добавляются позже
    через bulk_update_chunk_embeddings().

    Параметры:
        chunks: Список словарей с полями:
            - document_id: int
            - chunk_index: int
            - chunk_text: str
            - chunk_size: int
            - page_number: Optional[int]
            - category: str
            - subcategory: Optional[str]
    """
    if not chunks:
        return

    pool = get_pool()

    records = []
    for chunk in chunks:
        records.append((
            chunk["document_id"],
            chunk["chunk_index"],
            chunk["chunk_text"],
            chunk["chunk_size"],
            chunk.get("page_number"),
            chunk["category"],
            chunk.get("subcategory"),
        ))

    async with pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO document_chunks (
                document_id,
                chunk_index,
                chunk_text,
                chunk_size,
                page_number,
                category,
                subcategory
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7);
            """,
            records
        )


async def bulk_update_chunk_embeddings(updates: List[Dict]) -> int:
    """
    Массовое обновление embeddings для чанков.

    Используется на втором этапе обработки после паспортизации.

    Параметры:
        updates: Список словарей с полями:
            - chunk_id: int
            - embedding: List[float]

    Возвращает количество обновлённых записей.
    """
    if not updates:
        return 0

    pool = get_pool()
    count = 0

    async with pool.acquire() as conn:
        for update in updates:
            norm_embedding = _normalize_embedding(update["embedding"])
            vector_str = "[" + ",".join(f"{x:.6f}" for x in norm_embedding) + "]"

            result = await conn.execute(
                """
                UPDATE document_chunks
                SET embedding = $2::vector
                WHERE id = $1;
                """,
                update["chunk_id"],
                vector_str,
            )
            if result == "UPDATE 1":
                count += 1

    return count


async def chunks_count_by_document(document_id: int) -> int:
    """
    Возвращает количество чанков для документа.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT COUNT(*) as count
            FROM document_chunks
            WHERE document_id = $1;
            """,
            document_id,
        )

    return row["count"] if row else 0


# ============================================
# RAG v2.0: Функции паспортизации чанков
# ============================================

async def get_chunks_by_document(document_id: int) -> List[Dict]:
    """
    Получить все чанки документа с данными паспорта.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id,
                document_id,
                chunk_index,
                chunk_text,
                chunk_size,
                page_number,
                cultures,
                culture_subtypes,
                goals,
                growth_phases,
                prefix,
                context,
                is_active,
                created_at
            FROM document_chunks
            WHERE document_id = $1
            ORDER BY chunk_index ASC;
            """,
            document_id,
        )

    return [dict(r) for r in rows]


async def get_chunk_by_id(chunk_id: int) -> Optional[Dict]:
    """
    Получить чанк по ID.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                id,
                document_id,
                chunk_index,
                chunk_text,
                chunk_size,
                page_number,
                cultures,
                culture_subtypes,
                goals,
                growth_phases,
                prefix,
                context,
                is_active,
                created_at
            FROM document_chunks
            WHERE id = $1;
            """,
            chunk_id,
        )

    return dict(row) if row else None


def generate_prefix(
    cultures: Optional[List[str]],
    culture_subtypes: Optional[Dict],
    goals: Optional[List[str]],
    growth_phases: Optional[List[str]],
) -> str:
    """
    Генерирует prefix (служебную шапку) для чанка на основе паспорта.

    Пример: [Культуры: малина (ремонтантная), клубника (летняя)][Цели: питание, защита][Фазы: весна]

    Поддерживает массивы значений и подтипы для каждой культуры.
    """
    parts = []
    subtypes = culture_subtypes or {}

    all_cultures = cultures or []
    all_goals = goals or []
    all_phases = growth_phases or []

    filtered_cultures = [c for c in all_cultures if c and c != 'общая']
    filtered_goals = [g for g in all_goals if g and g != 'общая']
    filtered_phases = [p for p in all_phases if p and p != 'общая']

    # Культуры
    if filtered_cultures:
        culture_parts = []
        for culture in filtered_cultures:
            subtype = subtypes.get(culture)
            if subtype and subtype != 'общая':
                culture_parts.append(f"{culture} ({subtype})")
            else:
                culture_parts.append(culture)
        label = "Культура" if len(filtered_cultures) == 1 else "Культуры"
        parts.append(f"[{label}: {', '.join(culture_parts)}]")
    elif 'общая' in all_cultures:
        parts.append("[Подходит ко всем культурам]")

    # Цели
    if filtered_goals:
        label = "Цель" if len(filtered_goals) == 1 else "Цели"
        parts.append(f"[{label}: {', '.join(filtered_goals)}]")
    elif 'общая' in all_goals:
        parts.append("[Подходит ко всем типам работ]")

    # Фазы
    if filtered_phases:
        label = "Фаза" if len(filtered_phases) == 1 else "Фазы"
        parts.append(f"[{label}: {', '.join(filtered_phases)}]")
    elif 'общая' in all_phases:
        parts.append("[Подходит ко всем фазам роста]")

    return " ".join(parts) if parts else ""


async def update_chunk_passport(
    chunk_id: int,
    cultures: Optional[List[str]],
    culture_subtypes: Optional[Dict],
    goals: Optional[List[str]],
    growth_phases: Optional[List[str]],
    chunk_text: Optional[str] = None,
    context: Optional[str] = None,
) -> Optional[Dict]:
    """
    Обновить паспорт чанка и сгенерировать prefix.

    Поддерживает:
    - Массивы культур, целей, фаз роста
    - Словарь подтипов для каждой культуры
    - Опциональное обновление текста чанка и контекста
    """
    pool = get_pool()

    # Генерируем prefix
    prefix = generate_prefix(cultures, culture_subtypes, goals, growth_phases)

    async with pool.acquire() as conn:
        # Строим динамический запрос
        set_parts = [
            "cultures = $2",
            "culture_subtypes = $3",
            "goals = $4",
            "growth_phases = $5",
            "prefix = $6",
        ]
        params = [chunk_id, cultures or [], culture_subtypes or {}, goals or [], growth_phases or [], prefix]
        param_idx = 7

        if chunk_text is not None:
            set_parts.append(f"chunk_text = ${param_idx}")
            params.append(chunk_text)
            param_idx += 1
            # Обновляем chunk_size при изменении текста
            set_parts.append(f"chunk_size = ${param_idx}")
            params.append(len(chunk_text))
            param_idx += 1

        if context is not None:
            set_parts.append(f"context = ${param_idx}")
            params.append(context)
            param_idx += 1

        query = f"""
            UPDATE document_chunks
            SET {', '.join(set_parts)}
            WHERE id = $1
            RETURNING
                id,
                document_id,
                chunk_index,
                chunk_text,
                chunk_size,
                page_number,
                cultures,
                culture_subtypes,
                goals,
                growth_phases,
                prefix,
                context,
                is_active,
                created_at;
        """

        row = await conn.fetchrow(query, *params)

    return dict(row) if row else None


async def update_chunk_context(chunk_id: int, context: str) -> Optional[Dict]:
    """
    Обновить LLM-сгенерированный контекст чанка.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE document_chunks
            SET context = $2
            WHERE id = $1
            RETURNING
                id,
                document_id,
                chunk_index,
                chunk_text,
                chunk_size,
                page_number,
                culture,
                culture_subtype,
                goal,
                growth_phase,
                prefix,
                context,
                is_active,
                created_at;
            """,
            chunk_id,
            context,
        )

    return dict(row) if row else None


async def bulk_update_chunk_contexts(updates: List[Dict]) -> int:
    """
    Массовое обновление контекстов чанков.

    Параметры:
        updates: Список словарей с полями:
            - chunk_id: int
            - context: str

    Возвращает количество обновлённых записей.
    """
    if not updates:
        return 0

    pool = get_pool()
    count = 0

    async with pool.acquire() as conn:
        for update in updates:
            result = await conn.execute(
                """
                UPDATE document_chunks
                SET context = $2
                WHERE id = $1;
                """,
                update["chunk_id"],
                update["context"],
            )
            if result == "UPDATE 1":
                count += 1

    return count


async def get_passport_options() -> Dict:
    """
    Получить все справочные данные для выпадающих списков паспорта.

    Возвращает:
        {
            "cultures": [{"id": 1, "name": "малина"}, ...],
            "subtypes": {1: [{"id": 1, "name": "ремонтантная"}, ...], ...},
            "goals": [{"id": 1, "name": "питание"}, ...],
            "phases": [{"id": 1, "name": "весна"}, ...]
        }
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        # Культуры
        cultures_rows = await conn.fetch(
            """
            SELECT id, name
            FROM passport_cultures
            ORDER BY sort_order, name;
            """
        )

        # Подтипы
        subtypes_rows = await conn.fetch(
            """
            SELECT id, culture_id, name
            FROM passport_subtypes
            ORDER BY sort_order, name;
            """
        )

        # Цели
        goals_rows = await conn.fetch(
            """
            SELECT id, name
            FROM passport_goals
            ORDER BY sort_order, name;
            """
        )

        # Фазы
        phases_rows = await conn.fetch(
            """
            SELECT id, name
            FROM passport_phases
            ORDER BY sort_order, name;
            """
        )

    # Формируем результат
    cultures = [{"id": r["id"], "name": r["name"]} for r in cultures_rows]

    # Группируем подтипы по culture_id
    subtypes: Dict[int, List[Dict]] = {}
    for r in subtypes_rows:
        culture_id = r["culture_id"]
        if culture_id not in subtypes:
            subtypes[culture_id] = []
        subtypes[culture_id].append({"id": r["id"], "name": r["name"]})

    goals = [{"id": r["id"], "name": r["name"]} for r in goals_rows]
    phases = [{"id": r["id"], "name": r["name"]} for r in phases_rows]

    return {
        "cultures": cultures,
        "subtypes": subtypes,
        "goals": goals,
        "phases": phases,
    }


async def get_passported_chunks_count(document_id: int) -> int:
    """
    Получить количество чанков с заполненным паспортом.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT COUNT(*) as count
            FROM document_chunks
            WHERE document_id = $1
              AND (
                  cardinality(cultures) > 0
                  OR cardinality(goals) > 0
                  OR cardinality(growth_phases) > 0
              );
            """,
            document_id,
        )

    return row["count"] if row else 0


async def chunks_search_with_passport(
    *,
    query_embedding: List[float],
    culture: Optional[str] = None,
    goal: Optional[str] = None,
    phase: Optional[str] = None,
    limit: int = 5,
    distance_threshold: Optional[float] = 0.35,
) -> List[Dict]:
    """
    Поиск чанков с фильтрацией по паспорту.

    Возвращает чанки с prefix + context + chunk_text для использования в RAG.
    Использует массивы cultures, goals, growth_phases.
    """
    pool = get_pool()

    norm_embedding = _normalize_embedding(query_embedding)
    vector_str = "[" + ",".join(f"{x:.6f}" for x in norm_embedding) + "]"

    # Строим условия фильтрации
    conditions = ["c.is_active = TRUE", "d.is_active = TRUE"]
    params = [vector_str, limit]
    param_idx = 3

    if culture:
        # Используем ANY для поиска в массиве
        conditions.append(f"${param_idx} = ANY(c.cultures)")
        params.append(culture)
        param_idx += 1

    if goal:
        conditions.append(f"${param_idx} = ANY(c.goals)")
        params.append(goal)
        param_idx += 1

    if phase:
        conditions.append(f"${param_idx} = ANY(c.growth_phases)")
        params.append(phase)
        param_idx += 1

    where_clause = " AND ".join(conditions)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
                c.id,
                c.document_id,
                c.chunk_text,
                c.page_number,
                c.subcategory,
                c.cultures,
                c.culture_subtype,
                c.goals,
                c.growth_phases,
                c.prefix,
                c.context,
                c.embedding <=> $1::vector AS distance
            FROM document_chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE {where_clause}
            ORDER BY c.embedding <=> $1::vector
            LIMIT $2;
            """,
            *params,
        )

    # Фильтрация по distance_threshold
    if distance_threshold is not None:
        rows = [r for r in rows if r["distance"] <= distance_threshold]

    return [dict(r) for r in rows]
