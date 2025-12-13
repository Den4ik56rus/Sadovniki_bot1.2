# src/prompts/category_prompts/_culture_groups.py

"""
Маппинг культур на группы для категорийных промптов.

Каждая категория консультации может иметь разные группы культур
с уникальными промптами.

Формат словаря:
    CULTURE_GROUPS = {
        "категория консультации": {
            "культура": "group_key",
            ...
        },
        ...
    }

Naming convention для group_key:
    - group_{letter}_{descriptive_name}
    - Примеры: group_a_strawberry_raspberry, group_b_berries
"""

from typing import Dict, Optional

# ==================================================================
# ПИТАНИЕ РАСТЕНИЙ
# ==================================================================
NUTRITION_CULTURE_GROUPS = {
    # Группа Strawberry: Клубника (все типы)
    "клубника летняя": "group_strawberry",
    "клубника ремонтантная": "group_strawberry",
    "клубника общая": "group_strawberry",

    # Группа Raspberry: Малина (все типы)
    "малина летняя": "group_raspberry",
    "малина ремонтантная": "group_raspberry",
    "малина общая": "group_raspberry",

    # Группа Raspberry+Ежевика: Ежевика использует тот же промпт, что и малина
    "ежевика летняя": "group_raspberry",
    "ежевика ремонтантная": "group_raspberry",
    "ежевика общая": "group_raspberry",
    "ежевика": "group_raspberry",

    # Группа B: Смородина + Голубика + Жимолость + Крыжовник + Ирга + Арония
    "смородина": "group_b_berries",
    "голубика": "group_b_berries",
    "жимолость": "group_b_berries",
    "крыжовник": "group_b_berries",
    "ирга": "group_b_berries",
    "арония": "group_b_berries",
}

# ==================================================================
# ПОСАДКА И УХОД (пока все культуры используют один промпт)
# ==================================================================
PLANTING_CARE_CULTURE_GROUPS = {
    # Будет заполнено позже по мере необходимости
}

# ==================================================================
# ЗАЩИТА РАСТЕНИЙ
# ==================================================================
DISEASES_PESTS_CULTURE_GROUPS = {
    # Будет заполнено позже по мере необходимости
}

# ==================================================================
# УЛУЧШЕНИЕ ПОЧВЫ
# ==================================================================
SOIL_IMPROVEMENT_CULTURE_GROUPS = {
    # Будет заполнено позже по мере необходимости
}

# ==================================================================
# ПОДБОР СОРТОВ
# ==================================================================
VARIETY_SELECTION_CULTURE_GROUPS = {
    # Будет заполнено позже по мере необходимости
}

# ==================================================================
# МАСТЕР-СЛОВАРЬ
# ==================================================================
CULTURE_GROUPS: Dict[str, Dict[str, str]] = {
    "питание растений": NUTRITION_CULTURE_GROUPS,
    "посадка и уход": PLANTING_CARE_CULTURE_GROUPS,
    "защита растений": DISEASES_PESTS_CULTURE_GROUPS,
    "болезни и вредители": DISEASES_PESTS_CULTURE_GROUPS,  # алиас
    "улучшение почвы": SOIL_IMPROVEMENT_CULTURE_GROUPS,
    "подбор сортов": VARIETY_SELECTION_CULTURE_GROUPS,
    "подбор сорта": VARIETY_SELECTION_CULTURE_GROUPS,  # алиас
}


def get_prompt_group_for_culture(
    consultation_category: str,
    culture: str
) -> Optional[str]:
    """
    Возвращает ключ группы промптов для данной категории и культуры.

    Args:
        consultation_category: Тип консультации ('питание растений' и т.п.)
        culture: Название культуры ('малина летняя', 'голубика' и т.п.)

    Returns:
        Ключ группы (например, 'group_a_strawberry_raspberry') или None

    Примеры:
        >>> get_prompt_group_for_culture("питание растений", "малина летняя")
        'group_a_strawberry_raspberry'

        >>> get_prompt_group_for_culture("питание растений", "голубика")
        'group_b_berries'

        >>> get_prompt_group_for_culture("посадка и уход", "малина летняя")
        None  # Нет специфичной группы для этой категории
    """
    category_normalized = consultation_category.lower().strip()
    culture_normalized = culture.lower().strip()

    category_groups = CULTURE_GROUPS.get(category_normalized)
    if not category_groups:
        return None

    return category_groups.get(culture_normalized)
