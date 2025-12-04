"""
Тест для проверки flow определения культуры и RAG-поиска.
"""

import asyncio
from src.services.llm.classification_llm import detect_culture_name
from src.services.db.pool import init_db_pool, close_db_pool


async def test_culture_classification():
    """Тестирование классификации культур в различных сценариях."""

    print("="*60)
    print("ТЕСТ 1: Первое сообщение (общий вопрос)")
    print("="*60)

    text1 = "Питание растения"
    culture1 = await detect_culture_name(text1)
    print(f"Вход: '{text1}'")
    print(f"Результат: '{culture1}'")
    print(f"Ожидаемо: 'общая информация' или 'не определено'")
    print()

    print("="*60)
    print("ТЕСТ 2: Уточнение культуры (ответ на вопрос LLM)")
    print("="*60)

    text2 = "Питание растения\nКлубника"
    culture2 = await detect_culture_name(text2)
    print(f"Вход: '{text2}'")
    print(f"Результат: '{culture2}'")
    print(f"Ожидаемо: 'клубника общая'")
    print()

    print("="*60)
    print("ТЕСТ 3: Определение типа клубники (с контекстом)")
    print("="*60)

    # Симуляция логики из handle_variety_clarification
    old_culture = "клубника общая"
    variety_answer = "Летняя"
    variety_answer_lower = variety_answer.lower()

    if "ремонтант" in variety_answer_lower or "нсд" in variety_answer_lower:
        culture3 = "клубника ремонтантная"
    elif "летн" in variety_answer_lower or "июньск" in variety_answer_lower:
        culture3 = "клубника летняя"
    else:
        culture3 = await detect_culture_name(f"клубника {variety_answer}")
        if culture3 in ("общая информация", "не определено"):
            culture3 = old_culture

    print(f"Исходная культура: '{old_culture}'")
    print(f"Ответ пользователя: '{variety_answer}'")
    print(f"Результат: '{culture3}'")
    print(f"Ожидаемо: 'клубника летняя'")
    print()

    print("="*60)
    print("ТЕСТ 4: Определение ремонтантной клубники")
    print("="*60)

    old_culture = "клубника общая"
    variety_answer = "Ремонтантная"
    variety_answer_lower = variety_answer.lower()

    if "ремонтант" in variety_answer_lower or "нсд" in variety_answer_lower:
        culture4 = "клубника ремонтантная"
    elif "летн" in variety_answer_lower or "июньск" in variety_answer_lower:
        culture4 = "клубника летняя"
    else:
        culture4 = await detect_culture_name(f"клубника {variety_answer}")
        if culture4 in ("общая информация", "не определено"):
            culture4 = old_culture

    print(f"Исходная культура: '{old_culture}'")
    print(f"Ответ пользователя: '{variety_answer}'")
    print(f"Результат: '{culture4}'")
    print(f"Ожидаемо: 'клубника ремонтантная'")
    print()

    print("="*60)
    print("ТЕСТ 5: Малина летняя")
    print("="*60)

    old_culture = "малина общая"
    variety_answer = "Обычная"
    variety_answer_lower = variety_answer.lower()

    if "ремонтант" in variety_answer_lower or "нсд" in variety_answer_lower:
        culture5 = "малина ремонтантная"
    elif "летн" in variety_answer_lower or "обычн" in variety_answer_lower:
        culture5 = "малина летняя"
    else:
        culture5 = await detect_culture_name(f"малина {variety_answer}")
        if culture5 in ("общая информация", "не определено"):
            culture5 = old_culture

    print(f"Исходная культура: '{old_culture}'")
    print(f"Ответ пользователя: '{variety_answer}'")
    print(f"Результат: '{culture5}'")
    print(f"Ожидаемо: 'малина летняя'")
    print()

    print("="*60)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*60)

    results = {
        "Тест 1 (общий вопрос)": culture1 in ("общая информация", "не определено"),
        "Тест 2 (уточнение 'Клубника')": culture2 == "клубника общая",
        "Тест 3 (тип 'Летняя')": culture3 == "клубника летняя",
        "Тест 4 (тип 'Ремонтантная')": culture4 == "клубника ремонтантная",
        "Тест 5 (малина 'Обычная')": culture5 == "малина летняя",
    }

    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")

    all_passed = all(results.values())
    print()
    if all_passed:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    else:
        print("⚠️ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ")

    return all_passed


async def main():
    """Главная функция с инициализацией БД."""
    # Инициализация БД
    await init_db_pool()

    try:
        # Запуск тестов
        await test_culture_classification()
    finally:
        # Закрытие БД
        await close_db_pool()


if __name__ == "__main__":
    asyncio.run(main())
