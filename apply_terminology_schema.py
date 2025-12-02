#!/usr/bin/env python3
"""
Скрипт для применения схемы terminology к базе данных.
Использует настройки подключения из .env файла.
"""
import asyncio
import asyncpg
from src.config import settings


async def apply_schema():
    """Применяет schema_terminology.sql к базе данных."""

    # Читаем SQL из файла
    with open('db/schema_terminology.sql', 'r', encoding='utf-8') as f:
        sql = f.read()

    # Подключаемся к БД
    conn = await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
    )

    try:
        # Выполняем SQL
        await conn.execute(sql)
        print("✅ Схема terminology успешно применена!")
        print("✅ Таблица terminology создана")
        print("✅ Добавлены примеры: 'навоз' и 'помёт'")

    except Exception as e:
        print(f"❌ Ошибка при применении схемы: {e}")
        raise

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(apply_schema())
