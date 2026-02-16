#!/usr/bin/env python3
# scripts/reembed_kb.py

"""
Одноразовый скрипт для перезаэмбеддинга всех записей knowledge_base через Gemini.

Причина: KB записи были заэмбеддены через OpenAI (text-embedding-3-small, 1536D),
а документы — через Gemini (gemini-embedding-001, 3072D → truncated to 1536D).
Для корректного vector search всё должно быть в одном пространстве embeddings.

Использование:
    python scripts/reembed_kb.py
    python scripts/reembed_kb.py --dry-run   # только посчитать кол-во записей
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.db.pool import init_db_pool, close_db_pool, get_pool
from src.services.llm.gemini_embeddings import get_gemini_embedding
from src.services.db.kb_repo import KB_VECTOR_DIM, _normalize_embedding


BATCH_SIZE = 20  # Обрабатываем по 20 записей


async def reembed_all(dry_run: bool = False):
    """Перезаэмбеддить все активные KB записи через Gemini."""
    await init_db_pool()
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, question, answer FROM knowledge_base WHERE is_active = TRUE ORDER BY id"
        )

    total = len(rows)
    print(f"Найдено {total} активных KB записей")

    if dry_run:
        print("--dry-run: выход без изменений")
        await close_db_pool()
        return

    updated = 0
    errors = 0
    total_tokens_est = 0

    for i, row in enumerate(rows, 1):
        kb_id = row["id"]
        text = row["question"] or row["answer"]

        if not text or not text.strip():
            print(f"  [{i}/{total}] id={kb_id} — пропуск (пустой текст)")
            continue

        try:
            embedding = await get_gemini_embedding(text)

            # Нормализуем до 1536D для БД
            norm = _normalize_embedding(embedding)
            vector_str = "[" + ",".join(f"{x:.6f}" for x in norm) + "]"

            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE knowledge_base SET embedding = $1::vector WHERE id = $2",
                    vector_str,
                    kb_id,
                )

            updated += 1
            total_tokens_est += len(text) // 4

            if i % 10 == 0 or i == total:
                print(f"  [{i}/{total}] Обновлено: {updated}, ошибок: {errors}")

        except Exception as e:
            errors += 1
            print(f"  [{i}/{total}] id={kb_id} ОШИБКА: {e}")

        # Пауза между запросами (rate limit)
        if i % BATCH_SIZE == 0:
            await asyncio.sleep(1)

    cost_est = total_tokens_est * 0.00000015
    print(f"\nГотово!")
    print(f"  Обновлено: {updated}/{total}")
    print(f"  Ошибок: {errors}")
    print(f"  Примерная стоимость: ${cost_est:.4f}")

    await close_db_pool()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(reembed_all(dry_run=dry_run))
