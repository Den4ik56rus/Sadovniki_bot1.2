#!/usr/bin/env python3
"""
Батч-генерация всех PDF из таблицы admin_articles.

Использование:
    python scripts/generate_article_pdfs.py
    python scripts/generate_article_pdfs.py --dry-run     # только список без генерации
    python scripts/generate_article_pdfs.py --culture strawberry  # одна культура

Требует доступа к БД (bot_user@garden_bot через localhost:5432).
"""

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import asyncpg

# Импортируем конвертер из соседнего скрипта
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from md_to_pdf import generate_pdf


DB_DSN = "postgresql://bot_user:bot_password@localhost:5432/garden_bot"

OUTPUT_DIR = PROJECT_ROOT / "data" / "article_pdfs"


async def get_articles(pool: asyncpg.Pool, culture_filter: str = None) -> list[dict]:
    """Получает все статьи с заполненными ключами."""
    query = """
        SELECT id, topic, article_text, culture_key, variety_key, category_key
        FROM admin_articles
        WHERE culture_key IS NOT NULL AND culture_key != ''
    """
    params = []
    if culture_filter:
        query += " AND culture_key = $1"
        params.append(culture_filter)

    query += " ORDER BY culture_key, variety_key, category_key"

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    return [dict(r) for r in rows]


def get_output_path(culture_key: str, variety_key: str, category_key: str) -> Path:
    """Формирует путь для PDF файла."""
    if variety_key:
        folder = OUTPUT_DIR / f"{culture_key}_{variety_key}"
    else:
        folder = OUTPUT_DIR / culture_key
    return folder / f"{category_key}.pdf"


async def main():
    parser = argparse.ArgumentParser(description='Батч-генерация PDF статей')
    parser.add_argument('--dry-run', action='store_true', help='Список без генерации')
    parser.add_argument('--culture', help='Фильтр по культуре')
    parser.add_argument('--force', action='store_true', help='Перегенерировать существующие')
    parser.add_argument('--dsn', default=DB_DSN, help='DSN строка подключения к БД')
    args = parser.parse_args()

    print(f"Подключение к БД: {args.dsn.split('@')[1]}...")
    pool = await asyncpg.create_pool(args.dsn)

    articles = await get_articles(pool, culture_filter=args.culture)
    print(f"Найдено статей: {len(articles)}")

    if args.dry_run:
        for a in articles:
            path = get_output_path(a['culture_key'], a['variety_key'] or '', a['category_key'])
            exists = "✓" if path.exists() else "○"
            print(f"  {exists} {a['topic']} → {path.relative_to(PROJECT_ROOT)}")
        await pool.close()
        return

    generated = 0
    skipped = 0
    errors = []

    for a in articles:
        path = get_output_path(a['culture_key'], a['variety_key'] or '', a['category_key'])

        if path.exists() and not args.force:
            skipped += 1
            print(f"  SKIP  {a['topic']}")
            continue

        try:
            generate_pdf(
                article_text=a['article_text'],
                output_path=str(path),
                culture_key=a['culture_key'] or '',
                variety_key=a['variety_key'] or '',
                category_key=a['category_key'] or '',
                topic=a['topic'],
            )
            size_kb = path.stat().st_size // 1024
            generated += 1
            print(f"  OK    {a['topic']} ({size_kb} KB)")
        except Exception as e:
            errors.append((a['topic'], e))
            print(f"  ERR   {a['topic']}: {e}")

    await pool.close()

    print(f"\n{'='*50}")
    print(f"Готово: {generated} создано, {skipped} пропущено, {len(errors)} ошибок")
    if errors:
        print("\nОшибки:")
        for topic, err in errors:
            print(f"  {topic}: {err}")


if __name__ == '__main__':
    asyncio.run(main())
