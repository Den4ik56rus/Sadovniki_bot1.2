# src/services/db/expense_repo.py

"""
Репозиторий для работы с расходами проекта.

Функции:
    - get_expenses: Список расходов с фильтрацией
    - get_expense_by_id: Один расход по ID
    - create_expense: Создать расход
    - update_expense: Обновить расход
    - delete_expense: Удалить расход
    - get_expense_stats: Статистика (общая сумма, по категориям, по плательщикам)
    - get_expense_categories: Список категорий
    - create_expense_category: Создать категорию
    - delete_expense_category: Удалить категорию (только не-system)
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Optional, List, Dict, Any

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


# =============================================================================
# Expenses CRUD
# =============================================================================

async def get_expenses(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    category_id: Optional[int] = None,
    paid_by: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> Dict[str, Any]:
    """
    Получить список расходов с фильтрацией.

    Args:
        start_date: Начало периода (включительно)
        end_date: Конец периода (включительно)
        category_id: Фильтр по категории
        paid_by: Фильтр по плательщику ('Денис' или 'Данил')
        limit: Лимит записей
        offset: Смещение для пагинации

    Returns:
        {
            "expenses": [...],
            "total": int,
            "limit": int,
            "offset": int
        }
    """
    pool = get_pool()

    # Собираем условия WHERE
    conditions = []
    params = []
    param_idx = 1

    if start_date:
        conditions.append(f"e.date >= ${param_idx}")
        params.append(start_date)
        param_idx += 1

    if end_date:
        conditions.append(f"e.date <= ${param_idx}")
        params.append(end_date)
        param_idx += 1

    if category_id:
        conditions.append(f"e.category_id = ${param_idx}")
        params.append(category_id)
        param_idx += 1

    if paid_by:
        conditions.append(f"e.paid_by = ${param_idx}")
        params.append(paid_by)
        param_idx += 1

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with pool.acquire() as conn:
        # Получаем общее количество
        count_query = f"""
            SELECT COUNT(*)::int as total
            FROM expenses e
            {where_clause}
        """
        total = await conn.fetchval(count_query, *params)

        # Получаем записи
        params.append(limit)
        params.append(offset)

        query = f"""
            SELECT
                e.id,
                e.date,
                e.name,
                e.category_id,
                ec.name as category_name,
                ec.color as category_color,
                ec.icon as category_icon,
                e.amount,
                e.paid_by,
                e.created_at,
                e.updated_at
            FROM expenses e
            LEFT JOIN expense_categories ec ON ec.id = e.category_id
            {where_clause}
            ORDER BY e.date DESC, e.created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """

        rows = await conn.fetch(query, *params)

        return {
            "expenses": [dict(row) for row in rows],
            "total": total or 0,
            "limit": limit,
            "offset": offset
        }


async def get_expense_by_id(expense_id: int) -> Optional[Dict[str, Any]]:
    """Получить расход по ID."""
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                e.id,
                e.date,
                e.name,
                e.category_id,
                ec.name as category_name,
                ec.color as category_color,
                ec.icon as category_icon,
                e.amount,
                e.paid_by,
                e.created_at,
                e.updated_at
            FROM expenses e
            LEFT JOIN expense_categories ec ON ec.id = e.category_id
            WHERE e.id = $1
            """,
            expense_id
        )

        return dict(row) if row else None


async def create_expense(
    expense_date: date,
    name: str,
    category_id: int,
    amount: Decimal,
    paid_by: str
) -> Dict[str, Any]:
    """
    Создать новый расход.

    Args:
        expense_date: Дата расхода
        name: Название/описание
        category_id: ID категории
        amount: Сумма в рублях
        paid_by: Кто оплатил ('Денис' или 'Данил')

    Returns:
        Созданный расход с данными категории
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO expenses (date, name, category_id, amount, paid_by)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, date, name, category_id, amount, paid_by, created_at, updated_at
            """,
            expense_date,
            name,
            category_id,
            amount,
            paid_by
        )

        expense = dict(row)

        # Получаем данные категории
        category = await conn.fetchrow(
            "SELECT name, color, icon FROM expense_categories WHERE id = $1",
            category_id
        )

        if category:
            expense['category_name'] = category['name']
            expense['category_color'] = category['color']
            expense['category_icon'] = category['icon']

        return expense


async def update_expense(
    expense_id: int,
    expense_date: Optional[date] = None,
    name: Optional[str] = None,
    category_id: Optional[int] = None,
    amount: Optional[Decimal] = None,
    paid_by: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Обновить расход.

    Returns:
        Обновлённый расход или None если не найден
    """
    pool = get_pool()

    # Собираем поля для обновления
    updates = []
    params = [expense_id]
    param_idx = 2

    if expense_date is not None:
        updates.append(f"date = ${param_idx}")
        params.append(expense_date)
        param_idx += 1

    if name is not None:
        updates.append(f"name = ${param_idx}")
        params.append(name)
        param_idx += 1

    if category_id is not None:
        updates.append(f"category_id = ${param_idx}")
        params.append(category_id)
        param_idx += 1

    if amount is not None:
        updates.append(f"amount = ${param_idx}")
        params.append(amount)
        param_idx += 1

    if paid_by is not None:
        updates.append(f"paid_by = ${param_idx}")
        params.append(paid_by)
        param_idx += 1

    if not updates:
        return await get_expense_by_id(expense_id)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE expenses
            SET {', '.join(updates)}
            WHERE id = $1
            RETURNING id, date, name, category_id, amount, paid_by, created_at, updated_at
            """,
            *params
        )

        if not row:
            return None

        expense = dict(row)

        # Получаем данные категории
        if expense.get('category_id'):
            category = await conn.fetchrow(
                "SELECT name, color, icon FROM expense_categories WHERE id = $1",
                expense['category_id']
            )
            if category:
                expense['category_name'] = category['name']
                expense['category_color'] = category['color']
                expense['category_icon'] = category['icon']

        return expense


async def delete_expense(expense_id: int) -> bool:
    """
    Удалить расход.

    Returns:
        True если удалено, False если не найдено
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM expenses WHERE id = $1",
            expense_id
        )

        return result == "DELETE 1"


# =============================================================================
# Статистика
# =============================================================================

async def get_expense_stats(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> Dict[str, Any]:
    """
    Получить статистику расходов за период.

    Args:
        start_date: Начало периода
        end_date: Конец периода

    Returns:
        {
            "total_amount": float,
            "by_category": [{"category_id": int, "category_name": str, "color": str, "amount": float, "count": int}, ...],
            "by_paid_by": [{"paid_by": str, "amount": float, "count": int}, ...]
        }
    """
    pool = get_pool()

    # Собираем условия WHERE
    conditions = []
    params = []
    param_idx = 1

    if start_date:
        conditions.append(f"e.date >= ${param_idx}")
        params.append(start_date)
        param_idx += 1

    if end_date:
        conditions.append(f"e.date <= ${param_idx}")
        params.append(end_date)
        param_idx += 1

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with pool.acquire() as conn:
        # Общая сумма
        total_query = f"""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM expenses e
            {where_clause}
        """
        total_amount = await conn.fetchval(total_query, *params)

        # По категориям
        by_category_query = f"""
            SELECT
                e.category_id,
                ec.name as category_name,
                ec.color,
                SUM(e.amount) as amount,
                COUNT(*)::int as count
            FROM expenses e
            LEFT JOIN expense_categories ec ON ec.id = e.category_id
            {where_clause}
            GROUP BY e.category_id, ec.name, ec.color
            ORDER BY amount DESC
        """
        by_category_rows = await conn.fetch(by_category_query, *params)

        # По плательщикам (записи с 'Оба' делятся пополам между Денисом и Данилом)
        # Простой подход: получаем сырые данные и обрабатываем в Python
        by_paid_by_query = f"""
            SELECT
                paid_by,
                SUM(amount) as amount,
                COUNT(*)::int as count
            FROM expenses e
            {where_clause}
            GROUP BY paid_by
            ORDER BY amount DESC
        """
        by_paid_by_rows = await conn.fetch(by_paid_by_query, *params)

        # Обрабатываем 'Оба' - делим пополам между Денисом и Данилом
        result_by_paid_by = {}
        for row in by_paid_by_rows:
            paid_by = row['paid_by']
            amount = float(row['amount']) if row['amount'] else 0.0
            count = row['count']

            if paid_by == 'Оба':
                # Делим пополам
                half_amount = amount / 2
                if 'Денис' not in result_by_paid_by:
                    result_by_paid_by['Денис'] = {'paid_by': 'Денис', 'amount': 0.0, 'count': 0}
                if 'Данил' not in result_by_paid_by:
                    result_by_paid_by['Данил'] = {'paid_by': 'Данил', 'amount': 0.0, 'count': 0}
                result_by_paid_by['Денис']['amount'] += half_amount
                result_by_paid_by['Денис']['count'] += count
                result_by_paid_by['Данил']['amount'] += half_amount
                result_by_paid_by['Данил']['count'] += count
            else:
                if paid_by not in result_by_paid_by:
                    result_by_paid_by[paid_by] = {'paid_by': paid_by, 'amount': 0.0, 'count': 0}
                result_by_paid_by[paid_by]['amount'] += amount
                result_by_paid_by[paid_by]['count'] += count

        # Сортируем по сумме
        by_paid_by_list = sorted(result_by_paid_by.values(), key=lambda x: x['amount'], reverse=True)

        return {
            "total_amount": float(total_amount) if total_amount else 0.0,
            "by_category": [dict(row) for row in by_category_rows],
            "by_paid_by": by_paid_by_list
        }


# =============================================================================
# Категории расходов
# =============================================================================

async def get_expense_categories() -> List[Dict[str, Any]]:
    """Получить все категории расходов отсортированные по порядку."""
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, color, icon, is_system, sort_order, created_at
            FROM expense_categories
            ORDER BY sort_order ASC
            """
        )

        return [dict(row) for row in rows]


async def create_expense_category(
    name: str,
    color: str = '#6B7280',
    icon: str = 'default'
) -> Dict[str, Any]:
    """
    Создать новую категорию расходов.

    Args:
        name: Название категории
        color: Цвет в формате HEX
        icon: Название иконки

    Returns:
        Созданная категория
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        # Определяем sort_order (в конец)
        max_sort = await conn.fetchval(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM expense_categories"
        )

        row = await conn.fetchrow(
            """
            INSERT INTO expense_categories (name, color, icon, is_system, sort_order)
            VALUES ($1, $2, $3, false, $4)
            RETURNING id, name, color, icon, is_system, sort_order, created_at
            """,
            name,
            color,
            icon,
            max_sort
        )

        return dict(row)


async def update_expense_category(
    category_id: int,
    name: Optional[str] = None,
    color: Optional[str] = None,
    icon: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Обновить категорию расходов.

    Returns:
        Обновлённая категория или None если не найдена
    """
    pool = get_pool()

    updates = []
    params = [category_id]
    param_idx = 2

    if name is not None:
        updates.append(f"name = ${param_idx}")
        params.append(name)
        param_idx += 1

    if color is not None:
        updates.append(f"color = ${param_idx}")
        params.append(color)
        param_idx += 1

    if icon is not None:
        updates.append(f"icon = ${param_idx}")
        params.append(icon)
        param_idx += 1

    if not updates:
        return None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE expense_categories
            SET {', '.join(updates)}
            WHERE id = $1
            RETURNING id, name, color, icon, is_system, sort_order, created_at
            """,
            *params
        )

        return dict(row) if row else None


async def delete_expense_category(category_id: int) -> bool:
    """
    Удалить категорию расходов.

    Системные категории (is_system = true) удалить нельзя.
    Расходы с этой категорией получат category_id = NULL.

    Returns:
        True если удалено, False если категория системная или не найдена
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        # Проверяем что категория не системная
        is_system = await conn.fetchval(
            "SELECT is_system FROM expense_categories WHERE id = $1",
            category_id
        )

        if is_system is None:
            return False  # Категория не найдена

        if is_system:
            logger.warning(f"Cannot delete system expense category: {category_id}")
            return False

        # Удаляем категорию (расходы с ней получат NULL благодаря ON DELETE SET NULL)
        result = await conn.execute(
            "DELETE FROM expense_categories WHERE id = $1 AND is_system = false",
            category_id
        )

        return result == "DELETE 1"
