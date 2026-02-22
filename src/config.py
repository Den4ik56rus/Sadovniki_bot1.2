# src/config.py

"""
Модуль конфигурации проекта.

Задача:
    - считать настройки из переменных окружения / файла .env
    - предоставить объект settings, доступный из любого места проекта

Используем:
    - pydantic-settings (BaseSettings) для удобной работы с конфигами
"""

from pathlib import Path
from functools import lru_cache  # Для кэширования настроек (чтобы не создавать их каждый раз)

from pydantic_settings import BaseSettings, SettingsConfigDict  # Базовый класс для настроек
from pydantic import Field                                      # Для описания полей с подсказками и значениями по умолчанию

# Определяем какой .env файл использовать:
# .env.local (тестовый бот) имеет приоритет над .env (продакшен)
_project_root = Path(__file__).resolve().parent.parent
_env_local = _project_root / ".env.local"
_env_file = str(_env_local) if _env_local.exists() else ".env"


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
    telegram_bot_username: str = Field(
        "",
        description="Username бота (без @) для формирования deep links",
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
    openai_model_consultation: str = Field(
        "gpt-4o-mini",  # Fallback значение если не задано в admin_settings
        description="Модель для консультаций (OPENAI_MODEL_CONSULTATION) - используется как fallback, основные настройки в БД",
    )
    openai_model_article: str = Field(
        "gpt-4o-mini",  # Fallback значение
        description="Модель для статей (OPENAI_MODEL_ARTICLE) - используется как fallback, основные настройки в БД",
    )
    openai_model_classification: str = Field(
        "gpt-4o-mini",  # Fallback значение
        description="Модель для классификации (OPENAI_MODEL_CLASSIFICATION) - используется как fallback, основные настройки в БД",
    )
    openai_model_utility: str = Field(
        "gpt-4o-mini",  # Fallback значение
        description="Модель для вспомогательных задач (OPENAI_MODEL_UTILITY) - используется как fallback, основные настройки в БД",
    )
    openai_embeddings_model: str = Field(
        "text-embedding-3-small",  # модель эмбеддингов (1536 dimensions)
        description="Имя модели OpenAI для эмбеддингов",
    )
    openai_temperature: float | None = Field(
        None,  # None = не передавать temperature (для o1/gpt-5 моделей)
        description="Temperature для OpenAI (None = не передавать, 0.0-1.0 = конкретное значение)",
    )
    openai_admin_key: str = Field(
        "",
        description="Admin API Key для мониторинга расходов OpenAI (sk-admin-...)",
    )

    # --- QueryRouter (Gemini Embeddings) ---
    queryrouter_api_key: str = Field(
        "",
        description="API-ключ QueryRouter для Gemini Embeddings",
    )

    # --- Администраторы ---
    admin_ids: str = Field(
        "",
        description="Telegram user IDs администраторов (через запятую)",
    )

    # --- API сервер ---
    api_host: str = Field(
        "0.0.0.0",
        description="Хост API сервера",
    )
    api_port: int = Field(
        8080,
        description="Порт API сервера",
    )
    api_base_url: str = Field(
        "",
        description="Публичный base URL API для redirect-ссылок (например: http://72.56.121.98)",
    )

    # --- WebApp ---
    webapp_url: str = Field(
        "",
        description="URL WebApp на GitHub Pages (например: https://username.github.io/repo/)",
    )
    webapp_origin: str = Field(
        "*",
        description="Разрешённый origin для CORS (например: https://username.github.io)",
    )

    # --- YooKassa Payments ---
    YOOKASSA_SHOP_ID: str = Field(
        ...,
        description="YooKassa Shop ID",
    )
    YOOKASSA_SECRET_KEY: str = Field(
        ...,
        description="YooKassa Secret Key",
    )
    YOOKASSA_TEST_MODE: bool = Field(
        True,
        description="Использовать тестовый режим YooKassa",
    )
    YOOKASSA_RETURN_URL: str = Field(
        "https://t.me/garden_bot_ai_bot",
        description="URL для возврата после оплаты (ссылка на бота)",
    )
    YOOKASSA_WEBHOOK_URL: str = Field(
        "",
        description="Публичный URL для webhook от YooKassa (например, https://yourdomain.com/api/webhooks/yookassa)",
    )
    YOOKASSA_SEND_RECEIPT: bool = Field(
        True,
        description="Отправлять чеки в налоговую (54-ФЗ)",
    )
    YOOKASSA_TAX_SYSTEM_CODE: int = Field(
        1,
        description="Система налогообложения (1 = УСН доход)",
    )

    # --- Перенаправление оплаты на менеджера (тестовый запуск) ---
    PAYMENTS_REDIRECT_MODE: bool = Field(
        False,
        description="Перенаправлять на ручную оплату через сообщение вместо YooKassa",
    )
    PAYMENTS_CONTACT_USERNAME: str = Field(
        "orenqueen56",
        description="Username менеджера для ручной оплаты (без @)",
    )

    # Общая конфигурация pydantic-settings
    model_config = SettingsConfigDict(
        env_file=_env_file,          # .env.local (тестовый бот) или .env (продакшен)
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
    s = Settings()
    env_label = "LOCAL (.env.local)" if _env_local.exists() else "PRODUCTION (.env)"
    print(f"[config] Loaded: {env_label} | Bot: @{s.telegram_bot_username}")
    return s


# Глобальный объект настроек, который мы импортируем во всех модулях:
# from src.config import settings
settings: Settings = get_settings()
