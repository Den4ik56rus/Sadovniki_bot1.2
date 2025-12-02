# src/bot.py

"""
Модуль bot отвечает за создание объектов Bot и Dispatcher.

Задачи:
    - создать экземпляр Bot (Telegram-бот)
    - создать Dispatcher (управляет обработчиками)
    - подключить к Dispatcher все роутеры (handlers)
"""

from aiogram import Bot, Dispatcher                         # Основные классы aiogram
from aiogram.enums import ParseMode                         # Для выбора режима разметки (HTML/Markdown)
from aiogram.client.default import DefaultBotProperties     # Чтобы задать parse_mode по умолчанию

from src.config import settings                             # Глобальные настройки проекта
from src.handlers import setup_routers                      # Функция, которая ПОДКЛЮЧАЕТ роутеры к dp


def create_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    """
    Фабрика, которая создаёт и настраивает:
        - Bot
        - Dispatcher
    и возвращает их.
    """

    # 1. Создаём Bot с токеном и HTML-разметкой по умолчанию
    bot = Bot(
        token=settings.telegram_bot_token,          # ✔ Берём поле из Settings, как в config.py
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML              # Будем использовать HTML в сообщениях
        ),
    )

    # 2. Создаём Dispatcher
    dp = Dispatcher()

    # 3. Подключаем все роутеры проекта
    setup_routers(dp)

    # 4. Возвращаем пару (bot, dp), чтобы main.py мог запустить polling
    return bot, dp
