"""
Точка входа в приложение бота.

Запуск:
    python -m src.main
"""

import asyncio

# Создание Bot и Dispatcher
from src.bot import create_bot_and_dispatcher

# Пул БД
from src.services.db.pool import init_db_pool, close_db_pool

# Регистрация меню команд
from src.keyboards.main.bot_commands import set_main_menu_commands


async def main() -> None:
    """
    Основная асинхронная функция:

    1) Инициализирует пул подключений к базе данных.
    2) Создаёт bot и dispatcher.
    3) Регистрирует команды бота (показываются при вводе / ).
    4) Запускает long polling.
    5) При завершении закрывает пул БД.
    """

    print("Инициализирую пул подключений к БД...")
    await init_db_pool()
    print("Пул подключений к БД инициализирован.")

    # Создаём bot и dp
    bot, dp = create_bot_and_dispatcher()

    # Регистрируем команды бота в выезжающем меню Telegram
    print("Регистрирую команды бота...")
    await set_main_menu_commands(bot)
    print("Команды зарегистрированы.")

    print("Бот запущен. Нажмите Ctrl+C, чтобы остановить его.")

    try:
        # Старт long polling
        await dp.start_polling(bot)
    finally:
        # Корректное закрытие пула БД
        print("Останавливаю бота, закрываю пул БД...")
        await close_db_pool()
        print("Пул БД закрыт.")


if __name__ == "__main__":
    asyncio.run(main())
