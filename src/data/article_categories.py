# src/data/article_categories.py

"""
Маппинг категорий статей и культур для пакетной генерации.

6 категорий × 8 культур/вариантов = 48 статей.
"""

from typing import List, Dict, Any, Optional


# Категории статей — ключ → label → consultation_category (для RAG фильтрации)
ARTICLE_CATEGORIES = [
    {
        "key": "nutrition",
        "label": "Питание растений",
        "consultation_category": "питание растений",
    },
    {
        "key": "planting_care",
        "label": "Посадка и уход",
        "consultation_category": "посадка и уход",
    },
    {
        "key": "protection",
        "label": "Защита растений",
        "consultation_category": "защита растений",
    },
    {
        "key": "soil",
        "label": "Улучшение почвы",
        "consultation_category": "улучшение почвы",
    },
    {
        "key": "varieties",
        "label": "Подбор сорта",
        "consultation_category": "подбор сорта",
    },
    {
        "key": "pruning",
        "label": "Обрезка",
        "consultation_category": "посадка и уход",  # нет отдельной категории — используем ближайшую
    },
]

# Культуры для пакетной генерации
BATCH_CULTURES = [
    {"culture_key": "strawberry", "variety_key": "summer", "label": "Клубника летняя", "culture_russian": "клубника летняя"},
    {"culture_key": "strawberry", "variety_key": "remontant", "label": "Клубника ремонтантная", "culture_russian": "клубника ремонтантная"},
    {"culture_key": "raspberry", "variety_key": "summer", "label": "Малина летняя", "culture_russian": "малина летняя"},
    {"culture_key": "raspberry", "variety_key": "remontant", "label": "Малина ремонтантная", "culture_russian": "малина ремонтантная"},
    {"culture_key": "currant", "variety_key": None, "label": "Смородина", "culture_russian": "смородина"},
    {"culture_key": "honeysuckle", "variety_key": None, "label": "Жимолость", "culture_russian": "жимолость"},
    {"culture_key": "blackberry", "variety_key": None, "label": "Ежевика", "culture_russian": "ежевика"},
    {"culture_key": "blueberry", "variety_key": None, "label": "Голубика", "culture_russian": "голубика"},
]


def get_category_label(category_key: str) -> Optional[str]:
    """Получить label категории по ключу."""
    for cat in ARTICLE_CATEGORIES:
        if cat["key"] == category_key:
            return cat["label"]
    return None


def get_category_consultation(category_key: str) -> Optional[str]:
    """Получить consultation_category для RAG-фильтрации."""
    for cat in ARTICLE_CATEGORIES:
        if cat["key"] == category_key:
            return cat["consultation_category"]
    return None


def get_culture_label_for_batch(culture_key: str, variety_key: Optional[str] = None) -> Optional[str]:
    """Получить label культуры для batch."""
    for c in BATCH_CULTURES:
        if c["culture_key"] == culture_key and c["variety_key"] == variety_key:
            return c["label"]
    return None


def get_culture_russian_for_batch(culture_key: str, variety_key: Optional[str] = None) -> Optional[str]:
    """Получить русское название культуры для RAG subcategory."""
    for c in BATCH_CULTURES:
        if c["culture_key"] == culture_key and c["variety_key"] == variety_key:
            return c["culture_russian"]
    return None


def build_article_topic(category_label: str, culture_label: str) -> str:
    """Построить тему статьи: 'Питание растений — Клубника летняя'."""
    return f"{category_label} — {culture_label}"


def get_all_article_definitions() -> Dict[str, Any]:
    """Полный набор данных для фронтенда: категории + культуры."""
    return {
        "categories": ARTICLE_CATEGORIES,
        "cultures": BATCH_CULTURES,
    }


def get_all_combinations() -> List[Dict[str, Any]]:
    """Все 48 комбинаций категория × культура."""
    result = []
    for cat in ARTICLE_CATEGORIES:
        for culture in BATCH_CULTURES:
            result.append({
                "category_key": cat["key"],
                "category_label": cat["label"],
                "consultation_category": cat["consultation_category"],
                "culture_key": culture["culture_key"],
                "variety_key": culture["variety_key"],
                "culture_label": culture["label"],
                "culture_russian": culture["culture_russian"],
                "topic": build_article_topic(cat["label"], culture["label"]),
            })
    return result
