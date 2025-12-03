# src/services/db/document_chunks_repo.py

from typing import List, Dict, Optional
from src.services.db.pool import get_pool


# Размерность вектора (фиксированная для OpenAI embeddings)
VECTOR_DIM = 1536  # text-embedding-3-small


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
    category: str,
    query_embedding: List[float],
    subcategory: Optional[str] = None,
    limit: int = 2,
    distance_threshold: Optional[float] = 0.35,
):
    """
    Поиск похожих фрагментов документов по эмбеддингу.

    Фильтрация:
        - ВСЕГДА по category
        - ДОПОЛНИТЕЛЬНО по subcategory, если передана

    Возвращает список записей с полями:
        - id, document_id, chunk_text, page_number, distance, category, subcategory
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
                c.page_number,
                c.category,
                c.subcategory,
                c.embedding <=> $1::vector AS distance
            FROM document_chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE c.is_active = TRUE
              AND d.is_active = TRUE
              AND c.category = $2
              AND ($3::text IS NULL OR c.subcategory = $3)
            ORDER BY c.embedding <=> $1::vector
            LIMIT $4;
            """,
            vector_str,
            category,
            subcategory,
            limit,
        )

    # Фильтрация по distance_threshold
    if distance_threshold is not None:
        rows = [r for r in rows if r["distance"] <= distance_threshold]

    return rows


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
