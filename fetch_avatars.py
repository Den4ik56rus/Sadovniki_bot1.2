"""Одноразовый скрипт: скачать аватары всех существующих пользователей."""

import asyncio
import logging
from pathlib import Path

from aiogram import Bot
from dotenv import load_dotenv

load_dotenv()

from src.config import settings
from src.services.db.pool import init_db_pool, get_pool, close_db_pool
from src.services.avatars import download_user_avatar

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    await init_db_pool()
    pool = get_pool()

    bot = Bot(token=settings.telegram_bot_token)

    try:
        async with pool.acquire() as conn:
            users = await conn.fetch(
                "SELECT id, telegram_user_id, first_name FROM users"
            )

        logger.info(f"Найдено {len(users)} пользователей")

        downloaded = 0
        for user in users:
            uid = user['id']
            tg_id = user['telegram_user_id']
            name = user['first_name'] or tg_id

            filename = await download_user_avatar(bot, tg_id)
            if filename:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE users SET avatar_path = $1 WHERE id = $2",
                        filename, uid,
                    )
                downloaded += 1
                logger.info(f"  [{downloaded}] {name} (tg:{tg_id}) -> {filename}")
            else:
                logger.info(f"  [-] {name} (tg:{tg_id}) — нет фото")

        logger.info(f"Готово! Скачано {downloaded}/{len(users)} аватаров")

    finally:
        await bot.session.close()
        await close_db_pool()


if __name__ == "__main__":
    asyncio.run(main())
