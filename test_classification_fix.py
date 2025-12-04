#!/usr/bin/env python3
"""
Тестовый скрипт для проверки исправления бага классификации.

Проверяем, что "питание клубники обычной" определяется как "клубника летняя",
а не "клубника ремонтантная".
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.services.llm.classification_llm import detect_culture_name
from src.services.db.pool import init_db_pool, close_db_pool


async def test_classification_fix():
    """Тестируем исправление бага с 'обычная' -> 'летняя'."""

    test_cases = [
        # Основной тестовый кейс из бага
        ("питание клубники обычной", "клубника летняя"),

        # Дополнительные кейсы для клубники
        ("питание клубники летней", "клубника летняя"),
        ("питание клубники традиционной", "клубника летняя"),
        ("питание клубники июньской", "клубника летняя"),
        ("питание клубники ремонтантной", "клубника ремонтантная"),
        ("питание клубники НСД", "клубника ремонтантная"),
        ("питание клубники", "клубника общая"),

        # Кейсы для малины
        ("питание малины обычной", "малина летняя"),
        ("питание малины летней", "малина летняя"),
        ("питание малины ремонтантной", "малина ремонтантная"),
        ("питание малины", "малина общая"),

        # Пограничные случаи
        ("как удобрять ягоды", "общая информация"),
        ("погода завтра", "не определено"),
    ]

    # Инициализируем пул БД
    print("Инициализация пула БД...")
    try:
        await init_db_pool()
        print("✅ Пул БД инициализирован")
    except Exception as e:
        print(f"⚠️  Ошибка инициализации БД: {e}")
        print("Продолжаем без БД (классификатор будет работать без списка культур из БД)")

    print()
    print("=" * 80)
    print("ТЕСТ КЛАССИФИКАЦИИ КУЛЬТУР")
    print("=" * 80)
    print()

    passed = 0
    failed = 0

    for i, (question, expected) in enumerate(test_cases, 1):
        print(f"Тест {i}/{len(test_cases)}: {question!r}")
        print(f"  Ожидается: {expected!r}")

        detected = await detect_culture_name(question)

        print(f"  Получено:  {detected!r}")

        if detected == expected:
            print("  ✅ PASS")
            passed += 1
        else:
            print("  ❌ FAIL")
            failed += 1

        print()

    print("=" * 80)
    print(f"ИТОГО: {passed} успешных, {failed} неудачных из {len(test_cases)}")
    print("=" * 80)

    # Закрываем пул БД
    try:
        await close_db_pool()
        print("\n✅ Пул БД закрыт")
    except Exception:
        pass

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(test_classification_fix())
    sys.exit(0 if success else 1)
