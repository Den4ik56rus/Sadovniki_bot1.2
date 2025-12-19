# src/services/llm/context_generator.py
"""
RAG v2.0: Генератор контекста для чанков документов.

Использует GPT-4.1-mini для генерации краткого описания содержимого каждого чанка
на основе полного текста документа и самого чанка.
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

# Максимальная длина документа для отправки в LLM (в символах)
# GPT-4.1-mini имеет контекст 128K токенов, но мы ограничиваем для экономии
MAX_DOCUMENT_LENGTH = 50000  # ~12500 токенов

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


async def generate_contexts_for_document(
    document_text: str,
    chunks: List[Dict],
) -> BatchContextResult:
    """
    Генерирует контексты для всех чанков документа.

    Параметры:
        document_text: Полный текст документа
        chunks: Список чанков с полями:
            - id: int (chunk_id в БД)
            - chunk_text: str
            - chunk_index: int

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
    logger.info(f"[context_generator] Генерация контекста для {total_chunks} чанков...")

    for chunk in chunks:
        chunk_id = chunk["id"]
        chunk_text = chunk["chunk_text"]
        chunk_index = chunk["chunk_index"]

        try:
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
