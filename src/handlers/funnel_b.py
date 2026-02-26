"""
Воронка Тип Б — новая экспериментальная воронка для A/B теста.
Контент будет добавлен позже. Сейчас — инфраструктурный скелет.
"""
import logging
from aiogram.types import Message

logger = logging.getLogger(__name__)


async def start_funnel_b(message: Message, user_id: int) -> None:
    """
    Точка входа для новых пользователей с вариантом воронки Б.
    TODO: реализовать онбординг и новую воронку.
    """
    logger.info(f"User {user_id} entered funnel B")
    # Временный плейсхолдер — будет заменён реальным онбордингом
    await message.answer(
        "Добро пожаловать! Мы рады видеть вас в нашем боте."
    )
