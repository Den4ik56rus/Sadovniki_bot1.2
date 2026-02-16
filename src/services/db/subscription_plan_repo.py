"""
Репозиторий для работы с тарифными планами подписок.

Функции:
    - get_by_id — получить план по ID
    - get_all_active — получить все активные планы
    - get_all — получить все планы (для админки)
    - get_by_name — получить план по названию
    - update — обновить план
    - create — создать новый план
"""

from typing import Optional, List, Dict, Any
from decimal import Decimal

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


async def get_all() -> List[Dict[str, Any]]:
    """
    Получает все планы подписок (включая неактивные) для админ-панели.

    Returns:
        Список всех планов
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM subscription_plans ORDER BY id ASC"
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


async def update(plan_id: int, **fields) -> Optional[Dict[str, Any]]:
    """
    Обновляет план подписки.

    Args:
        plan_id: ID плана
        **fields: Поля для обновления (name, description, price_rub, tokens_included, is_active)

    Returns:
        Обновлённый план или None
    """
    allowed = {'name', 'description', 'price_rub', 'tokens_included', 'is_active'}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return None

    set_parts = []
    values = [plan_id]
    for i, (k, v) in enumerate(updates.items()):
        set_parts.append(f"{k} = ${i + 2}")
        if k == 'price_rub' and not isinstance(v, Decimal):
            v = Decimal(str(v))
        values.append(v)

    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"UPDATE subscription_plans SET {', '.join(set_parts)} WHERE id = $1 RETURNING *",
            *values,
        )
        return dict(row) if row else None


async def create(
    name: str,
    price_rub: float,
    duration_days: int,
    tokens_included: int,
    description: str = "",
) -> Dict[str, Any]:
    """
    Создаёт новый план подписки.

    Args:
        name: Название плана
        price_rub: Цена в рублях
        duration_days: Длительность в днях
        tokens_included: Количество вопросов
        description: Описание

    Returns:
        Созданный план
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO subscription_plans (name, description, price_rub, duration_days, tokens_included, is_active)
            VALUES ($1, $2, $3, $4, $5, true)
            RETURNING *
            """,
            name, description, Decimal(str(price_rub)), duration_days, tokens_included,
        )
        return dict(row)
