#!/usr/bin/env python3
# scripts/import_documents.py

"""
Скрипт импорта PDF-документов из структуры папок в базу знаний.

Структура папок:
    data/documents/
        <категория>/
            <культура>/
                *.pdf

Пример:
    data/documents/питание_растений/малина/guide.pdf

Использование:
    python scripts/import_documents.py
    python scripts/import_documents.py --category="питание растений"
    python scripts/import_documents.py --force-update
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional
import argparse

# Добавляем корневую директорию проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.db.pool import init_db_pool, close_db_pool
from src.services.documents.processor import process_pdf_document


# Базовая директория для документов
DOCUMENTS_DIR = project_root / "data" / "documents"


# Маппинг названий папок на корректные категории
CATEGORY_MAPPING = {
    "питание_растений": "питание растений",
    "посадка_и_уход": "посадка и уход",
    "защита_растений": "защита растений",
    "улучшение_почвы": "улучшение почвы",
    "подбор_сорта": "подбор сорта/места",
    "другая_тема": "другая тема",
}


# Маппинг названий папок подкатегорий на корректные subcategory
SUBCATEGORY_MAPPING = {
    # Малина (общая и специфичные типы)
    "малина общая": "малина общая",
    "малина_летняя": "малина летняя",
    "малина_ремонтантная": "малина ремонтантная",

    # Клубника (общая и специфичные типы)
    "клубника общая": "клубника общая",
    "клубника_летняя": "клубника летняя",
    "клубника_ремонтантная": "клубника ремонтантная",

    # Остальные культуры (без специфичных типов)
    "голубика": "голубика",
    "смородина": "смородина",
    "жимолость": "жимолость",
    "крыжовник": "крыжовник",
    "ежевика": "ежевика",

    # Общая информация
    "общая_информация": "общая информация",
}


def normalize_category(folder_name: str) -> Optional[str]:
    """
    Преобразует название папки в корректную категорию.
    """
    return CATEGORY_MAPPING.get(folder_name)


def normalize_subcategory(folder_name: str) -> str:
    """
    Преобразует название папки культуры в корректную подкатегорию.

    Примеры:
        малина общая -> малина общая
        малина_летняя -> малина летняя
        малина_ремонтантная -> малина ремонтантная
        клубника общая -> клубника общая
        клубника_ремонтантная -> клубника ремонтантная
        голубика -> голубика
        общая_информация -> общая информация
    """
    # Сначала проверяем маппинг
    if folder_name in SUBCATEGORY_MAPPING:
        return SUBCATEGORY_MAPPING[folder_name]

    # Fallback: заменяем подчеркивания на пробелы
    return folder_name.replace("_", " ")


def scan_documents_directory(
    base_dir: Path,
    filter_category: Optional[str] = None,
) -> List[Dict]:
    """
    Сканирует структуру папок и возвращает список PDF-файлов для импорта.

    Возвращает список словарей:
        [
            {
                "file_path": Path,
                "category": str,
                "subcategory": str,
            },
            ...
        ]
    """
    if not base_dir.exists():
        print(f"Директория не найдена: {base_dir}")
        return []

    documents = []

    # Проходим по категориям (папки первого уровня)
    for category_dir in base_dir.iterdir():
        if not category_dir.is_dir():
            continue

        category_folder_name = category_dir.name
        category = normalize_category(category_folder_name)

        if category is None:
            print(f"Пропускаем неизвестную категорию: {category_folder_name}")
            continue

        # Фильтр по категории, если задан
        if filter_category and category != filter_category:
            continue

        # Проходим по культурам (папки второго уровня)
        for subcategory_dir in category_dir.iterdir():
            if not subcategory_dir.is_dir():
                continue

            subcategory_folder_name = subcategory_dir.name
            subcategory = normalize_subcategory(subcategory_folder_name)

            # Проходим по PDF-файлам
            for pdf_file in subcategory_dir.glob("*.pdf"):
                documents.append({
                    "file_path": pdf_file,
                    "category": category,
                    "subcategory": subcategory,
                })

    return documents


async def import_document(
    file_path: Path,
    category: str,
    subcategory: str,
    force_update: bool = False,
) -> Dict:
    """
    Импортирует один документ.
    """
    print(f"\n{'='*80}")
    print(f"Обработка: {file_path.name}")
    print(f"Категория: {category} / {subcategory}")
    print(f"{'='*80}")

    result = await process_pdf_document(
        file_path=str(file_path),
        category=category,
        subcategory=subcategory,
        force_update=force_update,
    )

    if result["success"]:
        print(f"✅ Успешно обработан!")
        print(f"   - Document ID: {result['document_id']}")
        print(f"   - Chunks: {result['chunks_count']}")
    else:
        print(f"❌ Ошибка: {result['error']}")

    return result


async def main():
    """
    Основная функция импорта.
    """
    parser = argparse.ArgumentParser(
        description="Импорт PDF-документов в базу знаний"
    )
    parser.add_argument(
        "--category",
        type=str,
        help="Фильтр по категории (например, 'питание растений')",
        default=None,
    )
    parser.add_argument(
        "--force-update",
        action="store_true",
        help="Перезаписать существующие документы (по хешу)",
    )
    args = parser.parse_args()

    print("\n" + "="*80)
    print("ИМПОРТ ДОКУМЕНТОВ В БАЗУ ЗНАНИЙ")
    print("="*80)
    print(f"Директория: {DOCUMENTS_DIR}")
    if args.category:
        print(f"Фильтр по категории: {args.category}")
    if args.force_update:
        print("Режим: перезапись существующих документов")
    print("="*80 + "\n")

    # Инициализация пула подключений к БД
    print("Подключение к базе данных...")
    try:
        await init_db_pool()
        print("✅ Подключение установлено\n")
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return

    # Сканирование директории
    print("Сканирование директории документов...")
    documents = scan_documents_directory(
        DOCUMENTS_DIR,
        filter_category=args.category,
    )

    if not documents:
        print("❌ Документы для импорта не найдены")
        await close_db_pool()
        return

    print(f"✅ Найдено документов: {len(documents)}\n")

    # Обработка каждого документа
    success_count = 0
    error_count = 0

    for i, doc_info in enumerate(documents, start=1):
        print(f"\n[{i}/{len(documents)}]")

        result = await import_document(
            file_path=doc_info["file_path"],
            category=doc_info["category"],
            subcategory=doc_info["subcategory"],
            force_update=args.force_update,
        )

        if result["success"]:
            success_count += 1
        else:
            error_count += 1

        # Небольшая пауза между документами
        await asyncio.sleep(0.5)

    # Итоги
    print("\n" + "="*80)
    print("ИТОГИ ИМПОРТА")
    print("="*80)
    print(f"Всего документов: {len(documents)}")
    print(f"✅ Успешно: {success_count}")
    print(f"❌ Ошибок: {error_count}")
    print("="*80 + "\n")

    # Закрытие пула
    print("Закрытие подключения к БД...")
    await close_db_pool()
    print("✅ Завершено")


if __name__ == "__main__":
    asyncio.run(main())
