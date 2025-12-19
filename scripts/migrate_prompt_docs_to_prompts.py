#!/usr/bin/env python3
"""
Миграция промт-документов из prompt_documents в систему промптов (prompts).

Этот скрипт:
1. Создаёт группу 'prompt_docs' если её нет
2. Создаёт подгруппы для культур (strawberry, raspberry, bushes)
3. Переносит content_text из prompt_documents в prompts

После миграции промт-документы будут редактироваться как текст в редакторе промптов.
"""

import asyncio
import os
import sys

# Добавляем корень проекта в path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg


# Маппинг культур на slugs
CULTURE_TO_SLUG = {
    'Клубника': 'strawberry',
    'Малина': 'raspberry',
    'Кустарники': 'bushes',
}

# Маппинг подкультур
SUBCULTURE_TO_SLUG = {
    'летняя': 'summer',
    'ремонтантная': 'remontant',
    'общая': 'general',
}

# Маппинг типов работ
WORK_TYPE_TO_SLUG = {
    'Питание растений': 'nutrition',
    'Защита растений': 'protection',
    'Посадка и уход': 'planting',
    'Улучшение почвы': 'soil',
    'Подбор сорта': 'variety',
}


def generate_slug(subculture_name: str | None, work_type_name: str) -> str:
    """Генерирует slug для промпта."""
    work_type_slug = WORK_TYPE_TO_SLUG.get(work_type_name, work_type_name.lower().replace(' ', '_'))

    if not subculture_name:
        return work_type_slug

    subculture_slug = SUBCULTURE_TO_SLUG.get(subculture_name, subculture_name.lower().replace(' ', '_'))
    return f"{subculture_slug}_{work_type_slug}"


def generate_name(subculture_name: str | None, work_type_name: str) -> str:
    """Генерирует человекочитаемое имя."""
    if not subculture_name:
        return work_type_name
    return f"{subculture_name} — {work_type_name}"


async def migrate_prompt_docs():
    """Основная функция миграции."""
    # Подключаемся к БД
    conn = await asyncpg.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        user=os.getenv('POSTGRES_USER', 'bot_user'),
        password=os.getenv('POSTGRES_PASSWORD', 'bot_password'),
        database=os.getenv('POSTGRES_DB', 'garden_bot'),
    )

    try:
        print("=" * 60)
        print("Миграция промт-документов в систему промптов")
        print("=" * 60)

        # 1. Создаём группу prompt_docs
        print("\n[1/4] Создаю группу 'prompt_docs'...")

        group_id = await conn.fetchval("""
            INSERT INTO prompt_groups (slug, name, description, icon, sort_order, is_system)
            VALUES ('prompt_docs', 'Промт-документы', 'Специализированные инструкции по культурам и типам работ', '📋', 5, TRUE)
            ON CONFLICT (slug) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description
            RETURNING id
        """)
        print(f"   Группа создана/обновлена: id={group_id}")

        # 2. Создаём подгруппы
        print("\n[2/4] Создаю подгруппы для культур...")

        subgroups = [
            ('strawberry', 'Клубника', 'Промт-документы для клубники', 0),
            ('raspberry', 'Малина', 'Промт-документы для малины', 1),
            ('bushes', 'Кустарники', 'Промт-документы для кустарников (голубика, смородина и др.)', 2),
        ]

        subgroup_ids = {}
        for slug, name, description, sort_order in subgroups:
            subgroup_id = await conn.fetchval("""
                INSERT INTO prompt_subgroups (group_id, slug, name, description, sort_order, is_system)
                VALUES ($1, $2, $3, $4, $5, TRUE)
                ON CONFLICT (group_id, slug) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description
                RETURNING id
            """, group_id, slug, name, description, sort_order)
            subgroup_ids[slug] = subgroup_id
            print(f"   {name}: id={subgroup_id}")

        # 3. Получаем все промт-документы с контентом
        print("\n[3/4] Загружаю промт-документы...")

        docs = await conn.fetch("""
            SELECT
                d.id,
                c.name as culture_name,
                sc.name as subculture_name,
                w.name as work_type_name,
                d.content_text,
                d.original_filename
            FROM prompt_documents d
            JOIN prompt_cultures c ON c.id = d.culture_id
            LEFT JOIN prompt_subcultures sc ON sc.id = d.subculture_id
            JOIN prompt_work_types w ON w.id = d.work_type_id
            WHERE d.extraction_status = 'completed' AND d.content_text IS NOT NULL
            ORDER BY c.sort_order, sc.sort_order NULLS LAST, w.sort_order
        """)

        print(f"   Найдено документов: {len(docs)}")

        # 4. Миграция
        print("\n[4/4] Мигрирую документы в prompts...")

        migrated = 0
        for doc in docs:
            culture_name = doc['culture_name']
            subculture_name = doc['subculture_name']
            work_type_name = doc['work_type_name']
            content = doc['content_text']
            original_filename = doc['original_filename']

            # Определяем subgroup
            culture_slug = CULTURE_TO_SLUG.get(culture_name)
            if not culture_slug:
                print(f"   [SKIP] Неизвестная культура: {culture_name}")
                continue

            subgroup_id = subgroup_ids.get(culture_slug)
            if not subgroup_id:
                print(f"   [SKIP] Подгруппа не найдена: {culture_slug}")
                continue

            # Генерируем slug и name
            slug = generate_slug(subculture_name, work_type_name)
            name = generate_name(subculture_name, work_type_name)
            description = f"Из файла: {original_filename}"

            # Вставляем или обновляем
            result = await conn.fetchrow("""
                INSERT INTO prompts (
                    group_id,
                    subgroup_id,
                    slug,
                    name,
                    description,
                    content,
                    is_enabled,
                    use_minimal_base,
                    is_system,
                    updated_by
                )
                VALUES ($1, $2, $3, $4, $5, $6, TRUE, FALSE, TRUE, 'migration')
                ON CONFLICT (group_id, subgroup_id, slug) DO UPDATE SET
                    content = EXCLUDED.content,
                    description = EXCLUDED.description,
                    updated_at = NOW(),
                    updated_by = 'migration'
                RETURNING id, version
            """, group_id, subgroup_id, slug, name, description, content)

            migrated += 1
            print(f"   [{migrated}] {culture_name} / {subculture_name or '-'} / {work_type_name}")
            print(f"       → slug={slug}, id={result['id']}, version={result['version']}")

        print("\n" + "=" * 60)
        print(f"Миграция завершена: {migrated} документов")
        print("=" * 60)

        # Статистика
        total = await conn.fetchval("SELECT COUNT(*) FROM prompts WHERE group_id = $1", group_id)
        print(f"\nВсего промптов в группе 'prompt_docs': {total}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate_prompt_docs())
