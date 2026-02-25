# src/api/handlers/invite_links.py
"""
API handlers для инвайт-ссылок (campaign tracking).
"""

import logging
from datetime import date
from decimal import Decimal
from aiohttp import web

from src.config import settings
from src.services.db import invite_link_repo

logger = logging.getLogger(__name__)


def _serialize_value(value):
    """Сериализация специальных типов для JSON."""
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _serialize_dict(d: dict) -> dict:
    return {k: _serialize_value(v) for k, v in d.items()}


def _build_deep_link(code: str) -> str:
    """Сформировать deep link для инвайт-ссылки."""
    username = settings.telegram_bot_username
    return f"https://t.me/{username}?start=inv_{code}" if username else f"inv_{code}"


async def get_invite_links(request: web.Request) -> web.Response:
    """
    GET /api/admin/invite-links
    Получить все инвайт-ссылки со статистикой.

    Query params:
        start_date: YYYY-MM-DD (опционально)
        end_date: YYYY-MM-DD (опционально)
    """
    try:
        start_date = request.query.get('start_date')
        end_date = request.query.get('end_date')

        links = await invite_link_repo.get_invite_links_with_stats(
            start_date=start_date,
            end_date=end_date,
        )
        summary = await invite_link_repo.get_invite_links_summary(
            start_date=start_date,
            end_date=end_date,
        )

        serialized_links = []
        for link in links:
            d = _serialize_dict(link)
            d['deep_link'] = _build_deep_link(d['code'])
            d['total_revenue_rub'] = float(d.get('total_revenue_rub', 0))
            serialized_links.append(d)

        return web.json_response({
            'links': serialized_links,
            'summary': summary,
        })

    except Exception as e:
        logger.error(f'Error getting invite links: {e}', exc_info=True)
        raise web.HTTPInternalServerError(text='Database error')


async def create_invite_link(request: web.Request) -> web.Response:
    """
    POST /api/admin/invite-links
    Создать новую инвайт-ссылку.

    Body: { "name": "...", "bonus_tokens": 0, "discount_percent": 0, "discount_duration_days": 0 }
    """
    try:
        data = await request.json()
        name = data.get('name', '').strip()
        if not name:
            raise web.HTTPBadRequest(text='Name is required')

        bonus_tokens = int(data.get('bonus_tokens', 0))
        discount_percent = int(data.get('discount_percent', 0))
        discount_duration_days = int(data.get('discount_duration_days', 0))
        max_users = int(data.get('max_users', 0))
        token_bonus_percent = int(data.get('token_bonus_percent', 0))
        allow_existing_users = bool(data.get('allow_existing_users', False))
        existing_user_bonus_tokens = bool(data.get('existing_user_bonus_tokens', True))
        existing_user_discount = bool(data.get('existing_user_discount', True))
        existing_user_token_bonus = bool(data.get('existing_user_token_bonus', True))

        # Валидация
        if not (0 <= discount_percent <= 100):
            raise web.HTTPBadRequest(text='discount_percent must be 0-100')
        if not (0 <= token_bonus_percent <= 100):
            raise web.HTTPBadRequest(text='token_bonus_percent must be 0-100')
        if bonus_tokens < 0:
            raise web.HTTPBadRequest(text='bonus_tokens must be >= 0')
        if discount_duration_days < 0:
            raise web.HTTPBadRequest(text='discount_duration_days must be >= 0')
        if max_users < 0:
            raise web.HTTPBadRequest(text='max_users must be >= 0')

        link = await invite_link_repo.create_invite_link(
            name,
            bonus_tokens=bonus_tokens,
            discount_percent=discount_percent,
            discount_duration_days=discount_duration_days,
            max_users=max_users,
            token_bonus_percent=token_bonus_percent,
            allow_existing_users=allow_existing_users,
            existing_user_bonus_tokens=existing_user_bonus_tokens,
            existing_user_discount=existing_user_discount,
            existing_user_token_bonus=existing_user_token_bonus,
        )
        result = _serialize_dict(link)
        result['deep_link'] = _build_deep_link(result['code'])
        result['users_count'] = 0
        result['total_revenue_rub'] = 0.0

        return web.json_response(result, status=201)

    except web.HTTPBadRequest:
        raise
    except Exception as e:
        logger.error(f'Error creating invite link: {e}', exc_info=True)
        raise web.HTTPInternalServerError(text='Database error')


async def update_invite_link(request: web.Request) -> web.Response:
    """
    PATCH /api/admin/invite-links/{id}
    Обновить инвайт-ссылку.

    Body: { "name": "...", "bonus_tokens": 0, "discount_percent": 0, "discount_duration_days": 0 }
    """
    try:
        link_id = int(request.match_info['id'])
        data = await request.json()
        name = data.get('name', '').strip()
        if not name:
            raise web.HTTPBadRequest(text='Name is required')

        bonus_tokens = int(data.get('bonus_tokens', 0))
        discount_percent = int(data.get('discount_percent', 0))
        discount_duration_days = int(data.get('discount_duration_days', 0))
        max_users = int(data.get('max_users', 0))
        token_bonus_percent = int(data.get('token_bonus_percent', 0))
        allow_existing_users = bool(data.get('allow_existing_users', False))
        existing_user_bonus_tokens = bool(data.get('existing_user_bonus_tokens', True))
        existing_user_discount = bool(data.get('existing_user_discount', True))
        existing_user_token_bonus = bool(data.get('existing_user_token_bonus', True))
        is_active = data.get('is_active')
        if is_active is not None:
            is_active = bool(is_active)

        # Валидация
        if not (0 <= discount_percent <= 100):
            raise web.HTTPBadRequest(text='discount_percent must be 0-100')
        if not (0 <= token_bonus_percent <= 100):
            raise web.HTTPBadRequest(text='token_bonus_percent must be 0-100')
        if bonus_tokens < 0:
            raise web.HTTPBadRequest(text='bonus_tokens must be >= 0')
        if discount_duration_days < 0:
            raise web.HTTPBadRequest(text='discount_duration_days must be >= 0')
        if max_users < 0:
            raise web.HTTPBadRequest(text='max_users must be >= 0')

        link = await invite_link_repo.update_invite_link(
            link_id, name,
            bonus_tokens=bonus_tokens,
            discount_percent=discount_percent,
            discount_duration_days=discount_duration_days,
            max_users=max_users,
            token_bonus_percent=token_bonus_percent,
            allow_existing_users=allow_existing_users,
            existing_user_bonus_tokens=existing_user_bonus_tokens,
            existing_user_discount=existing_user_discount,
            existing_user_token_bonus=existing_user_token_bonus,
            is_active=is_active,
        )
        if not link:
            raise web.HTTPNotFound(text='Invite link not found')

        result = _serialize_dict(link)
        result['deep_link'] = _build_deep_link(result['code'])
        return web.json_response(result)

    except web.HTTPBadRequest:
        raise
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f'Error updating invite link: {e}', exc_info=True)
        raise web.HTTPInternalServerError(text='Database error')


async def delete_invite_link(request: web.Request) -> web.Response:
    """
    DELETE /api/admin/invite-links/{id}
    Удалить инвайт-ссылку.
    """
    try:
        link_id = int(request.match_info['id'])
        deleted = await invite_link_repo.delete_invite_link(link_id)
        if not deleted:
            raise web.HTTPNotFound(text='Invite link not found')

        return web.json_response({'success': True})

    except (ValueError, web.HTTPNotFound):
        raise web.HTTPNotFound(text='Invite link not found')
    except Exception as e:
        logger.error(f'Error deleting invite link: {e}', exc_info=True)
        raise web.HTTPInternalServerError(text='Database error')


async def toggle_invite_link(request: web.Request) -> web.Response:
    """
    PATCH /api/admin/invite-links/{id}/toggle
    Включить/выключить инвайт-ссылку.

    Body: { "is_active": true/false }
    """
    try:
        link_id = int(request.match_info['id'])
        data = await request.json()
        is_active = data.get('is_active')
        if is_active is None:
            raise web.HTTPBadRequest(text='is_active is required')

        link = await invite_link_repo.toggle_invite_link_active(link_id, bool(is_active))
        if not link:
            raise web.HTTPNotFound(text='Invite link not found')

        result = _serialize_dict(link)
        result['deep_link'] = _build_deep_link(result['code'])
        return web.json_response(result)

    except web.HTTPBadRequest:
        raise
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f'Error toggling invite link: {e}', exc_info=True)
        raise web.HTTPInternalServerError(text='Database error')
