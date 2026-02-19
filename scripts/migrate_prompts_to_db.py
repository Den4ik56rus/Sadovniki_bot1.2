#!/usr/bin/env python3
"""
Скрипт миграции промптов из Python-файлов в базу данных.

Извлекает тексты промптов из:
- src/prompts/base_prompt.py (8 секций)
- src/prompts/category_prompts/*.py (категорийные промпты)
- src/prompts/category_prompts/_fertilizers_reference.py (справочники)
- src/prompts/article_prompt.py (режим статей)
- src/prompts/consultation_prompts.py (fallback)

И вставляет их в таблицу prompts (schema_28_prompts.sql).

Использование:
    python scripts/migrate_prompts_to_db.py
"""

import asyncio
import sys
import os

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg
from dotenv import load_dotenv

load_dotenv()


# Конфигурация подключения к БД
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "user": os.getenv("DB_USER", "bot_user"),
    "password": os.getenv("DB_PASSWORD", "bot_password"),
    "database": os.getenv("DB_NAME", "sadovniki_db"),
}


# ============================================================================
# Извлечение текстов промптов из Python-модулей
# ============================================================================

def get_base_sections() -> dict:
    """Извлекает 8 базовых секций из base_prompt.py."""
    from src.prompts.base_prompt import (
        _section_role,
        _section_scope,
        _section_defaults,
        _section_culture_rules,
        _section_kb_usage,
        _section_response_format,
        _section_tone,
        _section_safety,
    )

    return {
        "role": {
            "name": "Роль агронома",
            "description": "Определяет роль и специализацию AI-консультанта",
            "content": _section_role(),
            "use_minimal_base": False,
        },
        "scope": {
            "name": "Ограничения (scope)",
            "description": "Строгие ограничения: только ягодные культуры",
            "content": _section_scope(),
            "use_minimal_base": False,
        },
        "defaults": {
            "name": "Стандартные параметры",
            "description": "Параметры по умолчанию: регион и тип грунта. Переменные: {default_location}, {default_growing_type}",
            "content": _section_defaults("{default_location}", "{default_growing_type}"),
            "use_minimal_base": False,
        },
        "culture_rules": {
            "name": "Правила работы с культурой",
            "description": "Как работать с культурой из контекста беседы",
            "content": _section_culture_rules(),
            "use_minimal_base": False,
        },
        "kb_usage": {
            "name": "Работа с базой знаний",
            "description": "Правила использования информации из RAG (3 уровня приоритета)",
            "content": _section_kb_usage(),
            "use_minimal_base": False,
        },
        "response_format": {
            "name": "Формат ответа",
            "description": "Структура ответа (опционально, пропускается для категорий с детальными промптами)",
            "content": _section_response_format(),
            "use_minimal_base": False,
        },
        "tone": {
            "name": "Стиль ответа",
            "description": "Тон и стиль коммуникации (простой язык, без канцелярита)",
            "content": _section_tone(),
            "use_minimal_base": False,
        },
        "safety": {
            "name": "Правила безопасности",
            "description": "Критически важные правила: дозировки, выбор удобрений, молодая рассада",
            "content": _section_safety(),
            "use_minimal_base": False,
        },
    }


def get_nutrition_prompts() -> dict:
    """Извлекает 4 промпта для категории 'Питание растений'."""
    from src.prompts.category_prompts.nutrition import (
        _get_nutrition_prompt_strawberry,
        _get_nutrition_prompt_raspberry,
        _get_nutrition_prompt_group_b,
        _get_nutrition_prompt_default,
    )

    # Получаем промпты с параметрами по умолчанию
    strawberry_content, strawberry_minimal = _get_nutrition_prompt_strawberry(
        "{culture}", "средняя полоса", "открытый грунт"
    )
    raspberry_content, raspberry_minimal = _get_nutrition_prompt_raspberry(
        "{culture}", "средняя полоса", "открытый грунт"
    )
    b_berries_content, b_berries_minimal = _get_nutrition_prompt_group_b(
        "{culture}", "средняя полоса", "открытый грунт"
    )
    default_content, default_minimal = _get_nutrition_prompt_default(
        "{culture}", "средняя полоса", "открытый грунт"
    )

    return {
        "strawberry": {
            "name": "Клубника (питание)",
            "description": "Детальный промпт для питания клубники (летние и ремонтантные сорта)",
            "content": strawberry_content,
            "use_minimal_base": strawberry_minimal,
        },
        "raspberry": {
            "name": "Малина и ежевика (питание)",
            "description": "Детальный промпт для питания малины и ежевики",
            "content": raspberry_content,
            "use_minimal_base": raspberry_minimal,
        },
        "b_berries": {
            "name": "Ягодные кустарники (питание)",
            "description": "Промпт для смородины, крыжовника, голубики, жимолости, ирги, аронии",
            "content": b_berries_content,
            "use_minimal_base": b_berries_minimal,
        },
        "default": {
            "name": "Универсальный (питание)",
            "description": "Fallback промпт для культур без специфического промпта",
            "content": default_content,
            "use_minimal_base": default_minimal,
        },
    }


def get_category_prompts() -> dict:
    """Извлекает промпты для остальных категорий."""
    from src.prompts.category_prompts.diseases_pests import get_diseases_pests_category_prompt
    from src.prompts.category_prompts.soil_improvement import get_soil_improvement_category_prompt
    from src.prompts.category_prompts.planting_care import get_planting_care_category_prompt
    from src.prompts.category_prompts.variety_selection import get_variety_selection_category_prompt

    diseases_content, diseases_minimal = get_diseases_pests_category_prompt(
        "{culture}", "средняя полоса", "открытый грунт"
    )
    soil_content, soil_minimal = get_soil_improvement_category_prompt(
        "{culture}", "средняя полоса", "открытый грунт"
    )
    planting_content, planting_minimal = get_planting_care_category_prompt(
        "{culture}", "средняя полоса", "открытый грунт"
    )
    variety_content, variety_minimal = get_variety_selection_category_prompt(
        "{culture}", "средняя полоса", "открытый грунт"
    )

    return {
        "diseases_pests": {
            "name": "Защита растений",
            "description": "Система защиты от болезней и вредителей",
            "content": diseases_content,
            "use_minimal_base": diseases_minimal,
        },
        "soil_improvement": {
            "name": "Улучшение почвы",
            "description": "Подготовка и улучшение почвы для посадки",
            "content": soil_content,
            "use_minimal_base": soil_minimal,
        },
        "planting_care": {
            "name": "Посадка и уход",
            "description": "Посадка, обрезка, полив, подготовка к зиме",
            "content": planting_content,
            "use_minimal_base": planting_minimal,
        },
        "variety_selection": {
            "name": "Подбор сортов",
            "description": "Рекомендации по выбору сортов для региона",
            "content": variety_content,
            "use_minimal_base": variety_minimal,
        },
    }


def get_references() -> dict:
    """Извлекает справочники из _fertilizers_reference.py и _varieties_reference.py."""
    from src.prompts.category_prompts._fertilizers_reference import (
        get_fertilizers_reference,
        get_pesticides_reference,
    )
    from src.prompts.category_prompts._varieties_reference import (
        get_varieties_reference,
        get_varieties_instruction,
    )

    instruction = get_varieties_instruction()

    # Per-culture variety references
    CULTURE_SLUGS = {
        'клубника': ('varieties_strawberry', 'Справочник сортов — Клубника', 'Рекомендуемые сорта клубники (летние и ремонтантные)'),
        'малина': ('varieties_raspberry', 'Справочник сортов — Малина', 'Рекомендуемые сорта малины (летние и ремонтантные)'),
        'ежевика': ('varieties_blackberry', 'Справочник сортов — Ежевика', 'Рекомендуемые сорта ежевики'),
        'голубика': ('varieties_blueberry', 'Справочник сортов — Голубика', 'Рекомендуемые сорта голубики'),
        'жимолость': ('varieties_honeysuckle', 'Справочник сортов — Жимолость', 'Рекомендуемые сорта жимолости'),
        'смородина': ('varieties_currant', 'Справочник сортов — Смородина', 'Рекомендуемые сорта смородины'),
        'крыжовник': ('varieties_gooseberry', 'Справочник сортов — Крыжовник', 'Рекомендуемые сорта крыжовника'),
    }

    result = {
        "fertilizers": {
            "name": "Справочник удобрений",
            "description": "Рекомендуемые удобрения: водорастворимые, гранулированные, пролонгированные, органика",
            "content": get_fertilizers_reference(),
            "use_minimal_base": False,
        },
        "pesticides": {
            "name": "Справочник СЗР",
            "description": "Средства защиты растений: акарициды, фунгициды, инсектициды, биопрепараты",
            "content": get_pesticides_reference(),
            "use_minimal_base": False,
        },
    }

    for culture, (slug, name, description) in CULTURE_SLUGS.items():
        ref_text = get_varieties_reference(culture)
        if not ref_text:
            ref_text = f"Данные по {culture} ограничены. ИИ дополняет рекомендации из своей базы знаний."
        result[slug] = {
            "name": name,
            "description": description,
            "content": ref_text,
            "use_minimal_base": False,
        }

    # Отдельная инструкция для ИИ (общая для всех культур)
    result["varieties_instruction"] = {
        "name": "Инструкция ИИ — Подбор сортов",
        "description": "Общая инструкция для ИИ при рекомендации сортов (добавляется автоматически ко всем культурам)",
        "content": instruction,
        "use_minimal_base": False,
    }

    return result


def get_article_prompt() -> dict:
    """Извлекает промпт для режима статей."""
    # Статейный промпт сложнее, т.к. требует параметры. Берём базовую часть.
    base_role = """Ты — профессиональный агроном-консультант по ягодным культурам.

Специализация:
- клубника летняя и ремонтантная
- малина летняя и ремонтантная
- смородина (черная, красная, белая)
- голубика
- жимолость
- крыжовник
- ежевика

РЕЖИМ: НАПИСАНИЕ ЭКСПЕРТНОЙ СТАТЬИ"""

    task_description = """
ТЕМА СТАТЬИ: {topic}

ЗАДАЧА:
Написать профессиональную, но понятную статью на заданную тему.
Статья должна быть полезна садоводам-любителям и профессионалам.

ОБЯЗАТЕЛЬНАЯ СТРУКТУРА СТАТЬИ:

## 1. ВВЕДЕНИЕ (2-3 абзаца)
   - Краткое введение в тему
   - Почему эта тема важна для садовода
   - Масштаб проблемы или актуальность вопроса
   - Какие культуры рассматриваются

## 2. ПОСТАНОВКА ПРОБЛЕМЫ (3-4 абзаца)
   - Что происходит (симптомы, признаки, ситуация)
   - Когда и как возникает
   - Какие культуры и в каких условиях затрагивает
   - Последствия если не решить проблему

## 3. ПРИЧИНЫ - АГРОНОМИЧЕСКИЙ РАЗБОР (главный раздел, 5-7 абзацев)
   - Физиологические механизмы растения
   - Агрохимические факторы (NPK, pH, микроэлементы)
   - Биологические процессы
   - Взаимосвязь факторов
   - КРИТИЧНО: Объяснять НЕ ТОЛЬКО "что делать", но и "ПОЧЕМУ так работает"
   - Использовать научные термины, но с объяснениями для садоводов

## 4. РЕШЕНИЯ - ПРАКТИЧЕСКИЕ РЕКОМЕНДАЦИИ (главный раздел, 6-8 абзацев)
   - Конкретные действия с ТОЧНЫМИ дозировками
   - Сроки применения (календарные периоды, фазы развития растений)
   - Технология выполнения (как правильно применять)
   - Альтернативные подходы (органика vs минеральные удобрения)
   - Рекомендации для разных культур (если применимо)
   - Рекомендации для разных условий (открытый грунт, теплица, разные регионы)
   - Частые ошибки и как их избежать

## 5. ПРОФИЛАКТИКА (3-4 абзаца)
   - Как предотвратить проблему до её возникновения
   - Системный подход к выращиванию
   - Долгосрочная стратегия агротехники
   - Мониторинг и раннее обнаружение проблем

## 6. ВЫВОДЫ (2-3 абзаца)
   - Краткая сводка ключевых тезисов (3-5 пунктов)
   - Главные практические выводы
   - Что делать в первую очередь
   - Какие результаты даст правильный подход"""

    style_guidelines = """
ТРЕБОВАНИЯ К СТИЛЮ:

✅ ЧТО ДЕЛАТЬ:
- Профессиональный, но понятный язык (избегать канцелярита)
- Конкретные рекомендации с дозировками, сроками, технологиями
- Объяснять "почему так", а не только "что делать"
- Использовать списки, подзаголовки, структурированный формат
- Давать несколько вариантов решения (когда применимо)
- НЕ ограничивай длину ответа - статья должна быть подробной (3000-5000 слов)

❌ ЧЕГО НЕ ДЕЛАТЬ:
- НЕ использовать общие фразы типа:
  * "проконсультируйтесь со специалистом"
  * "всё зависит от ситуации"
  * "выбирайте сами"
- НЕ обрывать мысль из-за длины текста
- НЕ пропускать разделы структуры

КРИТИЧЕСКИ ВАЖНОЕ ПРАВИЛО О ДОЗИРОВКАХ:
При работе с минеральными удобрениями ЛУЧШЕ УМЕНЬШИТЬ дозировку, чем увеличить.
Высокая концентрация минеральных удобрений ОПАСНА — может вызвать ожог корней и листьев.
Всегда указывай безопасные дозировки с запасом.

ФОРМАТИРОВАНИЕ:
- Используй заголовки разметки Markdown (##, ###)
- Каждый раздел начинай с заголовка (## 1. ВВЕДЕНИЕ, ## 2. ПОСТАНОВКА ПРОБЛЕМЫ и т.д.)
- Используй списки для перечислений
- Выделяй важные моменты жирным шрифтом (**текст**)"""

    full_content = f"{base_role}\n\n{task_description}\n\n{style_guidelines}"

    return {
        "article_base": {
            "name": "Базовый промпт для статей",
            "description": "Промпт для генерации экспертных статей. Переменная: {topic}",
            "content": full_content,
            "use_minimal_base": False,
        },
    }


def get_fallback_prompt() -> dict:
    """Извлекает fallback-промпт из consultation_prompts.py."""
    from src.prompts.consultation_prompts import _get_fallback_prompt_python

    content, use_minimal = _get_fallback_prompt_python("{culture}")

    return {
        "fallback": {
            "name": "Универсальный fallback",
            "description": "Промпт для вопросов, не относящихся к основным категориям",
            "content": content,
            "use_minimal_base": use_minimal,
        },
    }


# ============================================================================
# Вставка в базу данных
# ============================================================================

async def get_group_id(conn, slug: str) -> int:
    """Получает ID группы по slug."""
    result = await conn.fetchval(
        "SELECT id FROM prompt_groups WHERE slug = $1",
        slug
    )
    if not result:
        raise ValueError(f"Group '{slug}' not found")
    return result


async def get_subgroup_id(conn, group_id: int, slug: str) -> int:
    """Получает ID подгруппы по group_id и slug."""
    result = await conn.fetchval(
        "SELECT id FROM prompt_subgroups WHERE group_id = $1 AND slug = $2",
        group_id, slug
    )
    if not result:
        raise ValueError(f"Subgroup '{slug}' not found in group {group_id}")
    return result


async def upsert_prompt(
    conn,
    group_id: int,
    subgroup_id: int | None,
    slug: str,
    name: str,
    description: str,
    content: str,
    use_minimal_base: bool,
) -> int:
    """Вставляет или обновляет промпт."""
    result = await conn.fetchval("""
        INSERT INTO prompts (group_id, subgroup_id, slug, name, description, content, use_minimal_base, is_system)
        VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE)
        ON CONFLICT (group_id, subgroup_id, slug)
        DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            content = EXCLUDED.content,
            use_minimal_base = EXCLUDED.use_minimal_base,
            updated_at = NOW()
        RETURNING id
    """, group_id, subgroup_id, slug, name, description, content, use_minimal_base)
    return result


async def migrate_prompts():
    """Основная функция миграции."""
    print("=" * 60)
    print("Миграция промптов в базу данных")
    print("=" * 60)

    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        # 1. Базовые секции (group=base)
        print("\n📋 Мигрируем базовые секции...")
        base_group_id = await get_group_id(conn, "base")
        base_sections = get_base_sections()

        for slug, data in base_sections.items():
            prompt_id = await upsert_prompt(
                conn,
                group_id=base_group_id,
                subgroup_id=None,
                slug=slug,
                name=data["name"],
                description=data["description"],
                content=data["content"],
                use_minimal_base=data["use_minimal_base"],
            )
            print(f"  ✓ {slug}: {data['name']} (id={prompt_id})")

        # 2. Категория "Питание растений" (group=categories, subgroup=nutrition)
        print("\n🌱 Мигрируем промпты питания...")
        categories_group_id = await get_group_id(conn, "categories")
        nutrition_subgroup_id = await get_subgroup_id(conn, categories_group_id, "nutrition")
        nutrition_prompts = get_nutrition_prompts()

        for slug, data in nutrition_prompts.items():
            prompt_id = await upsert_prompt(
                conn,
                group_id=categories_group_id,
                subgroup_id=nutrition_subgroup_id,
                slug=slug,
                name=data["name"],
                description=data["description"],
                content=data["content"],
                use_minimal_base=data["use_minimal_base"],
            )
            print(f"  ✓ nutrition/{slug}: {data['name']} (id={prompt_id})")

        # 3. Остальные категории (без подгрупп, напрямую в categories)
        print("\n📁 Мигрируем категорийные промпты...")
        category_prompts = get_category_prompts()

        # Маппинг slug категории -> subgroup_slug
        category_to_subgroup = {
            "diseases_pests": "diseases_pests",
            "soil_improvement": "soil_improvement",
            "planting_care": "planting_care",
            "variety_selection": "variety_selection",
        }

        for slug, data in category_prompts.items():
            subgroup_slug = category_to_subgroup.get(slug)
            subgroup_id = await get_subgroup_id(conn, categories_group_id, subgroup_slug) if subgroup_slug else None

            prompt_id = await upsert_prompt(
                conn,
                group_id=categories_group_id,
                subgroup_id=subgroup_id,
                slug="main",  # Основной промпт категории
                name=data["name"],
                description=data["description"],
                content=data["content"],
                use_minimal_base=data["use_minimal_base"],
            )
            print(f"  ✓ {slug}/main: {data['name']} (id={prompt_id})")

        # 4. Справочники (group=references)
        print("\n📚 Мигрируем справочники...")
        references_group_id = await get_group_id(conn, "references")
        references = get_references()

        for slug, data in references.items():
            prompt_id = await upsert_prompt(
                conn,
                group_id=references_group_id,
                subgroup_id=None,
                slug=slug,
                name=data["name"],
                description=data["description"],
                content=data["content"],
                use_minimal_base=data["use_minimal_base"],
            )
            print(f"  ✓ {slug}: {data['name']} (id={prompt_id})")

        # 5. Режим статей (group=article)
        print("\n📝 Мигрируем промпт для статей...")
        article_group_id = await get_group_id(conn, "article")
        article_prompts = get_article_prompt()

        for slug, data in article_prompts.items():
            prompt_id = await upsert_prompt(
                conn,
                group_id=article_group_id,
                subgroup_id=None,
                slug=slug,
                name=data["name"],
                description=data["description"],
                content=data["content"],
                use_minimal_base=data["use_minimal_base"],
            )
            print(f"  ✓ {slug}: {data['name']} (id={prompt_id})")

        # 6. Fallback (group=other)
        print("\n📄 Мигрируем fallback промпт...")
        other_group_id = await get_group_id(conn, "other")
        fallback_prompts = get_fallback_prompt()

        for slug, data in fallback_prompts.items():
            prompt_id = await upsert_prompt(
                conn,
                group_id=other_group_id,
                subgroup_id=None,
                slug=slug,
                name=data["name"],
                description=data["description"],
                content=data["content"],
                use_minimal_base=data["use_minimal_base"],
            )
            print(f"  ✓ {slug}: {data['name']} (id={prompt_id})")

        print("\n" + "=" * 60)
        print("✅ Миграция завершена успешно!")
        print("=" * 60)

        # Выводим статистику
        total = await conn.fetchval("SELECT COUNT(*) FROM prompts")
        print(f"\nВсего промптов в БД: {total}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate_prompts())
