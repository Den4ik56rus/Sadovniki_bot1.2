"""
Сервис для флагманских продуктов.

Загрузка конфигов, проверка доступа, отправка файлов с кешированием file_id.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from aiogram import Bot
from aiogram.types import FSInputFile
from aiogram.enums import ChatAction

from src.services.db import flagship_repo

logger = logging.getLogger(__name__)

# Базовая директория для данных флагманских продуктов
_FLAGSHIP_DIR = Path(__file__).resolve().parents[3] / "data" / "flagship"

# In-memory кеш конфигов (product_key → dict)
_config_cache: dict[str, dict] = {}


def load_product_config(product_key: str) -> dict:
    """Загружает config.json для продукта (с кешированием в памяти)."""
    if product_key in _config_cache:
        return _config_cache[product_key]

    config_path = _FLAGSHIP_DIR / product_key / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Flagship config not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    _config_cache[product_key] = config
    return config


def get_available_products() -> list[dict]:
    """Сканирует data/flagship/*/config.json и возвращает список продуктов."""
    products = []
    if not _FLAGSHIP_DIR.exists():
        return products
    for entry in sorted(_FLAGSHIP_DIR.iterdir()):
        config_path = entry / "config.json"
        if entry.is_dir() and config_path.exists():
            try:
                config = load_product_config(entry.name)
                products.append({
                    "product_key": entry.name,
                    "title": config.get("title", entry.name),
                    "price_rub": config.get("price_rub", 0),
                    "culture": config.get("culture", ""),
                    "variety": config.get("variety", ""),
                })
            except Exception as e:
                logger.error(f"Error loading flagship config {entry.name}: {e}")
    return products


async def has_product_access(
    user_id: int,
    product_key: str,
    telegram_user_id: int = 0,
) -> bool:
    """Проверяет доступ пользователя к продукту."""
    return await flagship_repo.check_access(user_id, product_key)


async def get_user_products(user_id: int) -> list[dict]:
    """Возвращает список купленных продуктов с метаданными из config."""
    rows = await flagship_repo.get_user_products(user_id)
    result = []
    for row in rows:
        product_key = row["product_key"]
        product_type = row.get("product_type", "seasonal_program")

        # Отдельный блок (тема): product_key = "strawberry_summer__nutrition"
        if product_type == "single_block" and "__" in product_key:
            base_key, topic_key = product_key.split("__", 1)
            try:
                config = load_product_config(base_key)
                topic_title = topic_key
                for article in config.get("articles", []):
                    if article["key"] == topic_key:
                        topic_title = article["title"]
                        break
                result.append({
                    "product_key": product_key,
                    "product_type": product_type,
                    "title": f"{topic_title} — {config.get('title', base_key)}",
                    "culture": config.get("culture", ""),
                    "purchased_at": row["purchased_at"],
                    "base_product_key": base_key,
                    "topic_key": topic_key,
                })
            except FileNotFoundError:
                result.append({
                    "product_key": product_key,
                    "product_type": product_type,
                    "title": product_key,
                    "culture": "",
                    "purchased_at": row["purchased_at"],
                })
        else:
            # Сезонная программа
            try:
                config = load_product_config(product_key)
                result.append({
                    "product_key": product_key,
                    "product_type": product_type,
                    "title": config.get("title", product_key),
                    "culture": config.get("culture", ""),
                    "purchased_at": row["purchased_at"],
                })
            except FileNotFoundError:
                result.append({
                    "product_key": product_key,
                    "product_type": product_type,
                    "title": product_key,
                    "culture": "",
                    "purchased_at": row["purchased_at"],
                })
    return result


async def send_flagship_file(
    bot: Bot,
    chat_id: int,
    product_key: str,
    content_key: str,
    file_path: str,
    file_type: str,
    caption: str = "",
) -> str:
    """Отправляет файл с кешированием Telegram file_id.

    Все файлы (включая видео) отправляются как document,
    чтобы сохранить оригинальное качество и пропорции.

    Args:
        bot: Bot instance
        chat_id: Telegram chat ID
        product_key: Ключ продукта (strawberry_summer)
        content_key: Ключ контента (nutrition:article)
        file_path: Абсолютный путь к файлу
        file_type: 'document' или 'video' (оба отправляются как document)
        caption: Подпись к файлу

    Returns:
        Telegram file_id
    """
    # 1. Проверить кеш
    cached_id = await flagship_repo.get_cached_file_id(product_key, content_key)

    if cached_id:
        try:
            await bot.send_document(
                chat_id=chat_id, document=cached_id, caption=caption,
            )
            logger.info(f"Flagship file sent from cache: {content_key}")
            return cached_id
        except Exception as e:
            logger.warning(f"Cache miss (file_id expired?): {content_key}: {e}")

    # 2. Загрузить файл
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Flagship file not found: {file_path}")

    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)

    input_file = FSInputFile(file_path)
    telegram_file_id = ""

    result = await bot.send_document(
        chat_id=chat_id,
        document=input_file,
        caption=caption,
        request_timeout=180,
    )
    if result.document:
        telegram_file_id = result.document.file_id

    # 3. Сохранить в кеш
    if telegram_file_id:
        try:
            await flagship_repo.save_cached_file_id(
                product_key, content_key, telegram_file_id, file_type,
            )
            logger.info(f"Flagship file cached: {content_key} → {telegram_file_id[:20]}...")
        except Exception as e:
            logger.error(f"Failed to cache file_id for {content_key}: {e}")

    return telegram_file_id


def resolve_file_path(product_key: str, relative_path: str) -> str:
    """Преобразует относительный путь из config.json в абсолютный."""
    return str(_FLAGSHIP_DIR / product_key / relative_path)
