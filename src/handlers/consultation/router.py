# src/handlers/consultation/router.py

"""
Общий роутер для всех сценариев консультаций.

Собирает:
    - culture_callback.py — обработка выбора культуры
    - pitanie_rastenii.py — сценарий "Питание растений"
    - entry.py  — общий хендлер консультаций (fallback для остальных случаев)
"""

from aiogram import Router

# Обработка выбора культуры
from .culture_callback import router as culture_callback_router

# Сценарий "Питание растений"
from .pitanie_rastenii import router as nutrition_router

# Базовый хендлер консультаций (общий вход)
from .entry import router as entry_router


def get_consultation_router() -> Router:
    """
    Возвращает общий роутер консультаций,
    в который включены все подроутеры сценариев.

    ВАЖНО:
        - culture_callback_router включён ПЕРВЫМ для обработки выбора культуры
        - nutrition_router включён ВТОРЫМ, чтобы его хендлеры
          имели приоритет над универсальными хендлерами из entry.py
    """
    router = Router(name="consultation")

    # 0. Обработка выбора культуры (callback)
    router.include_router(culture_callback_router)

    # 1. Специализированные сценарии (с фильтрами по состояниям)
    router.include_router(nutrition_router)

    # 2. Общий вход (fallback)
    router.include_router(entry_router)

    return router
