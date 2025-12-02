# src/handlers/consultation/router.py

"""
Общий роутер для всех сценариев консультаций.

Собирает:
    - pitanie_rastenii.py — сценарий "Питание растений"
    - entry.py  — общий хендлер консультаций (fallback для остальных случаев)
"""

from aiogram import Router

# Сценарий "Питание растений"
from .pitanie_rastenii import router as nutrition_router

# Базовый хендлер консультаций (общий вход)
from .entry import router as entry_router


def get_consultation_router() -> Router:
    """
    Возвращает общий роутер консультаций,
    в который включены все подроутеры сценариев.

    ВАЖНО:
        - nutrition_router включён ПЕРВЫМ, чтобы его хендлеры
          имели приоритет над универсальными хендлерами из entry.py
    """
    router = Router(name="consultation")

    # 1. Специализированные сценарии (с фильтрами по состояниям)
    router.include_router(nutrition_router)

    # 2. Общий вход (fallback)
    router.include_router(entry_router)

    return router
