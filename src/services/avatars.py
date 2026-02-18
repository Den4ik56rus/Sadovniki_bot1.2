# src/services/avatars.py
"""Загрузка аватаров пользователей из Telegram."""

import logging
from pathlib import Path

from aiogram import Bot

logger = logging.getLogger(__name__)

AVATARS_DIR = Path(__file__).parent.parent.parent / "data" / "avatars"


async def download_user_avatar(bot: Bot, telegram_user_id: int) -> str | None:
    """
    Скачивает фото профиля пользователя из Telegram.
    Возвращает имя файла (например '123456.jpg') или None.
    """
    try:
        AVATARS_DIR.mkdir(parents=True, exist_ok=True)

        photos = await bot.get_user_profile_photos(telegram_user_id, limit=1)
        if not photos.photos:
            return None

        # photos.photos[0] — массив размеров первого фото, [0] — самый маленький (160x160)
        smallest = photos.photos[0][0]
        filename = f"{telegram_user_id}.jpg"
        destination = AVATARS_DIR / filename

        await bot.download(smallest, destination=destination)
        return filename
    except Exception as e:
        logger.warning(f"Не удалось скачать аватар для {telegram_user_id}: {e}")
        return None
