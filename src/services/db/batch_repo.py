# src/services/db/batch_repo.py

"""
Репозиторий для пакетной генерации презентаций.

Таблицы: presentation_batches, presentation_batch_items.
"""

import logging
from typing import Optional, Dict, Any, List

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


async def create_batch(
    *,
    style_id: Optional[int] = None,
    template_id: Optional[int] = None,
    llm_model: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    image_model: Optional[str] = None,
    custom_system_prompt: Optional[str] = None,
    total_items: int = 0,
) -> int:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO presentation_batches
            (style_id, template_id, llm_model, reasoning_effort, image_model,
             custom_system_prompt, total_items)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
        """,
        style_id, template_id, llm_model, reasoning_effort, image_model,
        custom_system_prompt, total_items,
    )
    batch_id = row["id"]
    logger.info(f"[batch_repo] Пакет создан: id={batch_id}, total_items={total_items}")
    return batch_id


async def add_batch_items(batch_id: int, items: List[Dict[str, Any]]) -> List[int]:
    pool = get_pool()
    ids = []
    for i, item in enumerate(items):
        row = await pool.fetchrow(
            """
            INSERT INTO presentation_batch_items
                (batch_id, culture_key, variety_key, problem_key, sort_order)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            batch_id,
            item["culture_key"],
            item.get("variety_key"),
            item["problem_key"],
            i,
        )
        ids.append(row["id"])
    logger.info(f"[batch_repo] Добавлено {len(ids)} элементов в пакет {batch_id}")
    return ids


async def get_batch(batch_id: int) -> Optional[Dict[str, Any]]:
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM presentation_batches WHERE id = $1",
        batch_id,
    )
    if not row:
        return None

    batch = dict(row)
    items = await pool.fetch(
        """
        SELECT * FROM presentation_batch_items
        WHERE batch_id = $1
        ORDER BY sort_order
        """,
        batch_id,
    )
    batch["items"] = [dict(r) for r in items]
    return batch


async def get_batches(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT id, status, total_items, completed_items, failed_items,
               current_item_index, total_cost_usd, created_at, started_at, finished_at,
               llm_model, image_model, style_id
        FROM presentation_batches
        ORDER BY created_at DESC
        LIMIT $1 OFFSET $2
        """,
        limit, offset,
    )
    return [dict(r) for r in rows]


async def get_batches_count() -> int:
    pool = get_pool()
    row = await pool.fetchrow("SELECT COUNT(*) as cnt FROM presentation_batches")
    return row["cnt"]


async def get_batches_by_status(status: str) -> List[Dict[str, Any]]:
    pool = get_pool()
    rows = await pool.fetch(
        "SELECT id FROM presentation_batches WHERE status = $1",
        status,
    )
    result = []
    for row in rows:
        batch = await get_batch(row["id"])
        if batch:
            result.append(batch)
    return result


async def update_batch_status(
    batch_id: int,
    status: Optional[str] = None,
    *,
    started_at: Optional[Any] = None,
    finished_at: Optional[Any] = None,
    current_item_index: Optional[int] = None,
    error_message: Optional[str] = None,
) -> None:
    pool = get_pool()
    fields = []
    values = []
    idx = 1

    if status is not None:
        fields.append(f"status = ${idx}")
        values.append(status)
        idx += 1
    if started_at is not None:
        fields.append(f"started_at = ${idx}")
        values.append(started_at)
        idx += 1
    if finished_at is not None:
        fields.append(f"finished_at = ${idx}")
        values.append(finished_at)
        idx += 1
    if current_item_index is not None:
        fields.append(f"current_item_index = ${idx}")
        values.append(current_item_index)
        idx += 1
    if error_message is not None:
        fields.append(f"error_message = ${idx}")
        values.append(error_message)
        idx += 1

    if not fields:
        return

    values.append(batch_id)
    query = f"UPDATE presentation_batches SET {', '.join(fields)} WHERE id = ${idx}"
    await pool.execute(query, *values)


async def update_batch_item_status(
    item_id: int,
    status: str,
    *,
    presentation_id: Optional[int] = None,
    content_pdf_path: Optional[str] = None,
    error_message: Optional[str] = None,
    started_at: Optional[Any] = None,
    finished_at: Optional[Any] = None,
) -> None:
    pool = get_pool()
    fields = [f"status = $1"]
    values: list = [status]
    idx = 2

    if presentation_id is not None:
        fields.append(f"presentation_id = ${idx}")
        values.append(presentation_id)
        idx += 1
    if content_pdf_path is not None:
        fields.append(f"content_pdf_path = ${idx}")
        values.append(content_pdf_path)
        idx += 1
    if error_message is not None:
        fields.append(f"error_message = ${idx}")
        values.append(error_message)
        idx += 1
    if started_at is not None:
        fields.append(f"started_at = ${idx}")
        values.append(started_at)
        idx += 1
    if finished_at is not None:
        fields.append(f"finished_at = ${idx}")
        values.append(finished_at)
        idx += 1

    values.append(item_id)
    query = f"UPDATE presentation_batch_items SET {', '.join(fields)} WHERE id = ${idx}"
    await pool.execute(query, *values)


async def increment_batch_progress(
    batch_id: int,
    completed: int = 0,
    failed: int = 0,
    cost: float = 0,
) -> None:
    pool = get_pool()
    await pool.execute(
        """
        UPDATE presentation_batches
        SET completed_items = completed_items + $2,
            failed_items = failed_items + $3,
            total_cost_usd = total_cost_usd + $4
        WHERE id = $1
        """,
        batch_id, completed, failed, cost,
    )


async def cancel_batch(batch_id: int) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await conn.execute(
                """
                UPDATE presentation_batches
                SET status = 'cancelled', finished_at = NOW()
                WHERE id = $1 AND status IN ('pending', 'running')
                """,
                batch_id,
            )
            await conn.execute(
                """
                UPDATE presentation_batch_items
                SET status = 'skipped'
                WHERE batch_id = $1 AND status = 'pending'
                """,
                batch_id,
            )
            return result == "UPDATE 1"


async def delete_batch(batch_id: int) -> bool:
    pool = get_pool()
    result = await pool.execute(
        "DELETE FROM presentation_batches WHERE id = $1",
        batch_id,
    )
    return result == "DELETE 1"
