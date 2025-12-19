# src/api/handlers/prompt_documents.py
"""
API handlers для Промт-документов: CRUD документов, культур, подкультур, типов работ.
"""

import asyncio
import hashlib
import logging
import os
from datetime import date, datetime
from pathlib import Path
from aiohttp import web

from src.services.db import prompt_document_repo as repo
from src.services.documents.prompt_extractor import (
    extract_text_from_file,
    get_file_type,
    is_supported_file
)

logger = logging.getLogger(__name__)

# Директория для хранения промт-документов
PROMPT_DOCUMENTS_DIR = Path("data/prompt_documents")


def _serialize_value(value):
    """Serialize special types for JSON."""
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return value


def _serialize_dict(d: dict) -> dict:
    """Serialize all values in a dict."""
    return {k: _serialize_value(v) for k, v in d.items()}


def _transliterate(text: str) -> str:
    """Транслитерация кириллицы для имён файлов."""
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        ' ': '_', '-': '_'
    }
    result = []
    for char in text.lower():
        result.append(translit_map.get(char, char))
    return ''.join(result)


def _ensure_upload_dir():
    """Убедиться, что директория для загрузки существует."""
    PROMPT_DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# Cultures
# =============================================================================

async def get_cultures(request: web.Request) -> web.Response:
    """
    GET /api/admin/prompt-documents/cultures
    Получить все культуры.
    """
    try:
        cultures = await repo.get_cultures()
        return web.json_response([_serialize_dict(c) for c in cultures])

    except Exception as e:
        logger.error(f"Error getting cultures: {e}")
        raise web.HTTPInternalServerError(text="Database error")


# =============================================================================
# Subcultures
# =============================================================================

async def get_subcultures(request: web.Request) -> web.Response:
    """
    GET /api/admin/prompt-documents/subcultures?culture_id=X
    Получить подкультуры для культуры.
    """
    try:
        if 'culture_id' not in request.query:
            raise web.HTTPBadRequest(text="Missing 'culture_id' parameter")

        culture_id = int(request.query['culture_id'])
        subcultures = await repo.get_subcultures(culture_id)

        return web.json_response([_serialize_dict(s) for s in subcultures])

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid culture_id")
    except web.HTTPBadRequest:
        raise
    except Exception as e:
        logger.error(f"Error getting subcultures: {e}")
        raise web.HTTPInternalServerError(text="Database error")


# =============================================================================
# Work Types
# =============================================================================

async def get_work_types(request: web.Request) -> web.Response:
    """
    GET /api/admin/prompt-documents/work-types
    Получить все типы работ.
    """
    try:
        work_types = await repo.get_work_types()
        return web.json_response([_serialize_dict(w) for w in work_types])

    except Exception as e:
        logger.error(f"Error getting work types: {e}")
        raise web.HTTPInternalServerError(text="Database error")


# =============================================================================
# Documents CRUD
# =============================================================================

async def get_documents(request: web.Request) -> web.Response:
    """
    GET /api/admin/prompt-documents
    Получить список документов с фильтрацией.

    Query params:
        culture_id: int
        subculture_id: int
        work_type_id: int
    """
    try:
        culture_id = None
        subculture_id = None
        work_type_id = None

        if 'culture_id' in request.query:
            culture_id = int(request.query['culture_id'])

        if 'subculture_id' in request.query:
            subculture_id = int(request.query['subculture_id'])

        if 'work_type_id' in request.query:
            work_type_id = int(request.query['work_type_id'])

        result = await repo.get_documents(
            culture_id=culture_id,
            subculture_id=subculture_id,
            work_type_id=work_type_id
        )

        result['documents'] = [_serialize_dict(d) for d in result['documents']]

        return web.json_response(result)

    except ValueError as e:
        raise web.HTTPBadRequest(text=f"Invalid parameter: {e}")
    except Exception as e:
        logger.error(f"Error getting documents: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_document(request: web.Request) -> web.Response:
    """
    GET /api/admin/prompt-documents/{id}
    Получить документ по ID.
    """
    try:
        document_id = int(request.match_info["id"])
        doc = await repo.get_document_by_id(document_id)

        if not doc:
            raise web.HTTPNotFound(text="Document not found")

        return web.json_response(_serialize_dict(doc))

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid document ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error getting document: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_document_content(request: web.Request) -> web.Response:
    """
    GET /api/admin/prompt-documents/{id}/content
    Получить текстовый контент документа.
    """
    try:
        document_id = int(request.match_info["id"])
        content = await repo.get_document_content(document_id)

        if content is None:
            # Проверяем, существует ли документ
            doc = await repo.get_document_by_id(document_id)
            if not doc:
                raise web.HTTPNotFound(text="Document not found")
            # Документ есть, но контент не извлечён
            return web.json_response({
                "content": None,
                "message": "Контент ещё не извлечён или извлечение не удалось"
            })

        return web.json_response({"content": content})

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid document ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error getting document content: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def upload_document(request: web.Request) -> web.Response:
    """
    POST /api/admin/prompt-documents/upload
    Загрузить новый документ.

    Multipart form:
        file: File
        culture_id: int
        subculture_id: int (optional)
        work_type_id: int
    """
    try:
        reader = await request.multipart()

        file_data = None
        original_filename = None
        culture_id = None
        subculture_id = None
        work_type_id = None

        # Читаем multipart данные
        async for field in reader:
            if field.name == 'file':
                original_filename = field.filename
                file_data = await field.read()
            elif field.name == 'culture_id':
                culture_id = int((await field.read()).decode())
            elif field.name == 'subculture_id':
                value = (await field.read()).decode()
                if value and value != 'null' and value != 'undefined':
                    subculture_id = int(value)
            elif field.name == 'work_type_id':
                work_type_id = int((await field.read()).decode())

        # Валидация
        if not file_data or not original_filename:
            raise web.HTTPBadRequest(text="No file uploaded")

        if culture_id is None:
            raise web.HTTPBadRequest(text="Missing culture_id")

        if work_type_id is None:
            raise web.HTTPBadRequest(text="Missing work_type_id")

        if not is_supported_file(original_filename):
            raise web.HTTPBadRequest(text="Unsupported file format. Allowed: .pages, .docx, .pdf")

        # Проверяем, существует ли уже документ для этой комбинации
        existing = await repo.get_document_by_combination(
            culture_id, subculture_id, work_type_id
        )
        if existing:
            raise web.HTTPConflict(
                text=f"Документ для этой комбинации уже существует (ID: {existing['id']}). "
                     f"Используйте замену вместо загрузки."
            )

        # Вычисляем хеш файла
        file_hash = hashlib.sha256(file_data).hexdigest()

        # Получаем данные о культуре/подкультуре/типе работ для имени файла
        culture = await repo.get_culture_by_id(culture_id)
        subculture = await repo.get_subculture_by_id(subculture_id) if subculture_id else None
        work_type = await repo.get_work_type_by_id(work_type_id)

        if not culture:
            raise web.HTTPBadRequest(text="Invalid culture_id")
        if not work_type:
            raise web.HTTPBadRequest(text="Invalid work_type_id")

        # Генерируем имя файла
        file_type = get_file_type(original_filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        culture_name = _transliterate(culture['name'])
        subculture_name = _transliterate(subculture['name']) if subculture else 'all'
        work_type_name = _transliterate(work_type['name'])

        filename = f"{culture_name}_{subculture_name}_{work_type_name}_{timestamp}.{file_type}"

        # Сохраняем файл
        _ensure_upload_dir()
        file_path = PROMPT_DOCUMENTS_DIR / filename

        with open(file_path, 'wb') as f:
            f.write(file_data)

        # Создаём запись в БД
        doc = await repo.create_document(
            culture_id=culture_id,
            subculture_id=subculture_id,
            work_type_id=work_type_id,
            filename=filename,
            original_filename=original_filename,
            file_path=str(file_path),
            file_hash=file_hash,
            file_size=len(file_data),
            file_type=file_type
        )

        # Запускаем извлечение текста в фоне
        asyncio.create_task(_extract_content_background(doc['id'], str(file_path), file_type))

        return web.json_response(_serialize_dict(doc), status=201)

    except web.HTTPBadRequest:
        raise
    except web.HTTPConflict:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise web.HTTPInternalServerError(text=f"Upload error: {e}")


async def _extract_content_background(document_id: int, file_path: str, file_type: str):
    """Фоновая задача для извлечения текста из документа."""
    try:
        result = await extract_text_from_file(file_path, file_type)

        if result['success']:
            await repo.update_document_content(document_id, result['text'])
            logger.info(f"Successfully extracted text from document {document_id}")
        else:
            await repo.update_document_extraction_error(document_id, result['error'])
            logger.warning(f"Failed to extract text from document {document_id}: {result['error']}")

    except Exception as e:
        logger.error(f"Error in background extraction for document {document_id}: {e}")
        await repo.update_document_extraction_error(document_id, str(e))


async def delete_document(request: web.Request) -> web.Response:
    """
    DELETE /api/admin/prompt-documents/{id}
    Удалить документ.
    """
    try:
        document_id = int(request.match_info["id"])

        # Удаляем из БД и получаем путь к файлу
        file_path = await repo.delete_document(document_id)

        if not file_path:
            raise web.HTTPNotFound(text="Document not found")

        # Удаляем файл с диска
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.warning(f"Failed to delete file {file_path}: {e}")

        return web.json_response({"success": True})

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid document ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def replace_document(request: web.Request) -> web.Response:
    """
    PUT /api/admin/prompt-documents/{id}/replace
    Заменить файл документа (сохраняя категории).

    Multipart form:
        file: File
    """
    try:
        document_id = int(request.match_info["id"])

        # Проверяем, существует ли документ
        existing_doc = await repo.get_document_by_id(document_id)
        if not existing_doc:
            raise web.HTTPNotFound(text="Document not found")

        reader = await request.multipart()

        file_data = None
        original_filename = None

        async for field in reader:
            if field.name == 'file':
                original_filename = field.filename
                file_data = await field.read()

        if not file_data or not original_filename:
            raise web.HTTPBadRequest(text="No file uploaded")

        if not is_supported_file(original_filename):
            raise web.HTTPBadRequest(text="Unsupported file format. Allowed: .pages, .docx, .pdf")

        # Вычисляем хеш
        file_hash = hashlib.sha256(file_data).hexdigest()

        # Генерируем новое имя файла
        file_type = get_file_type(original_filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        culture_name = _transliterate(existing_doc['culture_name'])
        subculture_name = _transliterate(existing_doc['subculture_name']) if existing_doc['subculture_name'] else 'all'
        work_type_name = _transliterate(existing_doc['work_type_name'])

        filename = f"{culture_name}_{subculture_name}_{work_type_name}_{timestamp}.{file_type}"

        # Удаляем старый файл
        old_file_path = existing_doc.get('file_path')
        if old_file_path and os.path.exists(old_file_path):
            try:
                os.remove(old_file_path)
            except Exception as e:
                logger.warning(f"Failed to delete old file {old_file_path}: {e}")

        # Сохраняем новый файл
        _ensure_upload_dir()
        file_path = PROMPT_DOCUMENTS_DIR / filename

        with open(file_path, 'wb') as f:
            f.write(file_data)

        # Обновляем запись в БД
        doc = await repo.replace_document(
            document_id=document_id,
            filename=filename,
            original_filename=original_filename,
            file_path=str(file_path),
            file_hash=file_hash,
            file_size=len(file_data),
            file_type=file_type
        )

        # Запускаем извлечение текста в фоне
        asyncio.create_task(_extract_content_background(document_id, str(file_path), file_type))

        return web.json_response(_serialize_dict(doc))

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid document ID")
    except web.HTTPNotFound:
        raise
    except web.HTTPBadRequest:
        raise
    except Exception as e:
        logger.error(f"Error replacing document: {e}")
        raise web.HTTPInternalServerError(text=f"Replace error: {e}")
