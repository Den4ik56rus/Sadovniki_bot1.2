# src/api/handlers/rag_documents.py
"""
API handlers для RAG v2.0 — паспортизация чанков документов.

Endpoints:
- GET /api/admin/rag-documents — список документов с прогрессом паспортизации
- GET /api/admin/rag-documents/{id} — детали документа
- GET /api/admin/rag-documents/{id}/chunks — чанки документа
- GET /api/admin/rag-documents/passport-options — справочники для dropdown
- PATCH /api/admin/rag-documents/chunks/{id}/passport — обновить паспорт чанка
- POST /api/admin/rag-documents/chunks/{id}/generate-context — сгенерировать контекст
- POST /api/admin/rag-documents/{id}/embed — загрузить в библиотеку (генерация embeddings)
- DELETE /api/admin/rag-documents/{id} — удалить документ
- DELETE /api/admin/rag-documents/clear-all — очистить все документы
"""

import logging

from aiohttp import web

from src.services.db.pool import get_pool
from src.services.db import documents_repo
from src.services.db.document_chunks_repo import (
    get_chunks_by_document,
    get_chunk_by_id,
    get_passport_options,
    get_passported_chunks_count,
    update_chunk_passport,
    update_chunk_context,
)
from src.services.llm.context_generator import generate_chunk_context
from src.services.documents.processor import embed_document

logger = logging.getLogger(__name__)


async def get_rag_documents(request: web.Request) -> web.Response:
    """
    GET /api/admin/rag-documents

    Получить список всех RAG документов с прогрессом паспортизации.
    Включает информацию о двухэтапной обработке (chunking + embedding).
    """
    try:
        limit = int(request.query.get("limit", 100))

        pool = get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    d.id,
                    d.filename,
                    d.subcategory,
                    d.processing_status,
                    d.processing_error,
                    d.total_chunks,
                    d.file_size_bytes,
                    d.chunking_tokens,
                    d.chunking_cost_usd,
                    d.embedding_tokens,
                    d.embedding_cost_usd,
                    d.context_generation_cost,
                    d.context_generation_tokens,
                    d.is_embedded,
                    d.created_at,
                    COUNT(CASE WHEN cardinality(c.cultures) > 0 OR cardinality(c.goals) > 0 OR cardinality(c.growth_phases) > 0 THEN 1 END) as passported_chunks
                FROM documents d
                LEFT JOIN document_chunks c ON d.id = c.document_id
                GROUP BY d.id
                ORDER BY d.created_at DESC
                LIMIT $1
                """,
                limit,
            )

        documents = []
        for row in rows:
            chunking_cost = float(row["chunking_cost_usd"]) if row["chunking_cost_usd"] else 0
            embedding_cost = float(row["embedding_cost_usd"]) if row["embedding_cost_usd"] else 0
            context_cost = float(row["context_generation_cost"]) if row["context_generation_cost"] else 0
            documents.append({
                "id": row["id"],
                "filename": row["filename"],
                "subcategory": row["subcategory"],
                "status": row["processing_status"],
                "error": row["processing_error"],
                "chunks_count": row["total_chunks"] or 0,
                "passported_chunks": row["passported_chunks"] or 0,
                "file_size": row["file_size_bytes"],
                "chunking_tokens": row["chunking_tokens"] or 0,
                "chunking_cost": chunking_cost,
                "embedding_tokens": row["embedding_tokens"] or 0,
                "embedding_cost": embedding_cost,
                "context_cost": context_cost,
                "total_cost": chunking_cost + embedding_cost + context_cost,
                "context_tokens": row["context_generation_tokens"] or 0,
                "is_embedded": row["is_embedded"] if row["is_embedded"] is not None else False,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            })

        return web.json_response({
            "documents": documents,
            "total": len(documents),
        })

    except Exception as e:
        logger.error(f"Error getting RAG documents: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_rag_document(request: web.Request) -> web.Response:
    """
    GET /api/admin/rag-documents/{id}

    Получить детали документа.
    """
    try:
        document_id = int(request.match_info["id"])

        doc = await documents_repo.document_get_by_id(document_id)

        if not doc:
            raise web.HTTPNotFound(text="Document not found")

        # Получаем количество паспортизированных чанков
        passported_count = await get_passported_chunks_count(document_id)

        return web.json_response({
            "id": doc["id"],
            "filename": doc["filename"],
            "subcategory": doc["subcategory"],
            "status": doc["processing_status"],
            "error": doc["processing_error"],
            "chunks_count": doc["total_chunks"] or 0,
            "passported_chunks": passported_count,
            "file_size": doc.get("file_size_bytes") or 0,
            "context_cost": float(doc["context_generation_cost"]) if doc.get("context_generation_cost") else 0,
            "context_tokens": doc.get("context_generation_tokens") or 0,
            "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
        })

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid document ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error getting RAG document: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_document_chunks(request: web.Request) -> web.Response:
    """
    GET /api/admin/rag-documents/{id}/chunks

    Получить все чанки документа с данными паспорта.
    """
    try:
        document_id = int(request.match_info["id"])

        # Проверяем существование документа
        doc = await documents_repo.document_get_by_id(document_id)
        if not doc:
            raise web.HTTPNotFound(text="Document not found")

        # Получаем чанки
        chunks = await get_chunks_by_document(document_id)

        # Форматируем ответ
        formatted_chunks = []
        for chunk in chunks:
            cultures = chunk.get("cultures") or []
            goals = chunk.get("goals") or []
            growth_phases = chunk.get("growth_phases") or []
            culture_subtypes = chunk.get("culture_subtypes") or {}

            formatted_chunks.append({
                "id": chunk["id"],
                "chunk_index": chunk["chunk_index"],
                "chunk_text": chunk["chunk_text"],
                "chunk_size": chunk["chunk_size"],
                "page_number": chunk["page_number"],
                "cultures": cultures,
                "culture_subtypes": culture_subtypes,
                "goals": goals,
                "growth_phases": growth_phases,
                "prefix": chunk["prefix"],
                "context": chunk["context"],
                "is_passported": bool(cultures or goals or growth_phases),
                "created_at": chunk["created_at"].isoformat() if chunk.get("created_at") else None,
            })

        return web.json_response({
            "document_id": document_id,
            "filename": doc["filename"],
            "chunks": formatted_chunks,
            "total": len(formatted_chunks),
        })

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid document ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error getting document chunks: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_passport_options_handler(request: web.Request) -> web.Response:
    """
    GET /api/admin/rag-documents/passport-options

    Получить справочные данные для выпадающих списков паспорта.
    """
    try:
        options = await get_passport_options()

        return web.json_response(options)

    except Exception as e:
        logger.error(f"Error getting passport options: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def update_chunk_passport_handler(request: web.Request) -> web.Response:
    """
    PATCH /api/admin/rag-documents/chunks/{id}/passport

    Обновить паспорт чанка.

    Body (JSON):
        cultures: string[] — массив культур
        culture_subtypes: object — словарь подтипов { "малина": "ремонтантная", ... }
        goals: string[] — массив целей
        growth_phases: string[] — массив фаз роста
        chunk_text: string | null — опционально, текст чанка
        context: string | null — опционально, контекст чанка
    """
    try:
        chunk_id = int(request.match_info["id"])

        # Проверяем существование чанка
        chunk = await get_chunk_by_id(chunk_id)
        if not chunk:
            raise web.HTTPNotFound(text="Chunk not found")

        # Парсим тело запроса
        data = await request.json()

        cultures = data.get("cultures") or []
        culture_subtypes = data.get("culture_subtypes") or {}
        goals = data.get("goals") or []
        growth_phases = data.get("growth_phases") or []
        chunk_text = data.get("chunk_text")  # None если не передано
        context = data.get("context")  # None если не передано

        # Обновляем паспорт
        updated_chunk = await update_chunk_passport(
            chunk_id=chunk_id,
            cultures=cultures,
            culture_subtypes=culture_subtypes,
            goals=goals,
            growth_phases=growth_phases,
            chunk_text=chunk_text,
            context=context,
        )

        if not updated_chunk:
            raise web.HTTPInternalServerError(text="Failed to update passport")

        return web.json_response({
            "success": True,
            "chunk": {
                "id": updated_chunk["id"],
                "chunk_index": updated_chunk["chunk_index"],
                "chunk_text": updated_chunk["chunk_text"],
                "chunk_size": updated_chunk["chunk_size"],
                "cultures": updated_chunk["cultures"] or [],
                "culture_subtypes": updated_chunk["culture_subtypes"] or {},
                "goals": updated_chunk["goals"] or [],
                "growth_phases": updated_chunk["growth_phases"] or [],
                "prefix": updated_chunk["prefix"],
                "context": updated_chunk["context"],
                "is_passported": bool(
                    updated_chunk["cultures"]
                    or updated_chunk["goals"]
                    or updated_chunk["growth_phases"]
                ),
            },
        })

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid chunk ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error updating chunk passport: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def generate_chunk_context_handler(request: web.Request) -> web.Response:
    """
    POST /api/admin/rag-documents/chunks/{id}/generate-context

    Сгенерировать контекст для чанка через LLM.
    """
    try:
        chunk_id = int(request.match_info["id"])

        # Получаем чанк
        chunk = await get_chunk_by_id(chunk_id)
        if not chunk:
            raise web.HTTPNotFound(text="Chunk not found")

        # Получаем документ для полного текста
        doc = await documents_repo.document_get_by_id(chunk["document_id"])
        if not doc:
            raise web.HTTPNotFound(text="Document not found")

        # Получаем все чанки документа для подсчёта total
        all_chunks = await get_chunks_by_document(chunk["document_id"])
        total_chunks = len(all_chunks)

        # Собираем полный текст документа из чанков
        full_text = "\n\n".join([c["chunk_text"] for c in all_chunks])

        # Генерируем контекст
        context, input_tokens, output_tokens, cost = await generate_chunk_context(
            document_text=full_text,
            chunk_text=chunk["chunk_text"],
            chunk_index=chunk["chunk_index"],
            total_chunks=total_chunks,
        )

        # Сохраняем контекст
        updated_chunk = await update_chunk_context(chunk_id, context)

        return web.json_response({
            "success": True,
            "context": context,
            "tokens": {
                "input": input_tokens,
                "output": output_tokens,
            },
            "cost": cost,
            "chunk": {
                "id": updated_chunk["id"] if updated_chunk else chunk_id,
                "context": context,
            },
        })

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid chunk ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error generating chunk context: {e}")
        raise web.HTTPInternalServerError(text=f"Context generation failed: {str(e)}")


async def delete_rag_document(request: web.Request) -> web.Response:
    """
    DELETE /api/admin/rag-documents/{id}

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
            # Удаляем чанки (CASCADE должен сработать, но на всякий случай)
            await conn.execute(
                "DELETE FROM document_chunks WHERE document_id = $1",
                document_id,
            )

            # Удаляем документ
            await conn.execute(
                "DELETE FROM documents WHERE id = $1",
                document_id,
            )

        logger.info(f"Deleted RAG document {document_id}: {doc['filename']}")

        return web.json_response({
            "success": True,
            "message": f"Document '{doc['filename']}' deleted",
        })

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid document ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error deleting RAG document: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def embed_document_handler(request: web.Request) -> web.Response:
    """
    POST /api/admin/rag-documents/{id}/embed

    Загрузить документ в библиотеку — генерация финальных embeddings.

    Условия:
    - Все чанки должны быть паспортизированы (passported_chunks == chunks_count)
    - Документ ещё не загружен (is_embedded == False)
    """
    try:
        document_id = int(request.match_info["id"])

        # Получаем документ
        doc = await documents_repo.document_get_by_id(document_id)
        if not doc:
            raise web.HTTPNotFound(text="Document not found")

        # Проверяем что документ ещё не загружен
        if doc.get("is_embedded"):
            return web.json_response({
                "success": False,
                "error": "Документ уже загружен в библиотеку",
            }, status=400)

        # Проверяем что все чанки паспортизированы
        chunks_count = doc.get("total_chunks") or 0
        passported_count = await get_passported_chunks_count(document_id)

        if passported_count < chunks_count:
            return web.json_response({
                "success": False,
                "error": f"Не все чанки паспортизированы ({passported_count}/{chunks_count})",
            }, status=400)

        # Запускаем генерацию embeddings
        logger.info(f"Starting embedding for document {document_id}: {doc['filename']}")

        result = await embed_document(
            document_id=document_id,
            use_gemini_embeddings=True,
        )

        if not result["success"]:
            return web.json_response({
                "success": False,
                "error": result.get("error", "Unknown error"),
            }, status=500)

        logger.info(
            f"Embedded document {document_id}: {result['chunks_count']} chunks, "
            f"{result['embedding_tokens']} tokens, ${result['embedding_cost_usd']:.6f}"
        )

        return web.json_response({
            "success": True,
            "document_id": document_id,
            "chunks_count": result["chunks_count"],
            "embedding_tokens": result["embedding_tokens"],
            "embedding_cost": result["embedding_cost_usd"],
        })

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid document ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error embedding document: {e}")
        raise web.HTTPInternalServerError(text=f"Embedding failed: {str(e)}")


async def clear_all_rag_documents(request: web.Request) -> web.Response:
    """
    DELETE /api/admin/rag-documents/clear-all

    Удалить все RAG документы и чанки.
    ВНИМАНИЕ: prompt_documents НЕ затрагиваются.
    """
    try:
        pool = get_pool()

        async with pool.acquire() as conn:
            # Считаем сколько удаляем
            count_row = await conn.fetchrow("SELECT COUNT(*) as count FROM documents")
            doc_count = count_row["count"] if count_row else 0

            chunk_count_row = await conn.fetchrow("SELECT COUNT(*) as count FROM document_chunks")
            chunk_count = chunk_count_row["count"] if chunk_count_row else 0

            # Удаляем чанки
            await conn.execute("DELETE FROM document_chunks")

            # Удаляем документы
            await conn.execute("DELETE FROM documents")

        logger.warning(f"Cleared all RAG documents: {doc_count} documents, {chunk_count} chunks")

        return web.json_response({
            "success": True,
            "deleted_documents": doc_count,
            "deleted_chunks": chunk_count,
            "message": "All RAG documents cleared (prompt_documents not affected)",
        })

    except Exception as e:
        logger.error(f"Error clearing RAG documents: {e}")
        raise web.HTTPInternalServerError(text="Database error")
