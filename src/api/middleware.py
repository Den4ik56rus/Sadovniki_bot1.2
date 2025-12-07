# src/api/middleware.py
"""
Middleware для API: CORS и аутентификация через Telegram initData.
"""

import hashlib
import hmac
import json
import logging
from typing import Optional
from urllib.parse import parse_qs, unquote

from aiohttp import web

from src.config import settings
from src.services.db.users_repo import get_or_create_user

logger = logging.getLogger(__name__)


def validate_telegram_init_data(init_data: str, bot_token: str) -> Optional[dict]:
    """
    Валидация initData по алгоритму Telegram:
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

    1. Парсим параметры
    2. Сортируем и формируем data_check_string
    3. Проверяем HMAC-SHA256
    """
    if not init_data:
        return None

    try:
        # Парсим URL-encoded строку
        parsed = parse_qs(init_data)

        # Получаем hash
        hash_value = parsed.get("hash", [None])[0]
        if not hash_value:
            logger.warning("No hash in initData")
            return None

        # Формируем data_check_string (отсортированные пары key=value, кроме hash)
        data_check_pairs = []
        for key in sorted(parsed.keys()):
            if key != "hash":
                # parse_qs возвращает списки, берём первый элемент
                value = parsed[key][0]
                data_check_pairs.append(f"{key}={value}")

        data_check_string = "\n".join(data_check_pairs)

        # Вычисляем secret_key = HMAC-SHA256(bot_token, "WebAppData")
        secret_key = hmac.new(
            b"WebAppData", bot_token.encode(), hashlib.sha256
        ).digest()

        # Вычисляем hash
        computed_hash = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()

        # Сравниваем
        if computed_hash != hash_value:
            logger.warning("Invalid hash in initData")
            return None

        # Парсим user данные
        user_str = parsed.get("user", [None])[0]
        if not user_str:
            logger.warning("No user in initData")
            return None

        user_data = json.loads(unquote(user_str))
        return user_data

    except Exception as e:
        logger.error(f"Error validating initData: {e}")
        return None


@web.middleware
async def cors_middleware(request: web.Request, handler):
    """
    CORS middleware для разрешения запросов с GitHub Pages.
    """
    # Preflight запрос
    if request.method == "OPTIONS":
        response = web.Response()
    else:
        try:
            response = await handler(request)
        except web.HTTPException as e:
            response = e

    # Разрешаем запросы с любого origin (для разработки)
    # В production можно ограничить до конкретного домена GitHub Pages
    origin = request.headers.get("Origin", "*")
    allowed_origins = [
        settings.webapp_origin,  # GitHub Pages
        "http://localhost:5173",  # Dev server
        "http://127.0.0.1:5173",
    ]

    if origin in allowed_origins or settings.webapp_origin == "*":
        response.headers["Access-Control-Allow-Origin"] = origin
    else:
        response.headers["Access-Control-Allow-Origin"] = settings.webapp_origin

    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, PATCH, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Telegram-Init-Data"
    response.headers["Access-Control-Max-Age"] = "3600"

    return response


@web.middleware
async def telegram_auth_middleware(request: web.Request, handler):
    """
    Middleware для аутентификации через Telegram initData.
    Добавляет user_id в request если initData валидна.
    """
    # Пропускаем OPTIONS запросы (CORS preflight)
    if request.method == "OPTIONS":
        return await handler(request)

    # Получаем initData из заголовка
    init_data = request.headers.get("X-Telegram-Init-Data", "")

    # Для разработки: если нет initData и это localhost, пропускаем проверку
    if not init_data:
        origin = request.headers.get("Origin", "")
        if "localhost" in origin or "127.0.0.1" in origin:
            # Dev mode: используем тестового пользователя
            request["telegram_user"] = None
            request["db_user_id"] = None
            logger.debug("Dev mode: skipping auth")
            return await handler(request)

        raise web.HTTPUnauthorized(text="Missing X-Telegram-Init-Data header")

    # Валидируем initData
    user_data = validate_telegram_init_data(init_data, settings.telegram_bot_token)
    if not user_data:
        raise web.HTTPUnauthorized(text="Invalid Telegram initData")

    # Получаем или создаём пользователя в БД
    telegram_user_id = user_data.get("id")
    if not telegram_user_id:
        raise web.HTTPUnauthorized(text="No user ID in initData")

    try:
        db_user_id = await get_or_create_user(
            telegram_user_id=telegram_user_id,
            username=user_data.get("username"),
            first_name=user_data.get("first_name"),
            last_name=user_data.get("last_name"),
        )
    except Exception as e:
        logger.error(f"Error getting/creating user: {e}")
        raise web.HTTPInternalServerError(text="Database error")

    # Сохраняем данные в request для использования в handlers
    request["telegram_user"] = user_data
    request["db_user_id"] = db_user_id

    return await handler(request)
