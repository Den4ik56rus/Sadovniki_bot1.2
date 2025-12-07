"""
Точка входа в приложение бота.

Запуск:
    python -m src.main
"""

import asyncio

from aiohttp import web

# Создание Bot и Dispatcher
from src.bot import create_bot_and_dispatcher

# Пул БД
from src.services.db.pool import init_db_pool, close_db_pool

# Регистрация меню команд
from src.keyboards.main.bot_commands import set_main_menu_commands

# API сервер
from src.api import create_api_app
from src.config import settings


async def main() -> None:
    """
    Основная асинхронная функция:

    1) Инициализирует пул подключений к базе данных.
    2) Создаёт bot и dispatcher.
    3) Запускает API сервер для WebApp.
    4) Регистрирует команды бота (показываются при вводе / ).
    5) Запускает long polling.
    6) При завершении закрывает пул БД и API сервер.
    """

    print("Инициализирую пул подключений к БД...")
    await init_db_pool()
    print("Пул подключений к БД инициализирован.")

    # Создаём bot и dp
    bot, dp = create_bot_and_dispatcher()

    # Создаём и запускаем API сервер
    print(f"Запускаю API сервер на {settings.api_host}:{settings.api_port}...")
    api_app = await create_api_app()
    runner = web.AppRunner(api_app)
    await runner.setup()
    site = web.TCPSite(runner, settings.api_host, settings.api_port)
    await site.start()
    print(f"API сервер запущен на http://{settings.api_host}:{settings.api_port}")

    # Регистрируем команды бота в выезжающем меню Telegram
    print("Регистрирую команды бота...")
    await set_main_menu_commands(bot)
    print("Команды зарегистрированы.")

    print("Бот запущен. Нажмите Ctrl+C, чтобы остановить его.")

    try:
        # Старт long polling
        await dp.start_polling(bot)
    finally:
        # Корректное закрытие
        print("Останавливаю бота...")

        # Закрываем API сервер
        print("Останавливаю API сервер...")
        await runner.cleanup()
        print("API сервер остановлен.")

        # Закрываем пул БД
        print("Закрываю пул БД...")
        await close_db_pool()
        print("Пул БД закрыт.")


if __name__ == "__main__":
    asyncio.run(main())
