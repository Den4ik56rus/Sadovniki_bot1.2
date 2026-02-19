# src/api/handlers/openai_balance.py

"""
API handler для мониторинга баланса/расходов OpenAI.

Endpoints:
    GET /api/admin/openai-balance — расходы OpenAI за текущий месяц + остаток бюджета
    PATCH /api/admin/openai-balance/budget — обновить бюджет (сумма пополнения)
"""

import logging
import time
from decimal import Decimal

import aiohttp
from aiohttp import web

from src.config import settings
from src.services.db import settings_repo

logger = logging.getLogger(__name__)

OPENAI_COSTS_URL = "https://api.openai.com/v1/organization/costs"

# Кэш: (timestamp, data)
_cache: dict = {"data": None, "ts": 0}
CACHE_TTL = 300  # 5 минут


async def _fetch_openai_costs(days: int = 30) -> dict:
    """Запросить расходы из OpenAI Costs API."""
    admin_key = settings.openai_admin_key
    if not admin_key:
        return {"error": "OPENAI_ADMIN_KEY не настроен", "costs": []}

    now = int(time.time())

    # Проверяем кэш
    if _cache["data"] and (now - _cache["ts"]) < CACHE_TTL:
        return _cache["data"]

    start_time = now - (days * 24 * 60 * 60)

    headers = {
        "Authorization": f"Bearer {admin_key}",
    }
    params = {
        "start_time": str(start_time),
        "bucket_width": "1d",
        "limit": "31",
    }

    all_buckets = []
    page_cursor = None

    try:
        async with aiohttp.ClientSession() as session:
            while True:
                req_params = dict(params)
                if page_cursor:
                    req_params["page"] = page_cursor

                async with session.get(OPENAI_COSTS_URL, headers=headers, params=req_params) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.error(f"OpenAI Costs API error {resp.status}: {body[:200]}")
                        return {"error": f"OpenAI API вернул {resp.status}", "costs": []}

                    data = await resp.json()
                    all_buckets.extend(data.get("data", []))
                    page_cursor = data.get("next_page")
                    if not page_cursor:
                        break

        # Считаем расходы по дням
        daily_costs = []
        total = Decimal("0")
        for bucket in all_buckets:
            day_total = Decimal("0")
            for result in bucket.get("results", []):
                val = result.get("amount", {}).get("value", "0")
                day_total += Decimal(str(val))
            total += day_total
            daily_costs.append({
                "date": bucket.get("start_time_iso", "")[:10],
                "cost_usd": float(day_total),
            })

        result_data = {
            "total_cost_usd": float(total),
            "daily_costs": daily_costs,
            "days": days,
        }

        # Кэшируем
        _cache["data"] = result_data
        _cache["ts"] = now

        return result_data

    except Exception as e:
        logger.error(f"Error fetching OpenAI costs: {e}")
        return {"error": str(e), "costs": []}


async def get_openai_balance(request: web.Request) -> web.Response:
    """GET /api/admin/openai-balance — расходы + баланс."""
    try:
        days = int(request.query.get("days", 30))

        # Получаем расходы из OpenAI
        costs_data = await _fetch_openai_costs(days)

        # Получаем бюджет из настроек
        budget_setting = await settings_repo.get_setting("openai_budget_usd")
        budget_usd = float(budget_setting) if budget_setting else None

        remaining_usd = None
        if budget_usd is not None and "total_cost_usd" in costs_data:
            remaining_usd = budget_usd - costs_data["total_cost_usd"]

        return web.json_response({
            "total_cost_usd": costs_data.get("total_cost_usd", 0),
            "budget_usd": budget_usd,
            "remaining_usd": remaining_usd,
            "daily_costs": costs_data.get("daily_costs", []),
            "days": days,
            "error": costs_data.get("error"),
            "has_admin_key": bool(settings.openai_admin_key),
        })

    except Exception as e:
        logger.error(f"Error in get_openai_balance: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def update_openai_budget(request: web.Request) -> web.Response:
    """PATCH /api/admin/openai-balance/budget — обновить бюджет."""
    try:
        data = await request.json()
        budget_usd = data.get("budget_usd")

        if budget_usd is None:
            return web.json_response({"error": "budget_usd обязателен"}, status=400)

        await settings_repo.update_setting("openai_budget_usd", str(float(budget_usd)))

        logger.info(f"OpenAI budget updated to ${budget_usd}")
        return web.json_response({"success": True, "budget_usd": float(budget_usd)})

    except Exception as e:
        logger.error(f"Error updating OpenAI budget: {e}")
        return web.json_response({"error": str(e)}, status=500)
