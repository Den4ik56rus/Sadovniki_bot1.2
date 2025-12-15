# src/api/handlers/buyers.py
"""
API handlers для Покупателей: Kanban-доска, карточки покупателей.
"""

import json
import logging
from decimal import Decimal
from aiohttp import web

from src.services.db import buyer_repo
from src.services.db import consultation_logs_repo
from src.services.db import client_crm_repo

logger = logging.getLogger(__name__)


def _serialize_value(value):
    """Serialize special types for JSON."""
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


# =============================================================================
# Покупатели - Kanban
# =============================================================================

async def get_buyers(request: web.Request) -> web.Response:
    """
    GET /api/admin/buyers
    Получить всех покупателей сгруппированных по статусу для Kanban.

    Returns:
        {
            "buyers": {
                "pending_payment": [...],
                "paid": [...],
                "active": [...],
                "expired": [...]
            },
            "stats": {
                "pending_payment": 10,
                "paid": 25,
                ...
            }
        }
    """
    try:
        grouped = await buyer_repo.get_buyers_grouped_by_status()
        stats = await buyer_repo.get_buyer_stats()

        # Сериализация datetime и Decimal
        for status, buyers in grouped.items():
            grouped[status] = [_serialize_dict(b) for b in buyers]

        return web.json_response({
            "buyers": grouped,
            "stats": stats
        })

    except Exception as e:
        logger.error(f"Error getting buyers: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_buyer(request: web.Request) -> web.Response:
    """
    GET /api/admin/buyers/{id}
    Получить полную информацию о покупателе.

    Path params:
        id: int (user_id)
    """
    try:
        user_id = int(request.match_info["id"])

        buyer = await buyer_repo.get_buyer_by_id(user_id)

        if not buyer:
            raise web.HTTPNotFound(text="Buyer not found")

        return web.json_response(_serialize_dict(buyer))

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid buyer ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error getting buyer: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def update_buyer_status(request: web.Request) -> web.Response:
    """
    PATCH /api/admin/buyers/{id}/status
    Обновить статус покупателя (drag-and-drop).

    Path params:
        id: int (user_id)

    Body:
        {"status": "pending_payment" | "paid" | "active" | "expired" | "custom_*"}
    """
    try:
        user_id = int(request.match_info["id"])
        body = await request.json()

        new_status = body.get("status")
        if not new_status:
            raise web.HTTPBadRequest(text="Missing 'status' field")

        success = await buyer_repo.update_buyer_status(user_id, new_status)

        if not success:
            raise web.HTTPNotFound(text="Buyer not found or invalid status")

        return web.json_response({"success": True, "status": new_status})

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid buyer ID")
    except web.HTTPBadRequest:
        raise
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error updating buyer status: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_buyer_topics(request: web.Request) -> web.Response:
    """
    GET /api/admin/buyers/{id}/topics
    Получить топики покупателя для вкладки "Консультации".

    Path params:
        id: int (user_id)

    Query params:
        limit: int (default 50)
        offset: int (default 0)
    """
    try:
        user_id = int(request.match_info["id"])
        limit = int(request.query.get("limit", 50))
        offset = int(request.query.get("offset", 0))

        topics = await consultation_logs_repo.get_topics_by_user(
            user_id=user_id,
            limit=limit,
            offset=offset,
        )

        return web.json_response(topics)

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid parameter")
    except Exception as e:
        logger.error(f"Error getting buyer topics: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_buyer_stats(request: web.Request) -> web.Response:
    """
    GET /api/admin/buyers/stats
    Получить статистику покупателей.

    Returns:
        {"pending_payment": 10, "paid": 25, "active": 5, "expired": 3}
    """
    try:
        stats = await buyer_repo.get_buyer_stats()
        return web.json_response(stats)

    except Exception as e:
        logger.error(f"Error getting buyer stats: {e}")
        raise web.HTTPInternalServerError(text="Database error")


# =============================================================================
# Расширенная карточка покупателя (переиспользуем CRM функции)
# =============================================================================

async def get_buyer_full(request: web.Request) -> web.Response:
    """
    GET /api/admin/buyers/{id}/full
    Получить полные данные покупателя включая теги и кастомные поля.
    """
    try:
        user_id = int(request.match_info["id"])

        # Проверяем что это покупатель
        buyer = await buyer_repo.get_buyer_by_id(user_id)
        if not buyer:
            raise web.HTTPNotFound(text="Buyer not found")

        # Получаем расширенные данные через CRM repo
        client = await client_crm_repo.get_client_full_data(user_id)

        if not client:
            raise web.HTTPNotFound(text="Buyer not found")

        # Добавляем buyer-специфичные поля
        client['buyer_status'] = buyer['status']
        client['buyer_created_at'] = buyer.get('buyer_created_at')

        return web.json_response(_serialize_dict(client))

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid buyer ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error getting full buyer data: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_buyer_activity(request: web.Request) -> web.Response:
    """
    GET /api/admin/buyers/{id}/activity
    Получить ленту активности покупателя.

    Query:
        types: comma-separated (consultation,task_created,task_completed,note,status_change,tag_change,buyer_status_change)
        limit: int (default 50)
        offset: int (default 0)
    """
    try:
        user_id = int(request.match_info["id"])
        limit = int(request.query.get("limit", 50))
        offset = int(request.query.get("offset", 0))

        # Parse event types filter
        types_str = request.query.get("types")
        event_types = types_str.split(",") if types_str else None

        activity = await client_crm_repo.get_client_activity_with_consultations(
            user_id=user_id,
            event_types=event_types,
            limit=limit,
            offset=offset
        )

        return web.json_response([_serialize_dict(a) for a in activity])

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid parameters")
    except Exception as e:
        logger.error(f"Error getting buyer activity: {e}")
        raise web.HTTPInternalServerError(text="Database error")


# =============================================================================
# Колонки покупателей (Kanban columns)
# =============================================================================

async def get_buyer_columns(request: web.Request) -> web.Response:
    """
    GET /api/admin/buyers/columns
    Получить все колонки покупателей отсортированные по порядку.

    Returns: [
        {"id": "pending_payment", "title": "Ожидает оплаты", "color": "#F59E0B", "sort_order": 0, "is_system": true},
        {"id": "custom_1", "title": "МОЯ КОЛОНКА", "color": "#EF4444", "sort_order": 4, "is_system": false},
        ...
    ]
    """
    try:
        columns = await buyer_repo.get_buyer_columns()
        return web.json_response([_serialize_dict(c) for c in columns])

    except Exception as e:
        logger.error(f"Error getting buyer columns: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def create_buyer_column(request: web.Request) -> web.Response:
    """
    POST /api/admin/buyers/columns
    Создать новую кастомную колонку.

    Body: {
        "title": "string",
        "color": "#RRGGBB",
        "after_id": "paid"  // ID колонки после которой вставить (опционально)
    }

    Returns: созданная колонка
    """
    try:
        body = await request.json()

        title = body.get("title", "НОВЫЙ ЭТАП")
        color = body.get("color", "#6B7280")
        after_id = body.get("after_id")

        # Получаем следующий ID
        column_id = await buyer_repo.get_next_buyer_column_id()

        # Определяем sort_order
        columns = await buyer_repo.get_buyer_columns()
        if after_id:
            # Вставляем после указанной колонки
            after_idx = next((i for i, c in enumerate(columns) if c['id'] == after_id), len(columns) - 1)
            sort_order = after_idx + 1
            # Сдвигаем все последующие колонки
            for c in columns[sort_order:]:
                await buyer_repo.update_buyer_column(c['id'], sort_order=c['sort_order'] + 1)
        else:
            # Добавляем в конец
            sort_order = len(columns)

        column = await buyer_repo.create_buyer_column(
            column_id=column_id,
            title=title,
            color=color,
            sort_order=sort_order
        )

        return web.json_response(_serialize_dict(column), status=201)

    except Exception as e:
        logger.error(f"Error creating buyer column: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def update_buyer_column(request: web.Request) -> web.Response:
    """
    PUT /api/admin/buyers/columns/{id}
    Обновить колонку покупателей.

    Body: {
        "title": "string",
        "color": "#RRGGBB"
    }
    """
    try:
        column_id = request.match_info["id"]
        body = await request.json()

        column = await buyer_repo.update_buyer_column(
            column_id=column_id,
            title=body.get("title"),
            color=body.get("color"),
            sort_order=body.get("sort_order")
        )

        if not column:
            raise web.HTTPNotFound(text="Column not found")

        return web.json_response(_serialize_dict(column))

    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error updating buyer column: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def delete_buyer_column(request: web.Request) -> web.Response:
    """
    DELETE /api/admin/buyers/columns/{id}
    Удалить кастомную колонку.

    Системные колонки (pending_payment, paid, active, expired) удалить нельзя.
    Покупатели из удаляемой колонки перемещаются в 'pending_payment'.
    """
    try:
        column_id = request.match_info["id"]

        success = await buyer_repo.delete_buyer_column(column_id)

        if not success:
            raise web.HTTPBadRequest(text="Cannot delete system column or column not found")

        return web.json_response({"success": True})

    except web.HTTPBadRequest:
        raise
    except Exception as e:
        logger.error(f"Error deleting buyer column: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def reorder_buyer_columns(request: web.Request) -> web.Response:
    """
    PUT /api/admin/buyers/columns/reorder
    Изменить порядок колонок покупателей.

    Body: {
        "column_ids": ["pending_payment", "paid", "custom_1", "active", "expired"]
    }
    """
    try:
        body = await request.json()
        column_ids = body.get("column_ids", [])

        if not column_ids:
            raise web.HTTPBadRequest(text="Missing column_ids")

        await buyer_repo.reorder_buyer_columns(column_ids)

        return web.json_response({"success": True})

    except web.HTTPBadRequest:
        raise
    except Exception as e:
        logger.error(f"Error reordering buyer columns: {e}")
        raise web.HTTPInternalServerError(text="Database error")
