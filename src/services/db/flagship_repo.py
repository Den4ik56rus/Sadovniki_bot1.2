"""
Репозиторий для флагманских продуктов.

Функции:
    - check_access — проверить доступ пользователя к продукту
    - grant_access — выдать доступ после оплаты
    - get_user_products — все купленные продукты пользователя
    - get_cached_file_id — получить кешированный Telegram file_id
    - save_cached_file_id — сохранить file_id в кеш
"""

import logging
from typing import Optional

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


async def check_access(user_id: int, product_key: str) -> bool:
    """Проверяет, есть ли у пользователя доступ к продукту."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchval(
            """
            SELECT 1 FROM user_purchased_products
            WHERE user_id = $1 AND product_key = $2
            """,
            user_id, product_key,
        )
    return row is not None


async def grant_access(
    user_id: int,
    product_key: str,
    payment_id: int,
    product_type: str = "seasonal_program",
) -> None:
    """Выдаёт доступ к продукту (idempotent — ON CONFLICT DO NOTHING)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_purchased_products
                (user_id, product_type, product_key, payment_id)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id, product_type, product_key) DO NOTHING
            """,
            user_id, product_type, product_key, payment_id,
        )
    logger.info(
        f"Flagship access granted: user={user_id}, product={product_key}, payment={payment_id}"
    )


async def get_user_products(user_id: int) -> list[dict]:
    """Возвращает все купленные продукты пользователя (программы и отдельные блоки)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT product_type, product_key, purchased_at
            FROM user_purchased_products
            WHERE user_id = $1
            ORDER BY product_type ASC, purchased_at DESC
            """,
            user_id,
        )
    return [dict(r) for r in rows]


async def get_cached_file_id(
    product_key: str, content_key: str,
) -> Optional[str]:
    """Получить кешированный Telegram file_id."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            SELECT telegram_file_id FROM flagship_file_cache
            WHERE product_key = $1 AND content_key = $2
            """,
            product_key, content_key,
        )


async def save_cached_file_id(
    product_key: str,
    content_key: str,
    file_id: str,
    file_type: str,
) -> None:
    """Сохранить file_id в кеш (ON CONFLICT — обновить)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO flagship_file_cache
                (product_key, content_key, telegram_file_id, file_type)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (product_key, content_key)
            DO UPDATE SET
                telegram_file_id = EXCLUDED.telegram_file_id,
                cached_at = NOW()
            """,
            product_key, content_key, file_id, file_type,
        )
