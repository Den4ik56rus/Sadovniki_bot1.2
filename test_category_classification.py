#!/usr/bin/env python3
# test_category_classification.py

"""
Скрипт для тестирования автоопределения КАТЕГОРИИ консультации.

Тестирует функцию detect_category_and_culture на наборе тестовых фраз
и проверяет корректность классификации категорий.
"""

import asyncio
import sys
from typing import List, Tuple

# Добавляем корневую директорию в путь для импортов
sys.path.insert(0, "/Users/denis/Desktop/Main/Sadovniki-bot/Sadovniki_bot1.2")

from src.services.llm.classification_llm import detect_category_and_culture
from src.services.db.pool import init_db_pool, close_db_pool


# Тестовые кейсы: (текст вопроса, ожидаемая категория, ожидаемая культура или None для игнорирования)
TEST_CASES: List[Tuple[str, str, str | None]] = [
    # === ПОСАДКА И УХОД ===
    ("Когда сажать ремонтантную клубнику", "посадка и уход", "клубника ремонтантная"),
    ("Как правильно посадить малину весной", "посадка и уход", "малина общая"),
    ("Когда пересаживать клубнику на новое место", "посадка и уход", "клубника общая"),
    ("Как поливать голубику в жару", "посадка и уход", "голубика"),
    ("Когда обрезать малину осенью", "посадка и уход", "малина общая"),
    ("Как укрыть ежевику на зиму", "посадка и уход", "ежевика"),
    ("Нужно ли мульчировать клубнику", "посадка и уход", "клубника общая"),
    ("На каком расстоянии сажать смородину", "посадка и уход", "смородина"),

    # === ПИТАНИЕ РАСТЕНИЙ ===
    ("Чем подкормить малину весной", "питание растений", "малина общая"),
    ("Какие удобрения нужны клубнике", "питание растений", "клубника общая"),
    ("Когда вносить азотные удобрения под ягодные", "питание растений", None),
    ("Подкормка голубики - чем и когда", "питание растений", "голубика"),
    ("Нужен ли навоз для малины", "питание растений", "малина общая"),
    ("Как удобрять смородину осенью", "питание растений", "смородина"),
    ("Чем подкормить ежевику для урожая", "питание растений", "ежевика"),

    # === ЗАЩИТА РАСТЕНИЙ ===
    ("Как избавиться от тли на смородине", "защита растений", "смородина"),
    ("У клубники желтеют листья что делать", "защита растений", "клубника общая"),
    ("На малине появились черные точки", "защита растений", "малина общая"),
    ("Чем обработать голубику от болезней", "защита растений", "голубика"),
    ("Паутинный клещ на клубнике", "защита растений", "клубника общая"),
    ("Мучнистая роса на крыжовнике", "защита растений", "крыжовник"),
    ("Вредители на жимолости - как бороться", "защита растений", "жимолость"),
    ("Серая гниль на ягодах малины", "защита растений", "малина общая"),

    # === УЛУЧШЕНИЕ ПОЧВЫ ===
    ("Какой pH нужен для голубики", "улучшение почвы", "голубика"),
    ("Как подкислить почву для голубики", "улучшение почвы", "голубика"),
    ("Какая почва нужна для малины", "улучшение почвы", "малина общая"),
    ("Нужно ли известковать землю под клубнику", "улучшение почвы", "клубника общая"),
    ("Как улучшить глинистую почву для ягодных", "улучшение почвы", None),
    ("Дренаж для голубики - как сделать", "улучшение почвы", "голубика"),

    # === ПОДБОР СОРТА ===
    ("Какой сорт клубники выбрать для Урала", "подбор сорта", "клубника общая"),
    ("Лучшие сорта ремонтантной малины", "подбор сорта", "малина ремонтантная"),
    ("Посоветуйте морозостойкую голубику", "подбор сорта", "голубика"),
    ("Какую смородину посадить в тени", "подбор сорта", "смородина"),
    ("Самые урожайные сорта ежевики", "подбор сорта", "ежевика"),
    ("Какой крыжовник без шипов выбрать", "подбор сорта", "крыжовник"),

    # === ДРУГАЯ ТЕМА (нерелевантные вопросы) ===
    ("Сколько стоит саженец клубники", "другая тема", None),
    ("Где купить малину в Москве", "другая тема", None),
]


async def run_tests():
    """Запускает все тесты и выводит результаты."""

    print("="*80)
    print("ТЕСТИРОВАНИЕ АВТООПРЕДЕЛЕНИЯ КАТЕГОРИИ КОНСУЛЬТАЦИИ")
    print("="*80)
    print()

    # Инициализируем пул БД
    await init_db_pool()

    total = len(TEST_CASES)
    passed = 0
    failed = 0
    errors_list = []

    # Группируем результаты по категориям
    category_results = {}

    for i, (text, expected_category, expected_culture) in enumerate(TEST_CASES, 1):
        try:
            category, culture, _correction, cost, tokens = await detect_category_and_culture(text)

            # Проверяем категорию
            category_correct = category == expected_category

            # Проверяем культуру (если указана)
            culture_correct = expected_culture is None or culture == expected_culture

            is_correct = category_correct and culture_correct

            if is_correct:
                status = "✅ PASS"
                passed += 1
            else:
                status = "❌ FAIL"
                failed += 1
                error_info = {
                    "text": text,
                    "expected_category": expected_category,
                    "got_category": category,
                }
                if expected_culture is not None:
                    error_info["expected_culture"] = expected_culture
                    error_info["got_culture"] = culture
                errors_list.append(error_info)

            # Собираем статистику по категориям
            if expected_category not in category_results:
                category_results[expected_category] = {"total": 0, "passed": 0}
            category_results[expected_category]["total"] += 1
            if is_correct:
                category_results[expected_category]["passed"] += 1

            print(f"[{i}/{total}] {status}")
            print(f"  Вопрос: {text}")
            print(f"  Категория: ожидалось '{expected_category}', получено '{category}'")
            if expected_culture is not None:
                print(f"  Культура: ожидалось '{expected_culture}', получено '{culture}'")
            print(f"  Стоимость: ${cost:.6f}, токенов: {tokens}")
            print()

        except Exception as e:
            status = "💥 ERROR"
            failed += 1
            errors_list.append({
                "text": text,
                "expected_category": expected_category,
                "error": str(e),
            })
            print(f"[{i}/{total}] {status}")
            print(f"  Вопрос: {text}")
            print(f"  Ошибка: {e}")
            print()

    # Закрываем пул БД
    await close_db_pool()

    # Итоги
    print("="*80)
    print("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("="*80)
    print(f"Всего тестов: {total}")
    print(f"Успешно: {passed} ({passed*100//total}%)")
    print(f"Провалено: {failed} ({failed*100//total}%)")
    print()

    # Статистика по категориям
    print("="*80)
    print("СТАТИСТИКА ПО КАТЕГОРИЯМ")
    print("="*80)
    for cat, stats in sorted(category_results.items()):
        pct = stats["passed"]*100//stats["total"] if stats["total"] > 0 else 0
        print(f"  {cat}: {stats['passed']}/{stats['total']} ({pct}%)")
    print()

    if errors_list:
        print("="*80)
        print("ОШИБКИ КЛАССИФИКАЦИИ")
        print("="*80)
        for i, error in enumerate(errors_list, 1):
            print(f"\n{i}. Вопрос: {error['text']}")
            print(f"   Ожидалась категория: {error['expected_category']}")
            if "got_category" in error:
                print(f"   Получена категория: {error['got_category']}")
            if "expected_culture" in error:
                print(f"   Ожидалась культура: {error['expected_culture']}")
            if "got_culture" in error:
                print(f"   Получена культура: {error['got_culture']}")
            if "error" in error:
                print(f"   Ошибка: {error['error']}")
        print()

    return passed, failed


if __name__ == "__main__":
    passed, failed = asyncio.run(run_tests())

    # Возвращаем код выхода (0 = успех, 1 = есть ошибки)
    sys.exit(0 if failed == 0 else 1)
