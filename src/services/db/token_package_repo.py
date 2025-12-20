"""
Репозиторий для работы с пакетами токенов.

Функции:
    - get_by_id — получить пакет по ID
    - get_all_active — получить все активные пакеты
"""

from typing import Optional, List, Dict, Any

from src.services.db.pool import get_pool


async def get_by_id(package_id: int) -> Optional[Dict[str, Any]]:
    """
    Получает пакет токенов по ID.

    Args:
        package_id: ID пакета

    Returns:
        Пакет токенов или None
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM token_packages WHERE id = $1",
            package_id,
        )
        return dict(row) if row else None


async def get_all_active() -> List[Dict[str, Any]]:
    """
    Получает все активные пакеты токенов.

    Returns:
        Список активных пакетов
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM token_packages
            WHERE is_active = true
            ORDER BY price_rub ASC
            """
        )
        return [dict(row) for row in rows]
