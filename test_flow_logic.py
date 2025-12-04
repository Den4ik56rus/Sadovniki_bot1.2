#!/usr/bin/env python3
"""
Тестовый скрипт для проверки логики гибридного потока.
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.services.llm.classification_llm import detect_culture_name
from src.services.db.pool import init_db_pool, close_db_pool


async def test_flow():
    """Проверяем логику определения культур и выбор CASE."""

    # Инициализируем БД
    await init_db_pool()

    test_cases = [
        ("питание растений", "общая информация", "CASE 1 (vague)"),
        ("питание малины", "малина общая", "CASE 2 (general)"),
        ("питание клубники", "клубника общая", "CASE 2 (general)"),
        ("питание малины обычной", "малина летняя", "CASE 3 (specific)"),
        ("питание клубники ремонтантной", "клубника ремонтантная", "CASE 3 (specific)"),
        ("малина", "малина общая", "CASE 2 (general)"),
        ("обычная малина", "малина летняя", "CASE 3 (specific)"),
    ]

    print("=" * 80)
    print("ТЕСТ ЛОГИКИ ГИБРИДНОГО ПОТОКА")
    print("=" * 80)
    print()

    for question, expected_culture, expected_case in test_cases:
        detected = await detect_culture_name(question)

        # Определяем CASE
        if detected in ("не определено", "общая информация"):
            actual_case = "CASE 1 (vague)"
            rag_status = "skip_rag=True (БЕЗ RAG)"
        elif detected in ("клубника общая", "малина общая"):
            actual_case = "CASE 2 (general)"
            rag_status = "Спросить тип (летняя/ремонтантная)"
        else:
            actual_case = "CASE 3 (specific)"
            rag_status = "skip_rag=False (С RAG)"

        match = "✅" if (detected == expected_culture and actual_case == expected_case) else "❌"

        print(f"{match} Вопрос: {question!r}")
        print(f"   Культура: {detected!r} (ожидалось: {expected_culture!r})")
        print(f"   CASE: {actual_case} (ожидалось: {expected_case})")
        print(f"   RAG: {rag_status}")
        print()

    await close_db_pool()


if __name__ == "__main__":
    asyncio.run(test_flow())
