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
        BotCommand(command="kb_pending",        description="модерациия вопросов"),
    ]

    await bot.set_my_commands(commands)
