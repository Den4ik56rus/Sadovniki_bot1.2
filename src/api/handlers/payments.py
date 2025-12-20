# src/api/handlers/payments.py
"""
API handlers для Платежей: получение платежей пользователей и статистики.
"""

import json
import logging
from datetime import date, datetime
from decimal import Decimal
from aiohttp import web

from src.services.db import payment_repo

logger = logging.getLogger(__name__)


def _serialize_value(value):
    """Сериализация специальных типов для JSON."""
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
    """Сериализация всех значений в dict."""
    return {k: _serialize_value(v) for k, v in d.items()}


# =============================================================================
# Платежи пользователя
# =============================================================================

async def get_user_payments(request: web.Request) -> web.Response:
    """
    GET /api/admin/payments/user/{id}
    Получить платежи конкретного пользователя.

    Path params:
        id: user_id

    Query params:
        limit: int (default 50)
        offset: int (default 0)
        status: string ('pending', 'succeeded', 'canceled')

    Returns:
        {
            "payments": [...],
            "total": int,
            "total_paid": float
        }
    """
    try:
        user_id = int(request.match_info['id'])
        limit = int(request.query.get('limit', 50))
        offset = int(request.query.get('offset', 0))
        status = request.query.get('status') if 'status' in request.query else None

        # Получить платежи с деталями
        payments = await payment_repo.get_user_payments_with_details(
            user_id=user_id,
            limit=limit,
            offset=offset,
            status_filter=status,
        )

        # Получить общую сумму оплаченных платежей
        total_paid = await payment_repo.get_user_total_paid(user_id)

        # Сериализация
        payments = [_serialize_dict(p) for p in payments]

        return web.json_response({
            'payments': payments,
            'total': len(payments),
            'total_paid': total_paid,
        })

    except ValueError:
        raise web.HTTPBadRequest(text='Invalid user ID')
    except Exception as e:
        logger.error(f'Error getting user payments: {e}', exc_info=True)
        raise web.HTTPInternalServerError(text='Database error')


# =============================================================================
# Все платежи
# =============================================================================

async def get_all_payments(request: web.Request) -> web.Response:
    """
    GET /api/admin/payments
    Получить все платежи с фильтрацией.

    Query params:
        limit: int (default 50)
        offset: int (default 0)
        status: string ('pending', 'succeeded', 'canceled')
        payment_type: string ('subscription', 'tokens')
        user_id: int

    Returns:
        {
            "payments": [...],
            "total": int
        }
    """
    try:
        limit = int(request.query.get('limit', 50))
        offset = int(request.query.get('offset', 0))
        status = request.query.get('status') if 'status' in request.query else None
        payment_type = request.query.get('payment_type') if 'payment_type' in request.query else None
        user_id = int(request.query['user_id']) if 'user_id' in request.query else None

        # Получить все платежи с фильтрами
        payments = await payment_repo.get_all_payments_with_details(
            limit=limit,
            offset=offset,
            status_filter=status,
            payment_type_filter=payment_type,
            user_id_filter=user_id,
        )

        # Сериализация
        payments = [_serialize_dict(p) for p in payments]

        return web.json_response({
            'payments': payments,
            'total': len(payments),
        })

    except ValueError:
        raise web.HTTPBadRequest(text='Invalid parameters')
    except Exception as e:
        logger.error(f'Error getting all payments: {e}', exc_info=True)
        raise web.HTTPInternalServerError(text='Database error')


# =============================================================================
# Статистика платежей
# =============================================================================

async def get_payment_stats(request: web.Request) -> web.Response:
    """
    GET /api/admin/payments/stats
    Получить статистику по платежам.

    Query params:
        period: string ('day', 'week', 'month', 'all')

    Returns:
        {
            "total_count": int,
            "total_amount": float,
            "paid_amount": float,
            "pending_amount": float,
            "by_type": {...},
            "by_status": {...}
        }
    """
    try:
        period = request.query.get('period', 'all')

        stats = await payment_repo.get_payment_statistics(period=period if period != 'all' else None)

        return web.json_response(stats)

    except Exception as e:
        logger.error(f'Error getting payment stats: {e}', exc_info=True)
        raise web.HTTPInternalServerError(text='Database error')
