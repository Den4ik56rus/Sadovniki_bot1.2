# src/services/llm/context_generator.py
"""
RAG v2.5: Генератор контекста для чанков документов.

Использует GPT-4.1-mini для генерации краткого описания содержимого каждого чанка
на основе локального окна вокруг чанка (RAG v2.5) или полного текста документа (legacy).
"""

import logging
from typing import List, Dict, Tuple
from dataclasses import dataclass

from src.services.llm.core_llm import (
    create_chat_completion_with_usage,
    calculate_cost,
)

logger = logging.getLogger(__name__)

# Модель для генерации контекста (дешёвая и быстрая)
CONTEXT_MODEL = "gpt-4.1-mini"
CONTEXT_TEMPERATURE = 0.3  # Низкая температура для консистентных результатов

# Legacy: Максимальная длина документа для отправки в LLM (в символах)
# Используется только в fallback режиме для старых документов
MAX_DOCUMENT_LENGTH = 50000  # ~12500 токенов

# RAG v2.5: Константы для локального окна
CONTEXT_WINDOW_BEFORE = 2000  # символов до чанка
CONTEXT_WINDOW_AFTER = 2000   # символов после чанка

# Системный промпт для генерации контекста
CONTEXT_SYSTEM_PROMPT = """Ты — помощник для анализа агрономических документов о ягодных культурах.

Твоя задача: для каждого фрагмента документа написать краткий контекст (1-2 предложения),
который объясняет:
1. О чём конкретно идёт речь в этом фрагменте
2. Как он связан с общей темой документа

Контекст должен помогать понять фрагмент без чтения всего документа.

Правила:
- Пиши кратко: 1-2 предложения (не больше 200 символов)
- Используй ключевые термины из фрагмента
- Упоминай культуру/процесс если они очевидны из контекста
- Не повторяй сам текст фрагмента — описывай его суть

Примеры хорошего контекста:
- "Описывает весеннюю подкормку малины ремонтантной азотными удобрениями с указанием дозировок."
- "Содержит инструкцию по обрезке отплодоносивших побегов малины после сбора урожая."
- "Перечисляет признаки заражения клубники серой гнилью и методы профилактики."
"""


@dataclass
class ContextGenerationResult:
    """Результат генерации контекста для одного чанка."""
    chunk_id: int
    context: str
    input_tokens: int
    output_tokens: int
    cost: float


@dataclass
class BatchContextResult:
    """Результат генерации контекста для документа."""
    contexts: List[ContextGenerationResult]
    total_input_tokens: int
    total_output_tokens: int
    total_cost: float
    success_count: int
    error_count: int


async def generate_chunk_context(
    document_text: str,
    chunk_text: str,
    chunk_index: int,
    total_chunks: int,
) -> Tuple[str, int, int, float]:
    """
    Генерирует контекст для одного чанка документа.

    Параметры:
        document_text: Полный текст документа (или его сокращённая версия)
        chunk_text: Текст конкретного чанка
        chunk_index: Индекс чанка (0-based)
        total_chunks: Общее количество чанков в документе

    Возвращает:
        Tuple[context, input_tokens, output_tokens, cost]
    """
    # Обрезаем документ если слишком длинный
    truncated_doc = document_text[:MAX_DOCUMENT_LENGTH]
    if len(document_text) > MAX_DOCUMENT_LENGTH:
        truncated_doc += "\n\n[... документ обрезан для экономии токенов ...]"

    # Формируем промпт
    user_prompt = f"""ДОКУМЕНТ (полный текст):
{truncated_doc}

---

ФРАГМЕНТ #{chunk_index + 1} из {total_chunks}:
{chunk_text}

---

Напиши краткий контекст для этого фрагмента (1-2 предложения):"""

    messages = [
        {"role": "system", "content": CONTEXT_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    # Вызываем LLM
    result = await create_chat_completion_with_usage(
        messages=messages,
        model=CONTEXT_MODEL,
        temperature=CONTEXT_TEMPERATURE,
    )

    context = result["content"].strip()
    input_tokens = result["prompt_tokens"]
    output_tokens = result["completion_tokens"]
    cost = calculate_cost(CONTEXT_MODEL, input_tokens, output_tokens)

    return context, input_tokens, output_tokens, cost


def find_chunk_position(full_text: str, chunk_text: str) -> Tuple[int, int]:
    """
    Находит позицию чанка в полном тексте (RAG v2.5).

    Использует нормализацию пробелов для надёжного поиска.

    Параметры:
        full_text: Полный текст документа
        chunk_text: Текст чанка

    Возвращает:
        (start_pos, end_pos) или (-1, -1) если не найдено
    """
    # Нормализуем пробелы для поиска
    normalized_full = " ".join(full_text.split())
    normalized_chunk = " ".join(chunk_text.split())

    start_pos = normalized_full.find(normalized_chunk)

    if start_pos == -1:
        # Fallback: ищем первые 100 символов чанка
        preview = normalized_chunk[:100]
        start_pos = normalized_full.find(preview)

        if start_pos != -1:
            logger.debug("[find_chunk_position] Found by preview (first 100 chars)")

    if start_pos == -1:
        return (-1, -1)

    end_pos = start_pos + len(normalized_chunk)
    return (start_pos, end_pos)


async def generate_chunk_context_with_window(
    full_text: str,
    chunk_text: str,
    chunk_index: int,
    total_chunks: int,
) -> Tuple[str, int, int, float]:
    """
    Генерирует контекст используя локальное окно вокруг чанка (RAG v2.5).

    Алгоритм:
    1. Находим позицию чанка в полном тексте
    2. Берём окно ±2000 символов вокруг чанка
    3. Генерируем контекст на основе окна (не всего документа)

    Преимущества:
    - Контекст всегда релевантен чанку
    - Работает для документов любого размера
    - Включает информацию из соседних чанков
    - Экономия токенов: 4K символов вместо 50K

    Параметры:
        full_text: Полный текст документа (из БД)
        chunk_text: Текст конкретного чанка
        chunk_index: Индекс чанка (0-based)
        total_chunks: Общее количество чанков

    Возвращает:
        Tuple[context, input_tokens, output_tokens, cost]
    """
    # Находим позицию чанка
    start_pos, end_pos = find_chunk_position(full_text, chunk_text)

    if start_pos == -1:
        # Fallback: используем старую логику с обрезанием
        logger.warning(
            f"[context_generator] Chunk {chunk_index} not found in full_text, "
            "using truncated document (fallback)"
        )
        return await generate_chunk_context(
            document_text=full_text[:MAX_DOCUMENT_LENGTH],
            chunk_text=chunk_text,
            chunk_index=chunk_index,
            total_chunks=total_chunks,
        )

    # Вычисляем границы окна
    window_start = max(0, start_pos - CONTEXT_WINDOW_BEFORE)
    window_end = min(len(full_text), end_pos + CONTEXT_WINDOW_AFTER)

    # Извлекаем локальное окно
    local_context = full_text[window_start:window_end]

    # Добавляем маркеры для LLM (показываем что это фрагмент)
    if window_start > 0:
        local_context = "[... текст до фрагмента ...]\n\n" + local_context
    if window_end < len(full_text):
        local_context = local_context + "\n\n[... текст после фрагмента ...]"

    # Формируем промпт
    user_prompt = f"""ЛОКАЛЬНЫЙ КОНТЕКСТ (окно ±2000 символов вокруг фрагмента):
{local_context}

---

ЦЕЛЕВОЙ ФРАГМЕНТ #{chunk_index + 1} из {total_chunks}:
{chunk_text}

---

Напиши краткий контекст для этого фрагмента (1-2 предложения):"""

    messages = [
        {"role": "system", "content": CONTEXT_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    # Вызываем LLM
    result = await create_chat_completion_with_usage(
        messages=messages,
        model=CONTEXT_MODEL,
        temperature=CONTEXT_TEMPERATURE,
    )

    context = result["content"].strip()
    input_tokens = result["prompt_tokens"]
    output_tokens = result["completion_tokens"]
    cost = calculate_cost(CONTEXT_MODEL, input_tokens, output_tokens)

    logger.debug(
        f"[context_generator] Window-based context: "
        f"window={window_end - window_start} chars, "
        f"tokens={input_tokens}/{output_tokens}, cost=${cost:.6f}"
    )

    return context, input_tokens, output_tokens, cost


async def generate_contexts_for_document(
    document_text: str,
    chunks: List[Dict],
    use_window: bool = True,
) -> BatchContextResult:
    """
    Генерирует контексты для всех чанков документа.

    Параметры:
        document_text: Полный текст документа
        chunks: Список чанков с полями:
            - id: int (chunk_id в БД)
            - chunk_text: str
            - chunk_index: int
        use_window: True = локальное окно (RAG v2.5), False = обрезание (legacy)

    Возвращает:
        BatchContextResult с результатами генерации
    """
    results: List[ContextGenerationResult] = []
    total_input = 0
    total_output = 0
    total_cost = 0.0
    success_count = 0
    error_count = 0

    total_chunks = len(chunks)
    mode = "локальное окно" if use_window else "обрезание документа"
    logger.info(f"[context_generator] Генерация контекста для {total_chunks} чанков ({mode})...")

    for chunk in chunks:
        chunk_id = chunk["id"]
        chunk_text = chunk["chunk_text"]
        chunk_index = chunk["chunk_index"]

        try:
            if use_window:
                # RAG v2.5: Новая логика с локальным окном
                context, input_tokens, output_tokens, cost = await generate_chunk_context_with_window(
                    full_text=document_text,
                    chunk_text=chunk_text,
                    chunk_index=chunk_index,
                    total_chunks=total_chunks,
                )
            else:
                # Legacy: Старая логика с обрезанием (backward compatibility)
                context, input_tokens, output_tokens, cost = await generate_chunk_context(
                    document_text=document_text,
                    chunk_text=chunk_text,
                    chunk_index=chunk_index,
                    total_chunks=total_chunks,
                )

            results.append(ContextGenerationResult(
                chunk_id=chunk_id,
                context=context,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
            ))

            total_input += input_tokens
            total_output += output_tokens
            total_cost += cost
            success_count += 1

            logger.debug(
                f"[context_generator] Чанк {chunk_index + 1}/{total_chunks}: "
                f"{input_tokens} in, {output_tokens} out, ${cost:.6f}"
            )

        except Exception as e:
            logger.error(f"[context_generator] Ошибка для чанка {chunk_id}: {e}")
            error_count += 1
            # Добавляем пустой результат для отслеживания
            results.append(ContextGenerationResult(
                chunk_id=chunk_id,
                context="",
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
            ))

    logger.info(
        f"[context_generator] Завершено: {success_count}/{total_chunks} успешно, "
        f"токенов: {total_input} in + {total_output} out, "
        f"стоимость: ${total_cost:.4f}"
    )

    return BatchContextResult(
        contexts=results,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_cost=total_cost,
        success_count=success_count,
        error_count=error_count,
    )
