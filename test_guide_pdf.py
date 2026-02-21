"""Тестовый скрипт: генерация гайда по клубнике летней через новую систему (консультационные промпты + RAG + gpt-5.1)."""

import asyncio
import logging
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

async def main():
    # Инициализируем пул БД (нужен для RAG и промптов)
    from src.services.db.pool import init_db_pool, close_db_pool

    print("=" * 60)
    print("Тест: генерация гайда по клубнике летней")
    print("Модель: gpt-5.1 + RAG + консультационные промпты")
    print("=" * 60)

    await init_db_pool()

    try:
        from src.services.llm.guide_generation_llm import generate_full_guide
        from src.services.pdf_generator import generate_guide_pdf

        culture = "клубника летняя"
        culture_display = "Клубника летняя"

        async def on_progress(section_key, completed, total):
            print(f"  [{completed}/{total}] Секция: {section_key}")

        # 1. Генерация контента через LLM
        print("\n📝 Шаг 1/2: Генерация контента через LLM...")
        start = time.perf_counter()

        guide_data = await generate_full_guide(
            culture=culture,
            on_progress=on_progress,
        )

        llm_time = time.perf_counter() - start
        print(f"\n✅ LLM готово за {llm_time:.1f} сек")
        print(f"   Стоимость: ${guide_data['total_cost_usd']:.4f}")
        print(f"   Токены: {guide_data['total_tokens']}")
        print(f"   Ошибки: {guide_data['errors'] or 'нет'}")

        for key, section in guide_data["sections"].items():
            content_len = len(section.get("content", ""))
            print(f"   {key}: {section['title']} ({content_len} символов)")

        # 2. Генерация PDF
        print("\n📄 Шаг 2/2: Генерация PDF...")
        pdf_path = await generate_guide_pdf(
            sections=guide_data["sections"],
            culture=culture,
            culture_display=culture_display,
        )

        import os
        file_size = os.path.getsize(pdf_path)
        print(f"\n✅ PDF создан: {pdf_path}")
        print(f"   Размер: {file_size / 1024:.1f} KB")

        total_time = time.perf_counter() - start
        print(f"\n⏱️  Общее время: {total_time:.1f} сек")

    finally:
        await close_db_pool()

if __name__ == "__main__":
    asyncio.run(main())
