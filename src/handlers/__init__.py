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

    ВАЖНО: Порядок регистрации имеет значение!
    Админские хендлеры должны быть ПЕРЕД консультационными,
    иначе общий обработчик F.text перехватит сообщения админа.
    """

    # 1. Главное меню
    dp.include_router(menu_handlers.router)

    # 2. Админка (модерация /kb_pending и пр.) — ПЕРЕД консультациями!
    dp.include_router(moderation_handlers.router)

    # 3. Консультации (общий роутер, внутри — entry + питание и т.д.)
    consultation_router = get_consultation_router()
    dp.include_router(consultation_router)
