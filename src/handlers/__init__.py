# src/handlers/__init__.py

"""
Регистрация всех роутеров проекта.

Задача:
    - создать и подключить к Dispatcher все группы хендлеров:
        * меню
        * консультации
        * админка
"""

from aiogram import Dispatcher

# Главное меню (/start, кнопки и т.п.)
from src.handlers import menu as menu_handlers

# Консультации (все сценарии в папке consultation)
from src.handlers.consultation.router import get_consultation_router

# Админка (модерация базы знаний)
from src.handlers.admin import moderation as moderation_handlers


def setup_routers(dp: Dispatcher) -> None:
    """
    Подключает все роутеры к переданному Dispatcher.
    """

    # 1. Главное меню
    dp.include_router(menu_handlers.router)

    # 2. Консультации (общий роутер, внутри — entry + питание и т.д.)
    consultation_router = get_consultation_router()
    dp.include_router(consultation_router)

    # 3. Админка (модерация /kb_pending и пр.)
    dp.include_router(moderation_handlers.router)
