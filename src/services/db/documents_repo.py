# src/services/db/documents_repo.py

from typing import Optional, Dict
from src.services.db.pool import get_pool


async def document_insert(
    *,
    filename: str,
    file_path: str,
    file_hash: str,
    file_size_bytes: int,
    category: str,
    subcategory: Optional[str] = None,
    processing_status: str = "pending",
) -> int:
    """
    Создаёт новую запись в таблице documents и возвращает её id.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO documents (
                filename,
                file_path,
                file_hash,
                file_size_bytes,
                category,
                subcategory,
                processing_status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id;
            """,
            filename,
            file_path,
            file_hash,
            file_size_bytes,
            category,
            subcategory,
            processing_status,
        )

    return row["id"]


async def document_update_status(
    document_id: int,
    status: str,
    error: Optional[str] = None,
    total_chunks: Optional[int] = None,
) -> None:
    """
    Обновляет статус обработки документа.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        if total_chunks is not None:
            await conn.execute(
                """
                UPDATE documents
                SET processing_status = $1,
                    processing_error = $2,
                    total_chunks = $3
                WHERE id = $4;
                """,
                status,
                error,
                total_chunks,
                document_id,
            )
        else:
            await conn.execute(
                """
                UPDATE documents
                SET processing_status = $1,
                    processing_error = $2
                WHERE id = $3;
                """,
                status,
                error,
                document_id,
            )


async def document_exists_by_hash(file_hash: str) -> Optional[Dict]:
    """
    Проверяет, существует ли документ с данным хешем.
    Возвращает словарь с полями документа или None.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, filename, category, subcategory, processing_status
            FROM documents
            WHERE file_hash = $1
            LIMIT 1;
            """,
            file_hash,
        )

    if row:
        return dict(row)
    return None


async def document_get_by_id(document_id: int) -> Optional[Dict]:
    """
    Получает документ по ID.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT *
            FROM documents
            WHERE id = $1;
            """,
            document_id,
        )

    if row:
        return dict(row)
    return None


async def document_list_by_category(
    category: str,
    subcategory: Optional[str] = None,
    limit: int = 100,
) -> list:
    """
    Возвращает список документов по категории.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        if subcategory:
            rows = await conn.fetch(
                """
                SELECT *
                FROM documents
                WHERE category = $1 AND subcategory = $2
                ORDER BY created_at DESC
                LIMIT $3;
                """,
                category,
                subcategory,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT *
                FROM documents
                WHERE category = $1
                ORDER BY created_at DESC
                LIMIT $2;
                """,
                category,
                limit,
            )

    return [dict(row) for row in rows]
