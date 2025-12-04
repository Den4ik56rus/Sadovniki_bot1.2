#!/usr/bin/env python3
"""
Простой тестовый скрипт для демонстрации новой системы промптов (без БД).
"""

from src.prompts.base_prompt import get_base_system_prompt
from src.prompts.category_prompts import (
    get_nutrition_category_prompt,
    get_planting_care_category_prompt,
    get_diseases_pests_category_prompt,
    get_soil_improvement_category_prompt,
    get_variety_selection_category_prompt,
)


def test_prompts_simple():
    """Тестирует систему промптов без обращения к БД."""

    print("=" * 80)
    print("ТЕСТ НОВОЙ СИСТЕМЫ ПРОМПТОВ")
    print("=" * 80)

    # Базовый промпт (общий для всех)
    print("\n1. БАЗОВЫЙ ПРОМПТ (общий для всех категорий)")
    print("-" * 80)
    base_prompt = get_base_system_prompt()
    print(f"   Длина: {len(base_prompt)} символов")
    print(f"   Первые 200 символов:")
    print(f"   {base_prompt[:200]}...")

    # Категорийные промпты
    test_cases = [
        {
            "name": "Питание растений",
            "func": get_nutrition_category_prompt,
            "culture": "малина ремонтантная",
            "keywords": ["NPK", "подкормок", "дефицит", "удобрений"]
        },
        {
            "name": "Посадка и уход",
            "func": get_planting_care_category_prompt,
            "culture": "голубика",
            "keywords": ["посадки", "схемы", "обрезка", "уход"]
        },
        {
            "name": "Защита растений",
            "func": get_diseases_pests_category_prompt,
            "culture": "клубника летняя",
            "keywords": ["болезней", "вредителей", "диагностика", "препаратов"]
        },
        {
            "name": "Улучшение почвы",
            "func": get_soil_improvement_category_prompt,
            "culture": "смородина",
            "keywords": ["почвы", "pH", "плодородия", "структуры"]
        },
        {
            "name": "Подбор сортов",
            "func": get_variety_selection_category_prompt,
            "culture": "малина",
            "keywords": ["сортов", "зимостойкость", "урожайность", "ремонтантные"]
        },
    ]

    for i, test_case in enumerate(test_cases, 2):
        print(f"\n{i}. КАТЕГОРИЯ: {test_case['name']}")
        print("-" * 80)

        # Получаем категорийный промпт
        category_prompt = test_case['func'](test_case['culture'])

        print(f"   Культура: {test_case['culture']}")
        print(f"   Длина: {len(category_prompt)} символов")

        # Проверяем наличие специфичных терминов
        found_keywords = [kw for kw in test_case['keywords'] if kw.lower() in category_prompt.lower()]
        print(f"   Найдено терминов: {len(found_keywords)}/{len(test_case['keywords'])}")
        if found_keywords:
            print(f"   ✓ Термины: {', '.join(found_keywords)}")
        else:
            print(f"   ⚠ Специфичные термины не найдены")

        # Показываем фрагмент
        lines = category_prompt.split('\n')
        print(f"   Первые 3 строки:")
        for line in lines[:3]:
            print(f"   {line}")

    # Итоговая проверка
    print("\n" + "=" * 80)
    print("ИТОГОВАЯ ПРОВЕРКА")
    print("=" * 80)

    # Проверяем уникальность категорийных промптов
    prompt_nutrition = get_nutrition_category_prompt("малина")
    prompt_planting = get_planting_care_category_prompt("малина")

    different = prompt_nutrition != prompt_planting
    print(f"\n✓ Категорийные промпты различаются: {'ДА' if different else 'НЕТ'}")

    # Проверяем, что базовый промпт одинаковый
    base1 = get_base_system_prompt()
    base2 = get_base_system_prompt()
    same_base = base1 == base2
    print(f"✓ Базовый промпт стабильный: {'ДА' if same_base else 'НЕТ'}")

    # Проверяем структуру
    has_base_elements = all([
        "профессиональный агроном" in base1.lower(),
        "ягодным культурам" in base1.lower(),
        "ЭТАП 1" in base1,
        "ЭТАП 2" in base1,
    ])
    print(f"✓ Базовый промпт содержит все элементы: {'ДА' if has_base_elements else 'НЕТ'}")

    print(f"\n✓ Система работает корректно: {'ДА' if (different and same_base and has_base_elements) else 'НЕТ'}")

    print("\n" + "=" * 80)
    print("СТРУКТУРА ФАЙЛОВ")
    print("=" * 80)
    print("""
    src/prompts/
    ├── base_prompt.py              ✓ Базовый промпт (роль, scope, формат)
    ├── category_prompts/
    │   ├── __init__.py             ✓ Экспорты
    │   ├── nutrition.py            ✓ Питание растений
    │   ├── planting_care.py        ✓ Посадка и уход
    │   ├── diseases_pests.py       ✓ Защита от болезней
    │   ├── soil_improvement.py     ✓ Улучшение почвы
    │   └── variety_selection.py    ✓ Подбор сортов
    └── consultation_prompts.py     ✓ Оркестратор (собирает финальный промпт)

    КАК ЭТО РАБОТАЕТ:
    1. build_consultation_system_prompt() - главная функция
    2. Берет базовый промпт (общий)
    3. Добавляет категорийный промпт (специфичный)
    4. Добавляет контекст из базы знаний (RAG)
    5. Добавляет словарь терминологии
    6. Возвращает полный промпт для LLM
    """)
    print("=" * 80)


if __name__ == "__main__":
    test_prompts_simple()
