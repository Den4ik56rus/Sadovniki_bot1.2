# src/api/server.py
"""
aiohttp API сервер для WebApp календаря.
"""

from aiohttp import web

from src.api.middleware import cors_middleware, telegram_auth_middleware
from src.api.routes import setup_routes
from src.api.handlers.server_metrics import start_metrics_collector, stop_metrics_collector


async def create_api_app() -> web.Application:
    """
    Создаёт и настраивает aiohttp Application.
    """
    app = web.Application(
        middlewares=[
            cors_middleware,
            telegram_auth_middleware,
        ]
    )

    setup_routes(app)

    # Фоновый сбор метрик сервера (каждые 5 мин)
    app.on_startup.append(start_metrics_collector)
    app.on_cleanup.append(stop_metrics_collector)

    return app
