# src/api/handlers/funnels.py

"""
API handlers для универсальной системы воронок.

Endpoints:
    GET    /api/admin/funnels                           — список воронок
    POST   /api/admin/funnels                           — создать воронку
    GET    /api/admin/funnels/{id}                      — получить воронку
    PUT    /api/admin/funnels/{id}                      — обновить воронку
    DELETE /api/admin/funnels/{id}                      — удалить воронку
    PUT    /api/admin/funnels/reorder                   — переставить воронки

    GET    /api/admin/funnels/{id}/stages               — этапы воронки
    POST   /api/admin/funnels/{id}/stages               — создать этап
    PUT    /api/admin/funnels/{id}/stages/{key}         — обновить этап
    DELETE /api/admin/funnels/{id}/stages/{key}         — удалить этап
    PUT    /api/admin/funnels/{id}/stages/reorder       — переставить этапы

    GET    /api/admin/funnels/{id}/clients              — клиенты в воронке
    GET    /api/admin/funnels/{id}/stats                — статистика воронки
    PATCH  /api/admin/funnels/{id}/clients/{uid}/stage  — переместить клиента
    POST   /api/admin/funnels/{id}/clients/{uid}/transfer — перенести в другую воронку
    POST   /api/admin/funnels/{id}/clients/{uid}        — добавить клиента
    DELETE /api/admin/funnels/{id}/clients/{uid}        — убрать клиента
"""

import logging
from aiohttp import web

from src.services.db import funnel_repo

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ВОРОНКИ
# ═══════════════════════════════════════════════════════════════════════════════

async def get_funnels(request: web.Request) -> web.Response:
    """Получить список всех воронок."""
    try:
        funnels = await funnel_repo.get_funnels()
        return web.json_response({"funnels": funnels})
    except Exception as e:
        logger.error(f"Error getting funnels: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def get_funnel(request: web.Request) -> web.Response:
    """Получить воронку по ID."""
    funnel_id = request.match_info.get("id")

    try:
        funnel = await funnel_repo.get_funnel_by_id(funnel_id)
        if not funnel:
            return web.json_response({"error": "Funnel not found"}, status=404)
        return web.json_response(funnel)
    except Exception as e:
        logger.error(f"Error getting funnel {funnel_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def create_funnel(request: web.Request) -> web.Response:
    """Создать новую воронку."""
    try:
        data = await request.json()

        funnel_id = data.get("id")
        title = data.get("title")
        description = data.get("description")
        icon = data.get("icon", "deals")
        stages = data.get("stages", [])

        if not funnel_id or not title:
            return web.json_response(
                {"error": "id and title are required"},
                status=400
            )

        # Проверяем что ID уникален
        existing = await funnel_repo.get_funnel_by_id(funnel_id)
        if existing:
            return web.json_response(
                {"error": f"Funnel with id '{funnel_id}' already exists"},
                status=400
            )

        funnel = await funnel_repo.create_funnel(
            funnel_id=funnel_id,
            title=title,
            description=description,
            icon=icon,
            stages=stages
        )

        return web.json_response(funnel, status=201)
    except Exception as e:
        logger.error(f"Error creating funnel: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def update_funnel(request: web.Request) -> web.Response:
    """Обновить воронку."""
    funnel_id = request.match_info.get("id")

    try:
        data = await request.json()

        funnel = await funnel_repo.update_funnel(
            funnel_id=funnel_id,
            title=data.get("title"),
            description=data.get("description"),
            icon=data.get("icon")
        )

        if not funnel:
            return web.json_response({"error": "Funnel not found"}, status=404)

        return web.json_response(funnel)
    except Exception as e:
        logger.error(f"Error updating funnel {funnel_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def delete_funnel(request: web.Request) -> web.Response:
    """Удалить воронку."""
    funnel_id = request.match_info.get("id")

    try:
        success = await funnel_repo.delete_funnel(funnel_id)

        if not success:
            return web.json_response(
                {"error": "Cannot delete system funnel or funnel not found"},
                status=400
            )

        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error deleting funnel {funnel_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def reorder_funnels(request: web.Request) -> web.Response:
    """Изменить порядок воронок."""
    try:
        data = await request.json()
        funnel_ids = data.get("funnel_ids", [])

        if not funnel_ids:
            return web.json_response(
                {"error": "funnel_ids array is required"},
                status=400
            )

        await funnel_repo.reorder_funnels(funnel_ids)
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error reordering funnels: {e}")
        return web.json_response({"error": str(e)}, status=500)


# ═══════════════════════════════════════════════════════════════════════════════
# ЭТАПЫ ВОРОНКИ
# ═══════════════════════════════════════════════════════════════════════════════

async def get_funnel_stages(request: web.Request) -> web.Response:
    """Получить этапы воронки."""
    funnel_id = request.match_info.get("id")

    try:
        stages = await funnel_repo.get_funnel_stages(funnel_id)
        return web.json_response({"stages": stages})
    except Exception as e:
        logger.error(f"Error getting stages for funnel {funnel_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def create_funnel_stage(request: web.Request) -> web.Response:
    """Создать новый этап воронки."""
    funnel_id = request.match_info.get("id")

    try:
        data = await request.json()

        stage_key = data.get("stage_key")
        title = data.get("title")
        color = data.get("color", "#6B7280")

        # Если stage_key не указан, генерируем
        if not stage_key:
            stage_key = await funnel_repo.get_next_stage_key(funnel_id)

        if not title:
            return web.json_response(
                {"error": "title is required"},
                status=400
            )

        stage = await funnel_repo.create_stage(
            funnel_id=funnel_id,
            stage_key=stage_key,
            title=title,
            color=color
        )

        return web.json_response(stage, status=201)
    except Exception as e:
        logger.error(f"Error creating stage for funnel {funnel_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def update_funnel_stage(request: web.Request) -> web.Response:
    """Обновить этап воронки."""
    funnel_id = request.match_info.get("id")
    stage_key = request.match_info.get("key")

    try:
        data = await request.json()

        stage = await funnel_repo.update_stage(
            funnel_id=funnel_id,
            stage_key=stage_key,
            title=data.get("title"),
            color=data.get("color")
        )

        if not stage:
            return web.json_response({"error": "Stage not found"}, status=404)

        return web.json_response(stage)
    except Exception as e:
        logger.error(f"Error updating stage {funnel_id}/{stage_key}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def delete_funnel_stage(request: web.Request) -> web.Response:
    """Удалить этап воронки."""
    funnel_id = request.match_info.get("id")
    stage_key = request.match_info.get("key")

    try:
        success = await funnel_repo.delete_stage(funnel_id, stage_key)

        if not success:
            return web.json_response(
                {"error": "Cannot delete system stage or stage not found"},
                status=400
            )

        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error deleting stage {funnel_id}/{stage_key}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def reorder_funnel_stages(request: web.Request) -> web.Response:
    """Изменить порядок этапов воронки."""
    funnel_id = request.match_info.get("id")

    try:
        data = await request.json()
        stage_keys = data.get("stage_keys", [])

        if not stage_keys:
            return web.json_response(
                {"error": "stage_keys array is required"},
                status=400
            )

        await funnel_repo.reorder_stages(funnel_id, stage_keys)
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error reordering stages for funnel {funnel_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)


# ═══════════════════════════════════════════════════════════════════════════════
# КЛИЕНТЫ В ВОРОНКЕ
# ═══════════════════════════════════════════════════════════════════════════════

async def get_funnel_clients(request: web.Request) -> web.Response:
    """
    Получить клиентов в воронке, сгруппированных по этапам.

    Формат ответа:
    {
        "clients": {
            "new": [...],
            "tried": [...]
        },
        "stats": {
            "new": 10,
            "tried": 5
        }
    }
    """
    funnel_id = request.match_info.get("id")

    try:
        clients = await funnel_repo.get_clients_in_funnel(funnel_id)
        stats = await funnel_repo.get_funnel_stats(funnel_id)

        return web.json_response({
            "clients": clients,
            "stats": stats
        })
    except Exception as e:
        logger.error(f"Error getting clients for funnel {funnel_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def get_funnel_stats(request: web.Request) -> web.Response:
    """Получить статистику воронки."""
    funnel_id = request.match_info.get("id")

    try:
        stats = await funnel_repo.get_funnel_stats(funnel_id)
        return web.json_response({"stats": stats})
    except Exception as e:
        logger.error(f"Error getting stats for funnel {funnel_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def move_client_stage(request: web.Request) -> web.Response:
    """
    Переместить клиента на другой этап внутри воронки.

    Body: { "stage_key": "tried" }
    """
    funnel_id = request.match_info.get("id")
    user_id = int(request.match_info.get("uid"))

    try:
        data = await request.json()
        stage_key = data.get("stage_key")

        if not stage_key:
            return web.json_response(
                {"error": "stage_key is required"},
                status=400
            )

        success = await funnel_repo.move_client_to_stage(
            user_id=user_id,
            funnel_id=funnel_id,
            new_stage_key=stage_key
        )

        if not success:
            return web.json_response(
                {"error": "Client not found in funnel or invalid stage"},
                status=400
            )

        return web.json_response({"success": True, "stage_key": stage_key})
    except Exception as e:
        logger.error(f"Error moving client {user_id} in funnel {funnel_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def transfer_client(request: web.Request) -> web.Response:
    """
    Перенести клиента в другую воронку.

    Body: {
        "to_funnel_id": "buyers",
        "to_stage_key": "pending_payment"  // опционально
    }
    """
    from_funnel_id = request.match_info.get("id")
    user_id = int(request.match_info.get("uid"))

    try:
        data = await request.json()
        to_funnel_id = data.get("to_funnel_id")
        to_stage_key = data.get("to_stage_key")

        if not to_funnel_id:
            return web.json_response(
                {"error": "to_funnel_id is required"},
                status=400
            )

        success = await funnel_repo.transfer_client(
            user_id=user_id,
            from_funnel_id=from_funnel_id,
            to_funnel_id=to_funnel_id,
            to_stage_key=to_stage_key
        )

        if not success:
            return web.json_response(
                {"error": "Transfer failed"},
                status=400
            )

        return web.json_response({
            "success": True,
            "to_funnel_id": to_funnel_id,
            "to_stage_key": to_stage_key
        })
    except Exception as e:
        logger.error(f"Error transferring client {user_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def add_client_to_funnel(request: web.Request) -> web.Response:
    """
    Добавить клиента в воронку.

    Body: { "stage_key": "new" }  // опционально
    """
    funnel_id = request.match_info.get("id")
    user_id = int(request.match_info.get("uid"))

    try:
        data = await request.json()
        stage_key = data.get("stage_key")

        success = await funnel_repo.add_client_to_funnel(
            user_id=user_id,
            funnel_id=funnel_id,
            stage_key=stage_key
        )

        if not success:
            return web.json_response(
                {"error": "Failed to add client to funnel"},
                status=400
            )

        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error adding client {user_id} to funnel {funnel_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def remove_client_from_funnel(request: web.Request) -> web.Response:
    """Убрать клиента из воронки."""
    funnel_id = request.match_info.get("id")
    user_id = int(request.match_info.get("uid"))

    try:
        success = await funnel_repo.remove_client_from_funnel(user_id, funnel_id)

        if not success:
            return web.json_response(
                {"error": "Client not found in funnel"},
                status=404
            )

        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error removing client {user_id} from funnel {funnel_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def get_client_funnels(request: web.Request) -> web.Response:
    """Получить список воронок, в которых находится клиент."""
    user_id = int(request.match_info.get("uid"))

    try:
        funnels = await funnel_repo.get_client_funnels(user_id)
        return web.json_response({"funnels": funnels})
    except Exception as e:
        logger.error(f"Error getting funnels for client {user_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)
