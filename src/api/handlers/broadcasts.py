# src/api/handlers/broadcasts.py
"""
API handlers для рассылок (broadcasts).
"""

import asyncio
import json
import logging
import os
from datetime import date
from decimal import Decimal
from aiohttp import web

from src.services.db import broadcast_repo
from src.services.broadcast_sender import execute_broadcast

logger = logging.getLogger(__name__)

# Директория для загруженных фото рассылок
BROADCAST_PHOTOS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data", "broadcast_photos"
)
os.makedirs(BROADCAST_PHOTOS_DIR, exist_ok=True)


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


async def get_broadcasts(request: web.Request) -> web.Response:
    """
    GET /api/admin/broadcasts
    Список рассылок.

    Query params:
        limit: int (default 50)
        offset: int (default 0)
    """
    try:
        limit = int(request.query.get('limit', '50'))
        offset = int(request.query.get('offset', '0'))

        broadcasts = await broadcast_repo.get_broadcasts(limit=limit, offset=offset)
        return web.json_response({
            'broadcasts': [_serialize_dict(b) for b in broadcasts],
        })

    except Exception as e:
        logger.error(f'Error getting broadcasts: {e}', exc_info=True)
        raise web.HTTPInternalServerError(text='Database error')


async def create_broadcast(request: web.Request) -> web.Response:
    """
    POST /api/admin/broadcasts
    Создать черновик рассылки.

    Body: {
        "title": "...",
        "message_text": "...",
        "poll_question": "...",
        "poll_options": ["A", "B"],
        "poll_is_anonymous": true,
        "poll_allows_multiple": false,
        "target_type": "all|invite_link|funnel_stage|manual",
        "target_invite_link_id": null,
        "target_funnel_id": null,
        "target_stage_key": null,
        "target_user_ids": null,
        "scheduled_at": null
    }
    """
    try:
        data = await request.json()
        title = data.get('title', '').strip()
        if not title:
            raise web.HTTPBadRequest(text='Title is required')

        target_type = data.get('target_type', 'all')
        if target_type not in ('all', 'invite_link', 'funnel_stage', 'manual'):
            raise web.HTTPBadRequest(text='Invalid target_type')

        message_text = data.get('message_text')
        poll_question = data.get('poll_question')

        if not message_text and not poll_question:
            raise web.HTTPBadRequest(text='Either message_text or poll_question is required')

        if message_text and len(message_text) > 4096:
            raise web.HTTPBadRequest(text='Message too long (max 4096 chars)')

        if poll_question and len(poll_question) > 300:
            raise web.HTTPBadRequest(text='Poll question too long (max 300 chars)')

        poll_options = data.get('poll_options')
        if poll_question:
            if not poll_options or len(poll_options) < 2:
                raise web.HTTPBadRequest(text='Poll requires at least 2 options')
            if len(poll_options) > 10:
                raise web.HTTPBadRequest(text='Poll allows max 10 options')
            for opt in poll_options:
                if len(opt) > 100:
                    raise web.HTTPBadRequest(text='Poll option too long (max 100 chars)')

        # Валидация inline_buttons
        inline_buttons = data.get('inline_buttons')
        if inline_buttons:
            _validate_inline_buttons(inline_buttons)

        broadcast = await broadcast_repo.create_broadcast(
            title=title,
            message_text=message_text,
            photo_path=data.get('photo_path'),
            poll_question=poll_question,
            poll_options=poll_options,
            poll_is_anonymous=data.get('poll_is_anonymous', True),
            poll_allows_multiple=data.get('poll_allows_multiple', False),
            target_type=target_type,
            target_invite_link_id=data.get('target_invite_link_id'),
            target_funnel_id=data.get('target_funnel_id'),
            target_stage_key=data.get('target_stage_key'),
            target_user_ids=data.get('target_user_ids'),
            scheduled_at=data.get('scheduled_at'),
            inline_buttons=inline_buttons,
        )

        return web.json_response(_serialize_dict(broadcast), status=201)

    except web.HTTPBadRequest:
        raise
    except Exception as e:
        logger.error(f'Error creating broadcast: {e}', exc_info=True)
        raise web.HTTPInternalServerError(text='Database error')


async def get_broadcast(request: web.Request) -> web.Response:
    """
    GET /api/admin/broadcasts/{id}
    Детали рассылки.
    """
    try:
        broadcast_id = int(request.match_info['id'])
        broadcast = await broadcast_repo.get_broadcast(broadcast_id)
        if not broadcast:
            raise web.HTTPNotFound(text='Broadcast not found')

        return web.json_response(_serialize_dict(broadcast))

    except (ValueError, web.HTTPNotFound):
        raise web.HTTPNotFound(text='Broadcast not found')
    except Exception as e:
        logger.error(f'Error getting broadcast: {e}', exc_info=True)
        raise web.HTTPInternalServerError(text='Database error')


async def update_broadcast(request: web.Request) -> web.Response:
    """
    PUT /api/admin/broadcasts/{id}
    Обновить черновик рассылки.
    """
    try:
        broadcast_id = int(request.match_info['id'])
        data = await request.json()

        # Валидация
        message_text = data.get('message_text')
        if message_text and len(message_text) > 4096:
            raise web.HTTPBadRequest(text='Message too long (max 4096 chars)')

        poll_question = data.get('poll_question')
        if poll_question and len(poll_question) > 300:
            raise web.HTTPBadRequest(text='Poll question too long (max 300 chars)')

        poll_options = data.get('poll_options')
        if poll_options:
            if len(poll_options) < 2:
                raise web.HTTPBadRequest(text='Poll requires at least 2 options')
            if len(poll_options) > 10:
                raise web.HTTPBadRequest(text='Poll allows max 10 options')

        target_type = data.get('target_type')
        if target_type and target_type not in ('all', 'invite_link', 'funnel_stage', 'manual'):
            raise web.HTTPBadRequest(text='Invalid target_type')

        inline_buttons = data.get('inline_buttons')
        if inline_buttons:
            _validate_inline_buttons(inline_buttons)

        broadcast = await broadcast_repo.update_broadcast(
            broadcast_id=broadcast_id,
            title=data.get('title'),
            message_text=message_text,
            photo_path=data.get('photo_path'),
            poll_question=poll_question,
            poll_options=poll_options,
            poll_is_anonymous=data.get('poll_is_anonymous'),
            poll_allows_multiple=data.get('poll_allows_multiple'),
            target_type=target_type,
            target_invite_link_id=data.get('target_invite_link_id'),
            target_funnel_id=data.get('target_funnel_id'),
            target_stage_key=data.get('target_stage_key'),
            target_user_ids=data.get('target_user_ids'),
            scheduled_at=data.get('scheduled_at'),
            inline_buttons=inline_buttons,
        )

        if not broadcast:
            raise web.HTTPNotFound(text='Broadcast not found or not in draft status')

        return web.json_response(_serialize_dict(broadcast))

    except web.HTTPBadRequest:
        raise
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f'Error updating broadcast: {e}', exc_info=True)
        raise web.HTTPInternalServerError(text='Database error')


async def delete_broadcast(request: web.Request) -> web.Response:
    """
    DELETE /api/admin/broadcasts/{id}
    Удалить рассылку (только draft/scheduled).
    """
    try:
        broadcast_id = int(request.match_info['id'])
        deleted = await broadcast_repo.delete_broadcast(broadcast_id)
        if not deleted:
            raise web.HTTPNotFound(text='Broadcast not found or cannot be deleted')

        return web.json_response({'success': True})

    except (ValueError, web.HTTPNotFound):
        raise web.HTTPNotFound(text='Broadcast not found')
    except Exception as e:
        logger.error(f'Error deleting broadcast: {e}', exc_info=True)
        raise web.HTTPInternalServerError(text='Database error')


async def send_broadcast(request: web.Request) -> web.Response:
    """
    POST /api/admin/broadcasts/{id}/send
    Запустить мгновенную отправку рассылки.
    """
    try:
        broadcast_id = int(request.match_info['id'])
        broadcast = await broadcast_repo.get_broadcast(broadcast_id)
        if not broadcast:
            raise web.HTTPNotFound(text='Broadcast not found')

        if broadcast['status'] not in ('draft', 'scheduled'):
            raise web.HTTPBadRequest(text=f"Cannot send broadcast with status '{broadcast['status']}'")

        # Собираем получателей
        count = await broadcast_repo.resolve_recipients(broadcast_id)
        if count == 0:
            raise web.HTTPBadRequest(text='No recipients found for this broadcast')

        # Запускаем отправку в фоне
        asyncio.create_task(execute_broadcast(broadcast_id))

        return web.json_response({
            'success': True,
            'total_recipients': count,
        })

    except web.HTTPBadRequest:
        raise
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f'Error sending broadcast: {e}', exc_info=True)
        raise web.HTTPInternalServerError(text='Failed to send broadcast')


async def schedule_broadcast(request: web.Request) -> web.Response:
    """
    POST /api/admin/broadcasts/{id}/schedule
    Запланировать рассылку.

    Body: { "scheduled_at": "2026-02-22T15:00:00Z" }
    """
    try:
        broadcast_id = int(request.match_info['id'])
        broadcast = await broadcast_repo.get_broadcast(broadcast_id)
        if not broadcast:
            raise web.HTTPNotFound(text='Broadcast not found')

        if broadcast['status'] != 'draft':
            raise web.HTTPBadRequest(text='Only draft broadcasts can be scheduled')

        data = await request.json()
        scheduled_at = data.get('scheduled_at')
        if not scheduled_at:
            raise web.HTTPBadRequest(text='scheduled_at is required')

        # Обновляем scheduled_at и статус
        await broadcast_repo.update_broadcast(broadcast_id, scheduled_at=scheduled_at)
        await broadcast_repo.update_broadcast_status(broadcast_id, 'scheduled')

        updated = await broadcast_repo.get_broadcast(broadcast_id)
        return web.json_response(_serialize_dict(updated))

    except web.HTTPBadRequest:
        raise
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f'Error scheduling broadcast: {e}', exc_info=True)
        raise web.HTTPInternalServerError(text='Database error')


async def cancel_broadcast(request: web.Request) -> web.Response:
    """
    POST /api/admin/broadcasts/{id}/cancel
    Отменить рассылку (sending или scheduled).
    """
    try:
        broadcast_id = int(request.match_info['id'])
        broadcast = await broadcast_repo.get_broadcast(broadcast_id)
        if not broadcast:
            raise web.HTTPNotFound(text='Broadcast not found')

        if broadcast['status'] not in ('sending', 'scheduled'):
            raise web.HTTPBadRequest(text=f"Cannot cancel broadcast with status '{broadcast['status']}'")

        await broadcast_repo.update_broadcast_status(broadcast_id, 'cancelled')

        return web.json_response({'success': True})

    except web.HTTPBadRequest:
        raise
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f'Error cancelling broadcast: {e}', exc_info=True)
        raise web.HTTPInternalServerError(text='Database error')


async def get_broadcast_recipients(request: web.Request) -> web.Response:
    """
    GET /api/admin/broadcasts/{id}/recipients
    Список получателей рассылки со статусами.

    Query params:
        status: pending|sent|failed (опционально)
    """
    try:
        broadcast_id = int(request.match_info['id'])
        status_filter = request.query.get('status')

        recipients = await broadcast_repo.get_broadcast_recipients(
            broadcast_id, status_filter=status_filter,
        )

        return web.json_response({
            'recipients': [_serialize_dict(r) for r in recipients],
        })

    except Exception as e:
        logger.error(f'Error getting broadcast recipients: {e}', exc_info=True)
        raise web.HTTPInternalServerError(text='Database error')


async def preview_recipient_count(request: web.Request) -> web.Response:
    """
    POST /api/admin/broadcasts/preview-count
    Превью количества получателей для таргетинга.

    Body: {
        "target_type": "all|invite_link|funnel_stage|manual",
        "target_invite_link_id": null,
        "target_funnel_id": null,
        "target_stage_key": null,
        "target_user_ids": null
    }
    """
    try:
        data = await request.json()
        target_type = data.get('target_type', 'all')

        count = await broadcast_repo.get_recipient_count_preview(
            target_type=target_type,
            target_invite_link_id=data.get('target_invite_link_id'),
            target_funnel_id=data.get('target_funnel_id'),
            target_stage_key=data.get('target_stage_key'),
            target_user_ids=data.get('target_user_ids'),
        )

        return web.json_response({'count': count})

    except Exception as e:
        logger.error(f'Error previewing recipient count: {e}', exc_info=True)
        raise web.HTTPInternalServerError(text='Database error')


async def get_broadcast_users(request: web.Request) -> web.Response:
    """
    GET /api/admin/broadcasts/users
    Все пользователи для ручного выбора получателей.
    """
    try:
        users = await broadcast_repo.get_all_users_short()
        return web.json_response({'users': users})

    except Exception as e:
        logger.error(f'Error getting users: {e}', exc_info=True)
        raise web.HTTPInternalServerError(text='Database error')


async def upload_broadcast_photo(request: web.Request) -> web.Response:
    """
    POST /api/admin/broadcasts/upload-photo
    Загрузка фото для рассылки (multipart/form-data).

    Returns: { "photo_path": "/abs/path/to/photo.jpg" }
    """
    try:
        reader = await request.multipart()
        field = await reader.next()

        if not field or field.name != 'photo':
            raise web.HTTPBadRequest(text='Field "photo" is required')

        filename = field.filename or 'broadcast_photo.jpg'
        # Проверяем расширение
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
            raise web.HTTPBadRequest(text='Invalid file type. Allowed: jpg, jpeg, png, gif, webp')

        # Генерируем уникальное имя
        import time
        safe_name = f"broadcast_{int(time.time())}{ext}"
        filepath = os.path.join(BROADCAST_PHOTOS_DIR, safe_name)

        # Читаем и сохраняем
        size = 0
        with open(filepath, 'wb') as f:
            while True:
                chunk = await field.read_chunk()
                if not chunk:
                    break
                size += len(chunk)
                if size > 10 * 1024 * 1024:  # 10 MB limit (Telegram)
                    f.close()
                    os.remove(filepath)
                    raise web.HTTPBadRequest(text='File too large (max 10 MB)')
                f.write(chunk)

        return web.json_response({'photo_path': safe_name})

    except web.HTTPBadRequest:
        raise
    except Exception as e:
        logger.error(f'Error uploading broadcast photo: {e}', exc_info=True)
        raise web.HTTPInternalServerError(text='Upload failed')


async def get_broadcast_photo(request: web.Request) -> web.Response:
    """
    GET /api/admin/broadcasts/photo/{filename}
    Раздача загруженных фото рассылок.
    """
    filename = request.match_info['filename']
    # Защита от path traversal
    if '/' in filename or '..' in filename:
        raise web.HTTPBadRequest(text='Invalid filename')

    filepath = os.path.join(BROADCAST_PHOTOS_DIR, filename)
    if not os.path.isfile(filepath):
        raise web.HTTPNotFound(text='Photo not found')

    return web.FileResponse(filepath)


def _validate_inline_buttons(buttons: list) -> None:
    """Валидация массива inline-кнопок."""
    if not isinstance(buttons, list):
        raise web.HTTPBadRequest(text='inline_buttons must be an array')

    if len(buttons) > 10:
        raise web.HTTPBadRequest(text='Too many buttons (max 10)')

    rows = set()
    for btn in buttons:
        if not isinstance(btn, dict):
            raise web.HTTPBadRequest(text='Each button must be an object')

        text = btn.get('text', '')
        if not text or len(text) > 64:
            raise web.HTTPBadRequest(text='Button text must be 1-64 characters')

        btn_type = btn.get('type')
        if btn_type not in ('url', 'quick_reply'):
            raise web.HTTPBadRequest(text='Button type must be "url" or "quick_reply"')

        if btn_type == 'url':
            url = btn.get('url', '')
            if not url or not url.startswith(('http://', 'https://')):
                raise web.HTTPBadRequest(text='URL button requires a valid URL')

        rows.add(btn.get('row', 0))

    if len(rows) > 5:
        raise web.HTTPBadRequest(text='Maximum 5 button rows allowed')


async def get_broadcast_stats(request: web.Request) -> web.Response:
    """
    GET /api/admin/broadcasts/{id}/stats
    Статистика кликов по кнопкам и ответов на опрос.
    """
    try:
        broadcast_id = int(request.match_info['id'])
        broadcast = await broadcast_repo.get_broadcast(broadcast_id)
        if not broadcast:
            raise web.HTTPNotFound(text='Broadcast not found')

        button_clicks = await broadcast_repo.get_button_click_stats(broadcast_id)
        poll_answers = await broadcast_repo.get_poll_answer_stats(broadcast_id)

        # Вычисляем проценты для кнопок
        total_button = sum(s['click_count'] for s in button_clicks)
        for stat in button_clicks:
            stat['percentage'] = round(stat['click_count'] / total_button * 100, 1) if total_button > 0 else 0

        # Вычисляем проценты для опросов (один юзер может выбрать несколько вариантов)
        # Считаем уникальных отвечавших
        total_poll_respondents = 0
        if poll_answers:
            from src.services.db.pool import get_pool
            pool = get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT COUNT(*) AS cnt FROM broadcast_poll_answers WHERE broadcast_id = $1",
                    broadcast_id,
                )
            total_poll_respondents = row['cnt'] if row else 0

        total_answers = sum(s['answer_count'] for s in poll_answers)
        for stat in poll_answers:
            # Процент от общего числа ответивших
            stat['percentage'] = round(stat['answer_count'] / total_poll_respondents * 100, 1) if total_poll_respondents > 0 else 0

        # Добавляем текст варианта опроса из broadcast.poll_options
        poll_options = broadcast.get('poll_options')
        if isinstance(poll_options, str):
            poll_options = json.loads(poll_options)
        if poll_options:
            for stat in poll_answers:
                idx = stat['option_index']
                stat['option_text'] = poll_options[idx] if idx < len(poll_options) else f'Вариант {idx + 1}'

        return web.json_response({
            'button_clicks': button_clicks,
            'poll_answers': [_serialize_dict(s) for s in poll_answers],
            'total_button_respondents': total_button,
            'total_poll_respondents': total_poll_respondents,
        })

    except (ValueError, web.HTTPNotFound):
        raise web.HTTPNotFound(text='Broadcast not found')
    except Exception as e:
        logger.error(f'Error getting broadcast stats: {e}', exc_info=True)
        raise web.HTTPInternalServerError(text='Database error')


async def get_broadcast_stat_users(request: web.Request) -> web.Response:
    """
    GET /api/admin/broadcasts/{id}/stats/users?type=button&key=opt_0
    GET /api/admin/broadcasts/{id}/stats/users?type=poll&option=0
    Список пользователей для drill-down статистики.
    """
    try:
        broadcast_id = int(request.match_info['id'])
        stat_type = request.query.get('type')

        if stat_type == 'button':
            option_key = request.query.get('key', '')
            if not option_key:
                raise web.HTTPBadRequest(text='key parameter required')
            users = await broadcast_repo.get_button_click_users(broadcast_id, option_key)
        elif stat_type == 'poll':
            option_str = request.query.get('option', '')
            if option_str == '':
                raise web.HTTPBadRequest(text='option parameter required')
            option_index = int(option_str)
            users = await broadcast_repo.get_poll_answer_users(broadcast_id, option_index)
        else:
            raise web.HTTPBadRequest(text='type must be "button" or "poll"')

        return web.json_response({
            'users': [_serialize_dict(u) for u in users],
        })

    except web.HTTPBadRequest:
        raise
    except (ValueError, web.HTTPNotFound):
        raise web.HTTPNotFound(text='Broadcast not found')
    except Exception as e:
        logger.error(f'Error getting broadcast stat users: {e}', exc_info=True)
        raise web.HTTPInternalServerError(text='Database error')
