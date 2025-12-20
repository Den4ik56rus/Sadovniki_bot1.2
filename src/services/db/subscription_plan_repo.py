"""
Репозиторий для работы с тарифными планами подписок.

Функции:
    - get_by_id — получить план по ID
    - get_all_active — получить все активные планы
    - get_by_name — получить план по названию
"""

from typing import Optional, List, Dict, Any

from src.services.db.pool import get_pool


async def get_by_id(plan_id: int) -> Optional[Dict[str, Any]]:
    """
    Получает план подписки по ID.

    Args:
        plan_id: ID плана

    Returns:
        План подписки или None
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM subscription_plans WHERE id = $1",
            plan_id,
        )
        return dict(row) if row else None


async def get_all_active() -> List[Dict[str, Any]]:
    """
    Получает все активные планы подписок.

    Returns:
        Список активных планов
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM subscription_plans
            WHERE is_active = true
            ORDER BY price_rub ASC
            """
        )
        return [dict(row) for row in rows]


async def get_by_name(name: str) -> Optional[Dict[str, Any]]:
    """
    Получает план по названию.

    Args:
        name: Название плана

    Returns:
        План подписки или None
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM subscription_plans WHERE name = $1",
            name,
        )
        return dict(row) if row else None
