# src/api/handlers/documents.py
"""
API handlers для загрузки и управления документами базы знаний.
"""

import asyncio
import logging
import os
import shutil
import tempfile
from typing import Optional

from aiohttp import web

from src.services.db import documents_repo
from src.services.db.pool import get_pool
from src.services.documents.processor import process_document, SUPPORTED_EXTENSIONS

logger = logging.getLogger(__name__)

# Разрешённые категории (культуры)
ALLOWED_SUBCATEGORIES = [
    "приоритет",
    "малина общая",
    "малина летняя",
    "малина ремонтантная",
    "клубника общая",
    "клубника летняя",
    "клубника ремонтантная",
    "голубика",
    "смородина",
    "жимолость",
    "крыжовник",
    "ежевика",
    "общая информация",
]

# Максимальный размер файла (50 МБ)
MAX_UPLOAD_SIZE = 50 * 1024 * 1024

# Поддерживаемые расширения файлов (для отображения)
SUPPORTED_FORMATS = ["PDF", "TXT", "MD", "DOCX", "DOC"]


async def process_document_background(
    file_path: str,
    subcategory: str,
    temp_dir: str,
    document_id: Optional[int] = None,
) -> None:
    """
    Фоновая обработка документа.
    Удаляет временные файлы после обработки.
    """
    try:
        result = await process_document(
            file_path=file_path,
            category="общая_информация",
            subcategory=subcategory,
            force_update=False,
        )
        if not result["success"]:
            logger.error(f"Document processing failed: {result['error']}")
    except Exception as e:
        logger.error(f"Background processing error: {e}")
    finally:
        # Очистка временных файлов
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp dir {temp_dir}: {e}")


async def upload_document(request: web.Request) -> web.Response:
    """
    POST /api/admin/documents/upload

    Загрузка PDF документа для векторизации.

    Form data:
        file: PDF файл
        subcategory: категория/культура (например, "голубика")
    """
    try:
        reader = await request.multipart()

        file_data = None
        filename = None
        subcategory = None

        # Читаем multipart данные
        async for field in reader:
            if field.name == "file":
                filename = field.filename
                if not filename:
                    raise web.HTTPBadRequest(text="No filename provided")

                # Проверка расширения файла
                file_ext = filename.lower().split(".")[-1] if "." in filename else ""
                if f".{file_ext}" not in SUPPORTED_EXTENSIONS:
                    raise web.HTTPBadRequest(
                        text=f"Unsupported file format. Allowed: {', '.join(SUPPORTED_FORMATS)}"
                    )

                # Читаем файл в память (с ограничением размера)
                file_data = await field.read(decode=False)

                if len(file_data) > MAX_UPLOAD_SIZE:
                    raise web.HTTPBadRequest(
                        text=f"File too large. Max size: {MAX_UPLOAD_SIZE // (1024*1024)} MB"
                    )

            elif field.name == "subcategory":
                subcategory = (await field.read(decode=True)).decode("utf-8")

        # Валидация
        if not file_data:
            raise web.HTTPBadRequest(text="No file provided")

        if not subcategory:
            raise web.HTTPBadRequest(text="No subcategory provided")

        if subcategory not in ALLOWED_SUBCATEGORIES:
            raise web.HTTPBadRequest(
                text=f"Invalid subcategory. Allowed: {', '.join(ALLOWED_SUBCATEGORIES)}"
            )

        # Сохраняем во временный файл
        temp_dir = tempfile.mkdtemp(prefix="doc_upload_")
        file_path = os.path.join(temp_dir, filename)

        with open(file_path, "wb") as f:
            f.write(file_data)

        logger.info(f"Uploaded file saved: {file_path} ({len(file_data)} bytes)")

        # Запускаем обработку в фоне
        asyncio.create_task(
            process_document_background(
                file_path=file_path,
                subcategory=subcategory,
                temp_dir=temp_dir,
            )
        )

        return web.json_response({
            "status": "processing",
            "filename": filename,
            "subcategory": subcategory,
            "message": "Document uploaded and processing started",
        })

    except web.HTTPBadRequest:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise web.HTTPInternalServerError(text=f"Upload failed: {str(e)}")


async def get_documents_list(request: web.Request) -> web.Response:
    """
    GET /api/admin/documents

    Получить список всех документов с их статусами.

    Query params:
        limit: int (default 100)
        subcategory: str (фильтр по культуре)
    """
    try:
        limit = int(request.query.get("limit", 100))
        subcategory = request.query.get("subcategory")

        pool = get_pool()

        async with pool.acquire() as conn:
            if subcategory:
                rows = await conn.fetch(
                    """
                    SELECT
                        id,
                        filename,
                        subcategory,
                        processing_status,
                        processing_error,
                        total_chunks,
                        file_size_bytes,
                        embedding_tokens,
                        embedding_cost_usd,
                        created_at
                    FROM documents
                    WHERE subcategory = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                    """,
                    subcategory,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT
                        id,
                        filename,
                        subcategory,
                        processing_status,
                        processing_error,
                        total_chunks,
                        file_size_bytes,
                        embedding_tokens,
                        embedding_cost_usd,
                        created_at
                    FROM documents
                    ORDER BY created_at DESC
                    LIMIT $1
                    """,
                    limit,
                )

        documents = []
        for row in rows:
            documents.append({
                "id": row["id"],
                "filename": row["filename"],
                "subcategory": row["subcategory"],
                "status": row["processing_status"],
                "error": row["processing_error"],
                "chunks_count": row["total_chunks"] or 0,
                "file_size": row["file_size_bytes"],
                "embedding_tokens": row["embedding_tokens"] or 0,
                "embedding_cost_usd": float(row["embedding_cost_usd"]) if row["embedding_cost_usd"] else 0,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            })

        return web.json_response({
            "documents": documents,
            "total": len(documents),
            "subcategories": ALLOWED_SUBCATEGORIES,
        })

    except Exception as e:
        logger.error(f"Error getting documents list: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_document_status(request: web.Request) -> web.Response:
    """
    GET /api/admin/documents/{id}/status

    Получить статус обработки документа.
    """
    try:
        document_id = int(request.match_info["id"])

        doc = await documents_repo.document_get_by_id(document_id)

        if not doc:
            raise web.HTTPNotFound(text="Document not found")

        return web.json_response({
            "id": doc["id"],
            "filename": doc["filename"],
            "subcategory": doc["subcategory"],
            "status": doc["processing_status"],
            "error": doc["processing_error"],
            "chunks_count": doc["total_chunks"] or 0,
            "file_size": doc.get("file_size_bytes") or 0,
            "embedding_tokens": doc.get("embedding_tokens") or 0,
            "embedding_cost_usd": float(doc["embedding_cost_usd"]) if doc.get("embedding_cost_usd") else 0,
            "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
        })

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid document ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error getting document status: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def delete_document(request: web.Request) -> web.Response:
    """
    DELETE /api/admin/documents/{id}

    Удалить документ и все его чанки.
    """
    try:
        document_id = int(request.match_info["id"])

        # Проверяем существование
        doc = await documents_repo.document_get_by_id(document_id)
        if not doc:
            raise web.HTTPNotFound(text="Document not found")

        pool = get_pool()

        async with pool.acquire() as conn:
            # Удаляем чанки
            await conn.execute(
                "DELETE FROM document_chunks WHERE document_id = $1",
                document_id,
            )

            # Удаляем документ
            await conn.execute(
                "DELETE FROM documents WHERE id = $1",
                document_id,
            )

        logger.info(f"Deleted document {document_id}: {doc['filename']}")

        return web.json_response({
            "success": True,
            "message": f"Document '{doc['filename']}' deleted",
        })

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid document ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise web.HTTPInternalServerError(text="Database error")
