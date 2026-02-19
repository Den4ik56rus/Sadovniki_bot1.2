# src/services/db/client_crm_repo.py

"""
Репозиторий для расширенной карточки клиента CRM.

Функции:
    - Кастомные поля: CRUD для определений и значений
    - Теги: CRUD для тегов и привязок к клиентам
    - Задачи: CRUD для задач по клиентам
    - Заметки: CRUD для заметок
    - Лента активности: получение событий с фильтрацией
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
import json

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


# =============================================================================
# Кастомные поля — определения
# =============================================================================

async def get_custom_fields() -> List[Dict[str, Any]]:
    """Получить все определения кастомных полей."""
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, field_type, options, sort_order, is_required, created_at
            FROM client_custom_fields
            ORDER BY sort_order, id
            """
        )
        return [dict(row) for row in rows]


async def create_custom_field(
    name: str,
    field_type: str,
    options: Optional[List[str]] = None,
    sort_order: int = 0,
    is_required: bool = False
) -> Dict[str, Any]:
    """Создать новое кастомное поле."""
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO client_custom_fields (name, field_type, options, sort_order, is_required)
            VALUES ($1, $2, $3::jsonb, $4, $5)
            RETURNING id, name, field_type, options, sort_order, is_required, created_at
            """,
            name,
            field_type,
            json.dumps(options) if options else None,
            sort_order,
            is_required
        )
        return dict(row)


async def update_custom_field(
    field_id: int,
    name: Optional[str] = None,
    field_type: Optional[str] = None,
    options: Optional[List[str]] = None,
    sort_order: Optional[int] = None,
    is_required: Optional[bool] = None
) -> Optional[Dict[str, Any]]:
    """Обновить кастомное поле."""
    pool = get_pool()

    updates = []
    params = [field_id]
    param_idx = 2

    if name is not None:
        updates.append(f"name = ${param_idx}")
        params.append(name)
        param_idx += 1

    if field_type is not None:
        updates.append(f"field_type = ${param_idx}")
        params.append(field_type)
        param_idx += 1

    if options is not None:
        updates.append(f"options = ${param_idx}")
        params.append(json.dumps(options))
        param_idx += 1

    if sort_order is not None:
        updates.append(f"sort_order = ${param_idx}")
        params.append(sort_order)
        param_idx += 1

    if is_required is not None:
        updates.append(f"is_required = ${param_idx}")
        params.append(is_required)
        param_idx += 1

    if not updates:
        return None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE client_custom_fields
            SET {', '.join(updates)}
            WHERE id = $1
            RETURNING id, name, field_type, options, sort_order, is_required, created_at
            """,
            *params
        )
        return dict(row) if row else None


async def delete_custom_field(field_id: int) -> bool:
    """Удалить кастомное поле и все его значения."""
    pool = get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM client_custom_fields WHERE id = $1",
            field_id
        )
        return result == "DELETE 1"


# =============================================================================
# Кастомные поля — значения
# =============================================================================

async def get_client_field_values(user_id: int) -> List[Dict[str, Any]]:
    """Получить все значения кастомных полей для клиента."""
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                cf.id as field_id,
                cf.name,
                cf.field_type,
                cf.options,
                cf.is_required,
                cfv.value_text,
                cfv.value_number,
                cfv.value_date,
                cfv.value_bool,
                cfv.value_json
            FROM client_custom_fields cf
            LEFT JOIN client_custom_field_values cfv
                ON cfv.field_id = cf.id AND cfv.user_id = $1
            ORDER BY cf.sort_order, cf.id
            """,
            user_id
        )

        result = []
        for row in rows:
            field = dict(row)
            # Определяем актуальное значение в зависимости от типа
            field_type = field['field_type']
            if field_type == 'text':
                field['value'] = field['value_text']
            elif field_type == 'number':
                field['value'] = float(field['value_number']) if field['value_number'] else None
            elif field_type == 'date':
                field['value'] = field['value_date'].isoformat() if field['value_date'] else None
            elif field_type == 'checkbox':
                field['value'] = field['value_bool']
            elif field_type in ('select', 'multiselect'):
                field['value'] = field['value_json']
            else:
                field['value'] = None

            # Убираем отдельные value_* поля
            del field['value_text']
            del field['value_number']
            del field['value_date']
            del field['value_bool']
            del field['value_json']

            result.append(field)

        return result


async def set_client_field_value(
    user_id: int,
    field_id: int,
    value: Any
) -> bool:
    """Установить значение кастомного поля для клиента."""
    pool = get_pool()

    async with pool.acquire() as conn:
        # Получаем тип поля
        field_type = await conn.fetchval(
            "SELECT field_type FROM client_custom_fields WHERE id = $1",
            field_id
        )

        if not field_type:
            return False

        # Подготавливаем значения в зависимости от типа
        value_text = None
        value_number = None
        value_date = None
        value_bool = None
        value_json = None

        if value is not None:
            if field_type == 'text':
                value_text = str(value)
            elif field_type == 'number':
                value_number = Decimal(str(value))
            elif field_type == 'date':
                if isinstance(value, str):
                    value_date = date.fromisoformat(value)
                elif isinstance(value, date):
                    value_date = value
            elif field_type == 'checkbox':
                value_bool = bool(value)
            elif field_type in ('select', 'multiselect'):
                value_json = json.dumps(value) if isinstance(value, (list, dict)) else value

        # Upsert значения
        await conn.execute(
            """
            INSERT INTO client_custom_field_values
                (user_id, field_id, value_text, value_number, value_date, value_bool, value_json, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            ON CONFLICT (user_id, field_id) DO UPDATE SET
                value_text = EXCLUDED.value_text,
                value_number = EXCLUDED.value_number,
                value_date = EXCLUDED.value_date,
                value_bool = EXCLUDED.value_bool,
                value_json = EXCLUDED.value_json,
                updated_at = NOW()
            """,
            user_id, field_id, value_text, value_number, value_date, value_bool, value_json
        )

        return True


async def set_client_fields_bulk(user_id: int, fields: Dict[int, Any]) -> bool:
    """Установить несколько значений полей за раз."""
    for field_id, value in fields.items():
        await set_client_field_value(user_id, field_id, value)
    return True


# =============================================================================
# Теги
# =============================================================================

async def get_all_tags() -> List[Dict[str, Any]]:
    """Получить все теги."""
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, color, created_at
            FROM client_tags
            ORDER BY name
            """
        )
        return [dict(row) for row in rows]


async def create_tag(name: str, color: str = '#6B7280') -> Dict[str, Any]:
    """Создать новый тег."""
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO client_tags (name, color)
            VALUES ($1, $2)
            RETURNING id, name, color, created_at
            """,
            name, color
        )
        return dict(row)


async def update_tag(tag_id: int, name: Optional[str] = None, color: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Обновить тег."""
    pool = get_pool()

    updates = []
    params = [tag_id]
    param_idx = 2

    if name is not None:
        updates.append(f"name = ${param_idx}")
        params.append(name)
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
            UPDATE client_tags
            SET {', '.join(updates)}
            WHERE id = $1
            RETURNING id, name, color, created_at
            """,
            *params
        )
        return dict(row) if row else None


async def delete_tag(tag_id: int) -> bool:
    """Удалить тег."""
    pool = get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM client_tags WHERE id = $1",
            tag_id
        )
        return result == "DELETE 1"


async def get_client_tags(user_id: int) -> List[Dict[str, Any]]:
    """Получить теги клиента."""
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT t.id, t.name, t.color
            FROM client_tags t
            JOIN client_tag_links tl ON tl.tag_id = t.id
            WHERE tl.user_id = $1
            ORDER BY t.name
            """,
            user_id
        )
        return [dict(row) for row in rows]


async def set_client_tags(user_id: int, tag_ids: List[int]) -> bool:
    """Установить теги клиента (полная замена)."""
    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Удаляем старые связи
            await conn.execute(
                "DELETE FROM client_tag_links WHERE user_id = $1",
                user_id
            )

            # Добавляем новые
            if tag_ids:
                await conn.executemany(
                    "INSERT INTO client_tag_links (user_id, tag_id) VALUES ($1, $2)",
                    [(user_id, tag_id) for tag_id in tag_ids]
                )

    return True


async def add_client_tag(user_id: int, tag_id: int) -> bool:
    """Добавить тег клиенту."""
    pool = get_pool()

    async with pool.acquire() as conn:
        try:
            await conn.execute(
                "INSERT INTO client_tag_links (user_id, tag_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                user_id, tag_id
            )
            return True
        except Exception as e:
            logger.error(f"Error adding tag: {e}")
            return False


async def remove_client_tag(user_id: int, tag_id: int) -> bool:
    """Удалить тег у клиента."""
    pool = get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM client_tag_links WHERE user_id = $1 AND tag_id = $2",
            user_id, tag_id
        )
        return "DELETE" in result


# =============================================================================
# Задачи
# =============================================================================

async def get_client_tasks(user_id: int, include_completed: bool = True) -> List[Dict[str, Any]]:
    """Получить задачи клиента."""
    pool = get_pool()

    query = """
        SELECT id, user_id, title, description, due_date, priority, status,
               assignee, reminder_at, repeat_interval, completed_at, created_at, updated_at
        FROM client_tasks
        WHERE user_id = $1
    """

    if not include_completed:
        query += " AND status != 'completed'"

    query += " ORDER BY due_date NULLS LAST, created_at DESC"

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, user_id)
        return [dict(row) for row in rows]


async def get_task_by_id(task_id: int) -> Optional[Dict[str, Any]]:
    """Получить задачу по ID."""
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, user_id, title, description, due_date, priority, status,
                   assignee, reminder_at, repeat_interval, completed_at, created_at, updated_at
            FROM client_tasks
            WHERE id = $1
            """,
            task_id
        )
        return dict(row) if row else None


async def create_task(
    user_id: int,
    title: str,
    description: Optional[str] = None,
    due_date: Optional[datetime] = None,
    priority: str = 'medium',
    assignee: Optional[str] = None,
    reminder_at: Optional[datetime] = None,
    repeat_interval: Optional[str] = None
) -> Dict[str, Any]:
    """Создать задачу."""
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO client_tasks
                (user_id, title, description, due_date, priority, assignee, reminder_at, repeat_interval)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id, user_id, title, description, due_date, priority, status,
                      assignee, reminder_at, repeat_interval, completed_at, created_at, updated_at
            """,
            user_id, title, description, due_date, priority, assignee, reminder_at, repeat_interval
        )
        return dict(row)


async def update_task(
    task_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    due_date: Optional[datetime] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    assignee: Optional[str] = None,
    reminder_at: Optional[datetime] = None,
    repeat_interval: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Обновить задачу."""
    pool = get_pool()

    updates = []
    params = [task_id]
    param_idx = 2

    if title is not None:
        updates.append(f"title = ${param_idx}")
        params.append(title)
        param_idx += 1

    if description is not None:
        updates.append(f"description = ${param_idx}")
        params.append(description)
        param_idx += 1

    if due_date is not None:
        updates.append(f"due_date = ${param_idx}")
        params.append(due_date)
        param_idx += 1

    if priority is not None:
        updates.append(f"priority = ${param_idx}")
        params.append(priority)
        param_idx += 1

    if status is not None:
        updates.append(f"status = ${param_idx}")
        params.append(status)
        param_idx += 1
        if status == 'completed':
            updates.append(f"completed_at = NOW()")

    if assignee is not None:
        updates.append(f"assignee = ${param_idx}")
        params.append(assignee)
        param_idx += 1

    if reminder_at is not None:
        updates.append(f"reminder_at = ${param_idx}")
        params.append(reminder_at)
        param_idx += 1

    if repeat_interval is not None:
        updates.append(f"repeat_interval = ${param_idx}")
        params.append(repeat_interval)
        param_idx += 1

    if not updates:
        return None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE client_tasks
            SET {', '.join(updates)}
            WHERE id = $1
            RETURNING id, user_id, title, description, due_date, priority, status,
                      assignee, reminder_at, repeat_interval, completed_at, created_at, updated_at
            """,
            *params
        )
        return dict(row) if row else None


async def delete_task(task_id: int) -> bool:
    """Удалить задачу."""
    pool = get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM client_tasks WHERE id = $1",
            task_id
        )
        return result == "DELETE 1"


async def complete_task(task_id: int) -> Optional[Dict[str, Any]]:
    """Завершить задачу."""
    return await update_task(task_id, status='completed')


# =============================================================================
# Заметки
# =============================================================================

async def get_client_notes(user_id: int) -> List[Dict[str, Any]]:
    """Получить заметки клиента."""
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, user_id, text, created_at
            FROM client_notes
            WHERE user_id = $1
            ORDER BY created_at DESC
            """,
            user_id
        )
        return [dict(row) for row in rows]


async def create_note(user_id: int, text: str) -> Dict[str, Any]:
    """Создать заметку."""
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO client_notes (user_id, text)
            VALUES ($1, $2)
            RETURNING id, user_id, text, created_at
            """,
            user_id, text
        )
        return dict(row)


async def delete_note(note_id: int) -> bool:
    """Удалить заметку."""
    pool = get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM client_notes WHERE id = $1",
            note_id
        )
        return result == "DELETE 1"


# =============================================================================
# Лента активности
# =============================================================================

async def get_client_activity(
    user_id: int,
    event_types: Optional[List[str]] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Получить ленту активности клиента.

    Args:
        user_id: ID клиента
        event_types: Фильтр по типам событий (None = все)
        limit: Количество записей
        offset: Смещение для пагинации

    Returns:
        Список событий в хронологическом порядке (новые сверху)
    """
    pool = get_pool()

    query = """
        SELECT id, user_id, event_type, event_data, created_at
        FROM client_activity_log
        WHERE user_id = $1
    """
    params = [user_id]
    param_idx = 2

    if event_types:
        query += f" AND event_type = ANY(${param_idx})"
        params.append(event_types)
        param_idx += 1

    query += f" ORDER BY created_at DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
    params.extend([limit, offset])

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


async def get_client_activity_with_consultations(
    user_id: int,
    event_types: Optional[List[str]] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Получить ленту активности включая консультации из topics.

    Объединяет события из activity_log и topics в единую хронологическую ленту.
    """
    pool = get_pool()

    # Базовый запрос для activity_log
    activity_query = """
        SELECT
            id,
            'activity' as source,
            event_type,
            event_data,
            created_at
        FROM client_activity_log
        WHERE user_id = $1
    """

    # Запрос для консультаций
    consultation_query = """
        SELECT
            t.id,
            'topic' as source,
            'consultation' as event_type,
            jsonb_build_object(
                'topic_id', t.id,
                'culture', t.culture,
                'category', t.category,
                'status', t.status,
                'message_count', COALESCE(
                    (SELECT COUNT(*) FROM messages WHERE topic_id = t.id),
                    0
                ),
                'total_cost_usd', COALESCE(
                    (SELECT SUM(cost_usd) FROM consultation_logs WHERE topic_id = t.id),
                    0
                ),
                'first_question', COALESCE(
                    (SELECT text FROM messages
                     WHERE topic_id = t.id AND direction = 'user'
                     ORDER BY created_at ASC LIMIT 1),
                    ''
                )
            ) as event_data,
            t.created_at
        FROM topics t
        WHERE t.user_id = $1
    """

    # Запрос для сообщений чата — только системные/меню (без topic_id)
    # Сообщения с topic_id видны внутри консультации (TopicView)
    messages_query = """
        SELECT
            m.id,
            'message' as source,
            'chat_message' as event_type,
            jsonb_build_object(
                'direction', m.direction,
                'text', m.text,
                'topic_id', m.topic_id,
                'meta', m.meta
            ) as event_data,
            m.created_at
        FROM messages m
        WHERE m.user_id = $1
          AND m.topic_id IS NULL
    """

    # Объединяем
    combined_query = f"""
        WITH combined AS (
            {activity_query}
            UNION ALL
            {consultation_query}
            UNION ALL
            {messages_query}
        )
        SELECT * FROM combined
    """

    params = [user_id]
    param_idx = 2

    # Фильтр по типам
    if event_types:
        # Если включены консультации, добавляем их из topics
        if 'consultation' in event_types:
            other_types = [t for t in event_types if t != 'consultation']
            if other_types:
                combined_query += f" WHERE event_type = ANY(${param_idx})"
                params.append(event_types)
                param_idx += 1
        else:
            combined_query += f" WHERE event_type = ANY(${param_idx})"
            params.append(event_types)
            param_idx += 1

    combined_query += f" ORDER BY created_at DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
    params.extend([limit, offset])

    async with pool.acquire() as conn:
        rows = await conn.fetch(combined_query, *params)
        return [dict(row) for row in rows]


async def log_activity(
    user_id: int,
    event_type: str,
    event_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Записать событие в ленту активности."""
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO client_activity_log (user_id, event_type, event_data)
            VALUES ($1, $2, $3)
            RETURNING id, user_id, event_type, event_data, created_at
            """,
            user_id,
            event_type,
            json.dumps(event_data) if event_data else None
        )
        return dict(row)


# =============================================================================
# Расширенные данные клиента
# =============================================================================

async def update_client_priority(user_id: int, priority: str) -> bool:
    """Обновить приоритет клиента."""
    pool = get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE client_funnel_status
            SET priority = $2, updated_at = NOW()
            WHERE user_id = $1
            """,
            user_id, priority
        )
        return "UPDATE" in result


async def update_client_source(user_id: int, source: str) -> bool:
    """Обновить источник привлечения клиента."""
    pool = get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE client_funnel_status
            SET source = $2, updated_at = NOW()
            WHERE user_id = $1
            """,
            user_id, source
        )
        return "UPDATE" in result


async def get_client_full_data(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Получить полные данные клиента для карточки.

    Включает:
        - Базовую информацию о пользователе
        - Статус воронки, приоритет, источник
        - Статистику по консультациям
        - Теги
        - Кастомные поля
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        # Основные данные
        row = await conn.fetchrow(
            """
            SELECT
                u.id,
                u.telegram_user_id,
                u.username,
                u.first_name,
                u.last_name,
                u.avatar_path,
                u.token_balance,
                u.region,
                u.created_at as user_created_at,
                COALESCE(cfs.status, 'new') as status,
                cfs.auto_status,
                COALESCE(cfs.manual_override, false) as manual_override,
                COALESCE(cfs.priority, 'normal') as priority,
                cfs.source,
                cfs.updated_at as status_updated_at,
                COALESCE(stats.total_consultations, 0) as total_consultations,
                COALESCE(stats.total_tokens, 0) as total_tokens,
                COALESCE(stats.total_cost_usd, 0.0) as total_cost_usd,
                stats.last_consultation_at
            FROM users u
            LEFT JOIN client_funnel_status cfs ON cfs.user_id = u.id
            LEFT JOIN LATERAL (
                SELECT
                    COUNT(*)::int as total_consultations,
                    COALESCE(SUM(total_tokens), 0)::int as total_tokens,
                    COALESCE(SUM(cost_usd), 0.0) as total_cost_usd,
                    MAX(created_at) as last_consultation_at
                FROM consultation_logs cl
                WHERE cl.user_id = u.id
            ) stats ON true
            WHERE u.id = $1
            """,
            user_id
        )

        if not row:
            return None

        client = dict(row)

        # Добавляем теги
        client['tags'] = await get_client_tags(user_id)

        # Добавляем кастомные поля
        client['custom_fields'] = await get_client_field_values(user_id)

        return client
