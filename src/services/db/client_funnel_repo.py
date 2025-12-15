# src/services/db/client_funnel_repo.py

"""
Репозиторий для работы с CRM: статусы клиентов в воронке продаж.

Функции:
    - get_all_clients_with_status: Все клиенты сгруппированные по статусу
    - get_client_by_id: Полная информация о клиенте
    - update_client_status: Обновить статус (drag-and-drop)
    - ensure_client_status: Создать запись статуса если не существует
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)

# Статусы воронки
FUNNEL_STATUSES = ['new', 'tried', 'trial_ended', 'paid']


async def get_all_clients_with_status() -> List[Dict[str, Any]]:
    """
    Получить всех клиентов с их статусами и метриками.

    Возвращает список клиентов с полями:
        - id, telegram_user_id, username, first_name, last_name
        - status, auto_status, manual_override
        - total_consultations, total_tokens, total_cost_usd
        - last_consultation_at
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                u.id,
                u.telegram_user_id,
                u.username,
                u.first_name,
                u.last_name,
                u.created_at as user_created_at,
                COALESCE(cfs.status, 'new') as status,
                cfs.auto_status,
                COALESCE(cfs.manual_override, false) as manual_override,
                cfs.updated_at as status_updated_at,
                COALESCE(stats.total_consultations, 0) as total_consultations,
                COALESCE(stats.total_tokens, 0) as total_tokens,
                COALESCE(stats.total_cost_usd, 0.0) as total_cost_usd,
                stats.last_consultation_at
            FROM users u
            LEFT JOIN client_funnel_status cfs ON cfs.user_id = u.id
            LEFT JOIN LATERAL (
                SELECT
                    COUNT(*)::int as total_consultations,
                    COALESCE(SUM(total_tokens), 0)::int as total_tokens,
                    COALESCE(SUM(cost_usd), 0.0) as total_cost_usd,
                    MAX(created_at) as last_consultation_at
                FROM consultation_logs cl
                WHERE cl.user_id = u.id
            ) stats ON true
            ORDER BY stats.last_consultation_at DESC NULLS LAST, u.created_at DESC
            """
        )

        return [dict(row) for row in rows]


async def get_clients_grouped_by_status() -> Dict[str, List[Dict[str, Any]]]:
    """
    Получить клиентов сгруппированных по статусу для Kanban.

    Возвращает словарь: {'new': [...], 'tried': [...], 'trial_ended': [...], 'paid': [...]}
    """
    clients = await get_all_clients_with_status()

    grouped = {status: [] for status in FUNNEL_STATUSES}

    for client in clients:
        status = client.get('status', 'new')
        if status in grouped:
            grouped[status].append(client)
        else:
            grouped['new'].append(client)

    return grouped


async def get_client_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Получить полную информацию о клиенте по ID.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                u.id,
                u.telegram_user_id,
                u.username,
                u.first_name,
                u.last_name,
                u.token_balance,
                u.region,
                u.created_at as user_created_at,
                COALESCE(cfs.status, 'new') as status,
                cfs.auto_status,
                COALESCE(cfs.manual_override, false) as manual_override,
                cfs.updated_at as status_updated_at,
                COALESCE(stats.total_consultations, 0) as total_consultations,
                COALESCE(stats.total_tokens, 0) as total_tokens,
                COALESCE(stats.total_cost_usd, 0.0) as total_cost_usd,
                stats.last_consultation_at
            FROM users u
            LEFT JOIN client_funnel_status cfs ON cfs.user_id = u.id
            LEFT JOIN LATERAL (
                SELECT
                    COUNT(*)::int as total_consultations,
                    COALESCE(SUM(total_tokens), 0)::int as total_tokens,
                    COALESCE(SUM(cost_usd), 0.0) as total_cost_usd,
                    MAX(created_at) as last_consultation_at
                FROM consultation_logs cl
                WHERE cl.user_id = u.id
            ) stats ON true
            WHERE u.id = $1
            """,
            user_id
        )

        return dict(row) if row else None


async def update_client_status(user_id: int, new_status: str) -> bool:
    """
    Обновить статус клиента в воронке (drag-and-drop).

    Устанавливает manual_override = true.

    Возвращает True если успешно, False если клиент не найден.
    """
    if new_status not in FUNNEL_STATUSES:
        logger.warning(f"Invalid funnel status: {new_status}")
        return False

    pool = get_pool()

    async with pool.acquire() as conn:
        # Сначала убедимся что запись существует
        await ensure_client_status(user_id, conn=conn)

        # Обновляем статус
        result = await conn.execute(
            """
            UPDATE client_funnel_status
            SET status = $2, manual_override = true, updated_at = NOW()
            WHERE user_id = $1
            """,
            user_id,
            new_status
        )

        return result == "UPDATE 1"


async def ensure_client_status(user_id: int, conn=None) -> None:
    """
    Создать запись статуса для пользователя если не существует.

    Автоматически определяет статус:
        - 'tried' если есть консультации
        - 'new' если консультаций нет
    """
    pool = get_pool()
    should_release = conn is None

    if conn is None:
        conn = await pool.acquire()

    try:
        # Проверяем есть ли запись
        exists = await conn.fetchval(
            "SELECT 1 FROM client_funnel_status WHERE user_id = $1",
            user_id
        )

        if not exists:
            # Определяем автостатус
            has_consultations = await conn.fetchval(
                "SELECT 1 FROM topics WHERE user_id = $1 LIMIT 1",
                user_id
            )
            auto_status = 'tried' if has_consultations else 'new'

            await conn.execute(
                """
                INSERT INTO client_funnel_status (user_id, status, auto_status)
                VALUES ($1, $2, $2)
                ON CONFLICT (user_id) DO NOTHING
                """,
                user_id,
                auto_status
            )
    finally:
        if should_release:
            await pool.release(conn)


async def recalculate_auto_status(user_id: int) -> str:
    """
    Пересчитать автоматический статус клиента на основе данных.

    Логика:
        - 'paid' — есть оплаты (будущее)
        - 'trial_ended' — исчерпан лимит (будущее)
        - 'tried' — есть хотя бы 1 консультация
        - 'new' — нет консультаций

    Обновляет auto_status в БД, но НЕ меняет status если manual_override = true.

    Возвращает новый auto_status.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        # Проверяем наличие консультаций
        has_consultations = await conn.fetchval(
            "SELECT 1 FROM topics WHERE user_id = $1 LIMIT 1",
            user_id
        )

        # TODO: добавить проверку оплат когда появится монетизация
        # TODO: добавить проверку лимитов

        if has_consultations:
            auto_status = 'tried'
        else:
            auto_status = 'new'

        # Обновляем auto_status
        # Если manual_override = false, также обновляем основной status
        await conn.execute(
            """
            UPDATE client_funnel_status
            SET
                auto_status = $2,
                status = CASE WHEN manual_override = false THEN $2 ELSE status END,
                updated_at = NOW()
            WHERE user_id = $1
            """,
            user_id,
            auto_status
        )

        return auto_status


async def get_funnel_stats() -> Dict[str, int]:
    """
    Получить количество клиентов в каждом статусе воронки.

    Возвращает: {'new': 10, 'tried': 25, 'trial_ended': 5, 'paid': 3}
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                COALESCE(cfs.status, 'new') as status,
                COUNT(*)::int as count
            FROM users u
            LEFT JOIN client_funnel_status cfs ON cfs.user_id = u.id
            GROUP BY COALESCE(cfs.status, 'new')
            """
        )

        # Инициализируем все статусы нулями
        stats = {status: 0 for status in FUNNEL_STATUSES}

        for row in rows:
            status = row['status']
            if status in stats:
                stats[status] = row['count']

        return stats
