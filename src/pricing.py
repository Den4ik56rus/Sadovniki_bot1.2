# src/pricing.py
"""
Прайсы токенов для всех платных операций бота.

Редактируйте этот файл для изменения стоимости операций.
Все значения указаны в токенах.
"""

# =============================================================================
# КОНСУЛЬТАЦИИ
# =============================================================================

# Стоимость по умолчанию (за одну консультацию)
COST_NEW_TOPIC = 1

# Стоимость одной фазы (Тип B / Тип C)
PHASE_COST = 2

# Стоимость расширенного ответа (для простых вопросов — alias для PHASE_COST)
EXTENDED_ANSWER_COST = 2

# Бесплатные токены для новых пользователей (fallback, если не задано в admin_settings)
TRIAL_QUESTIONS = 3


async def get_trial_questions() -> int:
    """Возвращает количество бесплатных токенов из admin_settings, fallback на 3."""
    try:
        from src.services.db import settings_repo
        value = await settings_repo.get_setting('trial_questions', '3')
        return int(value)
    except (ValueError, TypeError, Exception):
        return TRIAL_QUESTIONS


def pluralize_questions(n: int) -> str:
    """Русское склонение слова 'токен': 1 токен, 2 токена, 5 токенов."""
    if 11 <= n % 100 <= 19:
        return f"{n} токенов"
    last_digit = n % 10
    if last_digit == 1:
        return f"{n} токен"
    elif 2 <= last_digit <= 4:
        return f"{n} токена"
    else:
        return f"{n} токенов"


# =============================================================================
# КЛАССИФИКАЦИЯ СЛОЖНОСТИ
# =============================================================================

COMPLEXITY_TIERS = {
    "short_answer": {
        "cost": 1,
        "description": "Короткий ответ на конкретный вопрос",
        "expected_length": 300,
    },
    "long_answer": {
        "cost": 2,
        "description": "Длинный ответ (план на 1 фазу роста)",
        "expected_length": 1200,
        "phases": ["весна-цветение", "цветение-плодоношение", "плодоношение-зима"],
        "offer_next_phase": True,
        "offer_turnkey": True,
    },
    "turnkey_solution": {
        "cost": None,  # Только покупка продукта
        "payment_required": True,
        "price_rub": 1190.00,
        "description": "Готовое решение: Уход под ключ на сезон",
        "includes": ["питание", "защита", "уходные работы", "чек-лист"],
    },
}

SEASONAL_PHASES = {
    "весна-цветение": {
        "next": "цветение-плодоношение",
        "months": ["март", "апрель", "май"],
    },
    "цветение-плодоношение": {
        "next": "плодоношение-зима",
        "months": ["июнь", "июль", "август"],
    },
    "плодоношение-зима": {
        "next": None,
        "months": ["сентябрь", "октябрь", "ноябрь", "февраль"],
    },
}

# Красивые названия фаз по ТЗ
PHASE_DISPLAY_NAMES = {
    "весна-цветение": "ранняя весна — начало цветения",
    "цветение-плодоношение": "цветение — окончание плодоношения",
    "плодоношение-зима": "конец плодоношения — уход в зиму",
}


def get_complexity_cost(tier: str) -> int:
    """Получить стоимость в токенах по уровню сложности."""
    tier_info = COMPLEXITY_TIERS.get(tier)
    if not tier_info:
        return COST_NEW_TOPIC
    cost = tier_info["cost"]
    if cost is None:
        raise ValueError(f"Tier {tier} требует покупки продукта, не токенов")
    return cost


def get_next_phase(current_phase: str) -> str | None:
    """Получить следующую фазу сезона."""
    phase_info = SEASONAL_PHASES.get(current_phase)
    return phase_info["next"] if phase_info else None


def get_phase_display_name(phase_key: str) -> str:
    """Получить красивое название фазы для отображения пользователю."""
    return PHASE_DISPLAY_NAMES.get(phase_key, phase_key)


def should_suggest_product(tier: str) -> bool:
    """Нужно ли предлагать готовое решение."""
    return tier == "turnkey_solution"


# DEPRECATED: используется только в legacy-коде, будет удалено
# Новая логика использует complexity-based pricing через get_complexity_cost()
CATEGORY_COSTS = {
    "питание растений": 2,
    "защита растений": 2,
}


def get_consultation_cost(category: str) -> int:
    """DEPRECATED: Возвращает стоимость по категории. Используйте get_complexity_cost()."""
    return CATEGORY_COSTS.get(category, COST_NEW_TOPIC)
