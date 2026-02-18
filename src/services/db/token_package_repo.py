"""
Репозиторий для работы с пакетами токенов.

Функции:
    - get_by_id — получить пакет по ID
    - get_all_active — получить все активные пакеты
    - get_all — получить все пакеты (для админки)
    - update — обновить пакет
    - create — создать новый пакет
"""

from typing import Optional, List, Dict, Any
from decimal import Decimal

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


async def get_all() -> List[Dict[str, Any]]:
    """
    Получает все пакеты токенов (включая неактивные) для админ-панели.

    Returns:
        Список всех пакетов
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM token_packages ORDER BY id ASC"
        )
        return [dict(row) for row in rows]


async def update(package_id: int, **fields) -> Optional[Dict[str, Any]]:
    """
    Обновляет пакет токенов.

    Args:
        package_id: ID пакета
        **fields: Поля для обновления (name, description, price_rub, tokens_amount, is_active)

    Returns:
        Обновлённый пакет или None
    """
    allowed = {'name', 'description', 'price_rub', 'tokens_amount', 'is_active'}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return None

    set_parts = []
    values = [package_id]
    for i, (k, v) in enumerate(updates.items()):
        set_parts.append(f"{k} = ${i + 2}")
        if k == 'price_rub' and not isinstance(v, Decimal):
            v = Decimal(str(v))
        values.append(v)

    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"UPDATE token_packages SET {', '.join(set_parts)} WHERE id = $1 RETURNING *",
            *values,
        )
        return dict(row) if row else None


async def create(
    name: str,
    price_rub: float,
    tokens_amount: int,
    description: str = "",
) -> Dict[str, Any]:
    """
    Создаёт новый пакет токенов.

    Args:
        name: Название пакета
        price_rub: Цена в рублях
        tokens_amount: Количество токенов
        description: Описание

    Returns:
        Созданный пакет
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO token_packages (name, description, price_rub, tokens_amount, is_active)
            VALUES ($1, $2, $3, $4, true)
            RETURNING *
            """,
            name, description, Decimal(str(price_rub)), tokens_amount,
        )
        return dict(row)
