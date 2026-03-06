# src/services/db/image_generator_repo.py

"""
Репозиторий для работы с генерацией картинок.

Таблица: generated_images.
"""

import logging
from typing import Optional, Dict, Any, List

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


async def create_generation(
    *,
    user_prompt: str,
    preset: str = "free",
    reference_image_path: Optional[str] = None,
    image_model: Optional[str] = None,
) -> int:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO generated_images (user_prompt, preset, reference_image_path, image_model)
        VALUES ($1, $2, $3, COALESCE($4, 'gemini-3.1-flash-image-preview'))
        RETURNING id
        """,
        user_prompt, preset, reference_image_path, image_model,
    )
    logger.info(f"[image_generator_repo] Генерация создана: id={row['id']}, preset='{preset}'")
    return row["id"]


async def update_generation(gen_id: int, **kwargs) -> Optional[Dict[str, Any]]:
    pool = get_pool()
    fields = []
    values = []
    idx = 1

    allowed = {
        "user_prompt", "optimized_prompt", "preset", "image_path",
        "reference_image_path", "image_model", "status", "error_message",
        "input_tokens", "output_tokens", "prompt_tokens",
        "prompt_completion_tokens", "cost_usd",
    }

    for key, val in kwargs.items():
        if key in allowed:
            fields.append(f"{key} = ${idx}")
            values.append(val)
            idx += 1

    if not fields:
        return await get_generation(gen_id)

    values.append(gen_id)
    query = f"""
        UPDATE generated_images
        SET {', '.join(fields)}
        WHERE id = ${idx}
        RETURNING *
    """
    row = await pool.fetchrow(query, *values)
    return dict(row) if row else None


async def get_generation(gen_id: int) -> Optional[Dict[str, Any]]:
    pool = get_pool()
    row = await pool.fetchrow("SELECT * FROM generated_images WHERE id = $1", gen_id)
    return dict(row) if row else None


async def get_generations(
    *,
    limit: int = 50,
    offset: int = 0,
    preset: Optional[str] = None,
) -> List[Dict[str, Any]]:
    pool = get_pool()
    if preset:
        rows = await pool.fetch(
            """
            SELECT * FROM generated_images
            WHERE preset = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            preset, limit, offset,
        )
    else:
        rows = await pool.fetch(
            """
            SELECT * FROM generated_images
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset,
        )
    return [dict(r) for r in rows]


async def get_generations_count(preset: Optional[str] = None) -> int:
    pool = get_pool()
    if preset:
        row = await pool.fetchrow(
            "SELECT COUNT(*) FROM generated_images WHERE preset = $1", preset
        )
    else:
        row = await pool.fetchrow("SELECT COUNT(*) FROM generated_images")
    return row["count"]


async def delete_generation(gen_id: int) -> bool:
    pool = get_pool()
    result = await pool.execute(
        "DELETE FROM generated_images WHERE id = $1", gen_id
    )
    return result == "DELETE 1"
