# src/services/db/user_state_repo.py

"""
Репозиторий для персистентного хранения состояния консультации.

Используется для синхронизации in-memory CONSULTATION_STATE/CONSULTATION_CONTEXT
с БД, чтобы восстановить состояние после рестарта бота.
"""

import json
import logging
from typing import Any, Dict, List

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


async def save_user_state(
    telegram_user_id: int,
    state_key: str,
    context: Dict[str, Any],
) -> None:
    """
    Сохраняет состояние консультации пользователя в БД (UPSERT).

    Важно: context НЕ должен содержать объекты Message, Bot и т.п. —
    они не сериализуемы в JSON. Передавать только примитивные поля.
    """
    pool = get_pool()
    safe_context = _serialize_context(context)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_bot_state (telegram_user_id, state_key, context_json, updated_at)
            VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
            ON CONFLICT (telegram_user_id)
            DO UPDATE SET
                state_key = EXCLUDED.state_key,
                context_json = EXCLUDED.context_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            telegram_user_id,
            state_key,
            json.dumps(safe_context, ensure_ascii=False),
        )


async def clear_user_state(telegram_user_id: int) -> None:
    """Удаляет сохранённое состояние пользователя из БД."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM user_bot_state WHERE telegram_user_id = $1",
            telegram_user_id,
        )


async def get_all_persisted_states() -> List[Dict[str, Any]]:
    """
    Возвращает все сохранённые состояния пользователей.
    Используется при старте бота для восстановления состояний.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT telegram_user_id, state_key, context_json FROM user_bot_state"
        )
    return [
        {
            "telegram_user_id": r["telegram_user_id"],
            "state_key": r["state_key"],
            "context": json.loads(r["context_json"]) if r["context_json"] else {},
        }
        for r in rows
    ]


def _serialize_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Фильтрует контекст: оставляет только JSON-сериализуемые поля.
    Исключает объекты типа Message, Bot и т.п.
    """
    safe: Dict[str, Any] = {}
    for key, value in context.items():
        if isinstance(value, (str, int, float, bool, type(None))):
            safe[key] = value
        elif isinstance(value, list):
            # Сохраняем списки (например, clarifications) — проверяем каждый элемент
            try:
                json.dumps(value)
                safe[key] = value
            except (TypeError, ValueError):
                pass
        elif isinstance(value, dict):
            try:
                json.dumps(value)
                safe[key] = value
            except (TypeError, ValueError):
                pass
        # Намеренно пропускаем несериализуемые объекты (Message, Bot, и т.д.)
    return safe
