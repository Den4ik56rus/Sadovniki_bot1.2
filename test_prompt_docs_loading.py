"""
Тест загрузки промт-документов из новой системы промптов.
Проверяет что все культуры и категории правильно маппятся.
"""

import asyncio
import sys
sys.path.insert(0, '.')

from src.services.db.pool import init_db_pool, close_db_pool
from src.services.db.prompt_repo import (
    get_prompt_document_content,
    check_prompt_doc_exists,
    CULTURE_TO_SUBGROUP,
    SUBCULTURE_TO_SLUG,
    CATEGORY_TO_WORK_SLUG,
)


async def test_prompt_docs():
    await init_db_pool()

    print("=" * 60)
    print("ТЕСТ ЗАГРУЗКИ ПРОМТ-ДОКУМЕНТОВ")
    print("=" * 60)

    # Тестовые комбинации
    test_cases = [
        # Клубника
        ("клубника летняя", "питание растений"),
        ("клубника ремонтантная", "защита растений"),
        ("клубника", "посадка и уход"),

        # Малина + Ежевика
        ("малина летняя", "питание растений"),
        ("малина ремонтантная", "защита растений"),
        ("ежевика", "питание растений"),
        ("ежевика", "обрезка"),  # Нет такого промпта пока

        # Смородина + Жимолость
        ("смородина", "обрезка"),
        ("смородина", "питание растений"),
        ("жимолость", "обрезка"),
        ("жимолость", "защита растений"),

        # Кустарники
        ("голубика", "питание растений"),
    ]

    print("\n📋 Маппинг культур:")
    for culture, subgroup in sorted(CULTURE_TO_SUBGROUP.items()):
        print(f"  {culture} → {subgroup}")

    print("\n📋 Маппинг подкультур:")
    for subculture, slug in SUBCULTURE_TO_SLUG.items():
        print(f"  {subculture} → {slug}")

    print("\n📋 Маппинг категорий:")
    for category, slug in CATEGORY_TO_WORK_SLUG.items():
        print(f"  {category} → {slug}")

    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ ПОИСКА")
    print("=" * 60)

    found_count = 0
    not_found_count = 0

    for culture, category in test_cases:
        exists = await check_prompt_doc_exists(culture, category)
        content = await get_prompt_document_content(culture, category)

        status = "✅" if content else ("📄 exists" if exists else "❌")
        content_len = len(content) if content else 0

        if content:
            found_count += 1
        else:
            not_found_count += 1

        print(f"\n{status} {culture} / {category}")
        if content:
            print(f"   → Найдено {content_len} символов")
            # Показать первые 100 символов
            preview = content[:100].replace('\n', ' ')
            if len(content) > 100:
                preview += "..."
            print(f"   → {preview}")

    print("\n" + "=" * 60)
    print(f"ИТОГО: Найдено {found_count}, не найдено {not_found_count}")
    print("=" * 60)

    await close_db_pool()


if __name__ == "__main__":
    asyncio.run(test_prompt_docs())
