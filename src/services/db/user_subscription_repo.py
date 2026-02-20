"""
Репозиторий для работы с подписками пользователей.

Функции:
    - create — создать подписку
    - get_active_subscription — получить активную подписку пользователя
    - get_by_id — получить подписку по ID
    - get_expiring_soon — получить подписки, истекающие скоро
    - update_status — обновить статус подписки
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from src.services.db.pool import get_pool


async def create(
    user_id: int,
    subscription_plan_id: int,
    payment_id: int,
    started_at: datetime,
    expires_at: datetime,
    tokens_granted: int,
    status: str = 'active',
    payment_method_id: Optional[str] = None,
    auto_renew: bool = True,
    next_billing_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Создает новую подписку.

    Args:
        user_id: ID пользователя
        subscription_plan_id: ID тарифного плана
        payment_id: ID платежа
        started_at: Дата начала
        expires_at: Дата окончания
        tokens_granted: Количество начисленных токенов
        status: Статус подписки
        payment_method_id: ID сохраненного способа оплаты для автопродления
        auto_renew: Автоматическое продление (по умолчанию включено)
        next_billing_date: Дата следующего автоплатежа

    Returns:
        Созданная подписка
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO user_subscriptions (
                user_id,
                subscription_plan_id,
                payment_id,
                started_at,
                expires_at,
                tokens_granted,
                status,
                is_active,
                payment_method_id,
                auto_renew,
                next_billing_date
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, true, $8, $9, $10)
            RETURNING *
            """,
            user_id,
            subscription_plan_id,
            payment_id,
            started_at,
            expires_at,
            tokens_granted,
            status,
            payment_method_id,
            auto_renew,
            next_billing_date,
        )
        return dict(row)


async def get_active_subscription(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Получает активную подписку пользователя.

    Args:
        user_id: ID пользователя

    Returns:
        Активная подписка или None
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM user_subscriptions
            WHERE user_id = $1
            AND status = 'active'
            AND is_active = true
            AND started_at <= NOW()
            AND expires_at > NOW()
            ORDER BY expires_at DESC
            LIMIT 1
            """,
            user_id,
        )
        return dict(row) if row else None


async def get_pending_subscription(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Получает отложенную подписку (оплачена, но ещё не началась).
    started_at > NOW() означает что подписка начнётся в будущем.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM user_subscriptions
            WHERE user_id = $1
            AND status = 'active'
            AND is_active = true
            AND started_at > NOW()
            ORDER BY started_at ASC
            LIMIT 1
            """,
            user_id,
        )
        return dict(row) if row else None


async def activate_pending_subscriptions() -> int:
    """
    Активирует отложенные подписки у которых наступил started_at.
    Начисляет токены. Вызывается из фоновой задачи.
    Returns: количество активированных.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT us.*, sp.tokens_included, sp.max_carryover, sp.name as plan_name
            FROM user_subscriptions us
            JOIN subscription_plans sp ON sp.id = us.subscription_plan_id
            WHERE us.status = 'active'
            AND us.is_active = true
            AND us.started_at <= NOW()
            AND us.started_at > (NOW() - INTERVAL '1 hour')
            AND us.tokens_granted_at IS NULL
            """,
        )

    count = 0
    for row in rows:
        try:
            from src.services.db.tokens_repo import reset_subscription_tokens_with_carryover
            await reset_subscription_tokens_with_carryover(
                user_id=row["user_id"],
                new_amount=row["tokens_included"],
                max_carryover=row["max_carryover"] or 0,
            )
            # Помечаем что токены начислены
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE user_subscriptions SET tokens_granted_at = NOW() WHERE id = $1",
                    row["id"],
                )
            count += 1
        except Exception:
            pass
    return count


async def get_by_id(subscription_id: int) -> Optional[Dict[str, Any]]:
    """Получает подписку по ID."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM user_subscriptions WHERE id = $1",
            subscription_id,
        )
        return dict(row) if row else None


async def get_expiring_soon(days: int = 3) -> List[Dict[str, Any]]:
    """
    Получает подписки, истекающие в ближайшие N дней.

    Args:
        days: Количество дней

    Returns:
        Список подписок
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM user_subscriptions
            WHERE status = 'active'
            AND expires_at BETWEEN NOW() AND NOW() + INTERVAL '%s days'
            """,
            days,
        )
        return [dict(row) for row in rows]


async def update_status(
    subscription_id: int,
    status: str,
    is_active: bool,
    cancellation_reason: Optional[str] = None,
) -> None:
    """
    Обновляет статус подписки.

    Args:
        subscription_id: ID подписки
        status: Новый статус
        is_active: Флаг активности
        cancellation_reason: Причина отмены
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE user_subscriptions
            SET status = $2,
                is_active = $3,
                cancellation_reason = $4,
                updated_at = NOW()
            WHERE id = $1
            """,
            subscription_id,
            status,
            is_active,
            cancellation_reason,
        )


async def expire_old_subscriptions() -> int:
    """
    Автоматически истекает просроченные подписки.

    Returns:
        Количество обновленных записей
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE user_subscriptions
            SET status = 'expired',
                is_active = false,
                updated_at = NOW()
            WHERE status = 'active'
            AND expires_at <= NOW()
            """
        )
        # Парсим результат "UPDATE N"
        count = int(result.split()[-1]) if result else 0
        return count
