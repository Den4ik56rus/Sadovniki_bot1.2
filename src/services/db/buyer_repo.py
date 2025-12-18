# src/services/db/buyer_repo.py

"""
Репозиторий для работы с покупателями (Buyers) — клиенты, оплатившие подписку.

Функции:
    - get_all_buyers_with_status: Все покупатели сгруппированные по статусу
    - get_buyers_grouped_by_status: Для Kanban-доски
    - get_buyer_by_id: Полная информация о покупателе
    - update_buyer_status: Обновить статус (drag-and-drop)
    - create_buyer_from_deal: Создать покупателя из сделки
    - get_buyer_columns: Получить колонки канбана
    - create/update/delete_buyer_column: CRUD колонок
"""

import logging
from typing import Optional, List, Dict, Any

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)

# Стандартные статусы покупателей
BUYER_STATUSES = ['pending_payment', 'paid', 'active', 'expired']

# Стандартные колонки с настройками по умолчанию
DEFAULT_BUYER_COLUMNS = [
    {'id': 'pending_payment', 'title': 'Ожидает оплаты', 'color': '#F59E0B', 'sort_order': 0, 'is_system': True},
    {'id': 'paid', 'title': 'Оплачено', 'color': '#22C55E', 'sort_order': 1, 'is_system': True},
    {'id': 'active', 'title': 'Активна', 'color': '#3B82F6', 'sort_order': 2, 'is_system': True},
    {'id': 'expired', 'title': 'Истекла', 'color': '#EF4444', 'sort_order': 3, 'is_system': True},
]


async def get_all_buyers_with_status() -> List[Dict[str, Any]]:
    """
    Получить всех покупателей с их статусами и метриками.

    Использует unified таблицу client_funnel_position для воронки 'buyers'.

    Возвращает список покупателей с полями:
        - id, telegram_user_id, username, first_name, last_name
        - status, manual_override, source
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
                cfp.stage_key as status,
                COALESCE(cfp.manual_override, false) as manual_override,
                cfp.updated_at as status_updated_at,
                cfp.entered_at as buyer_created_at,
                cfs.source,
                COALESCE(stats.total_consultations, 0) as total_consultations,
                COALESCE(stats.total_tokens, 0) as total_tokens,
                COALESCE(stats.total_cost_usd, 0.0) as total_cost_usd,
                stats.last_consultation_at
            FROM client_funnel_position cfp
            JOIN users u ON u.id = cfp.user_id
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
            WHERE cfp.funnel_id = 'buyers'
            ORDER BY cfp.entered_at DESC
            """
        )

        return [dict(row) for row in rows]


async def get_buyers_grouped_by_status() -> Dict[str, List[Dict[str, Any]]]:
    """
    Получить покупателей сгруппированных по статусу для Kanban.

    Поддерживает как стандартные, так и кастомные колонки.
    Возвращает словарь: {'pending_payment': [...], 'paid': [...], 'custom_1': [...], ...}
    """
    buyers = await get_all_buyers_with_status()
    columns = await get_buyer_columns()

    # Инициализируем все колонки пустыми списками
    grouped = {col['id']: [] for col in columns}

    for buyer in buyers:
        status = buyer.get('status', 'pending_payment')
        if status in grouped:
            grouped[status].append(buyer)
        else:
            # Если статус покупателя не найден среди колонок, кладём в 'pending_payment'
            if 'pending_payment' in grouped:
                grouped['pending_payment'].append(buyer)

    return grouped


async def get_buyer_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Получить полную информацию о покупателе по ID.
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
                bs.status,
                COALESCE(bs.manual_override, false) as manual_override,
                bs.updated_at as status_updated_at,
                bs.created_at as buyer_created_at,
                COALESCE(stats.total_consultations, 0) as total_consultations,
                COALESCE(stats.total_tokens, 0) as total_tokens,
                COALESCE(stats.total_cost_usd, 0.0) as total_cost_usd,
                stats.last_consultation_at
            FROM buyer_status bs
            JOIN users u ON u.id = bs.user_id
            LEFT JOIN LATERAL (
                SELECT
                    COUNT(*)::int as total_consultations,
                    COALESCE(SUM(total_tokens), 0)::int as total_tokens,
                    COALESCE(SUM(cost_usd), 0.0) as total_cost_usd,
                    MAX(created_at) as last_consultation_at
                FROM consultation_logs cl
                WHERE cl.user_id = u.id
            ) stats ON true
            WHERE bs.user_id = $1
            """,
            user_id
        )

        return dict(row) if row else None


async def update_buyer_status(user_id: int, new_status: str) -> bool:
    """
    Обновить статус покупателя (drag-and-drop).

    Устанавливает manual_override = true.

    Возвращает True если успешно, False если покупатель не найден.
    """
    # Проверяем что колонка существует (стандартная или кастомная)
    valid_columns = await get_buyer_columns()
    valid_ids = [col['id'] for col in valid_columns]

    if new_status not in valid_ids:
        logger.warning(f"Invalid buyer status: {new_status}")
        return False

    pool = get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE buyer_status
            SET status = $2, manual_override = true, updated_at = NOW()
            WHERE user_id = $1
            """,
            user_id,
            new_status
        )

        return result == "UPDATE 1"


async def create_buyer_from_deal(user_id: int, initial_status: str = 'pending_payment') -> bool:
    """
    Создать покупателя из сделки (при переходе в статус paid).

    Также удаляет клиента из client_funnel_status.

    Returns:
        True если успешно (пользователь существует), False если пользователь не найден
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Проверяем что пользователь существует
            user_exists = await conn.fetchval(
                "SELECT 1 FROM users WHERE id = $1",
                user_id
            )

            if not user_exists:
                logger.warning(f"User {user_id} not found when creating buyer")
                return False

            # Создаём запись покупателя (или игнорируем если уже есть)
            await conn.execute(
                """
                INSERT INTO buyer_status (user_id, status)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO NOTHING
                """,
                user_id,
                initial_status
            )

            # ВСЕГДА удаляем из сделок (независимо от того, был ли INSERT)
            deleted = await conn.execute(
                "DELETE FROM client_funnel_status WHERE user_id = $1",
                user_id
            )

            # Логируем событие только если был реальный перенос из CRM
            if "DELETE 1" in deleted:
                await conn.execute(
                    """
                    INSERT INTO client_activity_log (user_id, event_type, event_data)
                    VALUES ($1, 'became_buyer', $2::jsonb)
                    """,
                    user_id,
                    '{"source": "deal_conversion"}'
                )

            return True  # Всегда True если пользователь существует


async def get_buyer_stats() -> Dict[str, int]:
    """
    Получить количество покупателей в каждом статусе.

    Использует unified таблицу client_funnel_position для воронки 'buyers'.
    Поддерживает кастомные колонки.
    Возвращает: {'pending_payment': 10, 'paid': 25, 'custom_1': 5, ...}
    """
    pool = get_pool()
    columns = await get_buyer_columns()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT stage_key as status, COUNT(*)::int as count
            FROM client_funnel_position
            WHERE funnel_id = 'buyers'
            GROUP BY stage_key
            """
        )

        # Инициализируем все колонки нулями
        stats = {col['id']: 0 for col in columns}

        for row in rows:
            status = row['status']
            if status in stats:
                stats[status] = row['count']
            elif 'pending_payment' in stats:
                # Неизвестный статус — добавляем к первой колонке
                stats['pending_payment'] += row['count']

        return stats


# =============================================================================
# Buyer Columns Management (Kanban column configuration)
# =============================================================================

async def get_buyer_columns() -> List[Dict[str, Any]]:
    """
    Получить все колонки покупателей отсортированные по порядку.

    Если таблица пуста или не существует, возвращает стандартные колонки.
    """
    pool = get_pool()

    try:
        async with pool.acquire() as conn:
            # Проверяем существует ли таблица
            table_exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'buyer_funnel_columns'
                )
                """
            )

            if not table_exists:
                return DEFAULT_BUYER_COLUMNS

            rows = await conn.fetch(
                """
                SELECT id, title, color, sort_order, is_system
                FROM buyer_funnel_columns
                ORDER BY sort_order ASC
                """
            )

            if not rows:
                return DEFAULT_BUYER_COLUMNS

            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching buyer columns: {e}")
        return DEFAULT_BUYER_COLUMNS


async def create_buyer_column(
    column_id: str,
    title: str,
    color: str,
    sort_order: int
) -> Dict[str, Any]:
    """
    Создать новую кастомную колонку покупателей.

    Args:
        column_id: Уникальный ID (например 'custom_1')
        title: Отображаемое название
        color: Цвет в формате HEX
        sort_order: Позиция в списке

    Returns:
        Созданная колонка
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO buyer_funnel_columns (id, title, color, sort_order, is_system)
            VALUES ($1, $2, $3, $4, false)
            RETURNING id, title, color, sort_order, is_system
            """,
            column_id,
            title,
            color,
            sort_order
        )

        return dict(row)


async def update_buyer_column(
    column_id: str,
    title: Optional[str] = None,
    color: Optional[str] = None,
    sort_order: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Обновить колонку покупателей.

    Можно обновлять любые поля, включая системные колонки (кроме id и is_system).
    """
    pool = get_pool()

    # Собираем поля для обновления
    updates = []
    params = [column_id]
    param_idx = 2

    if title is not None:
        updates.append(f"title = ${param_idx}")
        params.append(title)
        param_idx += 1

    if color is not None:
        updates.append(f"color = ${param_idx}")
        params.append(color)
        param_idx += 1

    if sort_order is not None:
        updates.append(f"sort_order = ${param_idx}")
        params.append(sort_order)
        param_idx += 1

    if not updates:
        return None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE buyer_funnel_columns
            SET {', '.join(updates)}
            WHERE id = $1
            RETURNING id, title, color, sort_order, is_system
            """,
            *params
        )

        return dict(row) if row else None


async def delete_buyer_column(column_id: str) -> bool:
    """
    Удалить кастомную колонку покупателей.

    Системные колонки (is_system = true) удалить нельзя.
    Покупатели в удалённой колонке будут перемещены в 'pending_payment'.

    Returns:
        True если удалено, False если колонка системная или не найдена
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Проверяем что колонка не системная
            is_system = await conn.fetchval(
                "SELECT is_system FROM buyer_funnel_columns WHERE id = $1",
                column_id
            )

            if is_system is None:
                return False  # Колонка не найдена

            if is_system:
                logger.warning(f"Cannot delete system buyer column: {column_id}")
                return False

            # Переносим покупателей в 'pending_payment'
            await conn.execute(
                """
                UPDATE buyer_status
                SET status = 'pending_payment', manual_override = true
                WHERE status = $1
                """,
                column_id
            )

            # Удаляем колонку
            result = await conn.execute(
                "DELETE FROM buyer_funnel_columns WHERE id = $1 AND is_system = false",
                column_id
            )

            return result == "DELETE 1"


async def reorder_buyer_columns(column_ids: List[str]) -> bool:
    """
    Изменить порядок колонок покупателей.

    Args:
        column_ids: Список ID колонок в новом порядке

    Returns:
        True если успешно
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            for idx, col_id in enumerate(column_ids):
                await conn.execute(
                    """
                    UPDATE buyer_funnel_columns
                    SET sort_order = $2
                    WHERE id = $1
                    """,
                    col_id,
                    idx
                )

    return True


async def get_next_buyer_column_id() -> str:
    """
    Получить следующий доступный ID для кастомной колонки покупателей.

    Returns:
        ID в формате 'custom_N'
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        # Находим максимальный номер среди custom_* колонок
        max_num = await conn.fetchval(
            """
            SELECT MAX(
                CAST(SUBSTRING(id FROM 'custom_([0-9]+)') AS INTEGER)
            )
            FROM buyer_funnel_columns
            WHERE id LIKE 'custom_%'
            """
        )

        next_num = (max_num or 0) + 1
        return f"custom_{next_num}"
