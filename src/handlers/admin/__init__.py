# src/handlers/admin/__init__.py

from .moderation import (  # Импортируем из moderation.py
    router,
    ADMIN_IDS,
    WAITING_CATEGORY,
)

# Экспортируем эти имена наружу (для удобства импорта)
__all__ = [
    "router",
    "ADMIN_IDS",
    "WAITING_CATEGORY",
]
