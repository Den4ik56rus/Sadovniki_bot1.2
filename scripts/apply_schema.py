#!/usr/bin/env python3
# scripts/apply_schema.py

"""
Скрипт применения схемы БД для документов.
Использует asyncpg для подключения к PostgreSQL.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.db.pool import init_db_pool, close_db_pool, get_pool


async def apply_schema():
    """
    Применяет схему documents из файла schema_documents.sql.
    """
    schema_file = project_root / "db" / "schema_documents.sql"

    if not schema_file.exists():
        print(f"❌ Файл схемы не найден: {schema_file}")
        return False

    print(f"📄 Чтение схемы из: {schema_file}")

    with open(schema_file, 'r', encoding='utf-8') as f:
        schema_sql = f.read()

    print("🔌 Подключение к базе данных...")
    try:
        await init_db_pool()
        print("✅ Подключение установлено")
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return False

    print("\n📋 Применение схемы...")
    pool = get_pool()

    try:
        async with pool.acquire() as conn:
            # Выполняем SQL-скрипт
            await conn.execute(schema_sql)

        print("✅ Схема успешно применена!")
        print("\nСозданные таблицы:")
        print("  - documents")
        print("  - document_chunks")
        print("\nСозданные индексы:")
        print("  - idx_documents_category")
        print("  - idx_documents_subcategory")
        print("  - idx_documents_hash")
        print("  - idx_documents_status")
        print("  - idx_chunks_document")
        print("  - idx_chunks_category")
        print("  - idx_chunks_subcategory")
        print("  - idx_chunks_embedding (pgvector)")

        return True

    except Exception as e:
        print(f"❌ Ошибка применения схемы: {e}")
        return False

    finally:
        await close_db_pool()
        print("\n🔌 Соединение с БД закрыто")


async def main():
    print("\n" + "="*80)
    print("ПРИМЕНЕНИЕ СХЕМЫ БД ДЛЯ ДОКУМЕНТОВ")
    print("="*80 + "\n")

    success = await apply_schema()

    print("\n" + "="*80)
    if success:
        print("✅ СХЕМА УСПЕШНО ПРИМЕНЕНА")
    else:
        print("❌ ОШИБКА ПРИМЕНЕНИЯ СХЕМЫ")
    print("="*80 + "\n")

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
