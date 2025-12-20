# src/services/documents/processor.py

"""
Модуль обработки документов для загрузки в базу знаний.

Поддерживаемые форматы: PDF, TXT, MD, DOCX

Основная функция: process_document()
- Извлекает текст из документа
- Разбивает на чанки (semantic или fixed-size)
- Генерирует embeddings
- Сохраняет в БД

RAG v2.0: Добавлен semantic chunking с Gemini Embeddings
- Смысловое разбиение текста (+70% качества retrieval)
- Защита списков от разрыва
- Поддержка структурного парсинга DOCX
"""

import hashlib
import os
from pathlib import Path
from typing import Optional, Dict, List, Literal
import asyncio
import time

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

import subprocess

# Поддерживаемые форматы файлов
SUPPORTED_EXTENSIONS = {'.pdf', '.txt', '.md', '.docx', '.doc', '.pages'}

# Legacy chunker (fixed-size)
from src.services.documents.chunker import chunk_text

# RAG v2.0: Semantic chunking
from src.services.documents.semantic_chunker import chunk_text_semantic
from src.services.documents.docx_parser import extract_text_from_docx_v2
from src.services.documents.boundary_detector import detect_list_boundaries

# Embeddings
from src.services.llm.embeddings_llm import get_text_embedding, get_batch_embeddings_with_usage
from src.services.llm.gemini_embeddings import get_batch_embeddings_for_documents

from src.services.db.documents_repo import (
    document_insert,
    document_update_status,
    document_exists_by_hash,
)
from src.services.db.document_chunks_repo import (
    chunks_bulk_insert,
    bulk_update_chunk_contexts,
    get_chunks_by_document,
)
from src.services.llm.core_llm import calculate_embedding_cost
from src.services.llm.context_generator import generate_contexts_for_document

from src.config import settings

# Тип чанкинга
ChunkingMode = Literal["semantic", "fixed"]

# Максимальный размер файла в байтах (100 МБ)
MAX_FILE_SIZE = 100 * 1024 * 1024

# Минимальная длина текста для обработки
MIN_TEXT_LENGTH = 50

# Размер батча для генерации embeddings
EMBEDDING_BATCH_SIZE = 20


def compute_file_hash(file_path: str) -> str:
    """
    Вычисляет SHA256-хеш файла.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def extract_text_from_pdf(file_path: str) -> Dict[str, any]:
    """
    Извлекает текст из PDF постранично.

    Возвращает:
        {
            "full_text": str,  # весь текст
            "pages": List[Dict],  # список страниц с номерами и текстом
            "error": Optional[str]
        }
    """
    if PdfReader is None:
        return {
            "full_text": "",
            "pages": [],
            "error": "pypdf library not installed"
        }

    try:
        reader = PdfReader(file_path)
        pages = []
        full_text_parts = []

        for page_num, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
                pages.append({
                    "page_number": page_num,
                    "text": page_text,
                })
                full_text_parts.append(page_text)
            except Exception as e:
                print(f"[extract_text_from_pdf] Error extracting page {page_num}: {e}")
                pages.append({
                    "page_number": page_num,
                    "text": "",
                })

        full_text = "\n".join(full_text_parts)

        return {
            "full_text": full_text,
            "pages": pages,
            "error": None
        }

    except Exception as e:
        return {
            "full_text": "",
            "pages": [],
            "error": str(e)
        }


def extract_text_from_txt(file_path: str) -> Dict[str, any]:
    """
    Извлекает текст из TXT или MD файла.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            full_text = f.read()

        return {
            "full_text": full_text,
            "pages": [{"page_number": 1, "text": full_text}],
            "error": None
        }
    except UnicodeDecodeError:
        # Попробуем другую кодировку
        try:
            with open(file_path, "r", encoding="cp1251") as f:
                full_text = f.read()
            return {
                "full_text": full_text,
                "pages": [{"page_number": 1, "text": full_text}],
                "error": None
            }
        except Exception as e:
            return {
                "full_text": "",
                "pages": [],
                "error": f"Encoding error: {e}"
            }
    except Exception as e:
        return {
            "full_text": "",
            "pages": [],
            "error": str(e)
        }


def extract_text_from_docx(file_path: str) -> Dict[str, any]:
    """
    Извлекает текст из DOCX файла.
    """
    # Ленивый импорт — выполняется при вызове функции, а не при загрузке модуля
    try:
        from docx import Document as DocxDocument
    except ImportError:
        return {
            "full_text": "",
            "pages": [],
            "error": "python-docx library not installed. Install with: pip install python-docx"
        }

    try:
        doc = DocxDocument(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        full_text = "\n".join(paragraphs)

        return {
            "full_text": full_text,
            "pages": [{"page_number": 1, "text": full_text}],
            "error": None
        }
    except Exception as e:
        return {
            "full_text": "",
            "pages": [],
            "error": str(e)
        }


def extract_text_from_doc(file_path: str) -> Dict[str, any]:
    """
    Извлекает текст из DOC файла (старый формат Word).
    Использует antiword (должен быть установлен в системе).

    Установка antiword:
    - macOS: brew install antiword
    - Ubuntu: apt-get install antiword
    - Docker: apt-get install antiword
    """
    try:
        # Пробуем antiword
        result = subprocess.run(
            ["antiword", file_path],
            capture_output=True,
            timeout=60
        )

        if result.returncode == 0:
            # Пробуем разные кодировки
            for encoding in ["utf-8", "cp1251", "latin-1"]:
                try:
                    full_text = result.stdout.decode(encoding)
                    return {
                        "full_text": full_text,
                        "pages": [{"page_number": 1, "text": full_text}],
                        "error": None
                    }
                except UnicodeDecodeError:
                    continue

            # Если ничего не подошло, используем latin-1 с заменой
            full_text = result.stdout.decode("latin-1", errors="replace")
            return {
                "full_text": full_text,
                "pages": [{"page_number": 1, "text": full_text}],
                "error": None
            }
        else:
            error_msg = result.stderr.decode("utf-8", errors="replace")
            return {
                "full_text": "",
                "pages": [],
                "error": f"antiword error: {error_msg}"
            }

    except FileNotFoundError:
        return {
            "full_text": "",
            "pages": [],
            "error": "antiword not installed. Install with: brew install antiword (macOS) or apt-get install antiword (Linux)"
        }
    except subprocess.TimeoutExpired:
        return {
            "full_text": "",
            "pages": [],
            "error": "Document processing timeout (>60s)"
        }
    except Exception as e:
        return {
            "full_text": "",
            "pages": [],
            "error": str(e)
        }


def extract_text_from_pages(file_path: str) -> Dict[str, any]:
    """
    Извлекает текст из .pages файла (Apple Pages).

    Методы извлечения (в порядке приоритета):
    1. AppleScript — открывает Pages.app и извлекает body text (самый надёжный)
    2. textutil (macOS) — конвертация в txt
    3. QuickLook/Preview.pdf — fallback из архива .pages
    """
    import tempfile
    import zipfile
    import io
    import platform

    abs_path = os.path.abspath(file_path)

    # Метод 1: AppleScript через Pages.app (самый надёжный на macOS)
    if platform.system() == 'Darwin':
        try:
            # AppleScript для открытия документа, извлечения текста и закрытия
            script = f'''
            tell application "Pages"
                set theDoc to open POSIX file "{abs_path}"
                delay 1
                set bodyText to body text of theDoc
                close theDoc saving no
                return bodyText
            end tell
            '''

            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode == 0 and result.stdout.strip():
                full_text = result.stdout.strip()
                return {
                    "full_text": full_text,
                    "pages": [{"page_number": 1, "text": full_text}],
                    "error": None
                }
            else:
                print(f"[extract_pages] AppleScript failed: {result.stderr}")
        except Exception as e:
            print(f"[extract_pages] AppleScript error: {e}")

    # Метод 2: textutil (только на macOS)
    if platform.system() == 'Darwin':
        try:
            with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
                tmp_path = tmp.name

            result = subprocess.run(
                ['textutil', '-convert', 'txt', '-output', tmp_path, abs_path],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                with open(tmp_path, 'r', encoding='utf-8') as f:
                    full_text = f.read()
                os.unlink(tmp_path)

                if full_text.strip():
                    return {
                        "full_text": full_text,
                        "pages": [{"page_number": 1, "text": full_text}],
                        "error": None
                    }
            else:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                print(f"[extract_pages] textutil failed: {result.stderr}")
        except Exception as e:
            print(f"[extract_pages] textutil error: {e}")

    # Метод 3: QuickLook/Preview.pdf из .pages архива
    try:
        if PdfReader is None:
            return {
                "full_text": "",
                "pages": [],
                "error": "pypdf library not installed for .pages fallback"
            }

        with zipfile.ZipFile(abs_path, 'r') as zf:
            namelist = zf.namelist()

            # Ищем Preview.pdf
            pdf_path = None
            for name in namelist:
                if name.endswith('Preview.pdf') or name == 'QuickLook/Preview.pdf':
                    pdf_path = name
                    break

            if not pdf_path:
                for name in namelist:
                    if name.lower().endswith('.pdf'):
                        pdf_path = name
                        break

            if not pdf_path:
                return {
                    "full_text": "",
                    "pages": [],
                    "error": "Could not extract text from .pages file. Please open it in Apple Pages and export as .docx"
                }

            pdf_data = zf.read(pdf_path)
            reader = PdfReader(io.BytesIO(pdf_data))

            text_parts = []
            pages_list = []
            for page_num, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text() or ""
                if page_text.strip():
                    text_parts.append(page_text)
                    pages_list.append({"page_number": page_num, "text": page_text})

            full_text = '\n\n'.join(text_parts)

            return {
                "full_text": full_text,
                "pages": pages_list if pages_list else [{"page_number": 1, "text": full_text}],
                "error": None
            }

    except zipfile.BadZipFile:
        return {
            "full_text": "",
            "pages": [],
            "error": "Could not extract text from .pages file. Please open it in Apple Pages and export as .docx"
        }
    except Exception as e:
        return {
            "full_text": "",
            "pages": [],
            "error": f"Failed to extract from .pages: {str(e)}. Please export as .docx in Apple Pages"
        }


def extract_text_from_file(file_path: str) -> Dict[str, any]:
    """
    Извлекает текст из файла в зависимости от его расширения.
    Поддерживаемые форматы: PDF, TXT, MD, DOCX, DOC, PAGES
    """
    ext = Path(file_path).suffix.lower()

    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext in (".txt", ".md"):
        return extract_text_from_txt(file_path)
    elif ext == ".docx":
        return extract_text_from_docx(file_path)
    elif ext == ".doc":
        return extract_text_from_doc(file_path)
    elif ext == ".pages":
        return extract_text_from_pages(file_path)
    else:
        return {
            "full_text": "",
            "pages": [],
            "error": f"Unsupported file format: {ext}. Supported: PDF, TXT, MD, DOCX, DOC, PAGES"
        }


async def generate_embeddings_batch_with_tokens(texts: List[str]) -> tuple[List[List[float]], int, str]:
    """
    Генерирует embeddings для списка текстов с retry логикой.
    Использует batch API для эффективности.

    Возвращает (список embeddings, общее количество токенов, модель).
    """
    if not texts:
        from src.config import settings
        return [], 0, settings.openai_embeddings_model

    max_retries = 3
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            embeddings, tokens, model = await get_batch_embeddings_with_usage(texts)
            return embeddings, tokens, model
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"[generate_embeddings_batch] Retry {attempt + 1}/{max_retries} after error: {e}")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            else:
                print(f"[generate_embeddings_batch] Failed after {max_retries} attempts: {e}")
                # В случае полной неудачи возвращаем нулевые векторы
                from src.config import settings
                return [[0.0] * 1536 for _ in texts], 0, settings.openai_embeddings_model

    from src.config import settings
    return [[0.0] * 1536 for _ in texts], 0, settings.openai_embeddings_model


async def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Генерирует embeddings для списка текстов (обратная совместимость).
    """
    embeddings, _, _ = await generate_embeddings_batch_with_tokens(texts)
    return embeddings


async def process_document(
    file_path: str,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    force_update: bool = False,
    chunking_mode: ChunkingMode = "semantic",
    use_gemini_embeddings: bool = True,
) -> Dict[str, any]:
    """
    Обрабатывает документ: извлекает текст, разбивает на чанки,
    генерирует embeddings и сохраняет в БД.

    Поддерживаемые форматы: PDF, TXT, MD, DOCX

    Параметры:
        file_path: Путь к файлу (PDF, TXT, MD, DOCX)
        category: Категория консультации (УСТАРЕЛО, оставлено для совместимости)
        subcategory: Культура растения (например, "малина общая", "клубника летняя")
        force_update: Если True, перезаписывает существующий документ
        chunking_mode: "semantic" (RAG v2.0) или "fixed" (legacy)
        use_gemini_embeddings: True = Gemini API, False = OpenAI API

    Возвращает:
        {
            "success": bool,
            "document_id": Optional[int],
            "chunks_count": int,
            "error": Optional[str]
        }
    """
    result = {
        "success": False,
        "document_id": None,
        "chunks_count": 0,
        "error": None
    }

    # 1. Проверка существования файла
    if not os.path.exists(file_path):
        result["error"] = f"File not found: {file_path}"
        return result

    # 2. Проверка размера файла
    file_size = os.path.getsize(file_path)
    if file_size > MAX_FILE_SIZE:
        result["error"] = f"File too large: {file_size} bytes (max {MAX_FILE_SIZE})"
        return result

    if file_size == 0:
        result["error"] = "File is empty"
        return result

    # 3. Вычисление хеша
    try:
        file_hash = compute_file_hash(file_path)
    except Exception as e:
        result["error"] = f"Failed to compute hash: {e}"
        return result

    # 4. Проверка дубликата
    if not force_update:
        existing_doc = await document_exists_by_hash(file_hash)
        if existing_doc:
            result["error"] = f"Document already exists (ID: {existing_doc['id']}, filename: {existing_doc['filename']})"
            return result

    # 5. Извлечение текста из файла
    filename = os.path.basename(file_path)
    ext = Path(file_path).suffix.lower()
    print(f"[process_document] Processing: {filename} (mode: {chunking_mode})")

    # RAG v2.0: Используем улучшенный парсер для DOCX
    list_boundaries = []
    if ext == ".docx" and chunking_mode == "semantic":
        extraction_result = extract_text_from_docx_v2(file_path)
        if extraction_result["error"]:
            result["error"] = f"Text extraction failed: {extraction_result['error']}"
            return result
        full_text = extraction_result["full_text"]
        list_boundaries = extraction_result.get("lists", [])
        pages = [{"page_number": 1, "text": full_text}]  # DOCX как одна страница
    else:
        extraction_result = extract_text_from_file(file_path)
        if extraction_result["error"]:
            result["error"] = f"Text extraction failed: {extraction_result['error']}"
            return result
        full_text = extraction_result["full_text"]
        pages = extraction_result["pages"]
        # Для не-DOCX файлов детектируем списки из текста
        if chunking_mode == "semantic":
            list_boundaries = detect_list_boundaries(full_text)

    # 6. Проверка минимальной длины текста
    if len(full_text.strip()) < MIN_TEXT_LENGTH:
        result["error"] = f"Extracted text too short: {len(full_text)} chars (min {MIN_TEXT_LENGTH})"
        return result

    # 7. Создание записи в documents (статус 'processing')
    try:
        document_id = await document_insert(
            filename=filename,
            file_path=file_path,
            file_hash=file_hash,
            file_size_bytes=file_size,
            category=category or "общая_информация",
            subcategory=subcategory,
            processing_status="processing",
        )
        print(f"[process_document] Created document record ID: {document_id}")
    except Exception as e:
        result["error"] = f"Failed to insert document: {e}"
        return result

    # 8. Разбивка на чанки
    try:
        if chunking_mode == "semantic":
            # RAG v2.0: Semantic chunking с Gemini
            print(f"[process_document] Using semantic chunking (lists detected: {len(list_boundaries)})")
            chunks = await chunk_text_semantic(
                text=full_text,
                list_boundaries=list_boundaries,
                threshold_percentile=70,
                min_chunk_size=100,
                max_chunk_size=2000,
            )
        else:
            # Legacy: Fixed-size chunking
            print(f"[process_document] Using fixed-size chunking")
            chunks = chunk_text(full_text, chunk_size=800, overlap=200)

        print(f"[process_document] Created {len(chunks)} chunks")
    except Exception as e:
        await document_update_status(
            document_id,
            status="failed",
            error=f"Chunking failed: {e}"
        )
        result["error"] = f"Chunking failed: {e}"
        return result

    if len(chunks) == 0:
        await document_update_status(
            document_id,
            status="failed",
            error="No chunks generated"
        )
        result["error"] = "No chunks generated"
        return result

    # 9. Определение номера страницы для каждого чанка (упрощенная логика)
    # Для более точного определения нужна более сложная логика
    chunk_data_list = []
    for chunk_info in chunks:
        # Упрощенно: пытаемся определить страницу по позиции в тексте
        page_number = None
        cumulative_length = 0
        for page in pages:
            page_text_len = len(page["text"])
            if chunk_info["start_pos"] >= cumulative_length and chunk_info["start_pos"] < cumulative_length + page_text_len:
                page_number = page["page_number"]
                break
            cumulative_length += page_text_len

        chunk_data_list.append({
            "chunk_index": chunk_info["chunk_index"],
            "chunk_text": chunk_info["chunk_text"],
            "chunk_size": chunk_info["chunk_size"],
            "page_number": page_number,
        })

    # Убедимся что category не None
    category = category or "общая_информация"

    # 10. Генерация embeddings батчами с подсчётом токенов
    try:
        print(f"[process_document] Generating embeddings for {len(chunk_data_list)} chunks...")
        all_embeddings = []
        total_tokens = 0
        embedding_model = None

        batch_texts = [c["chunk_text"] for c in chunk_data_list]

        if use_gemini_embeddings and settings.queryrouter_api_key:
            # RAG v2.0: Gemini Embeddings
            print(f"[process_document] Using Gemini embeddings (gemini-embedding-001)")
            embedding_model = "gemini-embedding-001"

            for i in range(0, len(batch_texts), EMBEDDING_BATCH_SIZE):
                batch = batch_texts[i:i + EMBEDDING_BATCH_SIZE]
                print(f"[process_document] Processing batch {i // EMBEDDING_BATCH_SIZE + 1}/{(len(batch_texts) + EMBEDDING_BATCH_SIZE - 1) // EMBEDDING_BATCH_SIZE}")

                batch_embeddings = await get_batch_embeddings_for_documents(
                    texts=batch,
                    output_dimensionality=3072,  # Полная размерность для качества
                )
                all_embeddings.extend(batch_embeddings)

                # Оцениваем токены (~4 символа = 1 токен для русского)
                total_tokens += sum(len(t) // 4 for t in batch)

                # Небольшая задержка между батчами
                if i + EMBEDDING_BATCH_SIZE < len(batch_texts):
                    await asyncio.sleep(0.3)

            # Стоимость Gemini: $0.15 / 1M tokens
            embedding_cost = total_tokens * 0.00000015

        else:
            # Legacy: OpenAI Embeddings
            print(f"[process_document] Using OpenAI embeddings")

            for i in range(0, len(chunk_data_list), EMBEDDING_BATCH_SIZE):
                batch = chunk_data_list[i:i + EMBEDDING_BATCH_SIZE]
                batch_chunk_texts = [c["chunk_text"] for c in batch]

                print(f"[process_document] Processing batch {i // EMBEDDING_BATCH_SIZE + 1}/{(len(chunk_data_list) + EMBEDDING_BATCH_SIZE - 1) // EMBEDDING_BATCH_SIZE}")

                batch_embeddings, batch_tokens, batch_model = await generate_embeddings_batch_with_tokens(batch_chunk_texts)
                all_embeddings.extend(batch_embeddings)
                total_tokens += batch_tokens
                embedding_model = batch_model

                # Небольшая задержка между батчами для избежания rate limits
                if i + EMBEDDING_BATCH_SIZE < len(chunk_data_list):
                    await asyncio.sleep(0.5)

            # Расчёт стоимости по реальной модели из API
            embedding_cost = calculate_embedding_cost(embedding_model, total_tokens)

        print(f"[process_document] Generated {len(all_embeddings)} embeddings, {total_tokens} tokens, model: {embedding_model}, cost: ${embedding_cost:.6f}")

    except Exception as e:
        await document_update_status(
            document_id,
            status="failed",
            error=f"Embedding generation failed: {e}"
        )
        result["error"] = f"Embedding generation failed: {e}"
        return result

    # 11. Подготовка данных для bulk insert
    chunks_for_db = []
    for chunk_data, embedding in zip(chunk_data_list, all_embeddings):
        chunks_for_db.append({
            "document_id": document_id,
            "chunk_index": chunk_data["chunk_index"],
            "chunk_text": chunk_data["chunk_text"],
            "chunk_size": chunk_data["chunk_size"],
            "page_number": chunk_data["page_number"],
            "embedding": embedding,
            "category": category,
            "subcategory": subcategory,
        })

    # 12. Массовая вставка чанков в БД
    try:
        await chunks_bulk_insert(chunks_for_db)
        print(f"[process_document] Inserted {len(chunks_for_db)} chunks into DB")
    except Exception as e:
        await document_update_status(
            document_id,
            status="failed",
            error=f"Chunk insertion failed: {e}"
        )
        result["error"] = f"Chunk insertion failed: {e}"
        return result

    # 13. RAG v2.0: Генерация контекста для чанков через LLM
    context_cost = 0.0
    context_tokens = 0
    try:
        print(f"[process_document] Generating context for {len(chunks_for_db)} chunks...")

        # Получаем чанки из БД (нужны их ID)
        db_chunks = await get_chunks_by_document(document_id)

        # Генерируем контексты
        context_result = await generate_contexts_for_document(
            document_text=full_text,
            chunks=db_chunks,
        )

        context_cost = context_result.total_cost
        context_tokens = context_result.total_input_tokens + context_result.total_output_tokens

        # Обновляем контексты в БД
        if context_result.success_count > 0:
            updates = [
                {"chunk_id": cr.chunk_id, "context": cr.context}
                for cr in context_result.contexts
                if cr.context  # Только непустые контексты
            ]
            await bulk_update_chunk_contexts(updates)

        print(
            f"[process_document] Context generation: {context_result.success_count}/{len(db_chunks)} chunks, "
            f"tokens: {context_tokens}, cost: ${context_cost:.4f}"
        )

    except Exception as e:
        # Ошибка генерации контекста не критична — документ всё равно загружен
        print(f"[process_document] Context generation failed (non-critical): {e}")

    # 14. Обновление статуса документа на 'completed' с токенами, стоимостью и моделью
    try:
        await document_update_status(
            document_id,
            status="completed",
            total_chunks=len(chunks_for_db),
            embedding_tokens=total_tokens,
            embedding_cost_usd=embedding_cost,
            embedding_model=embedding_model,
            context_generation_cost=context_cost,
            context_generation_tokens=context_tokens,
        )
        print(f"[process_document] Document {document_id} processing completed")
    except Exception as e:
        result["error"] = f"Failed to update document status: {e}"
        return result

    # 15. Успех
    result["success"] = True
    result["document_id"] = document_id
    result["chunks_count"] = len(chunks_for_db)
    result["context_cost"] = context_cost
    result["context_tokens"] = context_tokens

    return result


# Алиас для обратной совместимости
process_pdf_document = process_document
