# src/services/db/discount_repo.py
"""
Репозиторий для персональных скидок рассылки.

Функции:
    - upsert_broadcast_discount — создать или заменить скидку пользователя
    - get_user_active_broadcast_discount — получить активную скидку (не истёкшую)
"""

import logging
from typing import Optional, Dict, Any

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


async def upsert_broadcast_discount(
    user_id: int,
    broadcast_id: int,
    option_key: str,
    discount_percent: int,
    bonus_tokens: int,
    duration_hours: int,
) -> Dict[str, Any]:
    """
    Создать или заменить активную скидку пользователя.
    UNIQUE(user_id) — при повторном клике старая скидка заменяется.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO user_broadcast_discounts
                (user_id, broadcast_id, option_key, discount_percent, bonus_tokens, expires_at)
            VALUES
                ($1, $2, $3, $4, $5, NOW() + ($6 * INTERVAL '1 hour'))
            ON CONFLICT (user_id) DO UPDATE SET
                broadcast_id     = EXCLUDED.broadcast_id,
                option_key       = EXCLUDED.option_key,
                discount_percent = EXCLUDED.discount_percent,
                bonus_tokens     = EXCLUDED.bonus_tokens,
                activated_at     = NOW(),
                expires_at       = NOW() + ($6 * INTERVAL '1 hour')
            RETURNING *
            """,
            user_id, broadcast_id, option_key, discount_percent, bonus_tokens, duration_hours,
        )
    return dict(row)


async def get_user_active_broadcast_discount(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Вернуть активную скидку (не истёкшую) или None.
    Возвращает: discount_percent, bonus_tokens, expires_at, broadcast_id
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT discount_percent, bonus_tokens, expires_at, broadcast_id
            FROM user_broadcast_discounts
            WHERE user_id = $1 AND expires_at > NOW()
            """,
            user_id,
        )
    return dict(row) if row else None
