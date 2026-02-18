# src/services/db/settings_repo.py

"""
Репозиторий для глобальных настроек админ-панели.

Таблица: admin_settings (key-value)
Кеширование: в памяти, инвалидируется при обновлении через API.
"""

import logging
from typing import Optional, Dict, Any, List

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)

# In-memory кеш (загружается лениво при первом обращении)
_settings_cache: Dict[str, str] = {}
_cache_loaded: bool = False


async def _ensure_cache_loaded() -> None:
    """Загрузить все настройки в кеш при первом обращении."""
    global _cache_loaded
    if _cache_loaded:
        return

    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT key, value FROM admin_settings")
            for row in rows:
                _settings_cache[row["key"]] = row["value"]
        _cache_loaded = True
        logger.info(f"[settings_repo] Загружено {len(_settings_cache)} настроек в кеш")
    except Exception as e:
        logger.warning(f"[settings_repo] Ошибка загрузки кеша: {e}")


async def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Получить значение настройки по ключу (из кеша)."""
    await _ensure_cache_loaded()
    return _settings_cache.get(key, default)


async def get_bool_setting(key: str, default: bool = True) -> bool:
    """Получить булево значение настройки. 'true' -> True, всё остальное -> False."""
    value = await get_setting(key)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes")


async def update_setting(key: str, value: str) -> Dict[str, Any]:
    """Обновить настройку. Обновляет и БД, и кеш."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO admin_settings (key, value, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (key) DO UPDATE
            SET value = $2, updated_at = NOW()
            RETURNING key, value, description, updated_at
            """,
            key, value,
        )

    # Обновляем кеш
    _settings_cache[key] = value

    logger.info(f"[settings_repo] Настройка '{key}' обновлена на '{value}'")
    return dict(row) if row else {"key": key, "value": value}


async def get_all_settings() -> List[Dict[str, Any]]:
    """Получить все настройки из БД (для админ-панели)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT key, value, description, updated_at FROM admin_settings ORDER BY key"
        )
    return [dict(row) for row in rows]


async def is_rag_enabled() -> bool:
    """Проверить, включена ли RAG-система глобально."""
    return await get_bool_setting("rag_enabled", default=True)


# =========================================================================
# LLM Model & Temperature — динамические настройки (DB-first, .env fallback)
# =========================================================================

# Маппинг task → атрибут в config.settings
_TASK_MODEL_MAP = {
    "consultation": "openai_model_consultation",
    "classification": "openai_model_classification",
    "article": "openai_model_article",
    "utility": "openai_model_utility",
    "complexity": "openai_model_classification",  # Fallback на classification модель
    "guide": "openai_model_consultation",  # Fallback на consultation модель
}


async def get_model_for_task(task: str) -> str:
    """
    Получить модель для задачи. Сначала проверяет admin_settings,
    затем fallback на .env (config.settings).
    """
    db_value = await get_setting(f"model_{task}")
    if db_value and db_value.strip():
        return db_value.strip()

    # Fallback на .env
    from src.config import settings as env_settings
    attr = _TASK_MODEL_MAP.get(task)
    if attr:
        return getattr(env_settings, attr, "gpt-4.1-mini")
    return "gpt-4.1-mini"


async def get_temperature_for_task(task: str) -> Optional[float]:
    """
    Получить temperature для задачи. Пустая строка = None (не передавать).
    Сначала проверяет admin_settings, затем fallback на .env.
    """
    db_value = await get_setting(f"temp_{task}")
    # Если ключ найден в БД
    if db_value is not None:
        if db_value.strip() == "":
            return None  # Отключено — не передавать
        try:
            return float(db_value.strip())
        except ValueError:
            return None

    # Fallback на .env
    from src.config import settings as env_settings
    return env_settings.openai_temperature


# Допустимые значения reasoning_effort
VALID_REASONING_EFFORTS = ("none", "low", "medium", "high")


async def get_reasoning_effort_for_task(task: str) -> Optional[str]:
    """
    Получить reasoning_effort для задачи.
    Пустая строка / 'none' = None (не передавать, обычный режим).
    Сначала проверяет admin_settings, затем None.
    """
    db_value = await get_setting(f"reasoning_{task}")
    if db_value is not None:
        value = db_value.strip().lower()
        if value in ("", "none"):
            return None  # Обычный режим без reasoning
        if value in VALID_REASONING_EFFORTS:
            return value
    return None  # По умолчанию — без reasoning
