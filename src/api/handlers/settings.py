# src/api/handlers/settings.py

"""
API handlers для глобальных настроек админ-панели.

Endpoints:
    GET  /api/admin/settings                       — все настройки
    GET  /api/admin/settings/llm                   — LLM-конфигурация (модели + temperature)
    PATCH /api/admin/settings/{key}                — обновить настройку
    GET  /api/admin/settings/pricing/plans         — все планы подписок
    POST /api/admin/settings/pricing/plans         — создать план подписки
    PUT  /api/admin/settings/pricing/plans/{id}    — обновить план подписки
    GET  /api/admin/settings/pricing/packages      — все пакеты токенов
    POST /api/admin/settings/pricing/packages      — создать пакет токенов
    PUT  /api/admin/settings/pricing/packages/{id} — обновить пакет токенов
"""

import logging
from datetime import datetime
from decimal import Decimal
from aiohttp import web

from src.services.db import settings_repo, subscription_plan_repo, token_package_repo
from src.services.db.settings_repo import get_model_for_task, get_temperature_for_task, get_reasoning_effort_for_task
from src.config import settings as env_settings

logger = logging.getLogger(__name__)

# Фиксированный список доступных моделей
AVAILABLE_MODELS = [
    "gpt-5-mini",
    "gpt-5.1",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4.1-mini",
    "o1",
    "o3-mini",
]

# Описание групп задач
TASK_LABELS = {
    "consultation": "Консультации",
    "classification": "Классификация",
    "article": "Статьи",
    "utility": "Утилиты",
}

# Маппинг task → .env атрибут для модели
_ENV_MODEL_MAP = {
    "consultation": "openai_model_consultation",
    "classification": "openai_model_classification",
    "article": "openai_model_article",
    "utility": "openai_model_utility",
}


async def get_settings(request: web.Request) -> web.Response:
    """GET /api/admin/settings — все настройки."""
    try:
        settings_list = await settings_repo.get_all_settings()

        for s in settings_list:
            if s.get("updated_at"):
                s["updated_at"] = s["updated_at"].isoformat()

        return web.json_response({"settings": settings_list})
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def update_setting(request: web.Request) -> web.Response:
    """PATCH /api/admin/settings/{key} — обновить настройку."""
    try:
        key = request.match_info["key"]
        data = await request.json()

        value = data.get("value")
        if value is None:
            return web.json_response({"error": "value is required"}, status=400)

        result = await settings_repo.update_setting(key, str(value))

        if result.get("updated_at"):
            result["updated_at"] = result["updated_at"].isoformat()

        logger.info(f"Setting '{key}' updated to '{value}'")
        return web.json_response({"setting": result, "success": True})
    except Exception as e:
        logger.error(f"Error updating setting {request.match_info.get('key')}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def get_llm_config(request: web.Request) -> web.Response:
    """GET /api/admin/settings/llm — текущая LLM-конфигурация."""
    try:
        tasks = {}
        for task, label in TASK_LABELS.items():
            model = await get_model_for_task(task)
            temperature = await get_temperature_for_task(task)
            reasoning_effort = await get_reasoning_effort_for_task(task)
            env_attr = _ENV_MODEL_MAP.get(task, "")
            env_model = getattr(env_settings, env_attr, "") if env_attr else ""
            env_temp = env_settings.openai_temperature

            tasks[task] = {
                "model": model,
                "temperature": temperature,
                "reasoning_effort": reasoning_effort,
                "env_model": env_model,
                "env_temp": env_temp,
                "label": label,
            }

        return web.json_response({
            "models": AVAILABLE_MODELS,
            "tasks": tasks,
        })
    except Exception as e:
        logger.error(f"Error getting LLM config: {e}")
        return web.json_response({"error": str(e)}, status=500)


# =========================================================================
# PRICING — управление тарифами из админ-панели
# =========================================================================

def _serialize_row(row: dict) -> dict:
    """Конвертирует Decimal и datetime поля для JSON-сериализации."""
    result = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            result[k] = float(v)
        elif isinstance(v, datetime):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


async def get_subscription_plans(request: web.Request) -> web.Response:
    """GET /api/admin/settings/pricing/plans — все планы подписок."""
    try:
        plans = await subscription_plan_repo.get_all()
        return web.json_response({"plans": [_serialize_row(p) for p in plans]})
    except Exception as e:
        logger.error(f"Error getting subscription plans: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def create_subscription_plan(request: web.Request) -> web.Response:
    """POST /api/admin/settings/pricing/plans — создать план подписки."""
    try:
        data = await request.json()

        name = data.get("name")
        price_rub = data.get("price_rub")
        tokens_included = data.get("tokens_included")
        duration_days = data.get("duration_days", 30)

        if not name or price_rub is None or tokens_included is None:
            return web.json_response(
                {"error": "name, price_rub, tokens_included обязательны"},
                status=400,
            )

        plan = await subscription_plan_repo.create(
            name=name,
            price_rub=float(price_rub),
            duration_days=int(duration_days),
            tokens_included=int(tokens_included),
            description=data.get("description", ""),
        )

        logger.info(f"Subscription plan created: {name} — {price_rub}₽")
        return web.json_response({"plan": _serialize_row(plan), "success": True})
    except Exception as e:
        logger.error(f"Error creating subscription plan: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def update_subscription_plan(request: web.Request) -> web.Response:
    """PUT /api/admin/settings/pricing/plans/{id} — обновить план подписки."""
    try:
        plan_id = int(request.match_info["id"])
        data = await request.json()

        plan = await subscription_plan_repo.update(plan_id, **data)
        if not plan:
            return web.json_response({"error": "Plan not found or no fields to update"}, status=404)

        logger.info(f"Subscription plan {plan_id} updated: {data}")
        return web.json_response({"plan": _serialize_row(plan), "success": True})
    except Exception as e:
        logger.error(f"Error updating subscription plan {request.match_info.get('id')}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def get_token_packages(request: web.Request) -> web.Response:
    """GET /api/admin/settings/pricing/packages — все пакеты токенов."""
    try:
        packages = await token_package_repo.get_all()
        return web.json_response({"packages": [_serialize_row(p) for p in packages]})
    except Exception as e:
        logger.error(f"Error getting token packages: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def create_token_package(request: web.Request) -> web.Response:
    """POST /api/admin/settings/pricing/packages — создать пакет токенов."""
    try:
        data = await request.json()

        name = data.get("name")
        price_rub = data.get("price_rub")
        tokens_amount = data.get("tokens_amount")

        if not name or price_rub is None or tokens_amount is None:
            return web.json_response(
                {"error": "name, price_rub, tokens_amount обязательны"},
                status=400,
            )

        package = await token_package_repo.create(
            name=name,
            price_rub=float(price_rub),
            tokens_amount=int(tokens_amount),
            description=data.get("description", ""),
        )

        logger.info(f"Token package created: {name} — {price_rub}₽")
        return web.json_response({"package": _serialize_row(package), "success": True})
    except Exception as e:
        logger.error(f"Error creating token package: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def update_token_package(request: web.Request) -> web.Response:
    """PUT /api/admin/settings/pricing/packages/{id} — обновить пакет токенов."""
    try:
        package_id = int(request.match_info["id"])
        data = await request.json()

        package = await token_package_repo.update(package_id, **data)
        if not package:
            return web.json_response({"error": "Package not found or no fields to update"}, status=404)

        logger.info(f"Token package {package_id} updated: {data}")
        return web.json_response({"package": _serialize_row(package), "success": True})
    except Exception as e:
        logger.error(f"Error updating token package {request.match_info.get('id')}: {e}")
        return web.json_response({"error": str(e)}, status=500)
