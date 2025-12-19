# src/services/db/prompt_document_repo.py

"""
Репозиторий для работы с промт-документами.

Промт-документы — это файлы, содержимое которых добавляется в системные промпты
по категориям: культура, подкультура, тип работ.

Функции:
    - get_cultures: Список культур
    - get_subcultures: Подкультуры для культуры
    - get_work_types: Список типов работ
    - get_documents: Список документов с фильтрацией
    - get_document_by_id: Один документ по ID
    - get_document_content: Текст документа
    - get_document_by_combination: Документ по комбинации (культура + подкультура + тип работ)
    - create_document: Создать документ
    - update_document_content: Обновить извлечённый текст
    - update_document_extraction_error: Записать ошибку извлечения
    - delete_document: Удалить документ
    - document_exists_by_hash: Проверить дубликат по хешу
"""

import logging
from typing import Optional, List, Dict, Any

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


# =============================================================================
# Cultures
# =============================================================================

async def get_cultures() -> List[Dict[str, Any]]:
    """Получить все культуры, отсортированные по порядку."""
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, sort_order, created_at
            FROM prompt_cultures
            ORDER BY sort_order ASC
            """
        )

        return [dict(row) for row in rows]


async def get_culture_by_id(culture_id: int) -> Optional[Dict[str, Any]]:
    """Получить культуру по ID."""
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name, sort_order, created_at FROM prompt_cultures WHERE id = $1",
            culture_id
        )

        return dict(row) if row else None


# =============================================================================
# Subcultures
# =============================================================================

async def get_subcultures(culture_id: int) -> List[Dict[str, Any]]:
    """Получить подкультуры для указанной культуры."""
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, culture_id, name, sort_order, created_at
            FROM prompt_subcultures
            WHERE culture_id = $1
            ORDER BY sort_order ASC
            """,
            culture_id
        )

        return [dict(row) for row in rows]


async def get_subculture_by_id(subculture_id: int) -> Optional[Dict[str, Any]]:
    """Получить подкультуру по ID."""
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, culture_id, name, sort_order, created_at
            FROM prompt_subcultures
            WHERE id = $1
            """,
            subculture_id
        )

        return dict(row) if row else None


# =============================================================================
# Work Types
# =============================================================================

async def get_work_types() -> List[Dict[str, Any]]:
    """Получить все типы работ, отсортированные по порядку."""
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, sort_order, created_at
            FROM prompt_work_types
            ORDER BY sort_order ASC
            """
        )

        return [dict(row) for row in rows]


async def get_work_type_by_id(work_type_id: int) -> Optional[Dict[str, Any]]:
    """Получить тип работ по ID."""
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name, sort_order, created_at FROM prompt_work_types WHERE id = $1",
            work_type_id
        )

        return dict(row) if row else None


# =============================================================================
# Documents CRUD
# =============================================================================

async def get_documents(
    culture_id: Optional[int] = None,
    subculture_id: Optional[int] = None,
    work_type_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Получить список документов с фильтрацией.

    Args:
        culture_id: Фильтр по культуре
        subculture_id: Фильтр по подкультуре
        work_type_id: Фильтр по типу работ

    Returns:
        {
            "documents": [...],
            "total": int
        }
    """
    pool = get_pool()

    # Собираем условия WHERE
    conditions = []
    params = []
    param_idx = 1

    if culture_id is not None:
        conditions.append(f"d.culture_id = ${param_idx}")
        params.append(culture_id)
        param_idx += 1

    if subculture_id is not None:
        conditions.append(f"d.subculture_id = ${param_idx}")
        params.append(subculture_id)
        param_idx += 1

    if work_type_id is not None:
        conditions.append(f"d.work_type_id = ${param_idx}")
        params.append(work_type_id)
        param_idx += 1

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with pool.acquire() as conn:
        query = f"""
            SELECT
                d.id,
                d.culture_id,
                c.name as culture_name,
                d.subculture_id,
                s.name as subculture_name,
                d.work_type_id,
                w.name as work_type_name,
                d.filename,
                d.original_filename,
                d.file_size,
                d.file_type,
                d.extraction_status,
                d.extraction_error,
                d.created_at,
                d.updated_at
            FROM prompt_documents d
            JOIN prompt_cultures c ON c.id = d.culture_id
            LEFT JOIN prompt_subcultures s ON s.id = d.subculture_id
            JOIN prompt_work_types w ON w.id = d.work_type_id
            {where_clause}
            ORDER BY c.sort_order, s.sort_order NULLS LAST, w.sort_order, d.created_at DESC
        """

        rows = await conn.fetch(query, *params)

        return {
            "documents": [dict(row) for row in rows],
            "total": len(rows)
        }


async def get_document_by_id(document_id: int) -> Optional[Dict[str, Any]]:
    """Получить документ по ID (без текста контента)."""
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                d.id,
                d.culture_id,
                c.name as culture_name,
                d.subculture_id,
                s.name as subculture_name,
                d.work_type_id,
                w.name as work_type_name,
                d.filename,
                d.original_filename,
                d.file_path,
                d.file_hash,
                d.file_size,
                d.file_type,
                d.extraction_status,
                d.extraction_error,
                d.content_extracted_at,
                d.uploaded_by_admin_id,
                d.created_at,
                d.updated_at
            FROM prompt_documents d
            JOIN prompt_cultures c ON c.id = d.culture_id
            LEFT JOIN prompt_subcultures s ON s.id = d.subculture_id
            JOIN prompt_work_types w ON w.id = d.work_type_id
            WHERE d.id = $1
            """,
            document_id
        )

        return dict(row) if row else None


async def get_document_content(document_id: int) -> Optional[str]:
    """Получить текстовый контент документа."""
    pool = get_pool()

    async with pool.acquire() as conn:
        content = await conn.fetchval(
            "SELECT content_text FROM prompt_documents WHERE id = $1",
            document_id
        )

        return content


async def get_document_by_combination(
    culture_id: int,
    subculture_id: Optional[int],
    work_type_id: int
) -> Optional[Dict[str, Any]]:
    """
    Получить документ по комбинации культура + подкультура + тип работ.

    Используется для проверки, существует ли уже документ для этой комбинации.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        if subculture_id is None:
            row = await conn.fetchrow(
                """
                SELECT id, filename, original_filename
                FROM prompt_documents
                WHERE culture_id = $1 AND subculture_id IS NULL AND work_type_id = $2
                """,
                culture_id, work_type_id
            )
        else:
            row = await conn.fetchrow(
                """
                SELECT id, filename, original_filename
                FROM prompt_documents
                WHERE culture_id = $1 AND subculture_id = $2 AND work_type_id = $3
                """,
                culture_id, subculture_id, work_type_id
            )

        return dict(row) if row else None


async def create_document(
    culture_id: int,
    subculture_id: Optional[int],
    work_type_id: int,
    filename: str,
    original_filename: str,
    file_path: str,
    file_hash: str,
    file_size: int,
    file_type: str,
    uploaded_by_admin_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Создать запись о документе.

    Args:
        culture_id: ID культуры
        subculture_id: ID подкультуры (может быть None для Кустарники)
        work_type_id: ID типа работ
        filename: Имя файла на диске
        original_filename: Оригинальное имя файла
        file_path: Путь к файлу
        file_hash: SHA256 хеш файла
        file_size: Размер в байтах
        file_type: Тип файла (pages, docx, pdf)
        uploaded_by_admin_id: ID админа, загрузившего файл

    Returns:
        Созданный документ с данными о культуре/подкультуре/типе работ
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO prompt_documents (
                culture_id, subculture_id, work_type_id,
                filename, original_filename, file_path, file_hash,
                file_size, file_type, uploaded_by_admin_id
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING id, culture_id, subculture_id, work_type_id,
                      filename, original_filename, file_path, file_hash,
                      file_size, file_type, extraction_status,
                      uploaded_by_admin_id, created_at, updated_at
            """,
            culture_id, subculture_id, work_type_id,
            filename, original_filename, file_path, file_hash,
            file_size, file_type, uploaded_by_admin_id
        )

        doc = dict(row)

        # Добавляем имена культуры/подкультуры/типа работ
        culture = await conn.fetchrow(
            "SELECT name FROM prompt_cultures WHERE id = $1", culture_id
        )
        doc['culture_name'] = culture['name'] if culture else None

        if subculture_id:
            subculture = await conn.fetchrow(
                "SELECT name FROM prompt_subcultures WHERE id = $1", subculture_id
            )
            doc['subculture_name'] = subculture['name'] if subculture else None
        else:
            doc['subculture_name'] = None

        work_type = await conn.fetchrow(
            "SELECT name FROM prompt_work_types WHERE id = $1", work_type_id
        )
        doc['work_type_name'] = work_type['name'] if work_type else None

        return doc


async def update_document_content(
    document_id: int,
    content_text: str,
    extraction_status: str = 'completed'
) -> Optional[Dict[str, Any]]:
    """
    Обновить извлечённый текст документа.

    Args:
        document_id: ID документа
        content_text: Извлечённый текст
        extraction_status: Статус (по умолчанию 'completed')

    Returns:
        Обновлённый документ или None
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE prompt_documents
            SET content_text = $2,
                extraction_status = $3,
                content_extracted_at = NOW()
            WHERE id = $1
            RETURNING id, extraction_status, content_extracted_at, updated_at
            """,
            document_id, content_text, extraction_status
        )

        return dict(row) if row else None


async def update_document_extraction_error(
    document_id: int,
    error: str
) -> Optional[Dict[str, Any]]:
    """
    Записать ошибку извлечения текста.

    Args:
        document_id: ID документа
        error: Текст ошибки

    Returns:
        Обновлённый документ или None
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE prompt_documents
            SET extraction_status = 'failed',
                extraction_error = $2
            WHERE id = $1
            RETURNING id, extraction_status, extraction_error, updated_at
            """,
            document_id, error
        )

        return dict(row) if row else None


async def delete_document(document_id: int) -> Optional[str]:
    """
    Удалить документ.

    Returns:
        Путь к файлу для удаления с диска, или None если документ не найден
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        # Сначала получаем путь к файлу
        file_path = await conn.fetchval(
            "SELECT file_path FROM prompt_documents WHERE id = $1",
            document_id
        )

        if not file_path:
            return None

        # Удаляем запись
        result = await conn.execute(
            "DELETE FROM prompt_documents WHERE id = $1",
            document_id
        )

        if result == "DELETE 1":
            return file_path

        return None


async def document_exists_by_hash(file_hash: str) -> bool:
    """Проверить, существует ли документ с таким хешем."""
    pool = get_pool()

    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM prompt_documents WHERE file_hash = $1)",
            file_hash
        )

        return exists


async def replace_document(
    document_id: int,
    filename: str,
    original_filename: str,
    file_path: str,
    file_hash: str,
    file_size: int,
    file_type: str
) -> Optional[Dict[str, Any]]:
    """
    Заменить файл документа (сохраняя категории).

    Args:
        document_id: ID документа
        filename: Новое имя файла на диске
        original_filename: Новое оригинальное имя
        file_path: Новый путь к файлу
        file_hash: Новый хеш
        file_size: Новый размер
        file_type: Новый тип файла

    Returns:
        Обновлённый документ или None
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE prompt_documents
            SET filename = $2,
                original_filename = $3,
                file_path = $4,
                file_hash = $5,
                file_size = $6,
                file_type = $7,
                content_text = NULL,
                extraction_status = 'pending',
                extraction_error = NULL,
                content_extracted_at = NULL
            WHERE id = $1
            RETURNING id, culture_id, subculture_id, work_type_id,
                      filename, original_filename, file_path, file_hash,
                      file_size, file_type, extraction_status,
                      created_at, updated_at
            """,
            document_id, filename, original_filename, file_path,
            file_hash, file_size, file_type
        )

        if not row:
            return None

        doc = dict(row)

        # Добавляем имена
        culture = await conn.fetchrow(
            "SELECT name FROM prompt_cultures WHERE id = $1", doc['culture_id']
        )
        doc['culture_name'] = culture['name'] if culture else None

        if doc['subculture_id']:
            subculture = await conn.fetchrow(
                "SELECT name FROM prompt_subcultures WHERE id = $1", doc['subculture_id']
            )
            doc['subculture_name'] = subculture['name'] if subculture else None
        else:
            doc['subculture_name'] = None

        work_type = await conn.fetchrow(
            "SELECT name FROM prompt_work_types WHERE id = $1", doc['work_type_id']
        )
        doc['work_type_name'] = work_type['name'] if work_type else None

        return doc


# =============================================================================
# Lookup by names (for prompt integration)
# =============================================================================

# Маппинг строковых названий культур на ID в БД
# Формат LLM: "клубника летняя", "клубника ремонтантная", "клубника общая", "малина летняя", и т.д.
CULTURE_NAME_TO_ID = {
    # Клубника
    "клубника": 1,
    "клубника летняя": 1,
    "клубника ремонтантная": 1,
    "клубника общая": 1,
    "земляника": 1,
    "земляника садовая": 1,
    # Малина
    "малина": 2,
    "малина летняя": 2,
    "малина ремонтантная": 2,
    "малина общая": 2,
    # Кустарники
    "кустарники": 3,
    "голубика": 3,
    "смородина": 3,
    "крыжовник": 3,
    "жимолость": 3,
    "ежевика": 3,
}

# Маппинг подкультур (для клубники и малины)
SUBCULTURE_NAME_TO_ID = {
    # Клубника
    ("клубника летняя", 1): 1,      # летняя
    ("клубника ремонтантная", 1): 2, # ремонтантная
    ("клубника общая", 1): 3,       # общая
    ("клубника", 1): 3,             # общая по умолчанию
    # Малина
    ("малина летняя", 2): 4,        # летняя
    ("малина ремонтантная", 2): 5,  # ремонтантная
    ("малина общая", 2): 6,         # общая
    ("малина", 2): 6,               # общая по умолчанию
}

# Маппинг категорий консультаций на типы работ
CATEGORY_TO_WORK_TYPE_ID = {
    "питание растений": 1,
    "защита растений": 2,
    "болезни и вредители": 2,  # алиас
    "посадка и уход": 3,
    "улучшение почвы": 4,
    "подбор сорта": 5,
    "подбор сортов": 5,  # алиас
}


async def get_prompt_document_content_for_consultation(
    culture: str,
    consultation_category: str
) -> Optional[str]:
    """
    Получить текст промт-документов для консультации.

    Ищет ВСЕ подходящие документы и объединяет их:
    1. Общий документ для культуры (например, "клубника общая")
    2. Специфический документ для подкультуры (например, "клубника летняя")

    Оба документа дополняют друг друга и возвращаются вместе.

    Args:
        culture: Культура из LLM (например, "клубника летняя", "малина ремонтантная")
        consultation_category: Категория консультации (например, "защита растений")

    Returns:
        Объединённый текст документов или None если ничего не найдено
    """
    # Нормализуем
    culture_lower = culture.lower().strip()
    category_lower = consultation_category.lower().strip()

    # Получаем ID культуры
    culture_id = CULTURE_NAME_TO_ID.get(culture_lower)
    if not culture_id:
        # Пробуем найти по первому слову (например, "голубика высокорослая" → "голубика")
        first_word = culture_lower.split()[0] if culture_lower else ""
        culture_id = CULTURE_NAME_TO_ID.get(first_word)

    if not culture_id:
        logger.debug(f"[prompt_doc] Culture not found: {culture}")
        return None

    # Получаем ID типа работ
    work_type_id = CATEGORY_TO_WORK_TYPE_ID.get(category_lower)
    if not work_type_id:
        logger.debug(f"[prompt_doc] Work type not found for category: {consultation_category}")
        return None

    # Получаем ID подкультуры
    subculture_id = SUBCULTURE_NAME_TO_ID.get((culture_lower, culture_id))

    # ID "общая" подкультуры для клубники и малины
    general_subculture_id = {1: 3, 2: 6}.get(culture_id)

    pool = get_pool()
    documents_content = []

    async with pool.acquire() as conn:
        # 1. Ищем ОБЩИЙ документ (подкультура "общая")
        if general_subculture_id:
            general_content = await conn.fetchval(
                """
                SELECT content_text
                FROM prompt_documents
                WHERE culture_id = $1
                  AND subculture_id = $2
                  AND work_type_id = $3
                  AND extraction_status = 'completed'
                  AND content_text IS NOT NULL
                """,
                culture_id, general_subculture_id, work_type_id
            )

            if general_content:
                logger.info(f"[prompt_doc] Found GENERAL doc: culture_id={culture_id}, subculture_id={general_subculture_id}, work_type_id={work_type_id}")
                documents_content.append(("📗 ОБЩАЯ ИНФОРМАЦИЯ", general_content))

        # 2. Ищем СПЕЦИФИЧЕСКИЙ документ (конкретная подкультура)
        # Только если подкультура отличается от "общая"
        if subculture_id and subculture_id != general_subculture_id:
            specific_content = await conn.fetchval(
                """
                SELECT content_text
                FROM prompt_documents
                WHERE culture_id = $1
                  AND subculture_id = $2
                  AND work_type_id = $3
                  AND extraction_status = 'completed'
                  AND content_text IS NOT NULL
                """,
                culture_id, subculture_id, work_type_id
            )

            if specific_content:
                # Определяем название подкультуры
                subculture_name = await conn.fetchval(
                    "SELECT name FROM prompt_subcultures WHERE id = $1",
                    subculture_id
                )
                label = f"📘 СПЕЦИФИКА: {subculture_name.upper()}" if subculture_name else "📘 СПЕЦИФИКА"
                logger.info(f"[prompt_doc] Found SPECIFIC doc: culture_id={culture_id}, subculture_id={subculture_id}, work_type_id={work_type_id}")
                documents_content.append((label, specific_content))

        # 3. Для кустарников (culture_id=3) — подкультура NULL
        if culture_id == 3:
            bushes_content = await conn.fetchval(
                """
                SELECT content_text
                FROM prompt_documents
                WHERE culture_id = $1
                  AND subculture_id IS NULL
                  AND work_type_id = $2
                  AND extraction_status = 'completed'
                  AND content_text IS NOT NULL
                """,
                culture_id, work_type_id
            )

            if bushes_content:
                logger.info(f"[prompt_doc] Found BUSHES doc: culture_id={culture_id}, work_type_id={work_type_id}")
                documents_content.append(("📗 ИНФОРМАЦИЯ", bushes_content))

    # Объединяем все найденные документы
    if not documents_content:
        logger.debug(f"[prompt_doc] No documents found for culture={culture}, category={consultation_category}")
        return None

    # Формируем итоговый текст
    parts = []
    for label, content in documents_content:
        parts.append(f"{label}\n\n{content}")

    combined = "\n\n---\n\n".join(parts)
    logger.info(f"[prompt_doc] Combined {len(documents_content)} documents, total {len(combined)} chars")
    return combined
