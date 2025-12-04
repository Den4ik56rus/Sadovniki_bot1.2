# src/prompts/category_prompts/__init__.py

"""
Промпты для разных категорий консультаций.
"""

from .nutrition import get_nutrition_category_prompt
from .planting_care import get_planting_care_category_prompt
from .diseases_pests import get_diseases_pests_category_prompt
from .soil_improvement import get_soil_improvement_category_prompt
from .variety_selection import get_variety_selection_category_prompt

__all__ = [
    "get_nutrition_category_prompt",
    "get_planting_care_category_prompt",
    "get_diseases_pests_category_prompt",
    "get_soil_improvement_category_prompt",
    "get_variety_selection_category_prompt",
]
