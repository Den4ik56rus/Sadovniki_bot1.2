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

# Middleware для отслеживания активности пользователей
from src.middleware.activity_tracker import ActivityTrackerMiddleware

# Главное меню (/start, кнопки и т.п.)
from src.handlers import menu as menu_handlers

# Консультации (все сценарии в папке consultation)
from src.handlers.consultation.router import get_consultation_router

# Админка (модерация базы знаний, написание статей)
from src.handlers.admin import moderation as moderation_handlers
from src.handlers.admin import terminology as terminology_handlers
from src.handlers.admin import article_writing as article_handlers

# Платежи (покупка токенов и подписок)
from src.handlers.payments import payments_router

# Кнопки рассылок + PollAnswer
from src.handlers.broadcast_callbacks import router as broadcast_cb_router

# Текстовые ответы на кнопки рассылок
from src.handlers.broadcast_responses import router as broadcast_responses_router

# Воронка Б — квиз-онбординг (callback-хендлеры quiz_*)
from src.handlers.funnel_b import router as funnel_b_router


def setup_routers(dp: Dispatcher) -> None:
    """
    Подключает все роутеры к переданному Dispatcher.

    ВАЖНО: Порядок регистрации имеет значение!
    Админские хендлеры должны быть ПЕРЕД консультационными,
    иначе общий обработчик F.text перехватит сообщения админа.
    """

    # 0. Middleware: обновление last_activity_at на каждый update
    dp.update.outer_middleware(ActivityTrackerMiddleware())

    # 1. Главное меню
    dp.include_router(menu_handlers.router)

    # 2. Платежи (покупка токенов и подписок)
    dp.include_router(payments_router)

    # 2.5. Кнопки рассылок + PollAnswer (перед админкой и консультациями)
    dp.include_router(broadcast_cb_router)

    # 2.6. Текстовые ответы на кнопки рассылок (перед админкой и консультациями)
    dp.include_router(broadcast_responses_router)

    # 2.7. Воронка Б — callback-хендлеры квиза (перед консультациями)
    dp.include_router(funnel_b_router)

    # 3. Админка (модерация /kb_pending и пр.) — ПЕРЕД консультациями!
    dp.include_router(moderation_handlers.router)
    dp.include_router(terminology_handlers.router)
    dp.include_router(article_handlers.router)  # Режим написания статей

    # 4. Консультации (общий роутер, внутри — entry + питание и т.д.)
    consultation_router = get_consultation_router()
    dp.include_router(consultation_router)
