# src/services/db/pool.py

import asyncpg  # Библиотека для работы с PostgreSQL асинхронно
from typing import Optional  # Для аннотации типов (Optional[...] может быть None)

from src.config import settings  # Конфиг проекта: из него берём параметры подключения к БД


# Глобальная переменная, в которой будет лежать пул соединений.
# Тип: asyncpg.Pool или None (если пул ещё не создан или уже закрыт).
_db_pool: Optional[asyncpg.Pool] = None


async def init_db_pool() -> None:
    """
    Создаёт пул подключений к базе данных.

    Вызывается один раз при старте бота (например, в main.py).
    """
    global _db_pool  # Говорим, что будем менять глобальную переменную _db_pool

    # Если пул уже создан, ничего не делаем (чтобы не пересоздавать его).
    if _db_pool is not None:
        return

    # Создаём пул соединений с БД.
    # Все параметры берём из settings (host, port, имя базы, логин, пароль).
    _db_pool = await asyncpg.create_pool(
        host=settings.db_host,         # Адрес сервера PostgreSQL
        port=settings.db_port,         # Порт PostgreSQL
        database=settings.db_name,     # Имя базы данных
        user=settings.db_user,         # Имя пользователя
        password=settings.db_password, # Пароль
        min_size=1,                    # Минимальное количество соединений в пуле
        max_size=5,                    # Максимальное количество соединений в пуле
    )


async def close_db_pool() -> None:
    """
    Корректно закрывает пул подключений к базе данных.

    Вызывается при остановке бота.
    """
    global _db_pool  # Будем изменять глобальную переменную

    # Если пул ещё не создан — просто выходим.
    if _db_pool is None:
        return

    # Закрываем все соединения в пуле.
    await _db_pool.close()
    # Обнуляем ссылку на пул, чтобы не использовать его после закрытия.
    _db_pool = None


def get_pool() -> asyncpg.Pool:
    """
    Возвращает текущий пул подключений.

    Если пул не инициализирован — выбрасывает ошибку.
    Эту функцию будут использовать все репозитории (users_repo, kb_repo и т.д.).
    """
    # Если пул ещё не создан — это ошибка инициализации приложения.
    if _db_pool is None:
        raise RuntimeError("Пул подключений к БД не инициализирован. Сначала вызовите init_db_pool().")

    # Возвращаем активный пул.
    return _db_pool
