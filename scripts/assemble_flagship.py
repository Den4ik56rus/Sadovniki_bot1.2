#!/usr/bin/env python3
"""
Сборка флагман-продукта "Сезонная программа" для заданной культуры.

Копирует текстовые PDF и презентации в data/flagship/{culture}_{variety}/
и генерирует config.json с метаданными.

Использование:
    python scripts/assemble_flagship.py                          # strawberry summer
    python scripts/assemble_flagship.py --culture strawberry --variety summer
    python scripts/assemble_flagship.py --dry-run
    python scripts/assemble_flagship.py --force                  # перезаписать

Требует:
    - data/article_pdfs/{culture}_{variety}/*.pdf (запустить generate_article_pdfs.py)
    - data/presentations/{id}/presentation.pdf на сервере
    - Доступ к БД для поиска presentation_id по culture/variety/category
"""

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import asyncpg

DB_DSN = "postgresql://bot_user:bot_password@localhost:5432/garden_bot"

ARTICLE_DIR = PROJECT_ROOT / "data" / "article_pdfs"
PRESENTATIONS_DIR = PROJECT_ROOT / "data" / "presentations"
FLAGSHIP_DIR = PROJECT_ROOT / "data" / "flagship"

CULTURE_LABELS = {
    "strawberry": "Клубника",
    "raspberry": "Малина",
    "blackberry": "Ежевика",
    "blueberry": "Голубика",
    "currant": "Смородина",
    "honeysuckle": "Жимолость",
}

VARIETY_LABELS = {
    "summer": "летняя",
    "remontant": "ремонтантная",
}

CATEGORY_LABELS = {
    "nutrition": "Питание растений",
    "planting_care": "Посадка и уход",
    "protection": "Защита растений",
    "soil": "Улучшение почвы",
    "varieties": "Подбор сорта",
    "pruning": "Обрезка",
    "season_plan": "Сезонный план работ",
}

CATEGORY_ORDER = ["nutrition", "planting_care", "protection", "soil", "varieties", "pruning"]


async def find_presentation_ids(pool: asyncpg.Pool, culture_key: str, variety_key: str) -> dict[str, int]:
    """Ищет presentation_id для каждой категории (article mode)."""
    query = """
        SELECT id, problem_key
        FROM presentations
        WHERE culture_key = $1
          AND (variety_key = $2 OR ($2 = '' AND variety_key IS NULL))
          AND generation_mode = 'article'
          AND status = 'completed'
        ORDER BY id DESC
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, culture_key, variety_key)

    # Берём последний completed для каждого problem_key
    result = {}
    for row in rows:
        key = row["problem_key"]
        if key and key not in result:
            result[key] = row["id"]
    return result


async def main():
    parser = argparse.ArgumentParser(description="Сборка флагман-продукта")
    parser.add_argument("--culture", default="strawberry", help="Культура (strawberry, raspberry, ...)")
    parser.add_argument("--variety", default="summer", help="Вариант (summer, remontant, или пусто)")
    parser.add_argument("--dry-run", action="store_true", help="Показать план без копирования")
    parser.add_argument("--force", action="store_true", help="Перезаписать существующие файлы")
    parser.add_argument("--price", type=int, default=3990, help="Цена в рублях")
    parser.add_argument("--dsn", default=DB_DSN, help="DSN строка подключения к БД")
    args = parser.parse_args()

    culture = args.culture
    variety = args.variety

    # Формируем имена
    culture_label = CULTURE_LABELS.get(culture, culture)
    variety_label = VARIETY_LABELS.get(variety, variety)
    full_name = f"{culture_label} {variety_label}".strip()
    folder_name = f"{culture}_{variety}" if variety else culture

    print(f"Сборка флагмана: {full_name}")
    print(f"Папка: {folder_name}")

    # Пути источников
    articles_src = ARTICLE_DIR / folder_name
    flagship_dst = FLAGSHIP_DIR / folder_name

    # Подключаемся к БД
    pool = await asyncpg.create_pool(args.dsn)
    presentation_ids = await find_presentation_ids(pool, culture, variety or "")
    await pool.close()

    print(f"\nНайдено презентаций в БД: {len(presentation_ids)}")
    for key, pid in presentation_ids.items():
        label = CATEGORY_LABELS.get(key, key)
        src = PRESENTATIONS_DIR / str(pid) / "presentation.pdf"
        exists = "✓" if src.exists() else "MISSING"
        print(f"  [{exists}] {label} (id={pid}) → presentations/{key}.pdf")

    print(f"\nТекстовые PDF из статей:")
    for cat in CATEGORY_ORDER:
        src = articles_src / f"{cat}.pdf"
        label = CATEGORY_LABELS.get(cat, cat)
        exists = "✓" if src.exists() else "MISSING"
        print(f"  [{exists}] {label} → articles/{cat}.pdf")

    if args.dry_run:
        print("\n[dry-run] Выход без копирования.")
        return

    # Создаём структуру папок
    (flagship_dst / "articles").mkdir(parents=True, exist_ok=True)
    (flagship_dst / "presentations").mkdir(parents=True, exist_ok=True)
    (flagship_dst / "video").mkdir(parents=True, exist_ok=True)

    errors = []

    # Копируем текстовые PDF
    print("\nКопирование текстовых PDF...")
    for cat in CATEGORY_ORDER:
        src = articles_src / f"{cat}.pdf"
        dst = flagship_dst / "articles" / f"{cat}.pdf"
        if not src.exists():
            print(f"  SKIP  {cat}.pdf — источник не найден: {src}")
            errors.append(f"articles/{cat}.pdf: источник не найден")
            continue
        if dst.exists() and not args.force:
            print(f"  SKIP  articles/{cat}.pdf — уже есть")
            continue
        shutil.copy2(src, dst)
        size_kb = dst.stat().st_size // 1024
        print(f"  OK    articles/{cat}.pdf ({size_kb} KB)")

    # Копируем презентации
    print("\nКопирование презентаций...")
    for cat_key, pid in presentation_ids.items():
        src = PRESENTATIONS_DIR / str(pid) / "presentation.pdf"
        dst = flagship_dst / "presentations" / f"{cat_key}.pdf"
        if not src.exists():
            print(f"  SKIP  {cat_key}.pdf — источник не найден: {src}")
            errors.append(f"presentations/{cat_key}.pdf: источник не найден")
            continue
        if dst.exists() and not args.force:
            print(f"  SKIP  presentations/{cat_key}.pdf — уже есть")
            continue
        shutil.copy2(src, dst)
        size_mb = dst.stat().st_size // (1024 * 1024)
        print(f"  OK    presentations/{cat_key}.pdf ({size_mb} MB)")

    # Копируем season_plan article (care plan PDF) если есть
    season_plan_article = None
    care_plan_src = PROJECT_ROOT / "data" / "article_pdfs" / f"care_plan_{folder_name}.pdf"
    if not care_plan_src.exists() and variety:
        # Попробуем без culture_ prefix (например care_plan_remontant.pdf)
        care_plan_src = PROJECT_ROOT / "data" / "article_pdfs" / f"care_plan_{variety}.pdf"
    if care_plan_src.exists():
        dst = flagship_dst / "articles" / "season_plan.pdf"
        if not dst.exists() or args.force:
            shutil.copy2(care_plan_src, dst)
            size_kb = dst.stat().st_size // 1024
            print(f"  OK    articles/season_plan.pdf ({size_kb} KB) ← care plan")
        season_plan_article = "articles/season_plan.pdf"

    # Генерируем config.json
    articles_list = []
    for cat in CATEGORY_ORDER:
        entry = {
            "key": cat,
            "title": CATEGORY_LABELS.get(cat, cat),
        }
        art_file = flagship_dst / "articles" / f"{cat}.pdf"
        pres_file = flagship_dst / "presentations" / f"{cat}.pdf"
        if art_file.exists():
            entry["article_pdf"] = f"articles/{cat}.pdf"
        if pres_file.exists():
            entry["presentation_pdf"] = f"presentations/{cat}.pdf"
        if entry.get("article_pdf") or entry.get("presentation_pdf"):
            articles_list.append(entry)

    config = {
        "product": "seasonal_program",
        "culture": culture,
        "variety": variety,
        "title": f"Сезонная программа — {full_name}",
        "price_rub": args.price,
        "articles": articles_list,
    }

    # Добавляем season_plan если есть презентация
    if "season_plan" in presentation_ids:
        season_dst = flagship_dst / "presentations" / "season_plan.pdf"
        if season_dst.exists():
            sp = {
                "title": CATEGORY_LABELS["season_plan"],
                "presentation_pdf": "presentations/season_plan.pdf",
            }
            if season_plan_article:
                sp["article_pdf"] = season_plan_article
            config["season_plan"] = sp

    config_path = flagship_dst / "config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"\nconfig.json записан: {config_path}")

    # Итог
    print(f"\n{'='*50}")
    if errors:
        print(f"Завершено с {len(errors)} ошибками:")
        for e in errors:
            print(f"  - {e}")
    else:
        print(f"Успешно собран флагман: {flagship_dst}")

    # Показываем итоговое дерево
    print("\nСтруктура:")
    for p in sorted(flagship_dst.rglob("*")):
        if p.is_file():
            size = p.stat().st_size
            size_str = f"{size // (1024*1024)} MB" if size > 1024*1024 else f"{size // 1024} KB"
            rel = p.relative_to(flagship_dst)
            print(f"  {rel} ({size_str})")


if __name__ == "__main__":
    asyncio.run(main())
