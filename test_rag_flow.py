"""
Тест для проверки RAG-поиска с skip_rag флагом.
"""

import asyncio
from src.services.db.pool import init_db_pool, close_db_pool
from src.services.llm.embeddings_llm import get_text_embedding
from src.services.rag.unified_retriever import retrieve_unified_snippets


async def test_rag_flow():
    """Тестирование RAG-поиска."""

    print("="*60)
    print("ТЕСТ 1: Поиск без указания культуры (должен пропуститься)")
    print("="*60)

    query = "Как подкормить растение?"
    query_embedding = await get_text_embedding(query)

    # Поиск без subcategory
    results1 = await retrieve_unified_snippets(
        category="питание растений",
        query_embedding=query_embedding,
        subcategory=None,  # Культура не указана
        qa_limit=2,
        doc_limit=3,
    )

    print(f"Запрос: '{query}'")
    print(f"Категория: 'питание растений'")
    print(f"Культура: None")
    print(f"Результатов: {len(results1)}")
    print()

    print("="*60)
    print("ТЕСТ 2: Поиск с указанием культуры 'клубника летняя'")
    print("="*60)

    query2 = "Чем подкормить клубнику летнюю?"
    query_embedding2 = await get_text_embedding(query2)

    # Поиск с subcategory
    results2 = await retrieve_unified_snippets(
        category="питание растений",
        query_embedding=query_embedding2,
        subcategory="клубника летняя",
        qa_limit=2,
        doc_limit=3,
    )

    print(f"Запрос: '{query2}'")
    print(f"Категория: 'питание растений'")
    print(f"Культура: 'клубника летняя'")
    print(f"Результатов: {len(results2)}")

    if results2:
        print("\nНайденные фрагменты:")
        for idx, snippet in enumerate(results2[:3], 1):
            source_type = snippet.get("source_type", "unknown")
            priority = snippet.get("priority_level", "?")
            distance = snippet.get("distance", 0)
            subcategory = snippet.get("subcategory", "?")
            content_preview = snippet.get("content", "")[:100]

            print(f"  #{idx} [УРОВЕНЬ {priority}] [{source_type}]")
            print(f"      Культура: {subcategory}")
            print(f"      Distance: {distance:.4f}")
            print(f"      Контент: {content_preview}...")
    print()

    print("="*60)
    print("ТЕСТ 3: Поиск с культурой 'клубника общая' (fallback)")
    print("="*60)

    query3 = "Подкормка клубники"
    query_embedding3 = await get_text_embedding(query3)

    results3 = await retrieve_unified_snippets(
        category="питание растений",
        query_embedding=query_embedding3,
        subcategory="клубника общая",
        qa_limit=2,
        doc_limit=3,
    )

    print(f"Запрос: '{query3}'")
    print(f"Категория: 'питание растений'")
    print(f"Культура: 'клубника общая'")
    print(f"Результатов: {len(results3)}")

    if results3:
        print("\nНайденные фрагменты:")
        for idx, snippet in enumerate(results3[:3], 1):
            source_type = snippet.get("source_type", "unknown")
            priority = snippet.get("priority_level", "?")
            distance = snippet.get("distance", 0)
            subcategory = snippet.get("subcategory", "?")
            content_preview = snippet.get("content", "")[:100]

            print(f"  #{idx} [УРОВЕНЬ {priority}] [{source_type}]")
            print(f"      Культура: {subcategory}")
            print(f"      Distance: {distance:.4f}")
            print(f"      Контент: {content_preview}...")
    print()

    print("="*60)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*60)

    print(f"Тест 1 (без культуры): Найдено {len(results1)} результатов")
    print(f"  - Ожидается: поиск только по Q&A (УРОВЕНЬ 1), УРОВЕНЬ 2 пропущен")
    print(f"Тест 2 ('клубника летняя'): Найдено {len(results2)} результатов")
    print(f"  - Ожидается: Q&A + документы по культуре")
    print(f"Тест 3 ('клубника общая'): Найдено {len(results3)} результатов")
    print(f"  - Ожидается: Q&A + документы (с fallback на общую культуру)")


async def main():
    """Главная функция с инициализацией БД."""
    await init_db_pool()

    try:
        await test_rag_flow()
    finally:
        await close_db_pool()


if __name__ == "__main__":
    asyncio.run(main())
