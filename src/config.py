# src/config.py

"""
Модуль конфигурации проекта.

Задача:
    - считать настройки из переменных окружения / файла .env
    - предоставить объект settings, доступный из любого места проекта

Используем:
    - pydantic-settings (BaseSettings) для удобной работы с конфигами
"""

from functools import lru_cache  # Для кэширования настроек (чтобы не создавать их каждый раз)

from pydantic_settings import BaseSettings, SettingsConfigDict  # Базовый класс для настроек
from pydantic import Field                                      # Для описания полей с подсказками и значениями по умолчанию


class Settings(BaseSettings):
    """
    Класс настроек проекта.

    Все поля читаются из:
        - переменных окружения
        - файла .env (если он есть в корне проекта)
    """

    # --- Telegram бот ---
    telegram_bot_token: str = Field(
        ...,  # ... = обязательное поле
        description="Токен Telegram-бота, выданный BotFather",
    )

    # --- Подключение к базе данных PostgreSQL ---
    db_host: str = Field(
        "db",  # значение по умолчанию (часто сервис называется db в docker-compose)
        description="Хост PostgreSQL (db / localhost / IP)",
    )
    db_port: int = Field(
        5432,
        description="Порт PostgreSQL",
    )
    db_name: str = Field(
        ...,
        description="Имя базы данных",
    )
    db_user: str = Field(
        ...,
        description="Пользователь БД",
    )
    db_password: str = Field(
        ...,
        description="Пароль пользователя БД",
    )

    # --- OpenAI ---
    openai_api_key: str = Field(
        ...,
        description="API-ключ OpenAI",
    )
    openai_model: str = Field(
        "gpt-4.1-mini",  # можешь поменять на нужную модель
        description="Имя модели OpenAI для чат-ответов",
    )
    openai_embeddings_model: str = Field(
        "text-embedding-3-large",  # модель эмбеддингов
        description="Имя модели OpenAI для эмбеддингов",
    )

    # --- Администраторы ---
    admin_ids: str = Field(
        "",
        description="Telegram user IDs администраторов (через запятую)",
    )

    # Общая конфигурация pydantic-settings
    model_config = SettingsConfigDict(
        env_file=".env",             # брать переменные ещё и из файла .env в корне проекта
        env_file_encoding="utf-8",   # кодировка файла .env
        extra="ignore",              # игнорировать лишние переменные
    )


@lru_cache
def get_settings() -> Settings:
    """
    Функция-обёртка, которая создаёт и кэширует объект настроек.

    Благодаря lru_cache:
        - Settings инициализируется только один раз
        - при повторных вызовах возвращается тот же объект
    """
    return Settings()


# Глобальный объект настроек, который мы импортируем во всех модулях:
# from src.config import settings
settings: Settings = get_settings()
