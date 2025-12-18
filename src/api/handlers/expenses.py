# src/api/handlers/expenses.py
"""
API handlers для Расходов: CRUD расходов и категорий, статистика.
"""

import json
import logging
from datetime import date, datetime
from decimal import Decimal
from aiohttp import web

from src.services.db import expense_repo

logger = logging.getLogger(__name__)


def _serialize_value(value):
    """Serialize special types for JSON."""
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str) and value.startswith('[') and value.endswith(']'):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    if isinstance(value, str) and value.startswith('{') and value.endswith('}'):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    return value


def _serialize_dict(d: dict) -> dict:
    """Serialize all values in a dict."""
    return {k: _serialize_value(v) for k, v in d.items()}


def _parse_date(date_str: str) -> date:
    """Parse date string in ISO format (YYYY-MM-DD)."""
    return datetime.strptime(date_str, '%Y-%m-%d').date()


# =============================================================================
# Расходы - CRUD
# =============================================================================

async def get_expenses(request: web.Request) -> web.Response:
    """
    GET /api/admin/expenses
    Получить список расходов с фильтрацией.

    Query params:
        start_date: YYYY-MM-DD
        end_date: YYYY-MM-DD
        category_id: int
        paid_by: string ('Денис' или 'Данил')
        limit: int (default 100)
        offset: int (default 0)

    Returns:
        {
            "expenses": [...],
            "total": int,
            "limit": int,
            "offset": int
        }
    """
    try:
        # Parse query params
        start_date = None
        end_date = None
        category_id = None
        paid_by = None

        if 'start_date' in request.query:
            start_date = _parse_date(request.query['start_date'])

        if 'end_date' in request.query:
            end_date = _parse_date(request.query['end_date'])

        if 'category_id' in request.query:
            category_id = int(request.query['category_id'])

        if 'paid_by' in request.query:
            paid_by = request.query['paid_by']

        limit = int(request.query.get('limit', 100))
        offset = int(request.query.get('offset', 0))

        result = await expense_repo.get_expenses(
            start_date=start_date,
            end_date=end_date,
            category_id=category_id,
            paid_by=paid_by,
            limit=limit,
            offset=offset
        )

        # Serialize expenses
        result['expenses'] = [_serialize_dict(e) for e in result['expenses']]

        return web.json_response(result)

    except ValueError as e:
        raise web.HTTPBadRequest(text=f"Invalid parameter: {e}")
    except Exception as e:
        logger.error(f"Error getting expenses: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_expense(request: web.Request) -> web.Response:
    """
    GET /api/admin/expenses/{id}
    Получить расход по ID.

    Path params:
        id: int
    """
    try:
        expense_id = int(request.match_info["id"])

        expense = await expense_repo.get_expense_by_id(expense_id)

        if not expense:
            raise web.HTTPNotFound(text="Expense not found")

        return web.json_response(_serialize_dict(expense))

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid expense ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error getting expense: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def create_expense(request: web.Request) -> web.Response:
    """
    POST /api/admin/expenses
    Создать новый расход.

    Body:
        {
            "date": "YYYY-MM-DD",
            "name": "string",
            "category_id": int,
            "amount": number,
            "paid_by": "Денис" | "Данил"
        }
    """
    try:
        body = await request.json()

        # Validate required fields
        required = ['date', 'name', 'category_id', 'amount', 'paid_by']
        for field in required:
            if field not in body:
                raise web.HTTPBadRequest(text=f"Missing '{field}' field")

        # Validate paid_by
        if body['paid_by'] not in ['Денис', 'Данил', 'Оба']:
            raise web.HTTPBadRequest(text="paid_by must be 'Денис', 'Данил' or 'Оба'")

        expense = await expense_repo.create_expense(
            expense_date=_parse_date(body['date']),
            name=body['name'],
            category_id=int(body['category_id']),
            amount=Decimal(str(body['amount'])),
            paid_by=body['paid_by']
        )

        return web.json_response(_serialize_dict(expense), status=201)

    except web.HTTPBadRequest:
        raise
    except ValueError as e:
        raise web.HTTPBadRequest(text=f"Invalid value: {e}")
    except Exception as e:
        logger.error(f"Error creating expense: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def update_expense(request: web.Request) -> web.Response:
    """
    PUT /api/admin/expenses/{id}
    Обновить расход.

    Path params:
        id: int

    Body (все поля опциональны):
        {
            "date": "YYYY-MM-DD",
            "name": "string",
            "category_id": int,
            "amount": number,
            "paid_by": "Денис" | "Данил"
        }
    """
    try:
        expense_id = int(request.match_info["id"])
        body = await request.json()

        # Validate paid_by if provided
        if 'paid_by' in body and body['paid_by'] not in ['Денис', 'Данил', 'Оба']:
            raise web.HTTPBadRequest(text="paid_by must be 'Денис', 'Данил' or 'Оба'")

        # Prepare update params
        update_params = {}

        if 'date' in body:
            update_params['expense_date'] = _parse_date(body['date'])

        if 'name' in body:
            update_params['name'] = body['name']

        if 'category_id' in body:
            update_params['category_id'] = int(body['category_id'])

        if 'amount' in body:
            update_params['amount'] = Decimal(str(body['amount']))

        if 'paid_by' in body:
            update_params['paid_by'] = body['paid_by']

        expense = await expense_repo.update_expense(expense_id, **update_params)

        if not expense:
            raise web.HTTPNotFound(text="Expense not found")

        return web.json_response(_serialize_dict(expense))

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid value")
    except web.HTTPBadRequest:
        raise
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error updating expense: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def delete_expense(request: web.Request) -> web.Response:
    """
    DELETE /api/admin/expenses/{id}
    Удалить расход.

    Path params:
        id: int
    """
    try:
        expense_id = int(request.match_info["id"])

        success = await expense_repo.delete_expense(expense_id)

        if not success:
            raise web.HTTPNotFound(text="Expense not found")

        return web.json_response({"success": True})

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid expense ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error deleting expense: {e}")
        raise web.HTTPInternalServerError(text="Database error")


# =============================================================================
# Статистика
# =============================================================================

async def get_expense_stats(request: web.Request) -> web.Response:
    """
    GET /api/admin/expenses/stats
    Получить статистику расходов за период.

    Query params:
        start_date: YYYY-MM-DD
        end_date: YYYY-MM-DD

    Returns:
        {
            "total_amount": float,
            "by_category": [...],
            "by_paid_by": [...]
        }
    """
    try:
        start_date = None
        end_date = None

        if 'start_date' in request.query:
            start_date = _parse_date(request.query['start_date'])

        if 'end_date' in request.query:
            end_date = _parse_date(request.query['end_date'])

        stats = await expense_repo.get_expense_stats(
            start_date=start_date,
            end_date=end_date
        )

        # Serialize Decimal values
        stats['by_category'] = [_serialize_dict(c) for c in stats['by_category']]
        stats['by_paid_by'] = [_serialize_dict(p) for p in stats['by_paid_by']]

        return web.json_response(stats)

    except ValueError as e:
        raise web.HTTPBadRequest(text=f"Invalid date format: {e}")
    except Exception as e:
        logger.error(f"Error getting expense stats: {e}")
        raise web.HTTPInternalServerError(text="Database error")


# =============================================================================
# Категории расходов
# =============================================================================

async def get_expense_categories(request: web.Request) -> web.Response:
    """
    GET /api/admin/expenses/categories
    Получить все категории расходов.

    Returns:
        [
            {"id": 1, "name": "Реклама", "color": "#F59E0B", "is_system": true, ...},
            ...
        ]
    """
    try:
        categories = await expense_repo.get_expense_categories()
        return web.json_response([_serialize_dict(c) for c in categories])

    except Exception as e:
        logger.error(f"Error getting expense categories: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def create_expense_category(request: web.Request) -> web.Response:
    """
    POST /api/admin/expenses/categories
    Создать новую категорию расходов.

    Body:
        {
            "name": "string",
            "color": "#RRGGBB" (optional, default #6B7280)
        }
    """
    try:
        body = await request.json()

        if 'name' not in body:
            raise web.HTTPBadRequest(text="Missing 'name' field")

        category = await expense_repo.create_expense_category(
            name=body['name'],
            color=body.get('color', '#6B7280')
        )

        return web.json_response(_serialize_dict(category), status=201)

    except web.HTTPBadRequest:
        raise
    except Exception as e:
        logger.error(f"Error creating expense category: {e}")
        # Проверяем на дубликат имени
        if 'unique constraint' in str(e).lower() or 'duplicate' in str(e).lower():
            raise web.HTTPBadRequest(text="Category with this name already exists")
        raise web.HTTPInternalServerError(text="Database error")


async def update_expense_category(request: web.Request) -> web.Response:
    """
    PUT /api/admin/expenses/categories/{id}
    Обновить категорию расходов.

    Path params:
        id: int

    Body:
        {
            "name": "string",
            "color": "#RRGGBB"
        }
    """
    try:
        category_id = int(request.match_info["id"])
        body = await request.json()

        category = await expense_repo.update_expense_category(
            category_id=category_id,
            name=body.get('name'),
            color=body.get('color')
        )

        if not category:
            raise web.HTTPNotFound(text="Category not found")

        return web.json_response(_serialize_dict(category))

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid category ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error updating expense category: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def delete_expense_category(request: web.Request) -> web.Response:
    """
    DELETE /api/admin/expenses/categories/{id}
    Удалить категорию расходов.

    Системные категории удалить нельзя.

    Path params:
        id: int
    """
    try:
        category_id = int(request.match_info["id"])

        success = await expense_repo.delete_expense_category(category_id)

        if not success:
            raise web.HTTPBadRequest(text="Cannot delete system category or category not found")

        return web.json_response({"success": True})

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid category ID")
    except web.HTTPBadRequest:
        raise
    except Exception as e:
        logger.error(f"Error deleting expense category: {e}")
        raise web.HTTPInternalServerError(text="Database error")
