"""
Репозиторий для работы с платежами.

Функции:
    - create_payment — создать новый платеж
    - get_by_id — получить платеж по ID
    - get_by_yookassa_id — получить платеж по YooKassa ID
    - update_status — обновить статус платежа
    - update_webhook_timestamp — обновить время последнего webhook
    - get_user_payments — получить все платежи пользователя
    - get_expired_pending — получить просроченные платежи
"""

import json
from typing import Optional, List, Dict, Any
from datetime import datetime

from src.services.db.pool import get_pool


async def create_payment(
    user_id: int,
    yookassa_payment_id: str,
    idempotency_key: str,
    payment_type: str,
    amount_rub: float,
    description: str,
    confirmation_url: str,
    subscription_plan_id: Optional[int] = None,
    token_package_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    client_ip: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Создает новую запись о платеже.

    Args:
        user_id: ID пользователя
        yookassa_payment_id: ID платежа в YooKassa
        idempotency_key: Ключ идемпотентности
        payment_type: Тип платежа ('subscription' | 'tokens')
        amount_rub: Сумма в рублях
        description: Описание платежа
        confirmation_url: URL для оплаты
        subscription_plan_id: ID тарифа подписки (если тип = subscription)
        token_package_id: ID пакета токенов (если тип = tokens)
        metadata: Дополнительные данные
        client_ip: IP адрес клиента

    Returns:
        Созданный платеж
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        # Преобразовать metadata в JSON, если передан dict
        metadata_json = json.dumps(metadata) if metadata else None

        row = await conn.fetchrow(
            """
            INSERT INTO payments (
                user_id,
                yookassa_payment_id,
                idempotency_key,
                payment_type,
                subscription_plan_id,
                token_package_id,
                amount_rub,
                currency,
                status,
                description,
                confirmation_url,
                metadata,
                client_ip,
                created_at,
                expires_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, 'RUB', 'pending', $8, $9, $10::jsonb, $11, NOW(), NOW() + INTERVAL '30 minutes'
            )
            RETURNING *
            """,
            user_id,
            yookassa_payment_id,
            idempotency_key,
            payment_type,
            subscription_plan_id,
            token_package_id,
            amount_rub,
            description,
            confirmation_url,
            metadata_json,
            client_ip,
        )
        return dict(row)


async def get_by_id(payment_id: int) -> Optional[Dict[str, Any]]:
    """Получает платеж по внутреннему ID."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM payments WHERE id = $1",
            payment_id,
        )
        return dict(row) if row else None


async def get_by_yookassa_id(yookassa_payment_id: str) -> Optional[Dict[str, Any]]:
    """Получает платеж по YooKassa ID."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM payments WHERE yookassa_payment_id = $1",
            yookassa_payment_id,
        )
        return dict(row) if row else None


async def update_status(
    payment_id: int,
    status: str,
    paid: bool = False,
    paid_at: Optional[datetime] = None,
    canceled_at: Optional[datetime] = None,
    yookassa_payment_object: Optional[Dict[str, Any]] = None,
    webhook_verified: bool = False,
    receipt_registration: Optional[str] = None,
    fiscal_document_number: Optional[str] = None,
) -> None:
    """
    Обновляет статус платежа.

    Args:
        payment_id: ID платежа
        status: Новый статус
        paid: Флаг оплаты
        paid_at: Время оплаты
        canceled_at: Время отмены
        yookassa_payment_object: Полный объект платежа от YooKassa
        webhook_verified: Webhook верифицирован
        receipt_registration: Статус регистрации чека
        fiscal_document_number: Номер фискального документа
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        # Преобразовать yookassa_payment_object в JSON, если передан dict
        payment_object_json = json.dumps(yookassa_payment_object) if yookassa_payment_object else None

        await conn.execute(
            """
            UPDATE payments
            SET status = $2,
                paid = $3,
                paid_at = $4,
                canceled_at = $5,
                yookassa_payment_object = $6::jsonb,
                webhook_verified = $7,
                receipt_registration = $8,
                fiscal_document_number = $9,
                last_webhook_at = NOW()
            WHERE id = $1
            """,
            payment_id,
            status,
            paid,
            paid_at,
            canceled_at,
            payment_object_json,
            webhook_verified,
            receipt_registration,
            fiscal_document_number,
        )


async def update_webhook_timestamp(payment_id: int) -> None:
    """Обновляет timestamp последнего webhook."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE payments SET last_webhook_at = NOW() WHERE id = $1",
            payment_id,
        )


async def get_user_payments(
    user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    Получает все платежи пользователя.

    Args:
        user_id: ID пользователя
        limit: Количество записей
        offset: Смещение

    Returns:
        Список платежей
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM payments
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id,
            limit,
            offset,
        )
        return [dict(row) for row in rows]


async def get_expired_pending() -> List[Dict[str, Any]]:
    """Получает просроченные платежи в статусе pending."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM payments
            WHERE status = 'pending'
            AND expires_at < NOW()
            """
        )
        return [dict(row) for row in rows]


async def log_payment_error(
    user_id: int,
    payment_id: Optional[str],
    error_code: str,
    error_message: str,
    yookassa_error_data: Optional[Dict[str, Any]] = None,
    retry_count: int = 0,
) -> None:
    """
    Логирует ошибку платежа.

    Args:
        user_id: ID пользователя
        payment_id: ID платежа (может быть None)
        error_code: Код ошибки
        error_message: Сообщение об ошибке
        yookassa_error_data: Данные ошибки от YooKassa
        retry_count: Количество повторов
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO payment_errors (
                user_id,
                payment_id,
                error_code,
                error_message,
                yookassa_error_data,
                retry_count
            ) VALUES ($1, $2, $3, $4, $5, $6)
            """,
            user_id,
            payment_id,
            error_code,
            error_message,
            yookassa_error_data,
            retry_count,
        )


async def get_user_payments_with_details(
    user_id: int,
    limit: int = 50,
    offset: int = 0,
    status_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Получает платежи пользователя с деталями продуктов.

    Args:
        user_id: ID пользователя
        limit: Количество записей
        offset: Смещение
        status_filter: Фильтр по статусу (опционально)

    Returns:
        Список платежей с enriched полями
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                p.*,
                sp.name as subscription_plan_name,
                sp.duration_days,
                tp.name as token_package_name,
                tp.tokens_amount
            FROM payments p
            LEFT JOIN subscription_plans sp ON p.subscription_plan_id = sp.id
            LEFT JOIN token_packages tp ON p.token_package_id = tp.id
            WHERE p.user_id = $1
                AND ($2::text IS NULL OR p.status = $2)
            ORDER BY p.created_at DESC
            LIMIT $3 OFFSET $4
            """,
            user_id,
            status_filter,
            limit,
            offset,
        )
        return [dict(row) for row in rows]


async def get_all_payments_with_details(
    limit: int = 50,
    offset: int = 0,
    status_filter: Optional[str] = None,
    payment_type_filter: Optional[str] = None,
    user_id_filter: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Получает все платежи с деталями пользователей и продуктов.

    Args:
        limit: Количество записей
        offset: Смещение
        status_filter: Фильтр по статусу
        payment_type_filter: Фильтр по типу платежа
        user_id_filter: Фильтр по ID пользователя

    Returns:
        Список платежей с enriched полями
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                p.*,
                u.username,
                u.first_name,
                u.telegram_user_id,
                sp.name as subscription_plan_name,
                tp.name as token_package_name
            FROM payments p
            JOIN users u ON p.user_id = u.id
            LEFT JOIN subscription_plans sp ON p.subscription_plan_id = sp.id
            LEFT JOIN token_packages tp ON p.token_package_id = tp.id
            WHERE ($1::text IS NULL OR p.status = $1)
                AND ($2::text IS NULL OR p.payment_type = $2)
                AND ($3::bigint IS NULL OR p.user_id = $3)
            ORDER BY p.created_at DESC
            LIMIT $4 OFFSET $5
            """,
            status_filter,
            payment_type_filter,
            user_id_filter,
            limit,
            offset,
        )
        return [dict(row) for row in rows]


async def get_user_total_paid(user_id: int) -> float:
    """
    Получает общую сумму оплаченных платежей пользователя.

    Args:
        user_id: ID пользователя

    Returns:
        Сумма оплаченных платежей
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT COALESCE(SUM(amount_rub), 0) as total
            FROM payments
            WHERE user_id = $1 AND paid = true
            """,
            user_id,
        )
        return float(row['total']) if row else 0.0


async def get_payment_statistics(period: Optional[str] = None) -> Dict[str, Any]:
    """
    Получает статистику по платежам.

    Args:
        period: Период ('day', 'week', 'month', 'all')

    Returns:
        Статистика платежей
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        # Определяем временной фильтр
        time_filter = ""
        if period == 'day':
            time_filter = "AND created_at >= NOW() - INTERVAL '1 day'"
        elif period == 'week':
            time_filter = "AND created_at >= NOW() - INTERVAL '7 days'"
        elif period == 'month':
            time_filter = "AND created_at >= NOW() - INTERVAL '30 days'"

        # Общая статистика
        row = await conn.fetchrow(
            f"""
            SELECT
                COUNT(*) as total_count,
                COALESCE(SUM(amount_rub), 0) as total_amount,
                COALESCE(SUM(CASE WHEN paid = true THEN amount_rub ELSE 0 END), 0) as paid_amount,
                COALESCE(SUM(CASE WHEN status = 'pending' THEN amount_rub ELSE 0 END), 0) as pending_amount
            FROM payments
            WHERE 1=1 {time_filter}
            """
        )

        # Статистика по типам
        type_rows = await conn.fetch(
            f"""
            SELECT
                payment_type,
                COUNT(*) as count,
                COALESCE(SUM(amount_rub), 0) as amount
            FROM payments
            WHERE 1=1 {time_filter}
            GROUP BY payment_type
            """
        )

        # Статистика по статусам
        status_rows = await conn.fetch(
            f"""
            SELECT
                status,
                COUNT(*) as count,
                COALESCE(SUM(amount_rub), 0) as amount
            FROM payments
            WHERE 1=1 {time_filter}
            GROUP BY status
            """
        )

        by_type = {row['payment_type']: {'count': row['count'], 'amount': float(row['amount'])} for row in type_rows}
        by_status = {row['status']: {'count': row['count'], 'amount': float(row['amount'])} for row in status_rows}

        return {
            'total_count': row['total_count'],
            'total_amount': float(row['total_amount']),
            'paid_amount': float(row['paid_amount']),
            'pending_amount': float(row['pending_amount']),
            'by_type': by_type,
            'by_status': by_status,
        }
