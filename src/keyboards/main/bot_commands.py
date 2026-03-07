# src/keyboards/main/bot_commands.py

from aiogram import Bot
from aiogram.types import BotCommand


async def set_main_menu_commands(bot: Bot) -> None:
    """
    Регистрирует команды бота, которые показываются
    в выпадающем меню (по слэшу / или в меню бота).
    """
    commands = [
        BotCommand(command="start",        description="🚀 Запустить бота"),
        BotCommand(command="menu",         description="📋 Меню"),
        BotCommand(command="subscription", description="💳 Управление подпиской"),
        BotCommand(command="support",      description="💬 Написать в поддержку"),
    ]

    await bot.set_my_commands(commands)
