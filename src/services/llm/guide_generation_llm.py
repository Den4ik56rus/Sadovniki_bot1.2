# src/services/llm/guide_generation_llm.py

"""
LLM-сервис для генерации содержимого гайдов (Готовое решение).

Каждая секция генерируется как полноценная консультация:
    - Используются промпты из системы консультаций (base + category + prompt-docs + references)
    - RAG-поиск по базе знаний (embeddings + unified_retriever)

Генерирует 5 секций ПОСЛЕДОВАТЕЛЬНО (каждая видит контент предыдущих):
    1. nutrition — план питания на сезон (весна → зима)
    2. protection — защита от болезней и вредителей (весь сезон)
    3. soil_prep — подготовка почвы перед посадкой
    4. care_works — уходные работы: обрезка, полив, мульча, укрытие
    → intro — вступление (генерируется последним на основе всех секций, но ставится первым в PDF)
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable, Awaitable, List, Tuple

from src.services.llm.core_llm import create_chat_completion_with_retry, calculate_cost
from src.services.llm.gemini_embeddings import get_gemini_embedding_with_usage
from src.services.rag.unified_retriever import retrieve_unified_snippets
from src.prompts.consultation_prompts import build_consultation_system_prompt

logger = logging.getLogger(__name__)

# Fallback-модель (используется если настройка в БД не задана)
_GUIDE_MODEL_FALLBACK = "gpt-4.1-mini"


async def _get_guide_model_config():
    """Получить модель, temperature и reasoning из admin_settings."""
    from src.services.db.settings_repo import (
        get_model_for_task, get_temperature_for_task, get_reasoning_effort_for_task
    )
    model = await get_model_for_task("guide")
    temperature = await get_temperature_for_task("guide")
    reasoning = await get_reasoning_effort_for_task("guide")
    return model or _GUIDE_MODEL_FALLBACK, temperature, reasoning

# ─── Определение секций ───

# Основные секции (генерируются последовательно в этом порядке)
GUIDE_SECTIONS = {
    "nutrition": {
        "title": "План питания на сезон",
        "order": 1,
        "consultation_category": "питание растений",
        "user_question": (
            "Составь полный план питания {culture} на весь сезон — от ранней весны до ухода в зиму. "
            "Раздели по фазам развития:\n"
            "1. Ранняя весна — начало цветения: какие элементы критичны, удобрения с дозировками, сроки внесения\n"
            "2. Цветение — окончание плодоношения: потребности, удобрения с дозировками, внекорневые подкормки, микроэлементы\n"
            "3. Конец плодоношения — уход в зиму: задачи осеннего питания, удобрения с дозировками, что НЕ вносить осенью\n\n"
            "Для каждой фазы укажи конкретные препараты, нормы расхода, способы внесения. "
            "Включи сводную таблицу подкормок на весь сезон."
        ),
    },
    "protection": {
        "title": "Защита растений",
        "order": 2,
        "consultation_category": "защита растений",
        "user_question": "Защита {culture} от болезней и вредителей на весь сезон: основные болезни с симптомами, основные вредители с признаками, профилактические обработки по фазам, таблица обработок с препаратами и дозировками, биопрепараты, сроки ожидания перед сбором",
    },
    "soil_prep": {
        "title": "Подготовка почвы перед посадкой",
        "order": 3,
        "consultation_category": "посадка и уход",
        "user_question": "Подготовка почвы перед посадкой {culture}: анализ и оптимальные параметры почвы (pH, структура, плодородие), улучшение структуры, внесение органики и минеральных удобрений, дренаж, подготовка посадочных ям/гряд, сроки подготовки",
    },
    "care_works": {
        "title": "Уходные работы",
        "order": 4,
        "consultation_category": "посадка и уход",
        "user_question": "Уходные работы для {culture} на весь сезон: обрезка (когда, как, какие побеги), полив (режим по фазам, нормы, способы), мульчирование, прополка, укрытие на зиму, размножение, пересадка",
    },
}

# Вступление — генерируется ПОСЛЕДНИМ (видит весь контент), но в PDF ставится ПЕРВЫМ
INTRO_SECTION = {
    "key": "intro",
    "title": "Вступление",
    "order": 0,
    "consultation_category": "посадка и уход",
    "user_question": (
        "Напиши вступление для руководства по уходу за {culture}. "
        "Кратко расскажи о культуре: что это за растение, его особенности, почему оно популярно. "
        "Затем опиши структуру руководства — о чём пойдёт речь в каждом разделе: "
        "план питания на сезон, защита от болезней и вредителей, подготовка почвы, уходные работы. "
        "Стиль: дружелюбный, но профессиональный. Объём: 300-500 слов."
    ),
}

# Дополнительная инструкция для формата книги (добавляется к системному промпту)
_GUIDE_FORMAT_INSTRUCTION = """

📖 ФОРМАТ ОТВЕТА — РАЗДЕЛ КНИГИ-ГАЙДА:
Ты пишешь раздел для подробной книги-руководства по уходу за культурой на сезон.
- Стиль: профессиональный, конкретный, с дозировками и сроками
- Формат: markdown с заголовками ##/###, списками, таблицами где уместно
- Объём: развёрнутый, подробный (1000-2500 слов)
- НЕ задавай уточняющих вопросов — дай максимально полный ответ
- НЕ используй вступления типа "Давайте рассмотрим" — начинай сразу с сути
- Ответ на русском языке
"""

# Инструкция для секций с контекстом предыдущих разделов
_PREVIOUS_SECTIONS_INSTRUCTION = """

📚 КОНТЕКСТ ПРЕДЫДУЩИХ РАЗДЕЛОВ:
Ранее для этого же руководства были сгенерированы следующие разделы.
НЕ повторяй информацию из них — ссылайся при необходимости, но не дублируй.
---
{previous_content}
---
"""


# ─── RAG: получение контекста из базы знаний ───

async def _get_rag_context(
    query_text: str,
    consultation_category: str,
    culture: str,
) -> Tuple[List[Dict], bool]:
    """
    Выполняет RAG-поиск: embedding → unified_retriever.

    Returns:
        (kb_snippets, qa_found)
    """
    try:
        # Получаем embedding через Gemini
        query_embedding, embedding_tokens, embedding_model = await get_gemini_embedding_with_usage(
            query_text
        )
        logger.debug(
            f"[guide_rag] Embedding: size={len(query_embedding)}, "
            f"tokens={embedding_tokens}, model={embedding_model}"
        )

        # Поиск в базе знаний
        kb_snippets, qa_found = await retrieve_unified_snippets(
            category=consultation_category,
            subcategory=culture,
            query_embedding=query_embedding,
            qa_limit=3,
            doc_limit=6,
            priority_doc_limit=6,
            qa_distance_threshold=0.45,
            doc_distance_threshold=0.5,
        )

        logger.debug(
            f"[guide_rag] Found {len(kb_snippets)} snippets, qa_found={qa_found}"
        )
        return kb_snippets, qa_found

    except Exception as e:
        logger.error(f"[guide_rag] RAG error: {e}")
        return [], False


# ─── Генерация одной секции ───

async def generate_section(
    section_key: str,
    culture: str,
    location: str = "средняя полоса России",
    previous_sections_content: str = "",
) -> Dict[str, Any]:
    """
    Генерирует одну секцию гайда через систему консультаций.

    1. Формирует user_question для секции
    2. RAG-поиск по базе знаний
    3. Собирает системный промпт (base + category + prompt-docs + references + RAG)
    4. Добавляет контекст предыдущих секций (если есть)
    5. Вызывает LLM

    Args:
        section_key: Ключ секции из GUIDE_SECTIONS
        culture: Название культуры
        location: Регион выращивания
        previous_sections_content: Контент предыдущих секций (для избежания повторов)

    Returns:
        {"key": str, "title": str, "content": str, "cost_usd": float, "tokens": int}
    """
    if section_key == "intro":
        section = INTRO_SECTION
    else:
        section = GUIDE_SECTIONS[section_key]
    consultation_category = section["consultation_category"]
    user_question = section["user_question"].format(culture=culture)

    logger.info(
        f"[guide_llm] Генерация секции '{section_key}': "
        f"category='{consultation_category}', question='{user_question[:80]}...'"
    )

    try:
        # 0. Получить настройки модели
        model, temperature, reasoning = await _get_guide_model_config()

        # 1. RAG-поиск
        kb_snippets, qa_found = await _get_rag_context(
            query_text=user_question,
            consultation_category=consultation_category,
            culture=culture,
        )

        # 2. Системный промпт из консультационной системы
        system_prompt = await build_consultation_system_prompt(
            culture=culture,
            kb_snippets=kb_snippets,
            qa_found=qa_found,
            consultation_category=consultation_category,
            default_location=location,
            default_growing_type="открытый грунт",
        )

        # 3. Добавляем контекст предыдущих секций (если есть)
        if previous_sections_content:
            system_prompt += _PREVIOUS_SECTIONS_INSTRUCTION.format(
                previous_content=previous_sections_content
            )

        # 4. Добавляем инструкцию формата книги
        system_prompt += _GUIDE_FORMAT_INSTRUCTION

        # 5. Вызов LLM
        llm_kwargs: Dict[str, Any] = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_question},
            ],
            "model": model,
        }
        if temperature is not None:
            llm_kwargs["temperature"] = temperature
        if reasoning and reasoning not in ("none", ""):
            llm_kwargs["reasoning_effort"] = reasoning

        # Гайд — фоновая задача, пользователь ждёт до 10 минут.
        # Больше retry с большим backoff (10s, 20s, 40s) чем для консультаций.
        result = await create_chat_completion_with_retry(
            **llm_kwargs,
            max_attempts=4,
            base_delay=10.0,
        )

        cost = calculate_cost(
            model=result["model"],
            prompt_tokens=result["prompt_tokens"],
            completion_tokens=result["completion_tokens"],
        )

        logger.info(
            f"[guide_llm] Секция '{section_key}' готова: "
            f"model={model}, tokens={result['total_tokens']}, cost=${cost:.4f}, "
            f"rag_snippets={len(kb_snippets)}, "
            f"prev_context={'yes' if previous_sections_content else 'no'}"
        )

        return {
            "key": section_key,
            "title": section["title"],
            "content": result["content"],
            "cost_usd": cost,
            "tokens": result["total_tokens"],
            "prompt_tokens": result["prompt_tokens"],
            "completion_tokens": result["completion_tokens"],
            "model": result["model"],
            "rag_snippets_count": len(kb_snippets),
            "user_question": user_question,
            "system_prompt": system_prompt,
        }

    except Exception as e:
        logger.error(f"[guide_llm] Ошибка генерации секции {section_key}: {e}")
        return {
            "key": section_key,
            "title": section["title"],
            "content": "",
            "cost_usd": 0.0,
            "tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "model": "",
            "rag_snippets_count": 0,
            "user_question": user_question,
            "system_prompt": "",
            "error": str(e),
        }


# ─── Генерация полного гайда ───

async def generate_full_guide(
    culture: str,
    location: str = "средняя полоса России",
    on_progress: Optional[Callable[[str, int, int], Awaitable[None]]] = None,
) -> Dict[str, Any]:
    """
    Генерирует гайд из 5 секций ПОСЛЕДОВАТЕЛЬНО.

    Каждая следующая секция получает контент предыдущих в системный промпт,
    чтобы избежать повторов информации.

    Порядок генерации: Питание → Защита → Подготовка почвы → Уходные работы → Вступление
    Порядок в PDF: Вступление → Питание → Защита → Подготовка почвы → Уходные работы

    Вступление генерируется последним (видит весь контент), но в итоговом
    словаре sections получает order=0, чтобы в PDF стоять первым.

    Args:
        culture: Название культуры ("малина летняя", "клубника ремонтантная")
        location: Регион выращивания
        on_progress: Опциональный callback(section_key, completed, total)

    Returns:
        {
            "culture": str,
            "location": str,
            "sections": {key: {"title": str, "content": str}},
            "total_cost_usd": float,
            "total_tokens": int,
            "errors": [str],
        }
    """
    section_keys = sorted(
        GUIDE_SECTIONS.keys(),
        key=lambda k: GUIDE_SECTIONS[k]["order"],
    )
    # +1 для вступления
    total = len(section_keys) + 1

    # Получить модель для логов
    model, _, _ = await _get_guide_model_config()

    logger.info(
        f"[guide_llm] Запуск ПОСЛЕДОВАТЕЛЬНОЙ генерации гайда: culture={culture}, "
        f"model={model}, sections={total} (4 основных + вступление)"
    )

    sections = {}
    sections_meta = {}
    total_cost = 0.0
    total_tokens = 0
    errors = []
    accumulated_content = ""

    # 1. Генерируем основные секции последовательно — каждая видит контент предыдущих
    for i, key in enumerate(section_keys):
        result = await generate_section(
            key, culture, location,
            previous_sections_content=accumulated_content,
        )

        sections[key] = {
            "title": result["title"],
            "content": result["content"],
        }

        sections_meta[key] = {
            "title": result["title"],
            "prompt_tokens": result.get("prompt_tokens", 0),
            "completion_tokens": result.get("completion_tokens", 0),
            "cost_usd": result.get("cost_usd", 0.0),
            "model": result.get("model", ""),
            "user_question": result.get("user_question", ""),
            "system_prompt": result.get("system_prompt", ""),
            "rag_snippets_count": result.get("rag_snippets_count", 0),
        }

        if result.get("error"):
            errors.append(key)

        total_cost += result.get("cost_usd", 0.0)
        total_tokens += result.get("tokens", 0)

        # Накапливаем контент для следующей секции
        if result.get("content"):
            accumulated_content += f"## {result['title']}\n{result['content']}\n\n"

        # Прогресс
        if on_progress:
            try:
                await on_progress(key, i + 1, total)
            except Exception:
                pass

    # 2. Генерируем вступление ПОСЛЕДНИМ — оно видит весь контент
    intro_result = await generate_section(
        "intro", culture, location,
        previous_sections_content=accumulated_content,
    )

    sections["intro"] = {
        "title": intro_result["title"],
        "content": intro_result["content"],
    }

    sections_meta["intro"] = {
        "title": intro_result["title"],
        "prompt_tokens": intro_result.get("prompt_tokens", 0),
        "completion_tokens": intro_result.get("completion_tokens", 0),
        "cost_usd": intro_result.get("cost_usd", 0.0),
        "model": intro_result.get("model", ""),
        "user_question": intro_result.get("user_question", ""),
        "system_prompt": intro_result.get("system_prompt", ""),
        "rag_snippets_count": intro_result.get("rag_snippets_count", 0),
    }

    if intro_result.get("error"):
        errors.append("intro")

    total_cost += intro_result.get("cost_usd", 0.0)
    total_tokens += intro_result.get("tokens", 0)

    if on_progress:
        try:
            await on_progress("intro", total, total)
        except Exception:
            pass

    logger.info(
        f"[guide_llm] Гайд сгенерирован (последовательно): culture={culture}, "
        f"model={model}, "
        f"sections={total - len(errors)}/{total}, "
        f"cost=${total_cost:.4f}, tokens={total_tokens}, errors={errors}"
    )

    return {
        "culture": culture,
        "location": location,
        "sections": sections,
        "sections_meta": sections_meta,
        "total_cost_usd": total_cost,
        "total_tokens": total_tokens,
        "model": model,
        "errors": errors,
    }
