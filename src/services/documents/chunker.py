# src/services/documents/chunker.py

from typing import List, Dict


def chunk_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 200,
) -> List[Dict[str, any]]:
    """
    Разбивает текст на фрагменты фиксированного размера с перекрытием.

    Параметры:
        text: Исходный текст для разбивки
        chunk_size: Размер одного фрагмента в символах (по умолчанию 800)
        overlap: Размер перекрытия между фрагментами в символах (по умолчанию 200)

    Возвращает:
        Список словарей с полями:
            - chunk_index: Порядковый номер фрагмента (с 0)
            - chunk_text: Текст фрагмента
            - chunk_size: Реальный размер фрагмента
            - start_pos: Позиция начала в исходном тексте
            - end_pos: Позиция конца в исходном тексте
    """
    if not text or len(text.strip()) == 0:
        return []

    chunks = []
    start = 0
    chunk_index = 0
    text_length = len(text)

    while start < text_length:
        # Вычисляем конец текущего фрагмента
        end = min(start + chunk_size, text_length)

        # Извлекаем фрагмент
        chunk_text = text[start:end]

        # Пропускаем пустые фрагменты
        if chunk_text.strip():
            chunks.append({
                "chunk_index": chunk_index,
                "chunk_text": chunk_text,
                "chunk_size": len(chunk_text),
                "start_pos": start,
                "end_pos": end,
            })
            chunk_index += 1

        # Сдвигаемся на (chunk_size - overlap)
        # Если overlap >= chunk_size, то сдвиг будет минимальным (1 символ)
        step = max(1, chunk_size - overlap)
        start += step

        # Защита от бесконечного цикла: если мы в конце текста, выходим
        if start >= text_length:
            break

    return chunks
