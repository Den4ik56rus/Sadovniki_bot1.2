# src/pricing.py
"""
Прайсы вопросов для всех платных операций бота.

Редактируйте этот файл для изменения стоимости операций.
Все значения указаны в вопросах.
"""

# =============================================================================
# КОНСУЛЬТАЦИИ
# =============================================================================

# Стоимость по умолчанию (за одну консультацию)
COST_NEW_TOPIC = 1

# Бесплатные вопросы для новых пользователей (fallback, если не задано в admin_settings)
TRIAL_QUESTIONS = 3


async def get_trial_questions() -> int:
    """Возвращает количество бесплатных вопросов из admin_settings, fallback на 3."""
    try:
        from src.services.db import settings_repo
        value = await settings_repo.get_setting('trial_questions', '3')
        return int(value)
    except (ValueError, TypeError, Exception):
        return TRIAL_QUESTIONS

# Дифференцированная стоимость по категориям
# Категории, не указанные здесь, стоят COST_NEW_TOPIC (1 вопрос)
CATEGORY_COSTS = {
    "питание растений": 2,
    "защита растений": 2,
}


def get_consultation_cost(category: str) -> int:
    """Возвращает стоимость консультации в вопросах для данной категории."""
    return CATEGORY_COSTS.get(category, COST_NEW_TOPIC)


def pluralize_questions(n: int) -> str:
    """Русское склонение слова 'вопрос': 1 вопрос, 2 вопроса, 5 вопросов."""
    if 11 <= n % 100 <= 19:
        return f"{n} вопросов"
    last_digit = n % 10
    if last_digit == 1:
        return f"{n} вопрос"
    elif 2 <= last_digit <= 4:
        return f"{n} вопроса"
    else:
        return f"{n} вопросов"
