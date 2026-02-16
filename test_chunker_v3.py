"""
Тест нового SemanticChunkerV2 (structure-first chunking).

Тестирует Фазу 1 (структурную декомпозицию) без API-вызовов.
Для полного теста с Gemini API нужен QUERYROUTER_API_KEY.

Запуск:
    python test_chunker_v3.py              # только Фаза 1 (без API)
    python test_chunker_v3.py --full       # Фаза 1 + Фаза 2 (с API)
"""

import asyncio
import sys
import os

# Добавляем корень проекта в PATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.services.documents.semantic_chunker import SemanticChunkerV2, StructuralBlock
from src.services.documents.boundary_detector import detect_list_boundaries, detect_headings


# Пример текста для тестирования (имитация агрономического документа)
SAMPLE_TEXT = """Питание земляники садовой

Земляника садовая (Fragaria × ananassa) — одна из наиболее популярных ягодных культур в мире. Правильное минеральное питание играет ключевую роль в получении высоких урожаев качественных ягод.

Основные элементы питания

Для нормального роста и развития земляники необходимы макро- и микроэлементы. Основные макроэлементы — азот (N), фосфор (P) и калий (K). Каждый из них выполняет уникальную функцию в метаболизме растения.

Азот (N)

Азот является основным строительным материалом для белков и нуклеиновых кислот. Он необходим для активного роста вегетативной массы. Дефицит азота проявляется в виде хлороза листьев и замедления роста.

Рекомендуемые дозы внесения:
- Весна (начало вегетации): 30-40 кг/га
- После сбора урожая: 20-30 кг/га
- Осень: не рекомендуется

Важно! Избыток азота приводит к чрезмерному росту листвы в ущерб плодоношению. Также повышается восприимчивость к грибным заболеваниям, особенно серой гнили (Botrytis cinerea).

Фосфор (P)

Фосфор критически важен для развития корневой системы и формирования цветков. Он участвует в энергетическом обмене (АТФ) и передаче генетической информации.

Признаки дефицита фосфора:
1. Тёмно-зелёная окраска листьев с фиолетовым оттенком
2. Замедленное развитие корневой системы
3. Снижение урожайности
4. Мелкие ягоды с плохим вкусом

Калий (K)

Калий регулирует водный баланс растения и повышает устойчивость к стрессовым факторам. Он также улучшает вкусовые качества ягод, повышая содержание сахаров.

Система внесения удобрений

Для земляники рекомендуется дробное внесение удобрений в течение вегетационного периода. Это позволяет обеспечить растения необходимыми элементами в нужное время и в нужном количестве.

Весенняя подкормка

Проводится в начале вегетации, когда температура почвы достигает +8-10°С. Используют комплексные удобрения с преобладанием азота. Норма внесения зависит от плодородия почвы и предшественника.

Подкормка в период цветения

В фазу бутонизации и цветения растения нуждаются в повышенном количестве фосфора и калия. Азот в этот период ограничивают, т.к. его избыток может привести к опаданию завязей.

Подкормка в период плодоношения

Во время плодоношения основной акцент делается на калий. Он способствует накоплению сахаров и улучшает лёжкость ягод. Рекомендуется использовать сульфат калия (K₂SO₄) в дозе 15-20 кг/га.
"""


def test_phase1_structural_decomposition():
    """Тест Фазы 1: структурная декомпозиция без API."""
    print("=" * 70)
    print("ТЕСТ ФАЗЫ 1: Структурная декомпозиция")
    print("=" * 70)

    chunker = SemanticChunkerV2(
        merge_threshold=0.5,
        min_chunk_size=300,
        max_chunk_size=2000,
        overlap_sentences=2,
    )

    headings = detect_headings(SAMPLE_TEXT)
    list_boundaries = detect_list_boundaries(SAMPLE_TEXT)

    print(f"\nОбнаружено заголовков: {len(headings)}")
    for h in headings:
        print(f"  [{h['type']}] \"{h['text']}\" (pos: {h['start']}-{h['end']})")

    print(f"\nОбнаружено списков: {len(list_boundaries)}")
    for lb in list_boundaries:
        print(f"  [{lb['type']}] pos: {lb['start']}-{lb['end']}")

    # Тестируем _split_by_double_newline
    paragraphs = chunker._split_by_double_newline(SAMPLE_TEXT)
    print(f"\nПараграфы (\\n\\n): {len(paragraphs)}")
    for i, (text, start, end) in enumerate(paragraphs):
        preview = text[:80].replace('\n', '\\n')
        print(f"  [{i}] ({end-start} chars) \"{preview}...\"")

    # Тестируем полную Фазу 1
    blocks = chunker._split_into_structural_blocks(SAMPLE_TEXT, headings, list_boundaries)
    print(f"\nСтруктурные блоки: {len(blocks)}")
    for i, block in enumerate(blocks):
        preview = block.text[:80].replace('\n', '\\n')
        print(f"  [{i}] {block.block_type:10s} ({block.size:4d} chars) \"{preview}...\"")

    # Тестируем разбиение больших блоков
    blocks_split = chunker._split_oversized_blocks(blocks)
    if len(blocks_split) != len(blocks):
        print(f"\nПосле разбиения крупных: {len(blocks_split)} блоков (было {len(blocks)})")
    else:
        print(f"\nКрупных блоков нет — без изменений")

    print("\n✓ Фаза 1 прошла успешно!")
    return blocks


async def test_full_chunking():
    """Полный тест с Фазой 2 (требует API)."""
    print("\n" + "=" * 70)
    print("ТЕСТ ФАЗЫ 1 + 2: Полный чанкинг с Gemini API")
    print("=" * 70)

    chunker = SemanticChunkerV2(
        merge_threshold=0.5,
        min_chunk_size=300,
        max_chunk_size=2000,
        overlap_sentences=2,
    )

    headings = detect_headings(SAMPLE_TEXT)
    list_boundaries = detect_list_boundaries(SAMPLE_TEXT)

    try:
        chunks, stats = await chunker.chunk(
            text=SAMPLE_TEXT,
            list_boundaries=list_boundaries,
            headings=headings,
        )

        print(f"\n--- Результаты ---")
        print(f"Чанков: {len(chunks)}")
        print(f"Блоков: {stats.get('blocks_count', '?')}")
        print(f"Предложений: {stats['sentences_count']}")
        print(f"Токенов: {stats['chunking_tokens']}")
        print(f"Стоимость: ${stats['chunking_cost_usd']:.6f}")

        print(f"\n--- Чанки ---")
        for chunk in chunks:
            print(f"\n[Чанк #{chunk['chunk_index']}] ({chunk['chunk_size']} chars, {chunk['sentences_count']} sentences)")
            print("-" * 40)
            # Показываем первые и последние 100 символов
            text = chunk['chunk_text']
            if len(text) > 250:
                print(text[:120])
                print("  ...")
                print(text[-120:])
            else:
                print(text)
            print("-" * 40)

        print(f"\n✓ Полный тест прошёл успешно!")

    except Exception as e:
        print(f"\n✗ Ошибка: {e}")
        print("  Для полного теста нужен QUERYROUTER_API_KEY в .env")
        import traceback
        traceback.print_exc()


async def test_with_real_document():
    """Тест на реальном документе из data/documents."""
    docs_dir = os.path.join(os.path.dirname(__file__), "data", "documents")

    # Ищем маленький PDF для теста
    test_files = []
    for root, dirs, files in os.walk(docs_dir):
        for f in files:
            if f.endswith('.pdf') and not f.startswith('.'):
                fpath = os.path.join(root, f)
                size = os.path.getsize(fpath)
                if size < 500_000:  # < 500KB
                    test_files.append((fpath, size))

    if not test_files:
        print("\n⚠ Нет маленьких PDF-файлов для теста")
        return

    test_files.sort(key=lambda x: x[1])
    test_file, test_size = test_files[0]
    print(f"\n{'=' * 70}")
    print(f"ТЕСТ НА РЕАЛЬНОМ ДОКУМЕНТЕ: {os.path.basename(test_file)} ({test_size // 1024}KB)")
    print(f"{'=' * 70}")

    # Извлекаем текст
    try:
        from pypdf import PdfReader
        reader = PdfReader(test_file)
        full_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n\n"
    except Exception as e:
        print(f"✗ Не удалось прочитать PDF: {e}")
        return

    print(f"Извлечено текста: {len(full_text)} символов")

    # Фаза 1
    headings = detect_headings(full_text)
    list_boundaries = detect_list_boundaries(full_text)
    print(f"Заголовков: {len(headings)}, Списков: {len(list_boundaries)}")

    chunker = SemanticChunkerV2(
        merge_threshold=0.5,
        min_chunk_size=300,
        max_chunk_size=2000,
        overlap_sentences=2,
    )

    blocks = chunker._split_into_structural_blocks(full_text, headings, list_boundaries)
    blocks = chunker._split_oversized_blocks(blocks)
    print(f"Структурных блоков: {len(blocks)}")

    # Статистика блоков
    sizes = [b.size for b in blocks]
    types = {}
    for b in blocks:
        types[b.block_type] = types.get(b.block_type, 0) + 1

    if sizes:
        print(f"  Размеры: min={min(sizes)}, max={max(sizes)}, avg={sum(sizes)//len(sizes)}")
    print(f"  Типы: {types}")

    # Показываем первые 5 блоков
    print(f"\nПервые 5 блоков:")
    for i, block in enumerate(blocks[:5]):
        preview = block.text[:100].replace('\n', '\\n')
        print(f"  [{i}] {block.block_type:10s} ({block.size:4d} chars) \"{preview}...\"")


def main():
    full_mode = "--full" in sys.argv

    # Фаза 1 (без API)
    test_phase1_structural_decomposition()

    if full_mode:
        # Полный тест с API
        asyncio.run(test_full_chunking())

    # Тест на реальном документе (только Фаза 1)
    asyncio.run(test_with_real_document())


if __name__ == "__main__":
    main()
