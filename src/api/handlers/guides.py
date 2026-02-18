# src/api/handlers/guides.py

"""
API handlers для управления гайдами (Готовые решения) в админ-панели.

Endpoints:
    GET /api/admin/guides           — список заказов (пагинация, фильтр по статусу)
    GET /api/admin/guides/stats     — агрегированная статистика
    GET /api/admin/guides/{id}      — детали одного заказа + посекционные затраты
"""

import json
import logging
from datetime import datetime
from decimal import Decimal
from aiohttp import web

from src.services.db import guide_repo

logger = logging.getLogger(__name__)


def _serialize_value(value):
    """Конвертирует специальные типы для JSON."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str):
        # Попробовать распарсить JSONB-строки
        try:
            if value.startswith('{') or value.startswith('['):
                return json.loads(value)
        except (json.JSONDecodeError, AttributeError):
            pass
    return value


def _serialize_dict(d: dict) -> dict:
    return {k: _serialize_value(v) for k, v in d.items()}


async def get_guides(request: web.Request) -> web.Response:
    """GET /api/admin/guides — список заказов."""
    try:
        limit = int(request.query.get('limit', '50'))
        offset = int(request.query.get('offset', '0'))
        status = request.query.get('status')

        orders, total = await guide_repo.get_all_orders(
            limit=limit, offset=offset, status=status or None,
        )

        return web.json_response({
            'orders': [_serialize_dict(o) for o in orders],
            'total': total,
            'limit': limit,
            'offset': offset,
        })
    except Exception as e:
        logger.error(f'Error getting guides: {e}', exc_info=True)
        return web.json_response({'error': str(e)}, status=500)


async def get_guide_stats(request: web.Request) -> web.Response:
    """GET /api/admin/guides/stats — агрегированная статистика."""
    try:
        stats = await guide_repo.get_guide_stats()
        return web.json_response(stats)
    except Exception as e:
        logger.error(f'Error getting guide stats: {e}', exc_info=True)
        return web.json_response({'error': str(e)}, status=500)


async def get_guide_detail(request: web.Request) -> web.Response:
    """GET /api/admin/guides/{id} — детали заказа."""
    try:
        order_id = int(request.match_info['id'])
        order = await guide_repo.get_by_id(order_id)
        if not order:
            return web.json_response({'error': 'Заказ не найден'}, status=404)

        return web.json_response(_serialize_dict(order))
    except Exception as e:
        logger.error(f'Error getting guide detail: {e}', exc_info=True)
        return web.json_response({'error': str(e)}, status=500)
