#!/usr/bin/env python3
"""
Тестирование новых правил логики формирования ответа.

Проверяет:
1. Наличие секции answer_logic в промпте
2. Правильный порядок секций
3. Содержимое секции
"""

import asyncio
from src.prompts.base_prompt import (
    build_base_prompt,
    _section_answer_logic,
)
from src.services.db.prompt_repo import get_base_sections


async def test_answer_logic_section():
    """Тест 1: Проверка секции answer_logic в Python-промпте."""
    print("="*80)
    print("ТЕСТ 1: Секция answer_logic в Python-промпте")
    print("="*80)

    # Получаем содержимое секции
    content = _section_answer_logic()

    print("\n📋 Содержимое секции answer_logic:")
    print("-"*80)
    print(content)
    print("-"*80)

    # Проверяем ключевые фразы
    required_phrases = [
        "ФИЛЬТРАЦИЯ ЗНАНИЙ ПО КУЛЬТУРЕ",
        "РАЗБИЕНИЕ СЕЗОННЫХ ВОПРОСОВ",
        "УЗКИЕ ВОПРОСЫ — УЗКИЕ ОТВЕТЫ",
        "паспорт чанка",
        "subcategory",
        "план для первой половины сезона",
        "Защита растений должна состоять",
    ]

    print("\n✅ Проверка ключевых фраз:")
    all_found = True
    for phrase in required_phrases:
        if phrase in content:
            print(f"  ✓ '{phrase}' найдена")
        else:
            print(f"  ✗ '{phrase}' НЕ НАЙДЕНА")
            all_found = False

    if all_found:
        print("\n🎉 Секция answer_logic содержит все обязательные правила!")
    else:
        print("\n❌ Секция answer_logic НЕПОЛНАЯ — проверьте содержимое")

    return all_found


async def test_base_prompt_order():
    """Тест 2: Проверка порядка секций в базовом промпте."""
    print("\n" + "="*80)
    print("ТЕСТ 2: Порядок секций в базовом промпте")
    print("="*80)

    # Собираем промпт
    prompt = build_base_prompt(
        default_location="средняя полоса",
        default_growing_type="открытый грунт",
        include_response_format=True,
        culture_is_known=True,
    )

    # Ожидаемый порядок секций
    expected_markers = [
        "профессиональный агроном-консультант",  # role
        "Рекомендации:",  # scope
        "СТАНДАРТНЫЕ ПАРАМЕТРЫ",  # defaults
        "КРИТИЧЕСКИ ВАЖНО - Работа с известной культурой",  # culture_rules
        "ИЕРАРХИЯ ИСТОЧНИКОВ ИНФОРМАЦИИ",  # kb_usage
        "Формат ответа",  # response_format
        "КОНТЕКСТ РАБОТ — ДО И ПОСЛЕ",  # work_context
        "ЛОГИКА ФОРМИРОВАНИЯ ОТВЕТА",  # answer_logic ← НОВОЕ
        "Помни:",  # tone
        "КРИТИЧЕСКИ ВАЖНЫЕ ПРАВИЛА",  # safety
    ]

    print("\n📋 Проверка порядка секций:")
    last_pos = -1
    all_ordered = True

    for i, marker in enumerate(expected_markers, 1):
        pos = prompt.find(marker)
        if pos == -1:
            print(f"  {i}. ✗ '{marker[:50]}...' НЕ НАЙДЕНА")
            all_ordered = False
        elif pos < last_pos:
            print(f"  {i}. ✗ '{marker[:50]}...' в НЕПРАВИЛЬНОМ порядке (позиция {pos}, ожидалось >{last_pos})")
            all_ordered = False
        else:
            print(f"  {i}. ✓ '{marker[:50]}...' на позиции {pos}")
            last_pos = pos

    if all_ordered:
        print("\n🎉 Все секции в правильном порядке!")
    else:
        print("\n❌ Порядок секций НАРУШЕН")

    # Проверяем что answer_logic идёт после work_context и до tone
    answer_logic_pos = prompt.find("ЛОГИКА ФОРМИРОВАНИЯ ОТВЕТА")
    work_context_pos = prompt.find("КОНТЕКСТ РАБОТ — ДО И ПОСЛЕ")
    tone_pos = prompt.find("Помни:")

    if work_context_pos < answer_logic_pos < tone_pos:
        print("\n✅ Секция answer_logic корректно размещена между work_context и tone")
    else:
        print(f"\n❌ Секция answer_logic в неправильной позиции:")
        print(f"   work_context: {work_context_pos}")
        print(f"   answer_logic: {answer_logic_pos}")
        print(f"   tone: {tone_pos}")

    return all_ordered


async def test_db_sections():
    """Тест 3: Проверка загрузки секции из БД."""
    print("\n" + "="*80)
    print("ТЕСТ 3: Загрузка секции answer_logic из БД")
    print("="*80)

    try:
        # Загружаем все секции из БД
        sections = await get_base_sections(is_enabled_only=False)

        print(f"\n📋 Всего секций в БД: {len(sections)}")

        # Ищем answer_logic
        answer_logic_section = None
        for section in sections:
            print(f"  - {section['slug']}: {section.get('is_enabled', 'N/A')}")
            if section['slug'] == 'answer_logic':
                answer_logic_section = section

        if answer_logic_section:
            print(f"\n✅ Секция answer_logic найдена в БД")
            print(f"   ID: {answer_logic_section['id']}")
            print(f"   Включена: {answer_logic_section['is_enabled']}")
            print(f"   Версия: {answer_logic_section.get('version', 'N/A')}")
            print(f"\n📋 Содержимое (первые 200 символов):")
            print(f"   {answer_logic_section['content'][:200]}...")
            return True
        else:
            print(f"\n❌ Секция answer_logic НЕ НАЙДЕНА в БД")
            print(f"\n💡 Подсказка: Примените миграцию schema_47_answer_logic_section.sql:")
            print(f"   psql -U sadovniki_user -d sadovniki_db -h localhost -f db/schema_47_answer_logic_section.sql")
            return False

    except Exception as e:
        print(f"\n❌ Ошибка при загрузке из БД: {e}")
        print(f"\n💡 Возможные причины:")
        print(f"   1. БД не запущена (docker-compose up -d db)")
        print(f"   2. Миграция не применена (schema_47_answer_logic_section.sql)")
        print(f"   3. Проблемы с подключением к БД")
        return False


async def main():
    """Запуск всех тестов."""
    print("\n🧪 ТЕСТИРОВАНИЕ НОВЫХ ПРАВИЛ ЛОГИКИ ФОРМИРОВАНИЯ ОТВЕТА")
    print("="*80)

    results = []

    # Тест 1: Python-секция
    results.append(await test_answer_logic_section())

    # Тест 2: Порядок в базовом промпте
    results.append(await test_base_prompt_order())

    # Тест 3: БД
    results.append(await test_db_sections())

    # Итоги
    print("\n" + "="*80)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*80)

    test_names = [
        "Секция answer_logic (Python)",
        "Порядок секций в промпте",
        "Загрузка секции из БД",
    ]

    for name, result in zip(test_names, results):
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {status}: {name}")

    all_passed = all(results)

    if all_passed:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("\n📝 Следующие шаги:")
        print("   1. Если миграция не применена — применить schema_47_answer_logic_section.sql")
        print("   2. Протестировать на реальных вопросах пользователей")
        print("   3. Мониторить качество ответов через CRM → Консультации")
    else:
        print("\n⚠️  НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ")
        print("\n📝 Рекомендации:")
        if not results[2]:
            print("   - Применить миграцию: psql -U sadovniki_user -d sadovniki_db -f db/schema_47_answer_logic_section.sql")
        print("   - Проверить файлы:")
        print("     - src/prompts/base_prompt.py")
        print("     - src/prompts/consultation_prompts.py")
        print("     - src/services/db/prompt_repo.py")

    print("\n" + "="*80)


if __name__ == "__main__":
    asyncio.run(main())
