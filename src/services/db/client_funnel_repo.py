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

# Стандартные статусы воронки (для обратной совместимости)
FUNNEL_STATUSES = ['new', 'tried', 'trial_ended', 'paid']

# Стандартные колонки с настройками по умолчанию
DEFAULT_COLUMNS = [
    {'id': 'new', 'title': 'НЕРАЗОБРАННОЕ', 'color': '#3B82F6', 'sort_order': 0, 'is_system': True},
    {'id': 'tried', 'title': 'БИРЖА ЛИДОВ', 'color': '#8B5CF6', 'sort_order': 1, 'is_system': True},
    {'id': 'trial_ended', 'title': 'ВЗЯТ В РАБОТУ', 'color': '#F59E0B', 'sort_order': 2, 'is_system': True},
    {'id': 'paid', 'title': 'УЗНАЛ ЦЕНУ', 'color': '#22C55E', 'sort_order': 3, 'is_system': True},
]


async def get_all_clients_with_status() -> List[Dict[str, Any]]:
    """
    Получить всех клиентов CRM с их статусами и метриками.

    Исключает пользователей, которые уже находятся в других воронках
    (например, в воронке Покупателей).

    Возвращает список клиентов с полями:
        - id, telegram_user_id, username, first_name, last_name
        - status, auto_status, manual_override, source
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
                cfs.source,
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
            WHERE NOT EXISTS (
                SELECT 1 FROM client_funnel_position cfp
                WHERE cfp.user_id = u.id AND cfp.funnel_id != 'crm'
            )
            ORDER BY stats.last_consultation_at DESC NULLS LAST, u.created_at DESC
            """
        )

        return [dict(row) for row in rows]


async def get_clients_grouped_by_status() -> Dict[str, List[Dict[str, Any]]]:
    """
    Получить клиентов сгруппированных по статусу для Kanban.

    Поддерживает как стандартные, так и кастомные колонки.
    Возвращает словарь: {'new': [...], 'tried': [...], 'custom_1': [...], ...}
    """
    clients = await get_all_clients_with_status()
    columns = await get_funnel_columns()

    # Инициализируем все колонки пустыми списками
    grouped = {col['id']: [] for col in columns}

    for client in clients:
        status = client.get('status', 'new')
        if status in grouped:
            grouped[status].append(client)
        else:
            # Если статус клиента не найден среди колонок, кладём в 'new'
            if 'new' in grouped:
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

    ВАЖНО: Если новый статус = 'paid', клиент автоматически перемещается
    в раздел "Покупатели" и удаляется из "Сделок".

    Возвращает True если успешно, False если клиент не найден.
    """
    # Проверяем что колонка существует (стандартная или кастомная)
    valid_columns = await get_funnel_columns()
    valid_ids = [col['id'] for col in valid_columns]

    if new_status not in valid_ids:
        logger.warning(f"Invalid funnel status: {new_status}")
        return False

    pool = get_pool()

    async with pool.acquire() as conn:
        # Сначала убедимся что запись существует
        await ensure_client_status(user_id, conn=conn)

        # Если статус = 'paid', перемещаем в покупатели
        if new_status == 'paid':
            from src.services.db import buyer_repo
            success = await buyer_repo.create_buyer_from_deal(user_id)
            if success:
                logger.info(f"Client {user_id} moved to buyers (paid status)")
                return True
            else:
                logger.warning(f"Failed to move client {user_id} to buyers")
                return False

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
    Получить количество клиентов в каждом статусе воронки CRM.

    Исключает пользователей, которые находятся в других воронках.
    Поддерживает кастомные колонки.
    Возвращает: {'new': 10, 'tried': 25, 'custom_1': 5, ...}
    """
    pool = get_pool()
    columns = await get_funnel_columns()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                COALESCE(cfs.status, 'new') as status,
                COUNT(*)::int as count
            FROM users u
            LEFT JOIN client_funnel_status cfs ON cfs.user_id = u.id
            WHERE NOT EXISTS (
                SELECT 1 FROM client_funnel_position cfp
                WHERE cfp.user_id = u.id AND cfp.funnel_id != 'crm'
            )
            GROUP BY COALESCE(cfs.status, 'new')
            """
        )

        # Инициализируем все колонки нулями
        stats = {col['id']: 0 for col in columns}

        for row in rows:
            status = row['status']
            if status in stats:
                stats[status] = row['count']
            elif 'new' in stats:
                # Неизвестный статус — добавляем к 'new'
                stats['new'] += row['count']

        return stats


# =============================================================================
# Funnel Columns Management (Kanban column configuration)
# =============================================================================

async def get_funnel_columns() -> List[Dict[str, Any]]:
    """
    Получить все колонки воронки отсортированные по порядку.

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
                    WHERE table_name = 'crm_funnel_columns'
                )
                """
            )

            if not table_exists:
                return DEFAULT_COLUMNS

            rows = await conn.fetch(
                """
                SELECT id, title, color, sort_order, is_system
                FROM crm_funnel_columns
                ORDER BY sort_order ASC
                """
            )

            if not rows:
                return DEFAULT_COLUMNS

            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching funnel columns: {e}")
        return DEFAULT_COLUMNS


async def create_funnel_column(
    column_id: str,
    title: str,
    color: str,
    sort_order: int
) -> Dict[str, Any]:
    """
    Создать новую кастомную колонку воронки.

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
            INSERT INTO crm_funnel_columns (id, title, color, sort_order, is_system)
            VALUES ($1, $2, $3, $4, false)
            RETURNING id, title, color, sort_order, is_system
            """,
            column_id,
            title,
            color,
            sort_order
        )

        return dict(row)


async def update_funnel_column(
    column_id: str,
    title: Optional[str] = None,
    color: Optional[str] = None,
    sort_order: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Обновить колонку воронки.

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
            UPDATE crm_funnel_columns
            SET {', '.join(updates)}
            WHERE id = $1
            RETURNING id, title, color, sort_order, is_system
            """,
            *params
        )

        return dict(row) if row else None


async def delete_funnel_column(column_id: str) -> bool:
    """
    Удалить кастомную колонку воронки.

    Системные колонки (is_system = true) удалить нельзя.
    Клиенты в удалённой колонке будут перемещены в 'new'.

    Returns:
        True если удалено, False если колонка системная или не найдена
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Проверяем что колонка не системная
            is_system = await conn.fetchval(
                "SELECT is_system FROM crm_funnel_columns WHERE id = $1",
                column_id
            )

            if is_system is None:
                return False  # Колонка не найдена

            if is_system:
                logger.warning(f"Cannot delete system column: {column_id}")
                return False

            # Переносим клиентов в 'new'
            await conn.execute(
                """
                UPDATE client_funnel_status
                SET status = 'new', manual_override = true
                WHERE status = $1
                """,
                column_id
            )

            # Удаляем колонку
            result = await conn.execute(
                "DELETE FROM crm_funnel_columns WHERE id = $1 AND is_system = false",
                column_id
            )

            return result == "DELETE 1"


async def reorder_funnel_columns(column_ids: List[str]) -> bool:
    """
    Изменить порядок колонок воронки.

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
                    UPDATE crm_funnel_columns
                    SET sort_order = $2
                    WHERE id = $1
                    """,
                    col_id,
                    idx
                )

    return True


async def get_next_custom_column_id() -> str:
    """
    Получить следующий доступный ID для кастомной колонки.

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
            FROM crm_funnel_columns
            WHERE id LIKE 'custom_%'
            """
        )

        next_num = (max_num or 0) + 1
        return f"custom_{next_num}"


async def set_initial_source(user_id: int, source: str) -> bool:
    """
    Установить источник привлечения клиента только если он ещё не задан.

    Сохраняет первый источник, не перезаписывает при повторных переходах.

    Args:
        user_id: ID пользователя в таблице users
        source: Название источника (например "Сайт")

    Returns:
        True если источник был установлен, False если уже был задан
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        # Сначала убедимся что запись существует
        await ensure_client_status(user_id, conn=conn)

        # Обновляем только если source IS NULL или пустой
        result = await conn.execute(
            """
            UPDATE client_funnel_status
            SET source = $2, updated_at = NOW()
            WHERE user_id = $1 AND (source IS NULL OR source = '')
            """,
            user_id, source
        )

        updated = "UPDATE 1" in result
        if updated:
            logger.info(f"Set initial source '{source}' for user {user_id}")

        return updated
