"""
Репозиторий для работы с заказами на гайды (guide_orders).

Функции:
    - create_order — создать заказ
    - get_by_id — получить заказ по ID
    - get_by_payment_id — получить заказ по ID платежа
    - update_status — обновить статус заказа
    - update_content — сохранить LLM-контент
    - update_content_with_meta — сохранить LLM-контент + посекционные затраты
    - update_file — сохранить путь к файлу после генерации
    - update_delivery — отметить доставку (telegram_file_id)
    - get_user_orders — все заказы пользователя
    - get_user_order_for_culture — проверить есть ли готовый гайд для культуры
    - increment_retry — увеличить счётчик попыток
    - get_all_orders — все заказы для админ-панели
    - get_guide_stats — агрегированная статистика
"""

import json
import logging
from typing import Optional, List, Dict, Any, Tuple

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


async def create_order(
    user_id: int,
    culture_key: str,
    culture_display: str,
    payment_id: Optional[int] = None,
    status: str = "pending",
) -> Dict[str, Any]:
    """
    Создаёт новый заказ на гайд.

    Returns:
        Созданный заказ
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO guide_orders (user_id, payment_id, culture_key, culture_display, status)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
            """,
            user_id, payment_id, culture_key, culture_display, status,
        )
        return dict(row)


async def get_by_id(order_id: int) -> Optional[Dict[str, Any]]:
    """Получает заказ по ID."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM guide_orders WHERE id = $1",
            order_id,
        )
        return dict(row) if row else None


async def get_by_payment_id(payment_id: int) -> Optional[Dict[str, Any]]:
    """Получает заказ по ID платежа."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM guide_orders WHERE payment_id = $1",
            payment_id,
        )
        return dict(row) if row else None


async def update_status(
    order_id: int,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    """Обновляет статус заказа."""
    pool = get_pool()
    async with pool.acquire() as conn:
        if error_message is not None:
            await conn.execute(
                """
                UPDATE guide_orders
                SET status = $2, error_message = $3, updated_at = NOW()
                WHERE id = $1
                """,
                order_id, status, error_message,
            )
        else:
            await conn.execute(
                """
                UPDATE guide_orders
                SET status = $2, updated_at = NOW()
                WHERE id = $1
                """,
                order_id, status,
            )


async def update_content(
    order_id: int,
    content_json: dict,
    total_llm_cost_usd: float,
    total_llm_tokens: int,
) -> None:
    """Сохраняет LLM-контент в заказ."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE guide_orders
            SET content_json = $2, total_llm_cost_usd = $3, total_llm_tokens = $4,
                updated_at = NOW()
            WHERE id = $1
            """,
            order_id, json.dumps(content_json, ensure_ascii=False), total_llm_cost_usd, total_llm_tokens,
        )


async def update_file(
    order_id: int,
    file_path: str,
    file_format: str,
    file_size_bytes: int,
) -> None:
    """Сохраняет информацию о сгенерированном файле."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE guide_orders
            SET file_path = $2, file_format = $3,
                file_size_bytes = $4, updated_at = NOW()
            WHERE id = $1
            """,
            order_id, file_path, file_format, file_size_bytes,
        )


async def update_delivery(
    order_id: int,
    telegram_file_id: str,
) -> None:
    """Отмечает доставку файла пользователю."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE guide_orders
            SET telegram_file_id = $2, delivered_at = NOW(), status = 'completed',
                updated_at = NOW()
            WHERE id = $1
            """,
            order_id, telegram_file_id,
        )


async def get_user_orders(
    user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Получает все заказы пользователя."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM guide_orders
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id, limit, offset,
        )
        return [dict(row) for row in rows]


async def get_user_order_for_culture(
    user_id: int,
    culture_key: str,
    status: str = "completed",
) -> Optional[Dict[str, Any]]:
    """
    Проверяет, есть ли у пользователя готовый гайд для данной культуры.

    Returns:
        Последний завершённый заказ или None
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM guide_orders
            WHERE user_id = $1 AND culture_key = $2 AND status = $3
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id, culture_key, status,
        )
        return dict(row) if row else None


async def increment_retry(order_id: int) -> int:
    """Увеличивает счётчик попыток и возвращает новое значение."""
    pool = get_pool()
    async with pool.acquire() as conn:
        new_count = await conn.fetchval(
            """
            UPDATE guide_orders
            SET retry_count = retry_count + 1, updated_at = NOW()
            WHERE id = $1
            RETURNING retry_count
            """,
            order_id,
        )
        return new_count or 0


# =========================================================================
# Admin panel functions
# =========================================================================

async def update_content_with_meta(
    order_id: int,
    content_json: dict,
    sections_meta: dict,
    total_llm_cost_usd: float,
    total_llm_tokens: int,
    llm_model: str,
) -> None:
    """Сохраняет LLM-контент + посекционные затраты в заказ."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE guide_orders
            SET content_json = $2, sections_meta = $3,
                total_llm_cost_usd = $4, total_llm_tokens = $5,
                llm_model = $6, updated_at = NOW()
            WHERE id = $1
            """,
            order_id,
            json.dumps(content_json, ensure_ascii=False),
            json.dumps(sections_meta, ensure_ascii=False),
            total_llm_cost_usd,
            total_llm_tokens,
            llm_model,
        )


async def get_all_orders(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Все заказы для админ-панели (с данными пользователя).
    Не возвращает content_json (тяжёлый).

    Returns:
        (orders, total_count)
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        # Count
        if status:
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM guide_orders WHERE status = $1",
                status,
            )
        else:
            total = await conn.fetchval("SELECT COUNT(*) FROM guide_orders")

        # Orders (without content_json)
        query = """
            SELECT
                go.id, go.user_id, go.payment_id,
                go.culture_key, go.culture_display,
                go.status, go.total_llm_cost_usd, go.total_llm_tokens,
                go.llm_model, go.sections_meta,
                go.file_size_bytes, go.error_message, go.retry_count,
                go.created_at, go.updated_at,
                u.username, u.first_name, u.telegram_user_id
            FROM guide_orders go
            LEFT JOIN users u ON go.user_id = u.id
        """
        params: list = []
        if status:
            query += " WHERE go.status = $1"
            params.append(status)

        query += f" ORDER BY go.created_at DESC LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}"
        params.extend([limit, offset])

        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows], total or 0


async def get_guide_stats() -> Dict[str, Any]:
    """Агрегированная статистика по гайдам для админ-панели."""
    pool = get_pool()
    async with pool.acquire() as conn:
        # Main stats
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS total_orders,
                COUNT(*) FILTER (WHERE status = 'completed') AS completed_orders,
                COUNT(*) FILTER (WHERE status = 'failed') AS failed_orders,
                COALESCE(SUM(total_llm_cost_usd), 0) AS total_cost_usd,
                COALESCE(AVG(total_llm_cost_usd) FILTER (WHERE status = 'completed'), 0) AS avg_cost_usd,
                COALESCE(SUM(total_llm_tokens), 0) AS total_tokens
            FROM guide_orders
            """
        )

        # By culture
        culture_rows = await conn.fetch(
            """
            SELECT
                culture_key,
                COUNT(*) AS count,
                COALESCE(SUM(total_llm_cost_usd), 0) AS total_cost
            FROM guide_orders
            GROUP BY culture_key
            ORDER BY count DESC
            LIMIT 20
            """
        )

        return {
            "total_orders": row["total_orders"],
            "completed_orders": row["completed_orders"],
            "failed_orders": row["failed_orders"],
            "total_cost_usd": float(row["total_cost_usd"]),
            "avg_cost_usd": float(row["avg_cost_usd"]),
            "total_tokens": row["total_tokens"],
            "by_culture": [
                {
                    "culture_key": r["culture_key"],
                    "count": r["count"],
                    "total_cost": float(r["total_cost"]),
                }
                for r in culture_rows
            ],
        }
