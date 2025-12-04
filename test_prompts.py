#!/usr/bin/env python3
"""
Тестовый скрипт для демонстрации новой системы промптов.

Показывает, как разные категории консультаций получают свои специфичные инструкции.
"""

import asyncio
from src.prompts.consultation_prompts import build_consultation_system_prompt


async def test_prompts():
    """Тестирует сборку промптов для разных категорий."""

    print("=" * 80)
    print("ТЕСТ НОВОЙ СИСТЕМЫ ПРОМПТОВ")
    print("=" * 80)

    # Тестовые данные
    test_cases = [
        {
            "category": "питание растений",
            "culture": "малина ремонтантная",
            "description": "Консультация по питанию малины"
        },
        {
            "category": "посадка и уход",
            "culture": "голубика",
            "description": "Консультация по посадке голубики"
        },
        {
            "category": "защита растений",
            "culture": "клубника летняя",
            "description": "Консультация по болезням клубники"
        },
        {
            "category": "улучшение почвы",
            "culture": "смородина",
            "description": "Консультация по улучшению почвы"
        },
        {
            "category": "подбор сортов",
            "culture": "малина",
            "description": "Консультация по подбору сортов"
        },
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['description']}")
        print("-" * 80)

        # Собираем промпт (без KB snippets для простоты)
        prompt = await build_consultation_system_prompt(
            culture=test_case['culture'],
            kb_snippets=[],
            consultation_category=test_case['category']
        )

        # Выводим статистику
        lines = prompt.split('\n')
        print(f"   Категория: {test_case['category']}")
        print(f"   Культура: {test_case['culture']}")
        print(f"   Длина промпта: {len(prompt)} символов")
        print(f"   Количество строк: {len(lines)}")

        # Проверяем наличие категорийной специфики
        category_keywords = {
            "питание растений": ["NPK", "подкормок", "дефицит", "удобрений"],
            "посадка и уход": ["посадки", "схемы", "обрезка", "уход"],
            "защита растений": ["болезней", "вредителей", "диагностика", "препаратов"],
            "улучшение почвы": ["почвы", "pH", "плодородия", "структуры"],
            "подбор сортов": ["сортов", "зимостойкость", "урожайность", "характеристики"],
        }

        keywords = category_keywords.get(test_case['category'], [])
        found_keywords = [kw for kw in keywords if kw.lower() in prompt.lower()]

        if found_keywords:
            print(f"   ✓ Найдены специфичные термины: {', '.join(found_keywords)}")
        else:
            print(f"   ⚠ Специфичные термины не найдены")

        # Показываем фрагмент промпта с категорийной спецификой
        if "СПЕЦИФИКА КАТЕГОРИИ" in prompt:
            print(f"   ✓ Категорийный промпт добавлен")
            # Находим и показываем первые 3 строки категорийного промпта
            spec_start = prompt.find("СПЕЦИФИКА КАТЕГОРИИ")
            spec_fragment = prompt[spec_start:spec_start+200]
            print(f"   Фрагмент: {spec_fragment}...")
        else:
            print(f"   ⚠ Категорийный промпт НЕ добавлен")

    print("\n" + "=" * 80)
    print("ИТОГОВАЯ ПРОВЕРКА")
    print("=" * 80)

    # Проверяем, что базовый промпт общий для всех
    prompt1 = await build_consultation_system_prompt("малина", [], "питание растений")
    prompt2 = await build_consultation_system_prompt("малина", [], "посадка и уход")

    # Базовая часть должна быть одинаковой
    base_check = "Ты — профессиональный агроном-консультант" in prompt1
    base_check = base_check and "Ты — профессиональный агроном-консультант" in prompt2

    # Категорийные части должны отличаться
    diff_check = "питанию" in prompt1.lower() and "питанию" not in prompt2.lower()
    diff_check = diff_check or ("посадке" in prompt2.lower() and "посадке" not in prompt1.lower())

    print(f"\n✓ Базовый промпт общий для всех: {'ДА' if base_check else 'НЕТ'}")
    print(f"✓ Категорийные промпты различаются: {'ДА' if diff_check else 'НЕТ'}")
    print(f"✓ Система работает корректно: {'ДА' if (base_check and diff_check) else 'НЕТ'}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(test_prompts())
