# src/api/handlers/crm.py
"""
API handlers для CRM: Kanban-доска, карточки клиентов, теги, задачи, заметки.
"""

import json
import logging
from decimal import Decimal
from datetime import datetime
from typing import Optional
from aiohttp import web

from src.services.db import client_funnel_repo
from src.services.db import consultation_logs_repo
from src.services.db import client_crm_repo
from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


def _serialize_value(value):
    """Serialize special types for JSON."""
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    # asyncpg returns JSONB as string, parse it back to Python object
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
    result = {k: _serialize_value(v) for k, v in d.items()}
    # Конвертируем avatar_path → avatar_url
    avatar_path = result.pop('avatar_path', None)
    result['avatar_url'] = f"/api/admin/avatars/{avatar_path}" if avatar_path else None
    return result


async def get_crm_clients(request: web.Request) -> web.Response:
    """
    GET /api/admin/crm/clients
    Получить всех клиентов сгруппированных по статусу для Kanban.

    Returns:
        {
            "clients": {
                "new": [...],
                "tried": [...],
                "trial_ended": [...],
                "paid": [...]
            },
            "stats": {
                "new": 10,
                "tried": 25,
                "trial_ended": 5,
                "paid": 3
            }
        }
    """
    try:
        grouped = await client_funnel_repo.get_clients_grouped_by_status()
        stats = await client_funnel_repo.get_funnel_stats()

        # Сериализация datetime и Decimal
        for status, clients in grouped.items():
            grouped[status] = [_serialize_dict(c) for c in clients]

        return web.json_response({
            "clients": grouped,
            "stats": stats
        })

    except Exception as e:
        logger.error(f"Error getting CRM clients: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_crm_client(request: web.Request) -> web.Response:
    """
    GET /api/admin/crm/clients/{id}
    Получить полную информацию о клиенте.

    Path params:
        id: int (user_id)
    """
    try:
        user_id = int(request.match_info["id"])

        client = await client_funnel_repo.get_client_by_id(user_id)

        if not client:
            raise web.HTTPNotFound(text="Client not found")

        return web.json_response(_serialize_dict(client))

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid client ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error getting CRM client: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def update_crm_client_status(request: web.Request) -> web.Response:
    """
    PATCH /api/admin/crm/clients/{id}/status
    Обновить статус клиента в воронке (drag-and-drop).

    Path params:
        id: int (user_id)

    Body:
        {"status": "tried" | "trial_ended" | "paid" | "new" | "custom_*"}
    """
    try:
        user_id = int(request.match_info["id"])
        body = await request.json()

        new_status = body.get("status")
        if not new_status:
            raise web.HTTPBadRequest(text="Missing 'status' field")

        # Валидация происходит в update_client_status (проверяет существование колонки)
        success = await client_funnel_repo.update_client_status(user_id, new_status)

        if not success:
            raise web.HTTPNotFound(text="Client not found or invalid status")

        return web.json_response({"success": True, "status": new_status})

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid client ID")
    except web.HTTPBadRequest:
        raise
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error updating CRM client status: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_crm_client_topics(request: web.Request) -> web.Response:
    """
    GET /api/admin/crm/clients/{id}/topics
    Получить топики клиента для вкладки "Консультации".

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
        logger.error(f"Error getting client topics: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_funnel_stats(request: web.Request) -> web.Response:
    """
    GET /api/admin/crm/stats?tag_id=5
    Получить статистику воронки. Опционально фильтр по тегу.

    Returns:
        {"new": 10, "tried": 25, "trial_ended": 5, "paid": 3}
    """
    try:
        tag_id = request.query.get('tag_id')
        tag_id = int(tag_id) if tag_id else None
        stats = await client_funnel_repo.get_funnel_stats(tag_id=tag_id)
        return web.json_response(stats)

    except Exception as e:
        logger.error(f"Error getting funnel stats: {e}")
        raise web.HTTPInternalServerError(text="Database error")


# =============================================================================
# Расширенная карточка клиента
# =============================================================================

async def get_client_full(request: web.Request) -> web.Response:
    """
    GET /api/admin/crm/clients/{id}/full
    Получить полные данные клиента включая теги, кастомные поля и реферальную информацию.
    """
    try:
        user_id = int(request.match_info["id"])
        funnel_id = request.query.get("funnel_id")
        client = await client_crm_repo.get_client_full_data(user_id, funnel_id=funnel_id)

        if not client:
            raise web.HTTPNotFound(text="Client not found")

        result = _serialize_dict(client)

        # Добавляем реферальные данные
        from src.services.db.referral_repo import get_referrer_info, get_referral_stats
        from src.services.db.pool import get_pool

        referrer = await get_referrer_info(user_id)
        ref_stats = await get_referral_stats(user_id)

        pool = get_pool()
        async with pool.acquire() as conn:
            ref_code = await conn.fetchval(
                "SELECT referral_code FROM users WHERE id = $1", user_id
            )

            # Подписка, скидка и балансы токенов
            billing_row = await conn.fetchrow(
                """
                SELECT
                    us.id              AS sub_id,
                    us.subscription_plan_id,
                    sp.name            AS subscription_plan_name,
                    us.started_at      AS subscription_started_at,
                    us.expires_at      AS subscription_expires_at,
                    us.status          AS subscription_status,
                    u.personal_discount_percent,
                    u.personal_discount_valid_until,
                    COALESCE(u.subscription_token_balance, 0) AS subscription_token_balance,
                    COALESCE(u.purchased_token_balance, 0)    AS purchased_token_balance
                FROM users u
                LEFT JOIN user_subscriptions us
                    ON us.user_id = u.id AND us.is_active = true
                LEFT JOIN subscription_plans sp ON sp.id = us.subscription_plan_id
                WHERE u.id = $1
                ORDER BY us.expires_at DESC NULLS LAST
                LIMIT 1
                """,
                user_id
            )

        result["referrer"] = _serialize_dict(referrer) if referrer else None
        result["referrals_count"] = ref_stats["total_referrals"]
        result["referral_code"] = ref_code

        if billing_row:
            result["sub_id"] = billing_row["sub_id"]
            result["subscription_plan_id"] = billing_row["subscription_plan_id"]
            result["subscription_plan_name"] = billing_row["subscription_plan_name"]
            result["subscription_started_at"] = (
                billing_row["subscription_started_at"].isoformat()
                if billing_row["subscription_started_at"] else None
            )
            result["subscription_expires_at"] = (
                billing_row["subscription_expires_at"].isoformat()
                if billing_row["subscription_expires_at"] else None
            )
            result["subscription_status"] = billing_row["subscription_status"]
            result["personal_discount_percent"] = billing_row["personal_discount_percent"] or 0
            result["personal_discount_valid_until"] = (
                billing_row["personal_discount_valid_until"].isoformat()
                if billing_row["personal_discount_valid_until"] else None
            )
            result["subscription_token_balance"] = billing_row["subscription_token_balance"]
            result["purchased_token_balance"] = billing_row["purchased_token_balance"]

        # Funnel variant & quiz answers
        async with pool.acquire() as conn:
            fv = await conn.fetchval(
                "SELECT funnel_variant FROM users WHERE id = $1", user_id
            )
            quiz = await conn.fetchrow(
                "SELECT culture, region, problem FROM user_quiz_answers WHERE user_id = $1",
                user_id
            )
        result["funnel_variant"] = fv
        result["quiz_culture"] = quiz["culture"] if quiz else None
        result["quiz_region"] = quiz["region"] if quiz else None
        result["quiz_problem"] = quiz["problem"] if quiz else None

        return web.json_response(result)

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid client ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error getting full client data: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def update_client_billing(request: web.Request) -> web.Response:
    """
    PATCH /api/admin/crm/clients/{id}/billing
    Обновить биллинговые данные клиента: тариф, скидку, балансы токенов.

    Body (все поля опциональны):
        {
            "subscription_plan_id": 3,
            "subscription_started_at": "2026-02-01T00:00:00",
            "subscription_expires_at": "2026-03-01T00:00:00",
            "personal_discount_percent": 15,
            "personal_discount_valid_until": "2026-04-01T00:00:00",
            "subscription_token_balance": 10,
            "purchased_token_balance": 5
        }
    """
    try:
        user_id = int(request.match_info["id"])
        body = await request.json()

        pool = get_pool()
        async with pool.acquire() as conn:
            # ---- 1. Проверяем что пользователь существует ----
            exists = await conn.fetchval("SELECT id FROM users WHERE id = $1", user_id)
            if not exists:
                raise web.HTTPNotFound(text="Client not found")

            # ---- 2. Подписка ----
            plan_id = body.get("subscription_plan_id")
            started_at_str = body.get("subscription_started_at")
            expires_at_str = body.get("subscription_expires_at")

            if plan_id is not None or started_at_str or expires_at_str:
                started_at = None
                expires_at = None
                if started_at_str:
                    started_at = datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
                if expires_at_str:
                    expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))

                # Ищем активную подписку
                active_sub = await conn.fetchrow(
                    "SELECT id FROM user_subscriptions WHERE user_id = $1 AND is_active = true ORDER BY expires_at DESC LIMIT 1",
                    user_id
                )

                if active_sub:
                    # Обновляем существующую
                    if plan_id is not None:
                        tokens_granted = await conn.fetchval(
                            "SELECT tokens_included FROM subscription_plans WHERE id = $1", plan_id
                        ) or 0
                        await conn.execute(
                            """
                            UPDATE user_subscriptions
                            SET subscription_plan_id = $1,
                                tokens_granted = $2,
                                updated_at = NOW()
                            WHERE id = $3
                            """,
                            plan_id, tokens_granted, active_sub["id"]
                        )
                    if started_at:
                        await conn.execute(
                            "UPDATE user_subscriptions SET started_at = $1, updated_at = NOW() WHERE id = $2",
                            started_at, active_sub["id"]
                        )
                    if expires_at:
                        await conn.execute(
                            "UPDATE user_subscriptions SET expires_at = $1, updated_at = NOW() WHERE id = $2",
                            expires_at, active_sub["id"]
                        )
                else:
                    # Создаём новую подписку, если указан план
                    if plan_id is not None:
                        from datetime import timedelta
                        plan_row = await conn.fetchrow(
                            "SELECT tokens_included, duration_days FROM subscription_plans WHERE id = $1",
                            plan_id
                        )
                        tokens_granted = plan_row["tokens_included"] if plan_row else 0
                        duration_days = plan_row["duration_days"] if plan_row else 30
                        sub_started = started_at or datetime.utcnow()
                        sub_expires = expires_at or (sub_started + timedelta(days=duration_days))

                        # Деактивируем старые подписки
                        await conn.execute(
                            "UPDATE user_subscriptions SET is_active = false, status = 'canceled' WHERE user_id = $1",
                            user_id
                        )
                        await conn.execute(
                            """
                            INSERT INTO user_subscriptions
                                (user_id, subscription_plan_id, payment_id, started_at, expires_at,
                                 status, is_active, tokens_granted)
                            VALUES ($1, $2, 0, $3, $4, 'active', true, $5)
                            """,
                            user_id, plan_id, sub_started, sub_expires, tokens_granted
                        )

            # ---- 3. Персональная скидка ----
            discount_percent = body.get("personal_discount_percent")
            discount_valid_until_str = body.get("personal_discount_valid_until")

            if discount_percent is not None or discount_valid_until_str is not None:
                discount_valid_until = None
                if discount_valid_until_str:
                    discount_valid_until = datetime.fromisoformat(
                        discount_valid_until_str.replace("Z", "+00:00")
                    )
                updates = []
                params = []
                idx = 1
                if discount_percent is not None:
                    updates.append(f"personal_discount_percent = ${idx}")
                    params.append(max(0, min(100, int(discount_percent))))
                    idx += 1
                if discount_valid_until is not None or "personal_discount_valid_until" in body:
                    updates.append(f"personal_discount_valid_until = ${idx}")
                    params.append(discount_valid_until)
                    idx += 1
                if updates:
                    params.append(user_id)
                    await conn.execute(
                        f"UPDATE users SET {', '.join(updates)} WHERE id = ${idx}",
                        *params
                    )

            # ---- 4. Балансы токенов ----
            sub_tokens = body.get("subscription_token_balance")
            pur_tokens = body.get("purchased_token_balance")

            if sub_tokens is not None or pur_tokens is not None:
                token_updates = []
                token_params = []
                idx = 1
                if sub_tokens is not None:
                    token_updates.append(f"subscription_token_balance = ${idx}")
                    token_params.append(max(0, int(sub_tokens)))
                    idx += 1
                if pur_tokens is not None:
                    token_updates.append(f"purchased_token_balance = ${idx}")
                    token_params.append(max(0, int(pur_tokens)))
                    idx += 1
                token_params.append(user_id)
                await conn.execute(
                    f"UPDATE users SET {', '.join(token_updates)} WHERE id = ${idx}",
                    *token_params
                )
                # Пересчитываем token_balance из реальных данных
                await conn.execute(
                    """
                    UPDATE users
                    SET token_balance = COALESCE(subscription_token_balance, 0) + COALESCE(purchased_token_balance, 0)
                    WHERE id = $1
                    """,
                    user_id
                )
                # Логируем в token_transactions
                if sub_tokens is not None:
                    await conn.execute(
                        """
                        INSERT INTO token_transactions (user_id, amount, operation_type, description)
                        VALUES ($1, $2, 'admin_credit', 'Ручная корректировка: подписочные токены')
                        """,
                        user_id, int(sub_tokens)
                    )
                if pur_tokens is not None:
                    await conn.execute(
                        """
                        INSERT INTO token_transactions (user_id, amount, operation_type, description)
                        VALUES ($1, $2, 'admin_credit', 'Ручная корректировка: купленные токены')
                        """,
                        user_id, int(pur_tokens)
                    )

            # Системные сообщения о ручной корректировке токенов (вне транзакции)
            if sub_tokens is not None or pur_tokens is not None:
                try:
                    from src.services.db.messages_repo import log_system_message
                    parts = []
                    if sub_tokens is not None:
                        parts.append(f"{int(sub_tokens)} подписочных")
                    if pur_tokens is not None:
                        parts.append(f"{int(pur_tokens)} купленных")
                    msg_text = f"Токены изменены администратором: {', '.join(parts)}"
                    await log_system_message(
                        user_id=user_id,
                        text=msg_text,
                        meta={
                            "type": "admin_token_edit",
                            "subscription_token_balance": int(sub_tokens) if sub_tokens is not None else None,
                            "purchased_token_balance": int(pur_tokens) if pur_tokens is not None else None,
                        },
                    )
                except Exception as log_err:
                    logger.warning(f"Failed to log admin token edit system message: {log_err}")

        return web.json_response({"success": True})

    except ValueError as e:
        raise web.HTTPBadRequest(text=f"Invalid parameters: {e}")
    except web.HTTPBadRequest:
        raise
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error updating client billing: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def update_client_priority(request: web.Request) -> web.Response:
    """
    PATCH /api/admin/crm/clients/{id}/priority
    Обновить приоритет клиента.

    Body: {"priority": "low" | "normal" | "high" | "vip"}
    """
    try:
        user_id = int(request.match_info["id"])
        body = await request.json()

        priority = body.get("priority")
        if priority not in ('low', 'normal', 'high', 'vip'):
            raise web.HTTPBadRequest(text="Invalid priority")

        await client_crm_repo.update_client_priority(user_id, priority)
        return web.json_response({"success": True})

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid client ID")
    except web.HTTPBadRequest:
        raise
    except Exception as e:
        logger.error(f"Error updating priority: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def update_client_source(request: web.Request) -> web.Response:
    """
    PATCH /api/admin/crm/clients/{id}/source
    Обновить источник привлечения.

    Body: {"source": "string"}
    """
    try:
        user_id = int(request.match_info["id"])
        body = await request.json()

        source = body.get("source", "")
        await client_crm_repo.update_client_source(user_id, source)
        return web.json_response({"success": True})

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid client ID")
    except Exception as e:
        logger.error(f"Error updating source: {e}")
        raise web.HTTPInternalServerError(text="Database error")


# =============================================================================
# Кастомные поля
# =============================================================================

async def get_custom_fields(request: web.Request) -> web.Response:
    """
    GET /api/admin/crm/custom-fields
    Получить список всех определений кастомных полей.
    """
    try:
        fields = await client_crm_repo.get_custom_fields()
        return web.json_response([_serialize_dict(f) for f in fields])

    except Exception as e:
        logger.error(f"Error getting custom fields: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def create_custom_field(request: web.Request) -> web.Response:
    """
    POST /api/admin/crm/custom-fields
    Создать новое кастомное поле.

    Body: {
        "name": "string",
        "field_type": "text" | "number" | "date" | "checkbox" | "select" | "multiselect",
        "options": ["opt1", "opt2"],  // для select/multiselect
        "sort_order": 0,
        "is_required": false
    }
    """
    try:
        body = await request.json()

        name = body.get("name")
        field_type = body.get("field_type")

        if not name or not field_type:
            raise web.HTTPBadRequest(text="Missing name or field_type")

        valid_types = ('text', 'number', 'date', 'checkbox', 'select', 'multiselect')
        if field_type not in valid_types:
            raise web.HTTPBadRequest(text=f"Invalid field_type. Use: {', '.join(valid_types)}")

        field = await client_crm_repo.create_custom_field(
            name=name,
            field_type=field_type,
            options=body.get("options"),
            sort_order=body.get("sort_order", 0),
            is_required=body.get("is_required", False)
        )

        return web.json_response(_serialize_dict(field), status=201)

    except web.HTTPBadRequest:
        raise
    except Exception as e:
        logger.error(f"Error creating custom field: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def update_custom_field(request: web.Request) -> web.Response:
    """
    PUT /api/admin/crm/custom-fields/{id}
    Обновить кастомное поле.
    """
    try:
        field_id = int(request.match_info["id"])
        body = await request.json()

        field = await client_crm_repo.update_custom_field(
            field_id=field_id,
            name=body.get("name"),
            field_type=body.get("field_type"),
            options=body.get("options"),
            sort_order=body.get("sort_order"),
            is_required=body.get("is_required")
        )

        if not field:
            raise web.HTTPNotFound(text="Field not found")

        return web.json_response(_serialize_dict(field))

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid field ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error updating custom field: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def delete_custom_field(request: web.Request) -> web.Response:
    """
    DELETE /api/admin/crm/custom-fields/{id}
    Удалить кастомное поле.
    """
    try:
        field_id = int(request.match_info["id"])
        success = await client_crm_repo.delete_custom_field(field_id)

        if not success:
            raise web.HTTPNotFound(text="Field not found")

        return web.json_response({"success": True})

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid field ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error deleting custom field: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_client_field_values(request: web.Request) -> web.Response:
    """
    GET /api/admin/crm/clients/{id}/fields
    Получить значения кастомных полей клиента.
    """
    try:
        user_id = int(request.match_info["id"])
        values = await client_crm_repo.get_client_field_values(user_id)
        return web.json_response([_serialize_dict(v) for v in values])

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid client ID")
    except Exception as e:
        logger.error(f"Error getting client field values: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def update_client_field_values(request: web.Request) -> web.Response:
    """
    PUT /api/admin/crm/clients/{id}/fields
    Обновить значения кастомных полей клиента.

    Body: {
        "fields": {
            "1": "value for field 1",
            "2": 123,
            "3": ["opt1", "opt2"]
        }
    }
    """
    try:
        user_id = int(request.match_info["id"])
        body = await request.json()

        fields = body.get("fields", {})
        # Конвертируем ключи в int
        fields_int = {int(k): v for k, v in fields.items()}

        await client_crm_repo.set_client_fields_bulk(user_id, fields_int)
        return web.json_response({"success": True})

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid parameters")
    except Exception as e:
        logger.error(f"Error updating client field values: {e}")
        raise web.HTTPInternalServerError(text="Database error")


# =============================================================================
# Теги
# =============================================================================

async def get_tags(request: web.Request) -> web.Response:
    """
    GET /api/admin/crm/tags
    Получить все теги.
    """
    try:
        tags = await client_crm_repo.get_all_tags()
        return web.json_response([_serialize_dict(t) for t in tags])

    except Exception as e:
        logger.error(f"Error getting tags: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def create_tag(request: web.Request) -> web.Response:
    """
    POST /api/admin/crm/tags
    Создать новый тег.

    Body: {"name": "string", "color": "#RRGGBB"}
    """
    try:
        body = await request.json()

        name = body.get("name")
        if not name:
            raise web.HTTPBadRequest(text="Missing name")

        color = body.get("color", "#6B7280")

        tag = await client_crm_repo.create_tag(name=name, color=color)
        return web.json_response(_serialize_dict(tag), status=201)

    except web.HTTPBadRequest:
        raise
    except Exception as e:
        logger.error(f"Error creating tag: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def update_tag(request: web.Request) -> web.Response:
    """
    PUT /api/admin/crm/tags/{id}
    Обновить тег.
    """
    try:
        tag_id = int(request.match_info["id"])
        body = await request.json()

        tag = await client_crm_repo.update_tag(
            tag_id=tag_id,
            name=body.get("name"),
            color=body.get("color")
        )

        if not tag:
            raise web.HTTPNotFound(text="Tag not found")

        return web.json_response(_serialize_dict(tag))

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid tag ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error updating tag: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def delete_tag(request: web.Request) -> web.Response:
    """
    DELETE /api/admin/crm/tags/{id}
    Удалить тег.
    """
    try:
        tag_id = int(request.match_info["id"])
        success = await client_crm_repo.delete_tag(tag_id)

        if not success:
            raise web.HTTPNotFound(text="Tag not found")

        return web.json_response({"success": True})

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid tag ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error deleting tag: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_client_tags(request: web.Request) -> web.Response:
    """
    GET /api/admin/crm/clients/{id}/tags
    Получить теги клиента.
    """
    try:
        user_id = int(request.match_info["id"])
        tags = await client_crm_repo.get_client_tags(user_id)
        return web.json_response([_serialize_dict(t) for t in tags])

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid client ID")
    except Exception as e:
        logger.error(f"Error getting client tags: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def update_client_tags(request: web.Request) -> web.Response:
    """
    PUT /api/admin/crm/clients/{id}/tags
    Обновить теги клиента (полная замена).

    Body: {"tag_ids": [1, 2, 3]}
    """
    try:
        user_id = int(request.match_info["id"])
        body = await request.json()

        tag_ids = body.get("tag_ids", [])
        await client_crm_repo.set_client_tags(user_id, tag_ids)
        return web.json_response({"success": True})

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid parameters")
    except Exception as e:
        logger.error(f"Error updating client tags: {e}")
        raise web.HTTPInternalServerError(text="Database error")


# =============================================================================
# Задачи
# =============================================================================

async def get_client_tasks(request: web.Request) -> web.Response:
    """
    GET /api/admin/crm/clients/{id}/tasks
    Получить задачи клиента.

    Query: include_completed=true|false (default true)
    """
    try:
        user_id = int(request.match_info["id"])
        include_completed = request.query.get("include_completed", "true").lower() == "true"

        tasks = await client_crm_repo.get_client_tasks(user_id, include_completed)
        return web.json_response([_serialize_dict(t) for t in tasks])

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid client ID")
    except Exception as e:
        logger.error(f"Error getting client tasks: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def create_task(request: web.Request) -> web.Response:
    """
    POST /api/admin/crm/clients/{id}/tasks
    Создать задачу.

    Body: {
        "title": "string",
        "description": "string",
        "due_date": "2024-12-20T10:00:00",
        "priority": "low" | "medium" | "high",
        "assignee": "string",
        "reminder_at": "2024-12-19T10:00:00",
        "repeat_interval": "none" | "daily" | "weekly" | "monthly"
    }
    """
    try:
        user_id = int(request.match_info["id"])
        body = await request.json()

        title = body.get("title")
        if not title:
            raise web.HTTPBadRequest(text="Missing title")

        # Parse dates
        due_date = None
        if body.get("due_date"):
            due_date = datetime.fromisoformat(body["due_date"].replace("Z", "+00:00"))

        reminder_at = None
        if body.get("reminder_at"):
            reminder_at = datetime.fromisoformat(body["reminder_at"].replace("Z", "+00:00"))

        task = await client_crm_repo.create_task(
            user_id=user_id,
            title=title,
            description=body.get("description"),
            due_date=due_date,
            priority=body.get("priority", "medium"),
            assignee=body.get("assignee"),
            reminder_at=reminder_at,
            repeat_interval=body.get("repeat_interval")
        )

        return web.json_response(_serialize_dict(task), status=201)

    except ValueError as e:
        raise web.HTTPBadRequest(text=f"Invalid parameters: {e}")
    except web.HTTPBadRequest:
        raise
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_task(request: web.Request) -> web.Response:
    """
    GET /api/admin/crm/tasks/{id}
    Получить задачу по ID.
    """
    try:
        task_id = int(request.match_info["id"])
        task = await client_crm_repo.get_task_by_id(task_id)

        if not task:
            raise web.HTTPNotFound(text="Task not found")

        return web.json_response(_serialize_dict(task))

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid task ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error getting task: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def update_task(request: web.Request) -> web.Response:
    """
    PUT /api/admin/crm/tasks/{id}
    Обновить задачу.
    """
    try:
        task_id = int(request.match_info["id"])
        body = await request.json()

        # Parse dates
        due_date = None
        if "due_date" in body and body["due_date"]:
            due_date = datetime.fromisoformat(body["due_date"].replace("Z", "+00:00"))

        reminder_at = None
        if "reminder_at" in body and body["reminder_at"]:
            reminder_at = datetime.fromisoformat(body["reminder_at"].replace("Z", "+00:00"))

        task = await client_crm_repo.update_task(
            task_id=task_id,
            title=body.get("title"),
            description=body.get("description"),
            due_date=due_date,
            priority=body.get("priority"),
            status=body.get("status"),
            assignee=body.get("assignee"),
            reminder_at=reminder_at,
            repeat_interval=body.get("repeat_interval")
        )

        if not task:
            raise web.HTTPNotFound(text="Task not found")

        return web.json_response(_serialize_dict(task))

    except ValueError as e:
        raise web.HTTPBadRequest(text=f"Invalid parameters: {e}")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error updating task: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def delete_task(request: web.Request) -> web.Response:
    """
    DELETE /api/admin/crm/tasks/{id}
    Удалить задачу.
    """
    try:
        task_id = int(request.match_info["id"])
        success = await client_crm_repo.delete_task(task_id)

        if not success:
            raise web.HTTPNotFound(text="Task not found")

        return web.json_response({"success": True})

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid task ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error deleting task: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def complete_task(request: web.Request) -> web.Response:
    """
    POST /api/admin/crm/tasks/{id}/complete
    Завершить задачу.
    """
    try:
        task_id = int(request.match_info["id"])
        task = await client_crm_repo.complete_task(task_id)

        if not task:
            raise web.HTTPNotFound(text="Task not found")

        return web.json_response(_serialize_dict(task))

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid task ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error completing task: {e}")
        raise web.HTTPInternalServerError(text="Database error")


# =============================================================================
# Заметки
# =============================================================================

async def get_client_notes(request: web.Request) -> web.Response:
    """
    GET /api/admin/crm/clients/{id}/notes
    Получить заметки клиента.
    """
    try:
        user_id = int(request.match_info["id"])
        notes = await client_crm_repo.get_client_notes(user_id)
        return web.json_response([_serialize_dict(n) for n in notes])

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid client ID")
    except Exception as e:
        logger.error(f"Error getting client notes: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def create_note(request: web.Request) -> web.Response:
    """
    POST /api/admin/crm/clients/{id}/notes
    Создать заметку.

    Body: {"text": "string"}
    """
    try:
        user_id = int(request.match_info["id"])
        body = await request.json()

        text = body.get("text")
        if not text:
            raise web.HTTPBadRequest(text="Missing text")

        note = await client_crm_repo.create_note(user_id, text)
        return web.json_response(_serialize_dict(note), status=201)

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid client ID")
    except web.HTTPBadRequest:
        raise
    except Exception as e:
        logger.error(f"Error creating note: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def delete_note(request: web.Request) -> web.Response:
    """
    DELETE /api/admin/crm/notes/{id}
    Удалить заметку.
    """
    try:
        note_id = int(request.match_info["id"])
        success = await client_crm_repo.delete_note(note_id)

        if not success:
            raise web.HTTPNotFound(text="Note not found")

        return web.json_response({"success": True})

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid note ID")
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error deleting note: {e}")
        raise web.HTTPInternalServerError(text="Database error")


# =============================================================================
# Лента активности
# =============================================================================

async def get_client_activity(request: web.Request) -> web.Response:
    """
    GET /api/admin/crm/clients/{id}/activity
    Получить ленту активности клиента.

    Query:
        types: comma-separated (consultation,task_created,task_completed,note,status_change,tag_change)
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

        # Обрезаем длинные тексты в event_data (LEFT в SQL ломается на невалидных UTF-8)
        for item in activity:
            ed = item.get("event_data")
            if isinstance(ed, dict):
                if "text" in ed and isinstance(ed["text"], str) and len(ed["text"]) > 500:
                    ed["text"] = ed["text"][:500]
                if "first_question" in ed and isinstance(ed["first_question"], str) and len(ed["first_question"]) > 150:
                    ed["first_question"] = ed["first_question"][:150]

        return web.json_response([_serialize_dict(a) for a in activity])

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid parameters")
    except Exception as e:
        logger.error(f"Error getting client activity: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_client_chat_history(request: web.Request) -> web.Response:
    """
    GET /api/admin/crm/clients/{id}/chat
    Полная история чата пользователя (все сообщения со всех топиков).
    """
    try:
        user_id = int(request.match_info["id"])

        from src.services.db.messages_repo import get_user_chat_history
        result = await get_user_chat_history(user_id)

        return web.json_response(_serialize_dict(result))

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid user ID")
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        raise web.HTTPInternalServerError(text="Database error")


# =============================================================================
# Колонки воронки (Kanban columns)
# =============================================================================

async def get_funnel_columns(request: web.Request) -> web.Response:
    """
    GET /api/admin/crm/columns
    Получить все колонки воронки отсортированные по порядку.

    Returns: [
        {"id": "new", "title": "НЕРАЗОБРАННОЕ", "color": "#3B82F6", "sort_order": 0, "is_system": true},
        {"id": "custom_1", "title": "МОЯ КОЛОНКА", "color": "#EF4444", "sort_order": 4, "is_system": false},
        ...
    ]
    """
    try:
        columns = await client_funnel_repo.get_funnel_columns()
        return web.json_response([_serialize_dict(c) for c in columns])

    except Exception as e:
        logger.error(f"Error getting funnel columns: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def create_funnel_column(request: web.Request) -> web.Response:
    """
    POST /api/admin/crm/columns
    Создать новую кастомную колонку.

    Body: {
        "title": "string",
        "color": "#RRGGBB",
        "after_id": "new"  // ID колонки после которой вставить (опционально)
    }

    Returns: созданная колонка
    """
    try:
        body = await request.json()

        title = body.get("title", "НОВЫЙ ЭТАП")
        color = body.get("color", "#6B7280")
        after_id = body.get("after_id")

        # Получаем следующий ID
        column_id = await client_funnel_repo.get_next_custom_column_id()

        # Определяем sort_order
        columns = await client_funnel_repo.get_funnel_columns()
        if after_id:
            # Вставляем после указанной колонки
            after_idx = next((i for i, c in enumerate(columns) if c['id'] == after_id), len(columns) - 1)
            sort_order = after_idx + 1
            # Сдвигаем все последующие колонки
            for c in columns[sort_order:]:
                await client_funnel_repo.update_funnel_column(c['id'], sort_order=c['sort_order'] + 1)
        else:
            # Добавляем в конец
            sort_order = len(columns)

        column = await client_funnel_repo.create_funnel_column(
            column_id=column_id,
            title=title,
            color=color,
            sort_order=sort_order
        )

        return web.json_response(_serialize_dict(column), status=201)

    except Exception as e:
        logger.error(f"Error creating funnel column: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def update_funnel_column(request: web.Request) -> web.Response:
    """
    PUT /api/admin/crm/columns/{id}
    Обновить колонку воронки.

    Body: {
        "title": "string",
        "color": "#RRGGBB"
    }
    """
    try:
        column_id = request.match_info["id"]
        body = await request.json()

        column = await client_funnel_repo.update_funnel_column(
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
        logger.error(f"Error updating funnel column: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def delete_funnel_column(request: web.Request) -> web.Response:
    """
    DELETE /api/admin/crm/columns/{id}
    Удалить кастомную колонку.

    Системные колонки (new, tried, trial_ended, paid) удалить нельзя.
    Клиенты из удаляемой колонки перемещаются в 'new'.
    """
    try:
        column_id = request.match_info["id"]

        success = await client_funnel_repo.delete_funnel_column(column_id)

        if not success:
            raise web.HTTPBadRequest(text="Cannot delete system column or column not found")

        return web.json_response({"success": True})

    except web.HTTPBadRequest:
        raise
    except Exception as e:
        logger.error(f"Error deleting funnel column: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def get_client_referrals(request: web.Request) -> web.Response:
    """
    GET /api/admin/crm/clients/{id}/referrals
    Получить список приглашённых пользователей.
    """
    try:
        user_id = int(request.match_info["id"])
        from src.services.db.referral_repo import get_referrals_list
        referrals = await get_referrals_list(user_id)
        return web.json_response([_serialize_dict(r) for r in referrals])

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid client ID")
    except Exception as e:
        logger.error(f"Error getting client referrals: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def send_message_to_client(request: web.Request) -> web.Response:
    """
    POST /api/admin/crm/clients/{id}/send-message
    Отправить сообщение клиенту через Telegram из панели администратора.

    Body: {"text": "string"}
    Returns: {"success": true, "message_id": 123}
    """
    try:
        user_id = int(request.match_info["id"])
        body = await request.json()

        text = body.get("text", "").strip()
        if not text:
            raise web.HTTPBadRequest(text="Missing or empty 'text' field")
        if len(text) > 4096:
            raise web.HTTPBadRequest(text="Message too long (max 4096 chars)")

        # Получить telegram_user_id из БД
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT telegram_user_id FROM users WHERE id = $1",
                user_id
            )

        if not row:
            raise web.HTTPNotFound(text="Client not found")

        telegram_user_id = row["telegram_user_id"]

        # Отправить сообщение через бота
        from src.bot import get_bot
        bot = get_bot()
        await bot.send_message(chat_id=telegram_user_id, text=text)

        # Залогировать сообщение — SSE broadcast произойдёт автоматически
        from src.services.db.messages_repo import log_message
        msg_id = await log_message(
            user_id=user_id,
            direction="bot",
            text=text,
            session_id=f"admin:{user_id}",
            topic_id=None,
            meta={"source": "admin", "type": "manual"},
        )

        return web.json_response({"success": True, "message_id": msg_id})

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid client ID")
    except web.HTTPBadRequest:
        raise
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error sending message to client: {e}")
        raise web.HTTPInternalServerError(text=f"Failed to send message: {e}")


async def get_available_products(request: web.Request) -> web.Response:
    """
    GET /api/admin/crm/products
    Возвращает все доступные товары для отправки ссылки на оплату.
    """
    try:
        from src.services.db import subscription_plan_repo, token_package_repo
        from src.services.flagship.flagship_service import (
            get_available_products as get_flagships,
            load_product_config,
        )
        from src.pricing import COMPLEXITY_TIERS
        from src.services.quiz_solutions import _OFFER_HEADERS

        plans = await subscription_plan_repo.get_all_active()
        packages = await token_package_repo.get_all_active()
        flagships = get_flagships()
        guide_price = COMPLEXITY_TIERS["turnkey_solution"]["price_rub"]

        # Quiz plans — все 44 презентации из _OFFER_HEADERS
        quiz_plans = []
        for problem_key, (culture, problem) in _OFFER_HEADERS.items():
            quiz_plans.append({
                "problem_key": problem_key,
                "culture": culture,
                "problem": problem,
                "price_rub": 99,
            })

        # Single blocks — темы из flagship-конфигов
        single_blocks = []
        for fp in flagships:
            try:
                config = load_product_config(fp["product_key"])
                articles = [
                    {"key": a["key"], "title": a["title"]}
                    for a in config.get("articles", [])
                ]
                single_blocks.append({
                    "product_key": fp["product_key"],
                    "culture_title": config.get("title", fp["product_key"]),
                    "articles": articles,
                    "price_rub": 1990,
                })
            except FileNotFoundError:
                continue

        products = {
            "subscriptions": [
                {"id": p["id"], "name": p["name"], "price_rub": float(p["price_rub"]),
                 "tokens_included": p["tokens_included"], "duration_days": p["duration_days"]}
                for p in plans
            ],
            "token_packages": [
                {"id": p["id"], "name": p["name"], "price_rub": float(p["price_rub"]),
                 "tokens_amount": p["tokens_amount"]}
                for p in packages
            ],
            "guide": {"price_rub": float(guide_price)},
            "quiz_plan": {"price_rub": 99},
            "quiz_plans": quiz_plans,
            "single_blocks": single_blocks,
            "flagships": [
                {"product_key": f["product_key"], "title": f["title"],
                 "price_rub": float(f["price_rub"])}
                for f in flagships
            ],
        }
        return web.json_response(products)

    except Exception as e:
        logger.error(f"Error getting available products: {e}")
        raise web.HTTPInternalServerError(text="Failed to load products")


async def send_payment_link_to_client(request: web.Request) -> web.Response:
    """
    POST /api/admin/crm/clients/{id}/send-payment-link
    Создать платёж и отправить ссылку на оплату клиенту через Telegram.

    Body: {
        "product_type": "subscription" | "tokens" | "guide" | "quiz_plan" | "flagship" | "single_block",
        "product_id": int | str,
        "discount_percent": 0-100,
        "discount_duration_hours": int,
        "custom_message": "string"
    }
    """
    try:
        user_id = int(request.match_info["id"])
        body = await request.json()

        product_type = body.get("product_type", "")
        product_id = body.get("product_id")
        discount_percent = int(body.get("discount_percent", 0))
        discount_duration_hours = int(body.get("discount_duration_hours", 0))
        custom_message = body.get("custom_message", "").strip()
        send_quiz_after_payment = bool(body.get("send_quiz_after_payment", False))

        if product_type not in ("subscription", "tokens", "guide", "quiz_plan", "flagship", "single_block"):
            raise web.HTTPBadRequest(text=f"Invalid product_type: {product_type}")
        if discount_percent < 0 or discount_percent > 100:
            raise web.HTTPBadRequest(text="discount_percent must be 0-100")

        # Получить telegram_user_id
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT telegram_user_id FROM users WHERE id = $1", user_id
            )
        if not row:
            raise web.HTTPNotFound(text="Client not found")
        telegram_user_id = row["telegram_user_id"]

        # Импорты
        from src.services.payments.payment_service import (
            create_subscription_payment_custom,
            create_token_payment_custom,
            create_quiz_plan_payment,
            create_flagship_payment,
        )
        from src.services.payments import yookassa_client
        from src.services.db import payment_repo
        from src.config import settings

        product_name = ""
        original_price = 0
        payment_result = None
        is_free = (discount_percent == 100)

        if product_type == "subscription":
            from src.services.db import subscription_plan_repo
            plan = await subscription_plan_repo.get_by_id(int(product_id))
            if not plan:
                raise web.HTTPNotFound(text="Subscription plan not found")
            product_name = f"Подписка «{plan['name']}»"
            original_price = float(plan["price_rub"])
            final_price = 0 if is_free else max(round(original_price * (1 - discount_percent / 100)), 1)
            if is_free:
                from src.services.db import payment_repo as _payment_repo
                from src.services.payments.subscription_service import activate_subscription
                free_payment = await _payment_repo.create_free_grant(
                    user_id=user_id,
                    payment_type="subscription",
                    description=product_name,
                    subscription_plan_id=int(product_id),
                    metadata={"source": "admin_free_grant", "telegram_user_id": str(telegram_user_id)},
                )
                await activate_subscription(
                    user_id=user_id,
                    plan_id=int(product_id),
                    payment_id=free_payment["id"],
                )
                payment_result = {"payment_id": free_payment["id"], "confirmation_url": "", "amount": 0, "description": product_name}
            else:
                payment_result = await create_subscription_payment_custom(
                    user_id=user_id,
                    telegram_user_id=telegram_user_id,
                    plan_id=int(product_id),
                    custom_price=final_price if discount_percent > 0 else None,
                )

        elif product_type == "tokens":
            from src.services.db import token_package_repo
            package = await token_package_repo.get_by_id(int(product_id))
            if not package:
                raise web.HTTPNotFound(text="Token package not found")
            product_name = f"Пакет токенов: {package['tokens_amount']} шт."
            original_price = float(package["price_rub"])
            final_price = 0 if is_free else max(round(original_price * (1 - discount_percent / 100)), 1)
            if is_free:
                from src.services.db import payment_repo as _payment_repo
                from src.services.db.tokens_repo import add_purchased_tokens
                free_payment = await _payment_repo.create_free_grant(
                    user_id=user_id,
                    payment_type="tokens",
                    description=product_name,
                    token_package_id=int(product_id),
                    metadata={"source": "admin_free_grant", "telegram_user_id": str(telegram_user_id)},
                )
                await add_purchased_tokens(user_id=user_id, amount=package["tokens_amount"])
                payment_result = {"payment_id": free_payment["id"], "confirmation_url": "", "amount": 0, "description": product_name}
            else:
                payment_result = await create_token_payment_custom(
                    user_id=user_id,
                    telegram_user_id=telegram_user_id,
                    package_id=int(product_id),
                    custom_price=final_price if discount_percent > 0 else None,
                )

        elif product_type == "guide":
            from src.pricing import COMPLEXITY_TIERS
            original_price = float(COMPLEXITY_TIERS["turnkey_solution"]["price_rub"])
            product_name = "Готовое решение: уход под ключ на сезон"
            final_price = 0 if is_free else max(round(original_price * (1 - discount_percent / 100)), 1)

            if is_free:
                from src.services.db import payment_repo as _payment_repo
                from src.services.payments.payment_service import generate_guide_free
                free_payment = await _payment_repo.create_free_grant(
                    user_id=user_id,
                    payment_type="guide",
                    description=product_name,
                    metadata={"source": "admin_free_grant", "telegram_user_id": str(telegram_user_id)},
                )
                # Генерируем и отправляем готовое решение
                pool = get_pool()
                async with pool.acquire() as conn:
                    ctx_row = await conn.fetchrow(
                        "SELECT * FROM consultation_context WHERE user_id = $1 ORDER BY updated_at DESC LIMIT 1",
                        user_id,
                    )
                ctx_data = dict(ctx_row) if ctx_row else {}
                await generate_guide_free(
                    user_id=user_id,
                    telegram_user_id=telegram_user_id,
                    context=ctx_data,
                )
                payment_result = {"payment_id": free_payment["id"], "confirmation_url": "", "amount": 0, "description": product_name}
            else:
                # create_guide_payment не поддерживает custom price — создаём напрямую
                idempotency_key = f"guide_admin_{user_id}_{int(datetime.now().timestamp())}"
                description_text = product_name
                receipt_items = yookassa_client.create_receipt_items(
                    description=description_text,
                    amount_rub=Decimal(str(final_price)),
                    quantity=1,
                )
                metadata = {
                    "user_id": str(user_id),
                    "telegram_user_id": str(telegram_user_id),
                    "payment_type": "guide",
                    "source": "admin_payment_link",
                }
                if discount_percent > 0:
                    metadata["discount_percent"] = str(discount_percent)
                    metadata["original_price_rub"] = str(original_price)

                yookassa_payment = await yookassa_client.create_payment(
                    amount_rub=Decimal(str(final_price)),
                    description=description_text,
                    return_url=settings.YOOKASSA_RETURN_URL,
                    user_telegram_id=telegram_user_id,
                    receipt_items=receipt_items if settings.YOOKASSA_SEND_RECEIPT else None,
                    metadata=metadata,
                    idempotence_key=idempotency_key,
                )
                payment = await payment_repo.create_payment(
                    user_id=user_id,
                    yookassa_payment_id=yookassa_payment["id"],
                    idempotency_key=idempotency_key,
                    payment_type="guide",
                    amount_rub=float(final_price),
                    description=description_text,
                    confirmation_url=yookassa_payment["confirmation"]["confirmation_url"],
                    metadata=metadata,
                )
                from src.services.payments.payment_service import create_payment_activity_event
                await create_payment_activity_event(user_id, payment["id"])
                payment_result = {
                    "payment_id": payment["id"],
                    "confirmation_url": yookassa_payment["confirmation"]["confirmation_url"],
                    "amount": float(final_price),
                    "description": description_text,
                }

        elif product_type == "quiz_plan":
            from src.services.quiz_solutions import _OFFER_HEADERS as quiz_headers
            problem_key = str(product_id) if product_id else ""
            original_price = 99
            if problem_key and problem_key in quiz_headers:
                culture_name, problem_name = quiz_headers[problem_key]
                product_name = f"Презентация: {culture_name} — {problem_name}"
                culture_display = culture_name
                problem_display = problem_name
            else:
                product_name = "Персональный план"
                culture_display = "Персональный план"
                problem_display = "квиз-план"
            final_price = 0 if is_free else max(round(original_price * (1 - discount_percent / 100)), 1)
            if is_free:
                from src.services.db import payment_repo as _payment_repo
                free_meta = {"source": "admin_free_grant", "telegram_user_id": str(telegram_user_id), "problem_key": problem_key}
                if send_quiz_after_payment:
                    free_meta["trigger_upsell"] = "true"
                    free_meta["culture_display"] = culture_display
                    free_meta["problem_display"] = problem_display
                free_payment = await _payment_repo.create_free_grant(
                    user_id=user_id,
                    payment_type="quiz_plan",
                    description=product_name,
                    metadata=free_meta,
                )
                payment_result = {"payment_id": free_payment["id"], "confirmation_url": "", "amount": 0, "description": product_name}
            else:
                payment_result = await create_quiz_plan_payment(
                    user_id=user_id,
                    telegram_user_id=telegram_user_id,
                    culture_display=culture_display,
                    problem_display=problem_display,
                    problem_key=problem_key,
                    price_rub=float(final_price),
                    trigger_upsell=send_quiz_after_payment,
                )

        elif product_type == "single_block":
            from src.services.flagship.flagship_service import load_product_config as load_cfg
            block_id = str(product_id)  # формат: "strawberry_summer__nutrition"
            if "__" not in block_id:
                raise web.HTTPBadRequest(text="single_block product_id must be '{product_key}__{article_key}'")
            base_key, article_key = block_id.split("__", 1)
            try:
                config = load_cfg(base_key)
            except FileNotFoundError:
                raise web.HTTPNotFound(text=f"Flagship product not found: {base_key}")
            article = next((a for a in config.get("articles", []) if a["key"] == article_key), None)
            if not article:
                raise web.HTTPNotFound(text=f"Article not found: {article_key}")
            base_title = config.get("title", base_key)
            article_title = article["title"]
            product_name = f"{article_title} — {base_title}"
            original_price = 1990
            final_price = 0 if is_free else max(round(original_price * (1 - discount_percent / 100)), 1)
            if is_free:
                from src.services.db import payment_repo as _payment_repo
                from src.services.db import flagship_repo
                free_payment = await _payment_repo.create_free_grant(
                    user_id=user_id,
                    payment_type="flagship",
                    description=product_name,
                    metadata={"source": "admin_free_grant", "telegram_user_id": str(telegram_user_id), "product_key": block_id},
                )
                await flagship_repo.grant_access(user_id=user_id, product_key=block_id, payment_id=free_payment["id"], product_type="single_block")
                payment_result = {"payment_id": free_payment["id"], "confirmation_url": "", "amount": 0, "description": product_name}
            else:
                payment_result = await create_flagship_payment(
                    user_id=user_id,
                    telegram_user_id=telegram_user_id,
                    product_key=block_id,
                    product_title=product_name,
                    price_rub=Decimal(str(final_price)),
                    product_type="single_block",
                )

        elif product_type == "flagship":
            from src.services.flagship.flagship_service import load_product_config
            product_key = str(product_id)
            try:
                config = load_product_config(product_key)
            except FileNotFoundError:
                raise web.HTTPNotFound(text=f"Flagship product not found: {product_key}")
            product_name = config.get("title", product_key)
            original_price = float(config.get("price_rub", 0))
            final_price = 0 if is_free else max(round(original_price * (1 - discount_percent / 100)), 1)
            if is_free:
                from src.services.db import payment_repo as _payment_repo
                from src.services.db import flagship_repo
                free_payment = await _payment_repo.create_free_grant(
                    user_id=user_id,
                    payment_type="flagship",
                    description=product_name,
                    metadata={"source": "admin_free_grant", "telegram_user_id": str(telegram_user_id), "product_key": product_key},
                )
                await flagship_repo.grant_access(user_id=user_id, product_key=product_key, payment_id=free_payment["id"])
                payment_result = {"payment_id": free_payment["id"], "confirmation_url": "", "amount": 0, "description": product_name}
            else:
                payment_result = await create_flagship_payment(
                    user_id=user_id,
                    telegram_user_id=telegram_user_id,
                    product_key=product_key,
                    product_title=product_name,
                    price_rub=Decimal(str(final_price)),
                )

        # Сформировать текст сообщения
        final_price_actual = payment_result["amount"]

        def _build_price_text(orig: float, final: float, discount_pct: int, duration_hours: int) -> str:
            lines = []
            if discount_pct > 0:
                lines.append(f"<s>{int(orig)} ₽</s> → <b>{int(final)} ₽</b> (скидка {discount_pct}%)")
            else:
                lines.append(f"<b>{int(final)} ₽</b>")
            if duration_hours and duration_hours > 0:
                if duration_hours >= 24:
                    days = duration_hours // 24
                    hrs = duration_hours % 24
                    time_str = f"{days} дн." + (f" {hrs} ч." if hrs else "")
                else:
                    time_str = f"{duration_hours} ч."
                lines.append(f"Предложение действует: {time_str}")
            return "\n".join(lines)

        price_text = _build_price_text(original_price, final_price_actual, discount_percent, discount_duration_hours)
        message_text = f"<b>{product_name}</b>\n\n{price_text}"  # fallback

        from src.bot import get_bot
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
        bot = get_bot()

        if not is_free:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"💳 Оплатить {int(final_price_actual)} ₽",
                    url=payment_result["confirmation_url"],
                )]
            ])
        else:
            keyboard = None

        # Отправить custom_message первым (если есть)
        if custom_message:
            await bot.send_message(chat_id=telegram_user_id, text=custom_message, parse_mode="HTML")

        # Отправить оффер — с превью и описанием как в магазине
        if product_type == "quiz_plan" and problem_key:
            from src.services.quiz_solutions import get_quiz_solution, get_offer_text as get_file_offer
            from src.handlers.funnel_b import get_offer_keyboard, CONSULTATION_CONTEXT

            # Установить контекст для кнопки quiz_cta_payment
            ctx = CONSULTATION_CONTEXT.get(telegram_user_id, {})
            ctx["broadcast_quiz_price"] = 0 if is_free else final_price_actual
            ctx["broadcast_quiz_original_price"] = 490
            # При бесплатной CRM-выдаче пользователь мог не проходить квиз →
            # сохраняем данные в контекст чтобы handle_quiz_cta_payment мог их использовать
            if is_free and problem_key:
                ctx["crm_problem_key"] = problem_key
                ctx["crm_culture_display"] = culture_display
                ctx["crm_problem_display"] = problem_display
            if is_free and send_quiz_after_payment:
                ctx["crm_trigger_upsell"] = True
            CONSULTATION_CONTEXT[telegram_user_id] = ctx

            quiz_price_for_btn = 0 if is_free else int(final_price_actual)
            original_price_display = 490

            if is_free:
                offer_price_text = f"Обычно такой план стоит <s>{original_price_display} ₽</s>.\nДля Вас сегодня — <b>бесплатно</b>"
            elif discount_percent > 0:
                offer_price_text = f"Обычно такой план стоит <s>{original_price_display} ₽</s>.\nДля Вас сегодня — <b>{int(final_price_actual)} ₽</b>"
            else:
                offer_price_text = f"Обычно такой план стоит <s>{original_price_display} ₽</s>.\nДля Вас сегодня — <b>{int(final_price_actual)} ₽</b>"

            intro_text = get_file_offer(problem_key)
            if intro_text:
                await bot.send_message(chat_id=telegram_user_id, text=intro_text, parse_mode="HTML")

            solution = get_quiz_solution(problem_key)
            offer_keyboard = get_offer_keyboard(quiz_price=quiz_price_for_btn)

            if solution and solution.get("preview_path"):
                preview_photo = FSInputFile(solution["preview_path"])
                await bot.send_photo(
                    chat_id=telegram_user_id,
                    photo=preview_photo,
                    caption=offer_price_text,
                    parse_mode="HTML",
                    reply_markup=offer_keyboard,
                )
                message_text = offer_price_text
            else:
                await bot.send_message(
                    chat_id=telegram_user_id,
                    text=offer_price_text,
                    parse_mode="HTML",
                    reply_markup=offer_keyboard,
                )
                message_text = offer_price_text

        elif product_type == "single_block":
            content_lines = []
            if article.get("article_pdf"):
                content_lines.append("📝 Подробная статья с рекомендациями")
            if article.get("presentation_pdf"):
                content_lines.append("📊 Презентация со схемами")
            if article.get("video"):
                content_lines.append("🎥 Видео с практическими приёмами")
            content_text = "\n".join(content_lines)
            if is_free:
                message_text = (
                    f"✅ <b>{article_title}</b>\n"
                    f"<i>{base_title}</i>\n\n"
                    f"{content_text}\n\n"
                    f"Доступ открыт! Найдите материалы в «👤 Мой профиль» → «📂 Мои материалы»."
                )
            else:
                message_text = (
                    f"<b>{article_title}</b>\n"
                    f"<i>{base_title}</i>\n\n"
                    f"{content_text}\n\n"
                    f"Доступ <b>бессрочный</b>.\n\n"
                    f"{price_text}"
                )
            await bot.send_message(
                chat_id=telegram_user_id,
                text=message_text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )

        elif product_type == "flagship":
            articles_list = config.get("articles", [])
            categories = "\n".join(f"  • {a['title']}" for a in articles_list)
            has_video = any(a.get("video") for a in articles_list)
            if is_free:
                message_text = (
                    f"✅ <b>{product_name}</b>\n\n"
                    f"Полная система ухода на сезон:\n{categories}\n\n"
                    f"Доступ открыт! Найдите материалы в «👤 Мой профиль» → «📂 Мои материалы»."
                )
            else:
                message_text = (
                    f"<b>{product_name}</b>\n\n"
                    f"Полная система ухода на сезон:\n{categories}\n\n"
                    f"Каждый раздел включает:\n"
                    f"• Статью с рекомендациями\n"
                    f"• Презентацию с наглядными схемами\n"
                )
                if has_video:
                    message_text += "• Видео с практическими приёмами\n"
                message_text += f"\n+ 📅 Сезонный план работ по месяцам\n\nДоступ <b>бессрочный</b>.\n\n{price_text}"
            await bot.send_message(
                chat_id=telegram_user_id,
                text=message_text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )

        else:
            # subscription, tokens, guide
            if is_free:
                message_text = f"✅ <b>{product_name}</b>\n\nВыдано бесплатно!"
            else:
                message_text = f"<b>{product_name}</b>\n\n{price_text}"
            await bot.send_message(
                chat_id=telegram_user_id,
                text=message_text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )

        # Залогировать сообщение
        from src.services.db.messages_repo import log_message
        await log_message(
            user_id=user_id,
            direction="bot",
            text=message_text,
            session_id=f"admin:{user_id}",
            topic_id=None,
            meta={"source": "admin", "type": "payment_link", "product_type": product_type},
        )

        # Залогировать в activity feed
        try:
            await client_crm_repo.log_activity(
                user_id=user_id,
                event_type="payment_link_sent",
                event_data={
                    "product_type": product_type,
                    "product_name": product_name,
                    "original_price": original_price,
                    "final_price": final_price_actual,
                    "discount_percent": discount_percent,
                    "discount_duration_hours": discount_duration_hours,
                    "payment_id": payment_result.get("payment_id"),
                },
            )
        except Exception as e:
            logger.warning(f"Failed to log payment_link_sent activity: {e}")

        return web.json_response({
            "success": True,
            "payment_id": payment_result.get("payment_id"),
            "amount": final_price_actual,
        })

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid client ID")
    except web.HTTPBadRequest:
        raise
    except web.HTTPNotFound:
        raise
    except Exception as e:
        logger.error(f"Error sending payment link: {e}", exc_info=True)
        raise web.HTTPInternalServerError(text=f"Failed to send payment link: {e}")


async def reorder_funnel_columns(request: web.Request) -> web.Response:
    """
    PUT /api/admin/crm/columns/reorder
    Изменить порядок колонок воронки.

    Body: {
        "column_ids": ["new", "tried", "custom_1", "trial_ended", "paid"]
    }
    """
    try:
        body = await request.json()
        column_ids = body.get("column_ids", [])

        if not column_ids:
            raise web.HTTPBadRequest(text="Missing column_ids")

        await client_funnel_repo.reorder_funnel_columns(column_ids)

        return web.json_response({"success": True})

    except web.HTTPBadRequest:
        raise
    except Exception as e:
        logger.error(f"Error reordering funnel columns: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def update_client_funnel_variant(request: web.Request) -> web.Response:
    """
    PATCH /api/admin/crm/clients/{id}/funnel-variant
    Обновить вариант воронки (A/B) для клиента.
    Body: {"funnel_variant": "A"} или {"funnel_variant": "B"}
    """
    try:
        user_id = int(request.match_info["id"])
        data = await request.json()
        variant = data.get("funnel_variant", "").upper()

        if variant not in ("A", "B"):
            raise web.HTTPBadRequest(text="funnel_variant must be 'A' or 'B'")

        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET funnel_variant = $1 WHERE id = $2",
                variant, user_id
            )

        return web.json_response({"funnel_variant": variant})

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid client ID")
    except web.HTTPBadRequest:
        raise
    except Exception as e:
        logger.error(f"Error updating funnel_variant for {user_id}: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def update_client_quiz_answers(request: web.Request) -> web.Response:
    """
    PATCH /api/admin/crm/clients/{id}/quiz-answers
    Обновить ответы квиза клиента.
    Body: {"culture": "...", "region": "...", "problem": "..."}
    """
    try:
        user_id = int(request.match_info["id"])
        data = await request.json()

        culture = data.get("culture") or None
        region = data.get("region") or None
        problem = data.get("problem") or None

        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_quiz_answers (user_id, culture, region, problem)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id) DO UPDATE
                    SET culture = EXCLUDED.culture,
                        region = EXCLUDED.region,
                        problem = EXCLUDED.problem,
                        updated_at = NOW()
                """,
                user_id, culture, region, problem
            )

        return web.json_response({
            "quiz_culture": culture,
            "quiz_region": region,
            "quiz_problem": problem,
        })

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid client ID")
    except web.HTTPBadRequest:
        raise
    except Exception as e:
        logger.error(f"Error updating quiz answers for {user_id}: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def reset_client_quiz(request: web.Request) -> web.Response:
    """
    DELETE /api/admin/crm/clients/{id}/quiz-answers
    Сбросить ответы квиза — удалить запись из user_quiz_answers.
    При следующем /start пользователь пройдёт квиз заново.
    """
    try:
        user_id = int(request.match_info["id"])
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM user_quiz_answers WHERE user_id = $1",
                user_id
            )
        return web.json_response({"success": True})

    except ValueError:
        raise web.HTTPBadRequest(text="Invalid client ID")
    except Exception as e:
        logger.error(f"Error resetting quiz for {user_id}: {e}")
        raise web.HTTPInternalServerError(text="Database error")


async def delete_client(request: web.Request) -> web.Response:
    """
    DELETE /api/admin/crm/clients/{id}
    Полностью удаляет пользователя из БД (CASCADE на все связанные таблицы).
    При следующем /start он будет создан как новый пользователь.
    """
    try:
        user_id = int(request.match_info["id"])
        pool = get_pool()
        async with pool.acquire() as conn:
            # Получаем telegram_user_id перед удалением (для лога)
            row = await conn.fetchrow(
                "SELECT telegram_user_id FROM users WHERE id = $1",
                user_id,
            )
            if not row:
                raise web.HTTPNotFound(text="User not found")

            tg_id = row["telegram_user_id"]
            await conn.execute("DELETE FROM users WHERE id = $1", user_id)

        logger.info(f"Client {user_id} (tg:{tg_id}) deleted by admin")
        return web.json_response({"success": True})

    except web.HTTPNotFound:
        raise
    except ValueError:
        raise web.HTTPBadRequest(text="Invalid client ID")
    except Exception as e:
        logger.error(f"Error deleting client {request.match_info.get('id')}: {e}")
        raise web.HTTPInternalServerError(text="Database error")
