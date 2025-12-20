"""
Обработчики для работы с платежами в Telegram боте.

Модули:
    - menu — главное меню покупок
    - tokens — покупка пакетов токенов
    - subscription — покупка подписки
"""

from aiogram import Router

from . import menu, tokens, subscription

# Создать общий роутер для всех payment handlers
payments_router = Router(name="payments")

# Подключить sub-роутеры
payments_router.include_router(menu.router)
payments_router.include_router(tokens.router)
payments_router.include_router(subscription.router)

__all__ = ["payments_router"]
