# src/services/llm/article_llm.py

"""
LLM сервис для генерации статей в режиме администратора.

Отличия от consultation_llm:
- НЕ вызывает detect_category_and_culture() - пропускаем классификацию
- НЕ вызывает deduct_tokens() - бесплатно для админа
- Сохраняет статью в admin_articles для просмотра в админке
- НЕ загружает историю через get_last_messages() - нет диалога
- Использует category=None в RAG-поиске - поиск по всей базе
- Увеличенные лимиты документов для RAG
"""

import logging
from typing import Optional, Tuple

from src.services.rag.unified_retriever import retrieve_unified_snippets
from src.services.llm.embeddings_llm import get_text_embedding_with_usage
from src.services.llm.core_llm import create_chat_completion_with_usage, calculate_cost
from src.prompts.article_prompt import build_article_system_prompt
from src.services.db.article_repo import save_article
from src.config import settings

logger = logging.getLogger(__name__)


async def generate_article(
    *,
    topic: str,
    telegram_user_id: int,
) -> Tuple[str, int]:
    """
    Генерирует статью по заданной теме с использованием всей базы знаний.

    Особенности режима статей:
    - Поиск по ВСЕЙ базе знаний (без фильтрации по category/subcategory)
    - Увеличенные лимиты документов для RAG
    - Специальный промпт с обязательной структурой
    - БЕЗ списания токенов
    - БЕЗ сохранения в БД

    Параметры:
        topic: Тема статьи от администратора
        telegram_user_id: ID администратора (для логирования)

    Возвращает:
        Tuple[str, int]: (текст статьи, ID статьи в БД)

    Raises:
        Exception: При ошибках генерации или вызова API
    """
    print(f"\n[article_llm] ========== НАЧАЛО ГЕНЕРАЦИИ СТАТЬИ ==========")
    print(f"[article_llm] Тема: {topic}")
    print(f"[article_llm] Admin ID: {telegram_user_id}")

    try:
        # ============================================================
        # ШАГ 1: Получение embedding для темы статьи
        # ============================================================
        print(f"[article_llm] ШАГ 1: Получение embedding...")

        query_embedding, embed_tokens, embed_model = await get_text_embedding_with_usage(topic)

        print(f"[article_llm] Embedding получен:")
        print(f"  - Размерность: {len(query_embedding)}")
        print(f"  - Токены: {embed_tokens}")
        print(f"  - Модель: {embed_model}")

        # ============================================================
        # ШАГ 2: RAG-поиск БЕЗ фильтрации по категориям
        # ============================================================
        print(f"\n[article_llm] ШАГ 2: RAG-поиск по ВСЕЙ базе знаний...")
        print(f"[article_llm] Параметры поиска:")
        print(f"  - category=None (поиск по всей базе)")
        print(f"  - qa_limit=5")
        print(f"  - doc_limit=50")
        print(f"  - priority_doc_limit=20")
        print(f"  - qa_distance_threshold=0.6")
        print(f"  - doc_distance_threshold=0.75")

        kb_snippets, qa_found = await retrieve_unified_snippets(
            category=None,  # КРИТИЧНО: None для поиска по всей базе
            query_embedding=query_embedding,
            subcategory=None,
            qa_limit=5,              # Увеличено для статей (обычно 2)
            doc_limit=50,            # Увеличено для статей (обычно 5)
            priority_doc_limit=20,   # Увеличено для статей (обычно 3)
            qa_distance_threshold=0.6,    # Более мягкий порог (обычно 0.4)
            doc_distance_threshold=0.75,  # Более мягкий порог (обычно 0.35)
        )

        print(f"[article_llm] Результаты RAG-поиска:")
        print(f"  - Найдено фрагментов: {len(kb_snippets)}")
        print(f"  - Q&A найдены: {qa_found}")

        if not kb_snippets:
            print(f"[article_llm] WARNING: Релевантные фрагменты не найдены!")
            print(f"[article_llm] Статья будет сгенерирована на основе знаний LLM")
        else:
            # Подробная статистика по уровням
            level1 = [s for s in kb_snippets if s.get("priority_level") == 1]
            level2 = [s for s in kb_snippets if s.get("priority_level") == 2]
            level3 = [s for s in kb_snippets if s.get("priority_level") == 3]
            print(f"  - Уровень 1 (Q&A): {len(level1)}")
            print(f"  - Уровень 2 (приоритетные docs): {len(level2)}")
            print(f"  - Уровень 3 (обычные docs): {len(level3)}")

        # ============================================================
        # ШАГ 3: Формирование системного промпта
        # ============================================================
        print(f"\n[article_llm] ШАГ 3: Формирование промпта для статьи...")

        system_prompt = build_article_system_prompt(
            topic=topic,
            kb_snippets=kb_snippets,
            qa_found=qa_found,
        )

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

        print(f"[article_llm] Параметры LLM:")
        print(f"  - Модель: {settings.openai_model_article}")
        print(f"  - Temperature: {settings.openai_temperature}")
        print(f"  - Сообщений: {len(messages)}")

        response = await create_chat_completion_with_usage(
            messages=messages,
            model=settings.openai_model_article,
            # temperature берётся из settings.openai_temperature
        )

        article_text = response["content"]
        llm_tokens = response["total_tokens"]
        prompt_tokens = response["prompt_tokens"]
        completion_tokens = response["completion_tokens"]
        model_used = response["model"]

        # Вычисляем стоимость
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
        total_cost = llm_cost  # Стоимость embedding очень мала, можно не учитывать

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
