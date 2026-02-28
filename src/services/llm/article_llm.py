# src/services/llm/article_llm.py

"""
LLM сервис для генерации статей в режиме администратора.

Отличия от consultation_llm:
- НЕ вызывает detect_category_and_culture() - пропускаем классификацию
- НЕ вызывает deduct_tokens() - бесплатно для админа
- Сохраняет статью в admin_articles для просмотра в админке
- НЕ загружает историю через get_last_messages() - нет диалога
- По умолчанию category=None (поиск по всей базе), поддерживает фильтрацию
- Увеличенные лимиты документов для RAG
- Тогглы: use_scripts, skip_rag, model_override (для webapp)
"""

import logging
from typing import Optional, Tuple

from src.services.rag.unified_retriever import retrieve_unified_snippets
from src.services.llm.gemini_embeddings import get_gemini_embedding_with_usage
from src.services.llm.core_llm import create_chat_completion_with_usage, calculate_cost
from src.prompts.article_prompt import build_article_system_prompt
from src.prompts.consultation_prompts import build_consultation_system_prompt
from src.services.db.article_repo import save_article
from src.config import settings
from src.services.db.settings_repo import get_model_for_task, get_temperature_for_task, get_reasoning_effort_for_task

logger = logging.getLogger(__name__)


async def generate_article(
    *,
    topic: str,
    telegram_user_id: int,
    category: Optional[str] = None,
    culture: Optional[str] = None,
    use_scripts: bool = True,
    use_consultation_prompt: bool = False,
    skip_rag: bool = False,
    model_override: Optional[str] = None,
) -> Tuple[str, int]:
    """
    Генерирует статью по заданной теме.

    Параметры:
        topic: Тема статьи от администратора
        telegram_user_id: ID администратора (для логирования)
        category: Категория для фильтрации RAG (None = вся база)
        culture: Культура для фильтрации RAG subcategory (None = без фильтра)
        use_scripts: Использовать article_prompt
        use_consultation_prompt: Использовать consultation_prompt (как при обычной консультации)
        skip_rag: Пропустить RAG-поиск и embedding
        model_override: Переопределить модель из настроек

    Возвращает:
        Tuple[str, int]: (текст статьи, ID статьи в БД)
    """
    print(f"\n[article_llm] ========== НАЧАЛО ГЕНЕРАЦИИ СТАТЬИ ==========")
    print(f"[article_llm] Тема: {topic}")
    print(f"[article_llm] Admin ID: {telegram_user_id}")
    print(f"[article_llm] category={category}, culture={culture}, use_scripts={use_scripts}, skip_rag={skip_rag}, model_override={model_override}")

    try:
        embed_tokens = 0
        kb_snippets = []
        qa_found = False

        if not skip_rag:
            # ============================================================
            # ШАГ 1: Получение embedding для темы статьи
            # ============================================================
            print(f"[article_llm] ШАГ 1: Получение embedding...")

            query_embedding, embed_tokens, embed_model = await get_gemini_embedding_with_usage(topic)

            print(f"[article_llm] Embedding получен:")
            print(f"  - Размерность: {len(query_embedding)}")
            print(f"  - Токены: {embed_tokens}")
            print(f"  - Модель: {embed_model}")

            # ============================================================
            # ШАГ 2: RAG-поиск
            # ============================================================
            print(f"\n[article_llm] ШАГ 2: RAG-поиск...")
            print(f"  - category={category}, subcategory={culture}")
            print(f"  - qa_limit=5, doc_limit=50, priority_doc_limit=20")

            kb_snippets, qa_found = await retrieve_unified_snippets(
                category=category,
                query_embedding=query_embedding,
                subcategory=culture,
                qa_limit=5,
                doc_limit=50,
                priority_doc_limit=20,
                qa_distance_threshold=0.6,
                doc_distance_threshold=0.75,
            )

            print(f"[article_llm] Результаты RAG-поиска:")
            print(f"  - Найдено фрагментов: {len(kb_snippets)}")
            print(f"  - Q&A найдены: {qa_found}")

            if not kb_snippets:
                print(f"[article_llm] WARNING: Релевантные фрагменты не найдены!")
                print(f"[article_llm] Статья будет сгенерирована на основе знаний LLM")
            else:
                level1 = [s for s in kb_snippets if s.get("priority_level") == 1]
                level2 = [s for s in kb_snippets if s.get("priority_level") == 2]
                level3 = [s for s in kb_snippets if s.get("priority_level") == 3]
                print(f"  - Уровень 1 (Q&A): {len(level1)}")
                print(f"  - Уровень 2 (приоритетные docs): {len(level2)}")
                print(f"  - Уровень 3 (обычные docs): {len(level3)}")
        else:
            print(f"[article_llm] ШАГ 1-2: ПРОПУЩЕНЫ (skip_rag=True)")

        # ============================================================
        # ШАГ 3: Формирование системного промпта
        # ============================================================
        print(f"\n[article_llm] ШАГ 3: Формирование промпта (use_scripts={use_scripts}, use_consultation_prompt={use_consultation_prompt})...")

        parts = []

        if use_scripts:
            article_part = build_article_system_prompt(
                topic=topic,
                kb_snippets=kb_snippets,
                qa_found=qa_found,
            )
            parts.append(article_part)

        if use_consultation_prompt:
            consultation_part = await build_consultation_system_prompt(
                culture=culture or "не определено",
                kb_snippets=kb_snippets,
                qa_found=qa_found,
                consultation_category=category or "",
            )
            parts.append(consultation_part)

        if parts:
            system_prompt = "\n\n---\n\n".join(parts)
        else:
            system_prompt = f"Ты — профессиональный агроном, специализирующийся на ягодных культурах. Напиши подробную статью на тему: {topic}"

        print(f"[article_llm] Системный промпт сформирован:")
        print(f"  - Длина: {len(system_prompt)} символов")

        # ============================================================
        # ШАГ 4: Вызов LLM для генерации статьи
        # ============================================================
        print(f"\n[article_llm] ШАГ 4: Вызов LLM для генерации статьи...")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Напиши подробную статью на тему: {topic}"}
        ]

        article_model = model_override if model_override else await get_model_for_task("article")
        article_temp = await get_temperature_for_task("article")

        print(f"[article_llm] Параметры LLM:")
        print(f"  - Модель: {article_model}")
        print(f"  - Temperature: {article_temp}")
        print(f"  - Сообщений: {len(messages)}")

        article_reasoning = await get_reasoning_effort_for_task("article")

        response = await create_chat_completion_with_usage(
            messages=messages,
            model=article_model,
            temperature=article_temp,
            reasoning_effort=article_reasoning,
        )

        article_text = response["content"]
        llm_tokens = response["total_tokens"]
        prompt_tokens = response["prompt_tokens"]
        completion_tokens = response["completion_tokens"]
        model_used = response["model"]

        llm_cost = calculate_cost(model_used, prompt_tokens, completion_tokens)

        print(f"[article_llm] Статья сгенерирована:")
        print(f"  - Длина: {len(article_text)} символов")
        print(f"  - Токены: {llm_tokens} (prompt: {prompt_tokens}, completion: {completion_tokens})")
        print(f"  - Модель: {model_used}")
        print(f"  - Стоимость: ${llm_cost:.6f}")

        # ============================================================
        # ШАГ 5: Сохранение в БД
        # ============================================================
        total_tokens = embed_tokens + llm_tokens
        total_cost = llm_cost

        print(f"\n[article_llm] ШАГ 5: Сохранение статьи в БД...")

        article_id = await save_article(
            admin_telegram_id=telegram_user_id,
            topic=topic,
            article_text=article_text,
            rag_snippets=kb_snippets,
            rag_snippets_count=len(kb_snippets),
            system_prompt=system_prompt,
            embedding_tokens=embed_tokens,
            llm_prompt_tokens=prompt_tokens,
            llm_completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=total_cost,
            llm_model=model_used,
        )

        print(f"[article_llm] Статья сохранена с ID: {article_id}")

        # ============================================================
        # ШАГ 6: Итоговая статистика
        # ============================================================
        print(f"\n[article_llm] ========== ИТОГОВАЯ СТАТИСТИКА ==========")
        print(f"[article_llm] ID статьи: {article_id}")
        print(f"[article_llm] Всего токенов: {total_tokens}")
        print(f"[article_llm] Общая стоимость: ${total_cost:.6f}")
        print(f"[article_llm] Длина статьи: {len(article_text)} символов")
        print(f"[article_llm] ПРИМЕЧАНИЕ: Токены НЕ списываются (админский режим)")
        print(f"[article_llm] ========== ГЕНЕРАЦИЯ ЗАВЕРШЕНА ==========\n")

        return article_text, article_id

    except Exception as e:
        logger.error(f"[article_llm] Ошибка при генерации статьи: {e}", exc_info=True)
        print(f"[article_llm] ОШИБКА: {e}")
        raise
