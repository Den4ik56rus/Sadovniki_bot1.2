# src/api/server.py
"""
aiohttp API сервер для WebApp календаря.
"""

from aiohttp import web

from src.api.middleware import cors_middleware, telegram_auth_middleware
from src.api.routes import setup_routes


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

    return app
