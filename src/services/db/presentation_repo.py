# src/services/db/presentation_repo.py

"""
Репозиторий для работы с презентациями.

Таблицы: presentations, presentation_slides, slide_versions, presentation_styles, presentation_templates.
"""

import logging
from typing import Optional, Dict, Any, List

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


# =============================================================================
# Presentation Styles
# =============================================================================

async def create_style(
    *,
    name: str,
    description: Optional[str] = None,
    style_xml: str,
) -> int:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO presentation_styles (name, description, style_xml)
        VALUES ($1, $2, $3)
        RETURNING id
        """,
        name, description, style_xml,
    )
    logger.info(f"[presentation_repo] Стиль создан: id={row['id']}, name='{name}'")
    return row["id"]


async def update_style(
    style_id: int,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    style_xml: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    pool = get_pool()
    fields = []
    values = []
    idx = 1

    if name is not None:
        fields.append(f"name = ${idx}")
        values.append(name)
        idx += 1
    if description is not None:
        fields.append(f"description = ${idx}")
        values.append(description)
        idx += 1
    if style_xml is not None:
        fields.append(f"style_xml = ${idx}")
        values.append(style_xml)
        idx += 1

    if not fields:
        return await get_style_by_id(style_id)

    fields.append(f"updated_at = NOW()")
    values.append(style_id)

    query = f"""
        UPDATE presentation_styles
        SET {', '.join(fields)}
        WHERE id = ${idx}
        RETURNING *
    """
    row = await pool.fetchrow(query, *values)
    return dict(row) if row else None


async def delete_style(style_id: int) -> bool:
    pool = get_pool()
    result = await pool.execute(
        "DELETE FROM presentation_styles WHERE id = $1", style_id
    )
    return result == "DELETE 1"


async def get_style_by_id(style_id: int) -> Optional[Dict[str, Any]]:
    pool = get_pool()
    row = await pool.fetchrow("SELECT * FROM presentation_styles WHERE id = $1", style_id)
    return dict(row) if row else None


async def get_styles_list() -> List[Dict[str, Any]]:
    pool = get_pool()
    rows = await pool.fetch("SELECT * FROM presentation_styles ORDER BY created_at DESC")
    return [dict(r) for r in rows]


# =============================================================================
# Presentation Templates
# =============================================================================

async def create_template(
    *,
    name: str,
    description: Optional[str] = None,
    template_text: str,
) -> int:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO presentation_templates (name, description, template_text)
        VALUES ($1, $2, $3)
        RETURNING id
        """,
        name, description, template_text,
    )
    logger.info(f"[presentation_repo] Шаблон создан: id={row['id']}, name='{name}'")
    return row["id"]


async def update_template(
    template_id: int,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    template_text: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    pool = get_pool()
    fields = []
    values = []
    idx = 1

    if name is not None:
        fields.append(f"name = ${idx}")
        values.append(name)
        idx += 1
    if description is not None:
        fields.append(f"description = ${idx}")
        values.append(description)
        idx += 1
    if template_text is not None:
        fields.append(f"template_text = ${idx}")
        values.append(template_text)
        idx += 1

    if not fields:
        return await get_template_by_id(template_id)

    fields.append(f"updated_at = NOW()")
    values.append(template_id)

    query = f"""
        UPDATE presentation_templates
        SET {', '.join(fields)}
        WHERE id = ${idx}
        RETURNING *
    """
    row = await pool.fetchrow(query, *values)
    return dict(row) if row else None


async def delete_template(template_id: int) -> bool:
    pool = get_pool()
    result = await pool.execute(
        "DELETE FROM presentation_templates WHERE id = $1", template_id
    )
    return result == "DELETE 1"


async def get_template_by_id(template_id: int) -> Optional[Dict[str, Any]]:
    pool = get_pool()
    row = await pool.fetchrow("SELECT * FROM presentation_templates WHERE id = $1", template_id)
    return dict(row) if row else None


async def get_templates_list() -> List[Dict[str, Any]]:
    pool = get_pool()
    rows = await pool.fetch("SELECT * FROM presentation_templates ORDER BY created_at DESC")
    return [dict(r) for r in rows]


# =============================================================================
# Presentations
# =============================================================================

async def create_presentation(
    *,
    title: str,
    source_text: str = "",
    style_id: Optional[int] = None,
    template_id: Optional[int] = None,
    llm_model: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    image_model: Optional[str] = None,
    test_slide_index: Optional[int] = None,
    generation_mode: str = "article",
    culture_key: Optional[str] = None,
    variety_key: Optional[str] = None,
    problem_key: Optional[str] = None,
    custom_system_prompt: Optional[str] = None,
) -> int:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO presentations
            (title, source_text, style_id, template_id, llm_model, reasoning_effort,
             image_model, test_slide_index, generation_mode, culture_key, variety_key, problem_key,
             custom_system_prompt)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        RETURNING id
        """,
        title, source_text, style_id, template_id, llm_model, reasoning_effort,
        image_model, test_slide_index, generation_mode, culture_key, variety_key, problem_key,
        custom_system_prompt,
    )
    logger.info(f"[presentation_repo] Презентация создана: id={row['id']}, title='{title[:50]}', mode={generation_mode}")
    return row["id"]


async def get_presentation_by_id(presentation_id: int) -> Optional[Dict[str, Any]]:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        SELECT * FROM presentations WHERE id = $1
        """,
        presentation_id,
    )
    return dict(row) if row else None


async def get_presentations_list(
    *,
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    pool = get_pool()

    if status:
        rows = await pool.fetch(
            """
            SELECT id, title, status, slide_count, llm_model,
                   total_cost_usd, pdf_path, created_at, updated_at
            FROM presentations
            WHERE status = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            status, limit, offset,
        )
    else:
        rows = await pool.fetch(
            """
            SELECT id, title, status, slide_count, llm_model,
                   total_cost_usd, pdf_path, created_at, updated_at
            FROM presentations
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset,
        )
    return [dict(r) for r in rows]


async def get_presentations_count(status: Optional[str] = None) -> int:
    pool = get_pool()
    if status:
        row = await pool.fetchrow(
            "SELECT COUNT(*) FROM presentations WHERE status = $1", status
        )
    else:
        row = await pool.fetchrow("SELECT COUNT(*) FROM presentations")
    return row["count"]


async def update_presentation(
    presentation_id: int,
    **kwargs,
) -> Optional[Dict[str, Any]]:
    pool = get_pool()
    fields = []
    values = []
    idx = 1

    allowed = {
        "title", "status", "slide_count", "llm_model", "reasoning_effort",
        "text_prompt_tokens", "text_completion_tokens", "text_cost_usd",
        "image_input_tokens", "image_output_tokens", "image_cost_usd",
        "total_cost_usd", "pdf_path", "error_message",
        "source_text", "article_cost_usd", "article_prompt_tokens", "article_completion_tokens",
    }

    for key, val in kwargs.items():
        if key in allowed:
            fields.append(f"{key} = ${idx}")
            values.append(val)
            idx += 1

    if not fields:
        return await get_presentation_by_id(presentation_id)

    fields.append("updated_at = NOW()")
    values.append(presentation_id)

    query = f"""
        UPDATE presentations
        SET {', '.join(fields)}
        WHERE id = ${idx}
        RETURNING *
    """
    row = await pool.fetchrow(query, *values)
    return dict(row) if row else None


async def delete_presentation(presentation_id: int) -> bool:
    pool = get_pool()
    result = await pool.execute(
        "DELETE FROM presentations WHERE id = $1", presentation_id
    )
    return result == "DELETE 1"


# =============================================================================
# Slides
# =============================================================================

async def create_slide(
    *,
    presentation_id: int,
    slide_index: int,
    slide_title: Optional[str] = None,
    slide_prompt: str,
    slide_notes: Optional[str] = None,
) -> int:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO presentation_slides
            (presentation_id, slide_index, slide_title, slide_prompt, slide_notes)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        """,
        presentation_id, slide_index, slide_title, slide_prompt, slide_notes,
    )
    return row["id"]


async def get_slides_by_presentation(presentation_id: int) -> List[Dict[str, Any]]:
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT * FROM presentation_slides
        WHERE presentation_id = $1
        ORDER BY slide_index
        """,
        presentation_id,
    )
    return [dict(r) for r in rows]


async def get_slide_by_id(slide_id: int) -> Optional[Dict[str, Any]]:
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM presentation_slides WHERE id = $1", slide_id
    )
    return dict(row) if row else None


# =============================================================================
# Slide Versions
# =============================================================================

async def create_slide_version(
    *,
    slide_id: int,
    version_number: int,
    nbp_prompt: str,
    image_path: Optional[str] = None,
    edit_instruction: Optional[str] = None,
) -> int:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO slide_versions
            (slide_id, version_number, nbp_prompt, image_path, edit_instruction)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        """,
        slide_id, version_number, nbp_prompt, image_path, edit_instruction,
    )
    return row["id"]


async def update_slide_version(
    version_id: int,
    **kwargs,
) -> Optional[Dict[str, Any]]:
    pool = get_pool()
    fields = []
    values = []
    idx = 1

    allowed = {
        "image_path", "nbp_input_tokens", "nbp_output_tokens",
        "nbp_cost_usd", "status", "error_message",
    }

    for key, val in kwargs.items():
        if key in allowed:
            fields.append(f"{key} = ${idx}")
            values.append(val)
            idx += 1

    if not fields:
        return None

    values.append(version_id)
    query = f"""
        UPDATE slide_versions
        SET {', '.join(fields)}
        WHERE id = ${idx}
        RETURNING *
    """
    row = await pool.fetchrow(query, *values)
    return dict(row) if row else None


async def get_versions_by_slide(slide_id: int) -> List[Dict[str, Any]]:
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT * FROM slide_versions
        WHERE slide_id = $1
        ORDER BY version_number
        """,
        slide_id,
    )
    return [dict(r) for r in rows]


async def get_version_by_id(version_id: int) -> Optional[Dict[str, Any]]:
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM slide_versions WHERE id = $1", version_id
    )
    return dict(row) if row else None


async def get_latest_version(slide_id: int) -> Optional[Dict[str, Any]]:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        SELECT * FROM slide_versions
        WHERE slide_id = $1
        ORDER BY version_number DESC
        LIMIT 1
        """,
        slide_id,
    )
    return dict(row) if row else None


async def get_next_version_number(slide_id: int) -> int:
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT COALESCE(MAX(version_number), 0) + 1 AS next FROM slide_versions WHERE slide_id = $1",
        slide_id,
    )
    return row["next"]


# =============================================================================
# Composite queries (for API detail views)
# =============================================================================

async def get_presentation_full(presentation_id: int) -> Optional[Dict[str, Any]]:
    """Получает презентацию со слайдами и их версиями."""
    pres = await get_presentation_by_id(presentation_id)
    if not pres:
        return None

    slides = await get_slides_by_presentation(presentation_id)
    for slide in slides:
        slide["versions"] = await get_versions_by_slide(slide["id"])

    pres["slides"] = slides
    return pres
