"""
Репозиторий для работы с промптами.

Таблицы:
- prompt_groups: группы промптов (base, categories, references, article, other)
- prompt_subgroups: подгруппы (nutrition, diseases_pests, etc.)
- prompts: сами промпты с текстом
- prompt_history: история изменений (автоматическая через триггер)
"""

import logging
from typing import Dict, List, Any, Optional

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


# ============================================================================
# Чтение групп и подгрупп
# ============================================================================

async def get_all_groups() -> List[Dict[str, Any]]:
    """
    Получает все группы промптов с их подгруппами и счётчиками.

    Returns:
        Список групп с вложенными подгруппами и количеством промптов
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        # Получаем группы
        groups = await conn.fetch("""
            SELECT
                g.id,
                g.slug,
                g.name,
                g.description,
                g.icon,
                g.sort_order,
                g.is_system,
                (SELECT COUNT(*) FROM prompts p WHERE p.group_id = g.id) as prompts_count
            FROM prompt_groups g
            ORDER BY g.sort_order, g.name
        """)

        result = []
        for group in groups:
            group_dict = dict(group)

            # Получаем подгруппы для этой группы
            subgroups = await conn.fetch("""
                SELECT
                    s.id,
                    s.slug,
                    s.name,
                    s.description,
                    s.sort_order,
                    s.is_system,
                    (SELECT COUNT(*) FROM prompts p WHERE p.subgroup_id = s.id) as prompts_count
                FROM prompt_subgroups s
                WHERE s.group_id = $1
                ORDER BY s.sort_order, s.name
            """, group["id"])

            group_dict["subgroups"] = [dict(s) for s in subgroups]
            result.append(group_dict)

        return result


async def get_group_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """Получает группу по slug."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id, slug, name, description, icon, sort_order, is_system
            FROM prompt_groups
            WHERE slug = $1
        """, slug)
        return dict(row) if row else None


async def get_subgroup_by_slug(group_id: int, slug: str) -> Optional[Dict[str, Any]]:
    """Получает подгруппу по group_id и slug."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id, group_id, slug, name, description, sort_order, is_system
            FROM prompt_subgroups
            WHERE group_id = $1 AND slug = $2
        """, group_id, slug)
        return dict(row) if row else None


# ============================================================================
# Чтение промптов
# ============================================================================

async def get_all_prompts(
    group_id: Optional[int] = None,
    subgroup_id: Optional[int] = None,
    is_enabled: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """
    Получает все промпты с опциональными фильтрами.

    Args:
        group_id: Фильтр по группе
        subgroup_id: Фильтр по подгруппе
        is_enabled: Фильтр по включённости

    Returns:
        Список промптов
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        query = """
            SELECT
                p.id,
                p.group_id,
                p.subgroup_id,
                p.slug,
                p.name,
                p.description,
                p.content,
                p.is_enabled,
                p.use_minimal_base,
                p.is_system,
                p.version,
                p.updated_by,
                p.created_at,
                p.updated_at,
                g.slug as group_slug,
                g.name as group_name,
                s.slug as subgroup_slug,
                s.name as subgroup_name
            FROM prompts p
            JOIN prompt_groups g ON p.group_id = g.id
            LEFT JOIN prompt_subgroups s ON p.subgroup_id = s.id
            WHERE 1=1
        """
        params = []
        param_idx = 1

        if group_id is not None:
            query += f" AND p.group_id = ${param_idx}"
            params.append(group_id)
            param_idx += 1

        if subgroup_id is not None:
            query += f" AND p.subgroup_id = ${param_idx}"
            params.append(subgroup_id)
            param_idx += 1

        if is_enabled is not None:
            query += f" AND p.is_enabled = ${param_idx}"
            params.append(is_enabled)
            param_idx += 1

        query += " ORDER BY g.sort_order, s.sort_order, p.name"

        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


async def get_prompt_by_id(prompt_id: int) -> Optional[Dict[str, Any]]:
    """Получает промпт по ID."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT
                p.id,
                p.group_id,
                p.subgroup_id,
                p.slug,
                p.name,
                p.description,
                p.content,
                p.is_enabled,
                p.use_minimal_base,
                p.is_system,
                p.version,
                p.updated_by,
                p.created_at,
                p.updated_at,
                g.slug as group_slug,
                g.name as group_name,
                s.slug as subgroup_slug,
                s.name as subgroup_name
            FROM prompts p
            JOIN prompt_groups g ON p.group_id = g.id
            LEFT JOIN prompt_subgroups s ON p.subgroup_id = s.id
            WHERE p.id = $1
        """, prompt_id)
        return dict(row) if row else None


async def get_prompt_by_slug(
    group_slug: str,
    slug: str,
    subgroup_slug: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Получает промпт по slug-пути.

    Args:
        group_slug: Slug группы (например, "base", "categories")
        slug: Slug промпта (например, "role", "strawberry")
        subgroup_slug: Slug подгруппы (опционально, например, "nutrition")

    Returns:
        Промпт или None
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        if subgroup_slug:
            row = await conn.fetchrow("""
                SELECT
                    p.id,
                    p.group_id,
                    p.subgroup_id,
                    p.slug,
                    p.name,
                    p.description,
                    p.content,
                    p.is_enabled,
                    p.use_minimal_base,
                    p.is_system,
                    p.version,
                    p.updated_by,
                    p.created_at,
                    p.updated_at
                FROM prompts p
                JOIN prompt_groups g ON p.group_id = g.id
                JOIN prompt_subgroups s ON p.subgroup_id = s.id
                WHERE g.slug = $1 AND s.slug = $2 AND p.slug = $3
            """, group_slug, subgroup_slug, slug)
        else:
            row = await conn.fetchrow("""
                SELECT
                    p.id,
                    p.group_id,
                    p.subgroup_id,
                    p.slug,
                    p.name,
                    p.description,
                    p.content,
                    p.is_enabled,
                    p.use_minimal_base,
                    p.is_system,
                    p.version,
                    p.updated_by,
                    p.created_at,
                    p.updated_at
                FROM prompts p
                JOIN prompt_groups g ON p.group_id = g.id
                WHERE g.slug = $1 AND p.slug = $2 AND p.subgroup_id IS NULL
            """, group_slug, slug)

        return dict(row) if row else None


# ============================================================================
# Специализированные функции для consultation_prompts.py
# ============================================================================

async def get_base_sections(is_enabled_only: bool = True) -> List[Dict[str, Any]]:
    """
    Получает все базовые секции для build_base_prompt.

    Args:
        is_enabled_only: Если True, возвращает только включённые секции

    Returns:
        Список секций в порядке: role, scope, defaults, culture_rules, kb_usage, response_format, tone, safety
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        # Определяем порядок секций
        section_order = ["role", "scope", "defaults", "culture_rules", "kb_usage", "response_format", "tone", "safety"]

        query = """
            SELECT p.slug, p.content, p.is_enabled
            FROM prompts p
            JOIN prompt_groups g ON p.group_id = g.id
            WHERE g.slug = 'base'
        """
        if is_enabled_only:
            query += " AND p.is_enabled = TRUE"

        rows = await conn.fetch(query)

        # Преобразуем в словарь для быстрого доступа
        sections_dict = {row["slug"]: dict(row) for row in rows}

        # Возвращаем в правильном порядке
        result = []
        for slug in section_order:
            if slug in sections_dict:
                result.append(sections_dict[slug])

        return result


async def get_category_prompt(
    category_slug: str,
    culture_group: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Получает категорийный промпт для consultation_prompts.py.

    Args:
        category_slug: Slug категории (например, "nutrition", "diseases_pests")
        culture_group: Группа культуры для питания (например, "strawberry", "raspberry")

    Returns:
        Промпт с полями: content, use_minimal_base, is_enabled
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        # Для питания ищем по culture_group
        if category_slug == "nutrition" and culture_group:
            row = await conn.fetchrow("""
                SELECT p.content, p.use_minimal_base, p.is_enabled
                FROM prompts p
                JOIN prompt_groups g ON p.group_id = g.id
                JOIN prompt_subgroups s ON p.subgroup_id = s.id
                WHERE g.slug = 'categories'
                  AND s.slug = 'nutrition'
                  AND p.slug = $1
                  AND p.is_enabled = TRUE
            """, culture_group)
            if row:
                return dict(row)

            # Fallback на default
            row = await conn.fetchrow("""
                SELECT p.content, p.use_minimal_base, p.is_enabled
                FROM prompts p
                JOIN prompt_groups g ON p.group_id = g.id
                JOIN prompt_subgroups s ON p.subgroup_id = s.id
                WHERE g.slug = 'categories'
                  AND s.slug = 'nutrition'
                  AND p.slug = 'default'
                  AND p.is_enabled = TRUE
            """)
            return dict(row) if row else None

        # Для остальных категорий ищем main промпт
        row = await conn.fetchrow("""
            SELECT p.content, p.use_minimal_base, p.is_enabled
            FROM prompts p
            JOIN prompt_groups g ON p.group_id = g.id
            JOIN prompt_subgroups s ON p.subgroup_id = s.id
            WHERE g.slug = 'categories'
              AND s.slug = $1
              AND p.slug = 'main'
              AND p.is_enabled = TRUE
        """, category_slug)

        return dict(row) if row else None


async def check_category_exists(
    category_slug: str,
    culture_group: Optional[str] = None,
) -> bool:
    """
    Проверяет существует ли категорийный промпт в БД (независимо от is_enabled).

    Args:
        category_slug: Slug категории (например, "nutrition", "diseases_pests")
        culture_group: Группа культуры для питания (например, "strawberry", "raspberry")

    Returns:
        True если промпт существует в БД
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        # Для питания ищем по culture_group
        if category_slug == "nutrition" and culture_group:
            exists = await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM prompts p
                    JOIN prompt_groups g ON p.group_id = g.id
                    JOIN prompt_subgroups s ON p.subgroup_id = s.id
                    WHERE g.slug = 'categories'
                      AND s.slug = 'nutrition'
                      AND p.slug = $1
                )
            """, culture_group)
            if exists:
                return True

            # Проверяем default
            exists = await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM prompts p
                    JOIN prompt_groups g ON p.group_id = g.id
                    JOIN prompt_subgroups s ON p.subgroup_id = s.id
                    WHERE g.slug = 'categories'
                      AND s.slug = 'nutrition'
                      AND p.slug = 'default'
                )
            """)
            return exists

        # Для остальных категорий ищем main промпт
        exists = await conn.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM prompts p
                JOIN prompt_groups g ON p.group_id = g.id
                JOIN prompt_subgroups s ON p.subgroup_id = s.id
                WHERE g.slug = 'categories'
                  AND s.slug = $1
                  AND p.slug = 'main'
            )
        """, category_slug)

        return exists


async def get_reference_content(reference_slug: str) -> Optional[str]:
    """
    Получает содержимое справочника.

    Args:
        reference_slug: Slug справочника (fertilizers, pesticides, varieties)

    Returns:
        Текст справочника или None
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        content = await conn.fetchval("""
            SELECT p.content
            FROM prompts p
            JOIN prompt_groups g ON p.group_id = g.id
            WHERE g.slug = 'references'
              AND p.slug = $1
              AND p.is_enabled = TRUE
        """, reference_slug)
        return content


async def get_fallback_prompt() -> Optional[Dict[str, Any]]:
    """Получает fallback-промпт для неопределённых категорий."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT p.content, p.use_minimal_base, p.is_enabled
            FROM prompts p
            JOIN prompt_groups g ON p.group_id = g.id
            WHERE g.slug = 'other'
              AND p.slug = 'fallback'
              AND p.is_enabled = TRUE
        """)
        return dict(row) if row else None


async def get_article_prompt() -> Optional[Dict[str, Any]]:
    """Получает промпт для режима статей."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT p.content, p.use_minimal_base, p.is_enabled
            FROM prompts p
            JOIN prompt_groups g ON p.group_id = g.id
            WHERE g.slug = 'article'
              AND p.slug = 'article_base'
              AND p.is_enabled = TRUE
        """)
        return dict(row) if row else None


# ============================================================================
# Промт-документы (prompt_docs)
# ============================================================================

# Маппинг культур на subgroup slugs
CULTURE_TO_SUBGROUP = {
    'клубника': 'strawberry',
    'клубника летняя': 'strawberry',
    'клубника ремонтантная': 'strawberry',
    'клубника общая': 'strawberry',
    'земляника': 'strawberry',
    'земляника садовая': 'strawberry',
    'малина': 'raspberry',
    'малина летняя': 'raspberry',
    'малина ремонтантная': 'raspberry',
    'малина общая': 'raspberry',
    'кустарники': 'bushes',
    'голубика': 'bushes',
    'смородина': 'bushes',
    'крыжовник': 'bushes',
    'жимолость': 'bushes',
    'ежевика': 'bushes',
}

# Маппинг подкультур
SUBCULTURE_TO_SLUG = {
    'летняя': 'summer',
    'ремонтантная': 'remontant',
    'общая': 'general',
}

# Маппинг категорий консультаций на типы работ
CATEGORY_TO_WORK_SLUG = {
    'питание растений': 'nutrition',
    'защита растений': 'protection',
    'болезни и вредители': 'protection',
    'посадка и уход': 'planting',
    'улучшение почвы': 'soil',
    'подбор сорта': 'variety',
    'подбор сортов': 'variety',
}


def _parse_culture_subculture(culture: str) -> tuple[str, str | None]:
    """
    Парсит строку культуры на subgroup и subculture slug.

    Args:
        culture: Например, "клубника летняя", "малина ремонтантная", "голубика"

    Returns:
        (subgroup_slug, subculture_slug или None)
    """
    culture_lower = culture.lower().strip()

    # Определяем subgroup
    subgroup = CULTURE_TO_SUBGROUP.get(culture_lower)
    if not subgroup:
        # Пробуем первое слово
        first_word = culture_lower.split()[0] if culture_lower else ""
        subgroup = CULTURE_TO_SUBGROUP.get(first_word)

    if not subgroup:
        return (None, None)

    # Определяем subculture
    subculture = None
    for key, slug in SUBCULTURE_TO_SLUG.items():
        if key in culture_lower:
            subculture = slug
            break

    return (subgroup, subculture)


async def get_prompt_document_content(
    culture: str,
    consultation_category: str,
) -> Optional[str]:
    """
    Получает текст промт-документов из новой системы промптов.

    Ищет ВСЕ подходящие документы и объединяет их:
    1. Общий документ для культуры (например, "general_nutrition")
    2. Специфический документ для подкультуры (например, "summer_nutrition")

    Args:
        culture: Культура из LLM (например, "клубника летняя", "малина ремонтантная")
        consultation_category: Категория консультации (например, "защита растений")

    Returns:
        Объединённый текст документов или None если ничего не найдено
    """
    culture_lower = culture.lower().strip()
    category_lower = consultation_category.lower().strip()

    # Парсим культуру
    subgroup_slug, subculture_slug = _parse_culture_subculture(culture_lower)
    if not subgroup_slug:
        logger.debug(f"[get_prompt_document_content] Unknown culture: {culture}")
        return None

    # Получаем slug типа работ
    work_type_slug = CATEGORY_TO_WORK_SLUG.get(category_lower)
    if not work_type_slug:
        logger.debug(f"[get_prompt_document_content] Unknown category: {consultation_category}")
        return None

    pool = get_pool()
    documents_content = []

    async with pool.acquire() as conn:
        # Получаем subgroup_id
        subgroup_id = await conn.fetchval("""
            SELECT s.id
            FROM prompt_subgroups s
            JOIN prompt_groups g ON s.group_id = g.id
            WHERE g.slug = 'prompt_docs' AND s.slug = $1
        """, subgroup_slug)

        if not subgroup_id:
            logger.debug(f"[get_prompt_document_content] Subgroup not found: {subgroup_slug}")
            return None

        # 1. Ищем ОБЩИЙ документ (general_{work_type})
        general_slug = f"general_{work_type_slug}"
        general_content = await conn.fetchval("""
            SELECT p.content
            FROM prompts p
            JOIN prompt_groups g ON p.group_id = g.id
            WHERE g.slug = 'prompt_docs'
              AND p.subgroup_id = $1
              AND p.slug = $2
              AND p.is_enabled = TRUE
              AND p.content IS NOT NULL
              AND p.content != ''
        """, subgroup_id, general_slug)

        if general_content:
            logger.info(f"[prompt_doc] Found GENERAL: {subgroup_slug}/{general_slug}")
            documents_content.append(("📗 ОБЩАЯ ИНФОРМАЦИЯ", general_content))

        # 2. Ищем СПЕЦИФИЧЕСКИЙ документ (subculture_{work_type})
        if subculture_slug and subculture_slug != 'general':
            specific_slug = f"{subculture_slug}_{work_type_slug}"
            specific_content = await conn.fetchval("""
                SELECT p.content
                FROM prompts p
                JOIN prompt_groups g ON p.group_id = g.id
                WHERE g.slug = 'prompt_docs'
                  AND p.subgroup_id = $1
                  AND p.slug = $2
                  AND p.is_enabled = TRUE
                  AND p.content IS NOT NULL
                  AND p.content != ''
            """, subgroup_id, specific_slug)

            if specific_content:
                label = f"📘 СПЕЦИФИКА: {subculture_slug.upper()}"
                logger.info(f"[prompt_doc] Found SPECIFIC: {subgroup_slug}/{specific_slug}")
                documents_content.append((label, specific_content))

        # 3. Для кустарников — ищем просто work_type (без подкультуры)
        if subgroup_slug == 'bushes':
            bushes_content = await conn.fetchval("""
                SELECT p.content
                FROM prompts p
                JOIN prompt_groups g ON p.group_id = g.id
                WHERE g.slug = 'prompt_docs'
                  AND p.subgroup_id = $1
                  AND p.slug = $2
                  AND p.is_enabled = TRUE
                  AND p.content IS NOT NULL
                  AND p.content != ''
            """, subgroup_id, work_type_slug)

            if bushes_content:
                logger.info(f"[prompt_doc] Found BUSHES: {subgroup_slug}/{work_type_slug}")
                documents_content.append(("📗 ИНФОРМАЦИЯ", bushes_content))

    # Объединяем все найденные документы
    if not documents_content:
        logger.debug(f"[get_prompt_document_content] No docs for {culture}/{consultation_category}")
        return None

    # Формируем итоговый текст
    parts = []
    for label, content in documents_content:
        parts.append(f"{label}\n\n{content}")

    combined = "\n\n---\n\n".join(parts)
    logger.info(f"[get_prompt_document_content] Combined {len(documents_content)} docs, {len(combined)} chars")
    return combined


async def check_prompt_doc_exists(
    culture: str,
    consultation_category: str,
) -> bool:
    """
    Проверяет существует ли промт-документ в БД (независимо от is_enabled).
    """
    culture_lower = culture.lower().strip()
    category_lower = consultation_category.lower().strip()

    subgroup_slug, subculture_slug = _parse_culture_subculture(culture_lower)
    if not subgroup_slug:
        return False

    work_type_slug = CATEGORY_TO_WORK_SLUG.get(category_lower)
    if not work_type_slug:
        return False

    pool = get_pool()
    async with pool.acquire() as conn:
        # Проверяем любой подходящий промпт
        exists = await conn.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM prompts p
                JOIN prompt_groups g ON p.group_id = g.id
                JOIN prompt_subgroups s ON p.subgroup_id = s.id
                WHERE g.slug = 'prompt_docs'
                  AND s.slug = $1
                  AND (
                      p.slug = $2
                      OR p.slug = $3
                      OR p.slug = $4
                  )
            )
        """,
            subgroup_slug,
            f"general_{work_type_slug}",
            f"{subculture_slug}_{work_type_slug}" if subculture_slug else "",
            work_type_slug,
        )

        return exists


# ============================================================================
# Обновление промптов
# ============================================================================

async def update_prompt(
    prompt_id: int,
    content: str,
    updated_by: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Обновляет содержимое промпта.

    История сохраняется автоматически через триггер.

    Args:
        prompt_id: ID промпта
        content: Новый текст промпта
        updated_by: Кто обновил (опционально)

    Returns:
        Обновлённый промпт или None если не найден
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            UPDATE prompts
            SET content = $2, updated_by = $3
            WHERE id = $1
            RETURNING id, slug, name, content, version, updated_at
        """, prompt_id, content, updated_by)

        if row:
            logger.info(f"Prompt {prompt_id} updated to version {row['version']}")
            return dict(row)
        return None


async def toggle_prompt_enabled(
    prompt_id: int,
    enabled: bool,
) -> Optional[Dict[str, Any]]:
    """
    Включает или выключает промпт.

    Args:
        prompt_id: ID промпта
        enabled: True = включить, False = выключить

    Returns:
        Обновлённый промпт или None если не найден
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            UPDATE prompts
            SET is_enabled = $2, updated_at = NOW()
            WHERE id = $1
            RETURNING id, slug, name, is_enabled, updated_at
        """, prompt_id, enabled)

        if row:
            logger.info(f"Prompt {prompt_id} is_enabled set to {enabled}")
            return dict(row)
        return None


# ============================================================================
# История версий
# ============================================================================

async def get_prompt_history(prompt_id: int) -> List[Dict[str, Any]]:
    """
    Получает историю изменений промпта.

    Args:
        prompt_id: ID промпта

    Returns:
        Список версий от новых к старым
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                id,
                version,
                content,
                changed_by,
                change_reason,
                created_at
            FROM prompt_history
            WHERE prompt_id = $1
            ORDER BY version DESC
        """, prompt_id)
        return [dict(row) for row in rows]


async def get_prompt_version(prompt_id: int, version: int) -> Optional[Dict[str, Any]]:
    """Получает конкретную версию промпта из истории."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id, version, content, changed_by, change_reason, created_at
            FROM prompt_history
            WHERE prompt_id = $1 AND version = $2
        """, prompt_id, version)
        return dict(row) if row else None


async def revert_to_version(
    prompt_id: int,
    version: int,
    reverted_by: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Откатывает промпт к указанной версии.

    Args:
        prompt_id: ID промпта
        version: Номер версии для отката
        reverted_by: Кто откатил

    Returns:
        Обновлённый промпт или None если версия не найдена
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        # Получаем контент из истории
        old_content = await conn.fetchval("""
            SELECT content
            FROM prompt_history
            WHERE prompt_id = $1 AND version = $2
        """, prompt_id, version)

        if not old_content:
            logger.warning(f"Version {version} not found for prompt {prompt_id}")
            return None

        # Обновляем промпт (триггер сохранит текущую версию в историю)
        row = await conn.fetchrow("""
            UPDATE prompts
            SET content = $2, updated_by = $3
            WHERE id = $1
            RETURNING id, slug, name, content, version, updated_at
        """, prompt_id, old_content, reverted_by or f"revert_to_v{version}")

        if row:
            logger.info(f"Prompt {prompt_id} reverted to version {version}, new version is {row['version']}")
            return dict(row)
        return None
