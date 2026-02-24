# src/services/db/funnel_repo.py

"""
Универсальный репозиторий для работы с воронками.

Единая система для всех типов воронок (CRM, Buyers, и кастомных).

Функции:
    - get_funnels: Список всех воронок
    - create_funnel: Создать новую воронку
    - update_funnel: Обновить воронку
    - delete_funnel: Удалить воронку (только не системные)

    - get_funnel_stages: Этапы воронки
    - create_stage: Создать этап
    - update_stage: Обновить этап
    - delete_stage: Удалить этап (только не системные)
    - reorder_stages: Переставить порядок этапов

    - get_clients_in_funnel: Клиенты в воронке (сгруппированы по этапам)
    - move_client_to_stage: Переместить клиента на другой этап
    - transfer_client: Переместить клиента в другую воронку
    - add_client_to_funnel: Добавить клиента в воронку
    - remove_client_from_funnel: Убрать клиента из воронки
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


def _serialize_row(row: dict) -> dict:
    """Convert datetime and Decimal objects for JSON serialization."""
    result = dict(row)
    for key, value in result.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, Decimal):
            result[key] = float(value)
    # Конвертируем avatar_path → avatar_url
    avatar_path = result.pop('avatar_path', None)
    result['avatar_url'] = f"/api/admin/avatars/{avatar_path}" if avatar_path else None
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# ВОРОНКИ (CRUD)
# ═══════════════════════════════════════════════════════════════════════════════

async def get_funnels() -> List[Dict[str, Any]]:
    """
    Получить список всех воронок.

    Возвращает воронки отсортированные по sort_order.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id, title, description, icon, sort_order, is_system,
                created_at, updated_at
            FROM funnels
            ORDER BY sort_order ASC, created_at ASC
            """
        )

        return [_serialize_row(row) for row in rows]


async def get_funnel_by_id(funnel_id: str) -> Optional[Dict[str, Any]]:
    """Получить воронку по ID."""
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                id, title, description, icon, sort_order, is_system,
                created_at, updated_at
            FROM funnels
            WHERE id = $1
            """,
            funnel_id
        )

        return _serialize_row(row) if row else None


async def create_funnel(
    funnel_id: str,
    title: str,
    description: str = None,
    icon: str = 'deals',
    stages: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Создать новую воронку с начальными этапами.

    Args:
        funnel_id: Уникальный ID (например 'support', 'partners')
        title: Название воронки
        description: Описание
        icon: Иконка для UI
        stages: Список начальных этапов [{stage_key, title, color}, ...]

    Returns:
        Созданная воронка
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Получаем следующий sort_order
            max_order = await conn.fetchval(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM funnels"
            )

            # Создаём воронку
            row = await conn.fetchrow(
                """
                INSERT INTO funnels (id, title, description, icon, sort_order, is_system)
                VALUES ($1, $2, $3, $4, $5, false)
                RETURNING id, title, description, icon, sort_order, is_system, created_at
                """,
                funnel_id,
                title,
                description,
                icon,
                max_order
            )

            funnel = dict(row)

            # Создаём начальные этапы
            if stages:
                for idx, stage in enumerate(stages):
                    await conn.execute(
                        """
                        INSERT INTO funnel_stages
                            (funnel_id, stage_key, title, color, sort_order, is_system)
                        VALUES ($1, $2, $3, $4, $5, false)
                        """,
                        funnel_id,
                        stage.get('stage_key', f'stage_{idx}'),
                        stage.get('title', f'Этап {idx + 1}'),
                        stage.get('color', '#6B7280'),
                        idx
                    )
            else:
                # Создаём дефолтный этап если не указаны
                await conn.execute(
                    """
                    INSERT INTO funnel_stages
                        (funnel_id, stage_key, title, color, sort_order, is_system)
                    VALUES ($1, 'new', 'Новые', '#3B82F6', 0, false)
                    """,
                    funnel_id
                )

            return funnel


async def update_funnel(
    funnel_id: str,
    title: str = None,
    description: str = None,
    icon: str = None
) -> Optional[Dict[str, Any]]:
    """
    Обновить воронку.

    Можно обновлять любые воронки, включая системные.
    """
    pool = get_pool()

    updates = []
    params = [funnel_id]
    param_idx = 2

    if title is not None:
        updates.append(f"title = ${param_idx}")
        params.append(title)
        param_idx += 1

    if description is not None:
        updates.append(f"description = ${param_idx}")
        params.append(description)
        param_idx += 1

    if icon is not None:
        updates.append(f"icon = ${param_idx}")
        params.append(icon)
        param_idx += 1

    if not updates:
        return await get_funnel_by_id(funnel_id)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE funnels
            SET {', '.join(updates)}
            WHERE id = $1
            RETURNING id, title, description, icon, sort_order, is_system, created_at, updated_at
            """,
            *params
        )

        return _serialize_row(row) if row else None


async def delete_funnel(funnel_id: str) -> bool:
    """
    Удалить воронку.

    Системные воронки (is_system = true) удалить нельзя.
    Клиенты в удалённой воронке остаются в системе, но без привязки к этой воронке.

    Returns:
        True если удалено, False если системная или не найдена
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        # Проверяем что воронка не системная
        is_system = await conn.fetchval(
            "SELECT is_system FROM funnels WHERE id = $1",
            funnel_id
        )

        if is_system is None:
            return False

        if is_system:
            logger.warning(f"Cannot delete system funnel: {funnel_id}")
            return False

        # Удаляем (каскадно удалятся этапы и позиции клиентов)
        result = await conn.execute(
            "DELETE FROM funnels WHERE id = $1 AND is_system = false",
            funnel_id
        )

        return result == "DELETE 1"


async def reorder_funnels(funnel_ids: List[str]) -> bool:
    """Изменить порядок воронок."""
    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            for idx, funnel_id in enumerate(funnel_ids):
                await conn.execute(
                    "UPDATE funnels SET sort_order = $2 WHERE id = $1",
                    funnel_id,
                    idx
                )

    return True


# ═══════════════════════════════════════════════════════════════════════════════
# ЭТАПЫ ВОРОНКИ (CRUD)
# ═══════════════════════════════════════════════════════════════════════════════

async def get_funnel_stages(funnel_id: str) -> List[Dict[str, Any]]:
    """
    Получить все этапы воронки отсортированные по порядку.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, funnel_id, stage_key, title, color, sort_order, is_system
            FROM funnel_stages
            WHERE funnel_id = $1
            ORDER BY sort_order ASC
            """,
            funnel_id
        )

        return [_serialize_row(row) for row in rows]


async def create_stage(
    funnel_id: str,
    stage_key: str,
    title: str,
    color: str = '#6B7280'
) -> Dict[str, Any]:
    """
    Создать новый этап в воронке.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        # Получаем следующий sort_order
        max_order = await conn.fetchval(
            """
            SELECT COALESCE(MAX(sort_order), -1) + 1
            FROM funnel_stages
            WHERE funnel_id = $1
            """,
            funnel_id
        )

        row = await conn.fetchrow(
            """
            INSERT INTO funnel_stages (funnel_id, stage_key, title, color, sort_order, is_system)
            VALUES ($1, $2, $3, $4, $5, false)
            RETURNING id, funnel_id, stage_key, title, color, sort_order, is_system
            """,
            funnel_id,
            stage_key,
            title,
            color,
            max_order
        )

        return dict(row)


async def update_stage(
    funnel_id: str,
    stage_key: str,
    title: str = None,
    color: str = None
) -> Optional[Dict[str, Any]]:
    """
    Обновить этап воронки (название, цвет).

    Можно обновлять и системные этапы.
    """
    pool = get_pool()

    updates = []
    params = [funnel_id, stage_key]
    param_idx = 3

    if title is not None:
        updates.append(f"title = ${param_idx}")
        params.append(title)
        param_idx += 1

    if color is not None:
        updates.append(f"color = ${param_idx}")
        params.append(color)
        param_idx += 1

    if not updates:
        return None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE funnel_stages
            SET {', '.join(updates)}
            WHERE funnel_id = $1 AND stage_key = $2
            RETURNING id, funnel_id, stage_key, title, color, sort_order, is_system
            """,
            *params
        )

        return _serialize_row(row) if row else None


async def delete_stage(funnel_id: str, stage_key: str) -> bool:
    """
    Удалить этап воронки.

    Системные этапы удалить нельзя.
    Клиенты на удалённом этапе перемещаются на первый этап воронки.

    Returns:
        True если удалено
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Проверяем что этап не системный
            is_system = await conn.fetchval(
                """
                SELECT is_system FROM funnel_stages
                WHERE funnel_id = $1 AND stage_key = $2
                """,
                funnel_id,
                stage_key
            )

            if is_system is None:
                return False

            if is_system:
                logger.warning(f"Cannot delete system stage: {funnel_id}/{stage_key}")
                return False

            # Находим первый этап для перемещения клиентов
            first_stage = await conn.fetchval(
                """
                SELECT stage_key FROM funnel_stages
                WHERE funnel_id = $1 AND stage_key != $2
                ORDER BY sort_order ASC
                LIMIT 1
                """,
                funnel_id,
                stage_key
            )

            if first_stage:
                # Отменяем pending-триггеры для всех пользователей на удаляемом этапе
                from src.services.db.funnel_trigger_repo import delete_pending_triggers_for_deleted_stage
                await delete_pending_triggers_for_deleted_stage(funnel_id, stage_key, conn)

                # Перемещаем клиентов на первый этап
                await conn.execute(
                    """
                    UPDATE client_funnel_position
                    SET stage_key = $3, manual_override = true
                    WHERE funnel_id = $1 AND stage_key = $2
                    """,
                    funnel_id,
                    stage_key,
                    first_stage
                )

            # Удаляем этап
            result = await conn.execute(
                """
                DELETE FROM funnel_stages
                WHERE funnel_id = $1 AND stage_key = $2 AND is_system = false
                """,
                funnel_id,
                stage_key
            )

            return result == "DELETE 1"


async def reorder_stages(funnel_id: str, stage_keys: List[str]) -> bool:
    """Изменить порядок этапов воронки."""
    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            for idx, stage_key in enumerate(stage_keys):
                await conn.execute(
                    """
                    UPDATE funnel_stages
                    SET sort_order = $3
                    WHERE funnel_id = $1 AND stage_key = $2
                    """,
                    funnel_id,
                    stage_key,
                    idx
                )

    return True


async def get_next_stage_key(funnel_id: str) -> str:
    """
    Получить следующий доступный ключ для кастомного этапа.

    Returns:
        Ключ в формате 'custom_N'
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        max_num = await conn.fetchval(
            """
            SELECT MAX(
                CAST(SUBSTRING(stage_key FROM 'custom_([0-9]+)') AS INTEGER)
            )
            FROM funnel_stages
            WHERE funnel_id = $1 AND stage_key LIKE 'custom_%'
            """,
            funnel_id
        )

        next_num = (max_num or 0) + 1
        return f"custom_{next_num}"


# ═══════════════════════════════════════════════════════════════════════════════
# КЛИЕНТЫ В ВОРОНКЕ
# ═══════════════════════════════════════════════════════════════════════════════

async def get_clients_in_funnel(funnel_id: str, invite_link_id: Optional[int] = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Получить клиентов в воронке, сгруппированных по этапам.

    Для CRM-воронки автоматически включает пользователей без записи
    в client_funnel_position (новые пользователи, не попавшие в воронку).

    invite_link_id: если задан — показывать только клиентов из этой кампании.

    Возвращает словарь: {'new': [...], 'tried': [...], ...}
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        # Получаем все этапы
        stages = await get_funnel_stages(funnel_id)

        # Для CRM: автоматически добавляем пользователей без позиции в воронке
        # Исключаем бота (telegram_user_id = ID из BOT_TOKEN)
        if funnel_id == 'crm':
            bot_tg_id = None
            try:
                from src.config import get_settings
                bot_tg_id = int(get_settings().telegram_bot_token.split(":")[0])
            except Exception:
                pass

            await conn.execute(
                """
                INSERT INTO client_funnel_position (user_id, funnel_id, stage_key)
                SELECT u.id, 'crm', 'new'
                FROM users u
                WHERE NOT EXISTS (
                    SELECT 1 FROM client_funnel_position cfp
                    WHERE cfp.user_id = u.id
                )
                AND u.telegram_user_id != $1
                """,
                bot_tg_id or 0
            )

        # Базовый запрос — с опциональным фильтром по инвайт-ссылке
        if invite_link_id:
            rows = await conn.fetch(
                """
                SELECT
                    u.id,
                    u.telegram_user_id,
                    u.username,
                    u.first_name,
                    u.last_name,
                    u.avatar_path,
                    u.created_at as user_created_at,
                    COALESCE(u.token_balance, 0) as token_balance,
                    cfp.stage_key as status,
                    cfp.manual_override,
                    cfp.entered_at,
                    cfp.updated_at as status_updated_at,
                    COALESCE(stats.total_consultations, 0) as total_consultations,
                    COALESCE(stats.total_tokens, 0) as total_tokens,
                    COALESCE(stats.total_cost_usd, 0.0) as total_cost_usd,
                    stats.last_consultation_at,
                    sub_info.subscription_plan_name,
                    sub_info.subscription_status,
                    sub_info.subscription_expires_at
                FROM client_funnel_position cfp
                JOIN users u ON u.id = cfp.user_id
                JOIN invite_link_users ilu ON ilu.user_id = u.id AND ilu.invite_link_id = $2
                LEFT JOIN LATERAL (
                    SELECT
                        COUNT(*)::int as total_consultations,
                        COALESCE(SUM(total_tokens), 0)::int as total_tokens,
                        COALESCE(SUM(cost_usd), 0.0) as total_cost_usd,
                        MAX(created_at) as last_consultation_at
                    FROM consultation_logs cl
                    WHERE cl.user_id = u.id
                ) stats ON true
                LEFT JOIN LATERAL (
                    SELECT
                        sp.name as subscription_plan_name,
                        us.status as subscription_status,
                        us.expires_at as subscription_expires_at
                    FROM user_subscriptions us
                    JOIN subscription_plans sp ON sp.id = us.subscription_plan_id
                    WHERE us.user_id = u.id
                    ORDER BY us.created_at DESC
                    LIMIT 1
                ) sub_info ON true
                WHERE cfp.funnel_id = $1
                ORDER BY stats.last_consultation_at DESC NULLS LAST, cfp.entered_at DESC
                """,
                funnel_id, invite_link_id
            )
        else:
            rows = await conn.fetch(
                """
                SELECT
                    u.id,
                    u.telegram_user_id,
                    u.username,
                    u.first_name,
                    u.last_name,
                    u.avatar_path,
                    u.created_at as user_created_at,
                    COALESCE(u.token_balance, 0) as token_balance,
                    cfp.stage_key as status,
                    cfp.manual_override,
                    cfp.entered_at,
                    cfp.updated_at as status_updated_at,
                    COALESCE(stats.total_consultations, 0) as total_consultations,
                    COALESCE(stats.total_tokens, 0) as total_tokens,
                    COALESCE(stats.total_cost_usd, 0.0) as total_cost_usd,
                    stats.last_consultation_at,
                    sub_info.subscription_plan_name,
                    sub_info.subscription_status,
                    sub_info.subscription_expires_at
                FROM client_funnel_position cfp
                JOIN users u ON u.id = cfp.user_id
                LEFT JOIN LATERAL (
                    SELECT
                        COUNT(*)::int as total_consultations,
                        COALESCE(SUM(total_tokens), 0)::int as total_tokens,
                        COALESCE(SUM(cost_usd), 0.0) as total_cost_usd,
                        MAX(created_at) as last_consultation_at
                    FROM consultation_logs cl
                    WHERE cl.user_id = u.id
                ) stats ON true
                LEFT JOIN LATERAL (
                    SELECT
                        sp.name as subscription_plan_name,
                        us.status as subscription_status,
                        us.expires_at as subscription_expires_at
                    FROM user_subscriptions us
                    JOIN subscription_plans sp ON sp.id = us.subscription_plan_id
                    WHERE us.user_id = u.id
                    ORDER BY us.created_at DESC
                    LIMIT 1
                ) sub_info ON true
                WHERE cfp.funnel_id = $1
                ORDER BY stats.last_consultation_at DESC NULLS LAST, cfp.entered_at DESC
                """,
                funnel_id
            )

        # Группируем по этапам
        grouped = {stage['stage_key']: [] for stage in stages}

        for row in rows:
            client = _serialize_row(row)
            stage_key = client.get('status')
            if stage_key in grouped:
                grouped[stage_key].append(client)
            elif stages:
                # Неизвестный этап — кладём в первый
                first_stage = stages[0]['stage_key']
                grouped[first_stage].append(client)

        return grouped


async def get_funnel_stats(funnel_id: str) -> Dict[str, int]:
    """
    Получить количество клиентов на каждом этапе воронки.
    """
    pool = get_pool()

    stages = await get_funnel_stages(funnel_id)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT stage_key, COUNT(*)::int as count
            FROM client_funnel_position
            WHERE funnel_id = $1
            GROUP BY stage_key
            """,
            funnel_id
        )

        # Инициализируем все этапы нулями
        stats = {stage['stage_key']: 0 for stage in stages}

        for row in rows:
            stage_key = row['stage_key']
            if stage_key in stats:
                stats[stage_key] = row['count']

        return stats


async def move_client_to_stage(
    user_id: int,
    funnel_id: str,
    new_stage_key: str
) -> bool:
    """
    Переместить клиента на другой этап внутри воронки (drag-and-drop).

    Устанавливает manual_override = true.
    """
    pool = get_pool()

    # Проверяем что этап существует
    stages = await get_funnel_stages(funnel_id)
    valid_keys = [s['stage_key'] for s in stages]

    if new_stage_key not in valid_keys:
        logger.warning(f"Invalid stage key: {new_stage_key}")
        return False

    async with pool.acquire() as conn:
        # Получаем текущий этап для SSE
        old_stage_key = await conn.fetchval(
            """
            SELECT stage_key FROM client_funnel_position
            WHERE user_id = $1 AND funnel_id = $2
            """,
            user_id,
            funnel_id
        )

        # Отменяем pending-триггеры старого этапа перед перемещением
        if old_stage_key and old_stage_key != new_stage_key:
            from src.services.db.funnel_trigger_repo import delete_pending_triggers_for_stage
            await delete_pending_triggers_for_stage(user_id, funnel_id, old_stage_key)

        result = await conn.execute(
            """
            UPDATE client_funnel_position
            SET stage_key = $3, manual_override = true, updated_at = NOW()
            WHERE user_id = $1 AND funnel_id = $2
            """,
            user_id,
            funnel_id,
            new_stage_key
        )

        success = result == "UPDATE 1"

        # Получаем telegram_user_id для триггеров
        telegram_user_id = None
        if success:
            tg_row = await conn.fetchrow(
                "SELECT telegram_user_id FROM users WHERE id = $1",
                user_id,
            )
            telegram_user_id = tg_row['telegram_user_id'] if tg_row else None

        if success:
            try:
                from src.api.sse_manager import sse_manager
                await sse_manager.broadcast(
                    event_type='client_moved',
                    data={
                        'user_id': user_id,
                        'from_stage': old_stage_key,
                        'to_stage': new_stage_key,
                    },
                    endpoint_type=f'funnel-{funnel_id}'
                )
            except Exception as e:
                logger.warning(f"Failed to broadcast SSE client_moved: {e}")

            # Запускаем триггеры в фоне (не блокируя ответ)
            if telegram_user_id:
                try:
                    import asyncio
                    from src.services.funnel_trigger_sender import execute_stage_triggers
                    asyncio.create_task(
                        execute_stage_triggers(user_id, telegram_user_id, funnel_id, new_stage_key)
                    )
                except Exception as e:
                    logger.warning(f"Failed to launch stage triggers: {e}")

        return success


# Порядок системных стадий CRM-воронки (для авто-переходов)
CRM_STAGE_ORDER = {'new': 0, 'tried': 1, 'trial_ended': 2, 'paid': 3}


async def auto_move_client_in_crm(user_id: int, target_stage_key: str) -> bool:
    """
    Автоматически переместить клиента на этап CRM-воронки.

    Отличия от move_client_to_stage():
      - НЕ ставит manual_override=true (чтобы будущие авто-переходы работали)
      - Двигает только вперёд (по CRM_STAGE_ORDER)
      - Создаёт запись в client_funnel_position если её нет

    Возвращает True если перемещение произошло.
    """
    target_order = CRM_STAGE_ORDER.get(target_stage_key)
    if target_order is None:
        logger.warning(f"auto_move_client_in_crm: unknown target stage {target_stage_key}")
        return False

    pool = get_pool()

    async with pool.acquire() as conn:
        # Получаем текущую позицию
        row = await conn.fetchrow(
            """
            SELECT stage_key
            FROM client_funnel_position
            WHERE user_id = $1 AND funnel_id = 'crm'
            """,
            user_id,
        )

        if row is None:
            # Пользователь ещё не в воронке — создаём запись со stage 'new'
            await conn.execute(
                """
                INSERT INTO client_funnel_position (user_id, funnel_id, stage_key)
                VALUES ($1, 'crm', 'new')
                ON CONFLICT (user_id, funnel_id) DO NOTHING
                """,
                user_id,
            )
            current_stage = 'new'
        else:
            current_stage = row['stage_key']

        # Уже на этой стадии или дальше — не трогаем
        current_order = CRM_STAGE_ORDER.get(current_stage, -1)
        if current_order >= target_order:
            logger.debug(
                f"auto_move skip user {user_id}: {current_stage}({current_order}) >= {target_stage_key}({target_order})"
            )
            return False

        # Отменяем pending-триггеры текущего этапа перед перемещением
        from src.services.db.funnel_trigger_repo import delete_pending_triggers_for_stage
        await delete_pending_triggers_for_stage(user_id, 'crm', current_stage)

        # Перемещаем (manual_override остаётся false)
        await conn.execute(
            """
            UPDATE client_funnel_position
            SET stage_key = $2, updated_at = NOW()
            WHERE user_id = $1 AND funnel_id = 'crm'
            """,
            user_id,
            target_stage_key,
        )

        # Получаем telegram_user_id для триггеров
        tg_row = await conn.fetchrow(
            "SELECT telegram_user_id FROM users WHERE id = $1",
            user_id,
        )
        telegram_user_id = tg_row['telegram_user_id'] if tg_row else None

    # SSE — уведомляем админку
    try:
        from src.api.sse_manager import sse_manager
        await sse_manager.broadcast(
            event_type='client_moved',
            data={
                'user_id': user_id,
                'from_stage': current_stage,
                'to_stage': target_stage_key,
            },
            endpoint_type='funnel-crm',
        )
    except Exception as e:
        logger.warning(f"auto_move SSE broadcast failed: {e}")

    # Триггеры в фоне
    if telegram_user_id:
        try:
            import asyncio
            from src.services.funnel_trigger_sender import execute_stage_triggers
            asyncio.create_task(
                execute_stage_triggers(user_id, telegram_user_id, 'crm', target_stage_key)
            )
        except Exception as e:
            logger.warning(f"auto_move triggers failed: {e}")

    logger.info(f"auto_move user {user_id}: {current_stage} -> {target_stage_key}")
    return True


async def transfer_client(
    user_id: int,
    from_funnel_id: str,
    to_funnel_id: str,
    to_stage_key: str = None
) -> bool:
    """
    Переместить клиента из одной воронки в другую.

    Args:
        user_id: ID пользователя
        from_funnel_id: Исходная воронка
        to_funnel_id: Целевая воронка
        to_stage_key: Этап в целевой воронке (если не указан — первый этап)

    Returns:
        True если успешно
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Если этап не указан, берём первый
            if to_stage_key is None:
                to_stage_key = await conn.fetchval(
                    """
                    SELECT stage_key FROM funnel_stages
                    WHERE funnel_id = $1
                    ORDER BY sort_order ASC
                    LIMIT 1
                    """,
                    to_funnel_id
                )

                if not to_stage_key:
                    logger.error(f"No stages found in funnel: {to_funnel_id}")
                    return False

            # Отменяем все pending-триггеры в исходной воронке
            from src.services.db.funnel_trigger_repo import delete_all_pending_triggers_for_funnel
            await delete_all_pending_triggers_for_funnel(user_id, from_funnel_id)

            # Удаляем из исходной воронки
            await conn.execute(
                """
                DELETE FROM client_funnel_position
                WHERE user_id = $1 AND funnel_id = $2
                """,
                user_id,
                from_funnel_id
            )

            # Если переносим из CRM, также удаляем из legacy таблицы
            if from_funnel_id == 'crm':
                await conn.execute(
                    """
                    DELETE FROM client_funnel_status
                    WHERE user_id = $1
                    """,
                    user_id
                )

            # Добавляем в целевую воронку
            await conn.execute(
                """
                INSERT INTO client_funnel_position
                    (user_id, funnel_id, stage_key, manual_override)
                VALUES ($1, $2, $3, true)
                ON CONFLICT (user_id, funnel_id)
                DO UPDATE SET stage_key = $3, manual_override = true, updated_at = NOW()
                """,
                user_id,
                to_funnel_id,
                to_stage_key
            )

            # Логируем событие
            await conn.execute(
                """
                INSERT INTO client_activity_log (user_id, event_type, event_data)
                VALUES ($1, 'funnel_transfer', $2::jsonb)
                """,
                user_id,
                f'{{"from_funnel": "{from_funnel_id}", "to_funnel": "{to_funnel_id}", "to_stage": "{to_stage_key}"}}'
            )

            # SSE broadcast для обеих воронок
            try:
                from src.api.sse_manager import sse_manager
                await sse_manager.broadcast(
                    event_type='client_removed',
                    data={'user_id': user_id},
                    endpoint_type=f'funnel-{from_funnel_id}'
                )
                await sse_manager.broadcast(
                    event_type='client_added',
                    data={'user_id': user_id, 'stage_key': to_stage_key},
                    endpoint_type=f'funnel-{to_funnel_id}'
                )
            except Exception as e:
                logger.warning(f"Failed to broadcast SSE transfer: {e}")

            return True


async def add_client_to_funnel(
    user_id: int,
    funnel_id: str,
    stage_key: str = None
) -> bool:
    """
    Добавить клиента в воронку.

    Если клиент уже в этой воронке — ничего не происходит.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        # Если этап не указан, берём первый
        if stage_key is None:
            stage_key = await conn.fetchval(
                """
                SELECT stage_key FROM funnel_stages
                WHERE funnel_id = $1
                ORDER BY sort_order ASC
                LIMIT 1
                """,
                funnel_id
            )

        if not stage_key:
            return False

        result = await conn.execute(
            """
            INSERT INTO client_funnel_position (user_id, funnel_id, stage_key)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, funnel_id) DO NOTHING
            """,
            user_id,
            funnel_id,
            stage_key
        )

        return "INSERT" in result


async def remove_client_from_funnel(user_id: int, funnel_id: str) -> bool:
    """Убрать клиента из воронки."""
    pool = get_pool()

    async with pool.acquire() as conn:
        deleted = False

        result = await conn.execute(
            """
            DELETE FROM client_funnel_position
            WHERE user_id = $1 AND funnel_id = $2
            """,
            user_id,
            funnel_id
        )
        if result == "DELETE 1":
            deleted = True

        # Если удаляем из CRM, также удаляем из legacy таблицы
        if funnel_id == 'crm':
            legacy_result = await conn.execute(
                """
                DELETE FROM client_funnel_status
                WHERE user_id = $1
                """,
                user_id
            )
            if legacy_result == "DELETE 1":
                deleted = True

        if deleted:
            try:
                from src.api.sse_manager import sse_manager
                await sse_manager.broadcast(
                    event_type='client_removed',
                    data={'user_id': user_id},
                    endpoint_type=f'funnel-{funnel_id}'
                )
            except Exception as e:
                logger.warning(f"Failed to broadcast SSE client_removed: {e}")

        return deleted


async def get_client_funnels(user_id: int) -> List[Dict[str, Any]]:
    """
    Получить список воронок, в которых находится клиент.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                f.id as funnel_id,
                f.title as funnel_title,
                cfp.stage_key,
                fs.title as stage_title,
                cfp.entered_at,
                cfp.updated_at
            FROM client_funnel_position cfp
            JOIN funnels f ON f.id = cfp.funnel_id
            LEFT JOIN funnel_stages fs ON fs.funnel_id = cfp.funnel_id AND fs.stage_key = cfp.stage_key
            WHERE cfp.user_id = $1
            ORDER BY f.sort_order ASC
            """,
            user_id
        )

        return [_serialize_row(row) for row in rows]
