# src/services/llm/consultation_llm.py

"""
Модуль для работы с нейросетью (LLM — Large Language Model) в НОВОЙ структуре проекта.

Задача:
    - использовать историю диалога из БД через messages_repo;
    - подтягивать знания из knowledge_base через RAG;
    - формировать messages для модели;
    - вызывать OpenAI через общий core_llm;
    - возвращать текст ответа.

Основная функция:
    ask_consultation_llm(...)
"""

import time
import asyncio
import logging
from typing import Optional, List, Dict, Callable, Awaitable

from src.services.db.messages_repo import get_last_messages, get_recent_messages  # История сообщений
from src.services.rag.unified_retriever import retrieve_unified_snippets  # Объединенный RAG-поиск (Q&A + документы)
from src.services.llm.gemini_embeddings import get_gemini_embedding_with_usage   # Эмбеддинги текста через Gemini
from src.services.llm.core_llm import (
    create_chat_completion_with_usage,
    create_chat_completion_with_retry,
    create_chat_completion_streaming,
    calculate_cost,
    calculate_embedding_cost,
)
from src.prompts.consultation_prompts import build_consultation_system_prompt  # Системный промпт
from src.services.db.consultation_logs_repo import log_consultation  # Логирование консультаций

from src.config import settings
from src.services.db.settings_repo import get_model_for_task, get_temperature_for_task, get_reasoning_effort_for_task

logger = logging.getLogger(__name__)


async def compose_full_question(
    root_question: str,
    clarifications: List[Dict[str, str]],
    culture_context: Optional[str] = None,
) -> tuple:
    """
    Формирует полный читабельный вопрос из root_question + уточнений + культуры.

    Лёгкий LLM-вызов (gpt-4o-mini) без истории чата.
    ВСЕГДА вызывает LLM для красивого форматирования вопроса.

    Параметры:
        root_question: Исходный вопрос пользователя
        clarifications: Список уточнений [{"bot": "вопрос бота", "user": "ответ пользователя"}]
        culture_context: Контекст культуры для follow-up вопросов (например, "малина ремонтантная")

    Возвращает:
        Tuple: (composed_question, compose_cost_usd, compose_tokens)
        - composed_question: Полный сформулированный вопрос для RAG-поиска
        - compose_cost_usd: Стоимость вызова LLM в USD
        - compose_tokens: Общее количество токенов (prompt + completion)
    """
    # Формируем контекст для LLM (может быть пустым если нет уточнений)
    clarification_text = ""
    if clarifications:
        for idx, item in enumerate(clarifications, 1):
            bot_q = item.get("bot", "")
            user_a = item.get("user", "")
            if bot_q and user_a:
                clarification_text += f"\nУточнение {idx}:\n- Бот спросил: {bot_q}\n- Пользователь ответил: {user_a}"
            elif user_a:
                clarification_text += f"\nДополнение от пользователя: {user_a}"

    system_prompt = """Ты помощник, который формулирует грамотный вопрос для поиска в базе знаний.

Твоя задача: переформулировать исходный запрос пользователя в полный, читабельный вопрос.

Правила:
1. Результат должен быть одним предложением-вопросом
2. Если есть уточнения — включи всю важную информацию из них
3. ОБЯЗАТЕЛЬНО включи контекст культуры, если он указан
4. Вопрос должен быть грамматически правильным и начинаться с заглавной буквы
5. Если исходный запрос короткий (например "питание малины") — разверни его в полноценный вопрос
6. Не добавляй лишней информации, которой не было в исходном запросе
7. Отвечай ТОЛЬКО сформулированным вопросом, без пояснений

Примеры:
- "питание малины летней" → "Какое питание необходимо для летней малины?"
- "обрезка голубики" → "Как правильно проводить обрезку голубики?"
- "болезни клубники" → "Какие болезни бывают у клубники и как с ними бороться?"
- "как поливать" + контекст: "малина ремонтантная" → "Как правильно поливать малину ремонтантную?" """

    # Добавляем контекст культуры, если он указан
    if culture_context:
        context_note = f"\nКонтекст культуры: {culture_context}"
    else:
        context_note = ""

    if clarification_text:
        user_prompt = f"""Исходный вопрос: {root_question}
{clarification_text}{context_note}

Сформулируй полный вопрос:"""
    else:
        user_prompt = f"""Исходный запрос пользователя: {root_question}{context_note}

Сформулируй этот запрос в виде полного грамотного вопроса:"""

    try:
        response = await create_chat_completion_with_usage(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=await get_model_for_task("utility"),
            temperature=await get_temperature_for_task("utility"),
            reasoning_effort=await get_reasoning_effort_for_task("utility"),
        )

        composed = response["content"].strip()

        # Убираем кавычки если LLM обернула ответ
        if composed.startswith('"') and composed.endswith('"'):
            composed = composed[1:-1]
        if composed.startswith('«') and composed.endswith('»'):
            composed = composed[1:-1]

        # Рассчитываем стоимость вызова
        compose_cost = calculate_cost(
            model=response["model"],
            prompt_tokens=response["prompt_tokens"],
            completion_tokens=response["completion_tokens"],
        )
        compose_tokens = response["total_tokens"]

        print(f"[compose_full_question] Root: {root_question[:50]}...")
        print(f"[compose_full_question] Clarifications: {len(clarifications)}")
        print(f"[compose_full_question] Result: {composed}")
        print(f"[compose_full_question] Tokens: {compose_tokens}, Cost: ${compose_cost:.6f}")

        return composed, compose_cost, compose_tokens

    except Exception as e:
        logger.error(f"[compose_full_question] Error: {e}")
        # Fallback: простая склейка
        parts = [root_question]
        for item in clarifications:
            if item.get("user"):
                parts.append(item["user"])
        return " ".join(parts), 0.0, 0


def _detect_category_legacy(text: str) -> Optional[str]:
    """
    СТАРАЯ грубая классификация по ключевым словам (для совместимости).

    Возвращает:
        'strawberry' / 'raspberry' / 'bush' или None.

    Сейчас используется только как fallback, если сценарий не передал
    тип консультации и культуру.
    """
    t = text.lower()

    if any(
        word in t
        for word in (
            "клубник",
            "земляник",
            "фриго",
            "ремонтантная клубник",
            "ремонтантная земляник",
        )
    ):
        return "strawberry"

    if any(
        word in t
        for word in (
            "малина",
            "рем малина",
            "ремонтантная малина",
        )
    ):
        return "raspberry"

    if any(
        word in t
        for word in (
            "смородин",
            "жимолост",
            "крыжовник",
            "кустарник",
        )
    ):
        return "bush"

    return None


async def ask_consultation_llm(
    *,
    user_id: int,
    telegram_user_id: int,
    text: str,
    session_id: str,
    topic_id: Optional[int] = None,               # ID топика для логирования
    consultation_category: Optional[str] = None,  # Тип консультации: 'питание растений', 'посадка и уход' и т.п.
    culture: Optional[str] = None,                # Культура: 'малина', 'голубика' и т.п. (может быть 'не определено')
    default_location: str = "средняя полоса",     # Местоположение по умолчанию
    default_growing_type: str = "открытый грунт", # Тип выращивания по умолчанию
    is_first_llm_call: bool = False,              # DEPRECATED: больше не используется
    skip_rag: bool = False,                       # Флаг пропуска RAG-поиска
    composed_question: Optional[str] = None,      # Сформированный вопрос для RAG (если есть)
    compose_cost_usd: float = 0.0,                # Стоимость форматирования вопроса (добавляется к общей)
    compose_tokens: int = 0,                      # Токены форматирования вопроса
    classification_cost_usd: float = 0.0,         # Стоимость классификации (detect_culture, detect_category_and_culture)
    classification_tokens: int = 0,               # Токены классификации
    status_updater: Optional[Callable] = None,  # Callback для обновления прогресс-бара: (step, total, label)
    stream: bool = False,  # Включить стриминг ответа
    streaming_transition: Optional[Callable[[], Awaitable[Callable[[str], Awaitable[None]]]]] = None,  # Переход в стриминг-режим
    # Complexity tracking
    complexity_tier: Optional[str] = None,
    complexity_metadata: Optional[dict] = None,
    complexity_classification_cost_usd: float = 0.0,
    complexity_classification_tokens: int = 0,
    # Phase mode (Тип B/C)
    phase_mode: Optional[str] = None,       # "single_phase" | "seasonal_phase" | None
    phase_key: Optional[str] = None,        # "весна-цветение" и т.д.
    phase_topic: Optional[str] = None,      # "питание", "защита", "уход"
    is_last_phase: bool = False,            # Последняя фаза в Тип C
    phase_number: int = 0,                  # Номер фазы (1, 2, 3) для логирования
) -> str:
    """
    Основной вызов LLM.

    Параметры:
        user_id              — id пользователя в нашей БД;
        telegram_user_id     — Telegram ID (для логов/отладки);
        text                 — текущий текст запроса (полный вопрос);
        session_id           — идентификатор сессии диалога;
        consultation_category — тип консультации (если известен сценарию),
                                например: 'питание растений', 'посадка и уход';
        culture              — культура (если определена отдельным классификатором),
                                например: 'малина', 'голубика', 'общая информация', 'не определено';
        is_first_llm_call    — флаг, что это первое обращение к LLM (должен задать уточняющие вопросы);
        skip_rag             — если True, пропускаем RAG-поиск (используется на этапе уточняющих вопросов).

    Если consultation_category/culture не переданы, будет использоваться
    старая логика _detect_category_legacy (в основном для совместимости).
    """

    # Инициализируем счетчики стоимости (добавляем к переданным значениям)
    total_classification_cost = classification_cost_usd
    total_classification_tokens = classification_tokens

    # Определяем количество шагов для прогресс-бара
    total_steps = 3 if skip_rag else 6

    # Хелпер для безопасного обновления прогресс-бара
    # Минимальная задержка чтобы пользователь успел прочитать текст шага
    _last_progress_time: float = 0.0
    MIN_STEP_DISPLAY_SEC: float = 1.8  # минимум 1.8 сек на показ каждого шага

    async def update_progress(step: int, label: str) -> None:
        nonlocal _last_progress_time
        if status_updater:
            try:
                # Ждём чтобы предыдущий шаг был виден хотя бы MIN_STEP_DISPLAY_SEC
                now = time.perf_counter()
                if _last_progress_time > 0:
                    elapsed = now - _last_progress_time
                    if elapsed < MIN_STEP_DISPLAY_SEC:
                        await asyncio.sleep(MIN_STEP_DISPLAY_SEC - elapsed)
                await status_updater(step, total_steps, label)
                _last_progress_time = time.perf_counter()
            except Exception:
                pass  # Ошибки статуса не должны ломать консультацию

    # 1. История диалога
    if skip_rag:
        await update_progress(1, "Анализирую Ваш вопрос...")
    else:
        await update_progress(1, "Загружаю историю диалога...")

    # Фильтруем историю по topic_id чтобы не подхватывать контекст из других топиков
    if topic_id:
        history: List[Dict] = await get_recent_messages(
            topic_id=topic_id,
            limit=6,
        )
    else:
        history: List[Dict] = await get_last_messages(
            user_id=user_id,
            limit=6,
        )

    # 2. Собираем последние пользовательские сообщения
    user_history_texts: List[str] = [
        item["text"]
        for item in history
        if item.get("direction") == "user"
        and item.get("text")
    ]

    if text and (not user_history_texts or user_history_texts[-1] != text):
        user_history_texts.append(text)

    # Контекст для RAG
    if user_history_texts:
        # Склеиваем последние 2–3 сообщения пользователя — контекст для RAG
        recent_for_category = " ".join(user_history_texts[-3:])
    else:
        recent_for_category = text

    # 3. Определяем, по какой категории и культуре искать в KB

    rag_category: Optional[str] = None      # Тип консультации для knowledge_base.category
    rag_subcategory: Optional[str] = None   # Культура для knowledge_base.subcategory

    # 3.1. Если сценарий явно передал тип консультации и культуру — используем их
    if consultation_category:
        rag_category = consultation_category.strip()

        if culture and culture.strip() and culture.strip().lower() not in ("не определено", "общая информация"):
            rag_subcategory = culture.strip()

    # 3.2. Если тип консультации не передан — fallback на старую грубую классификацию
    if rag_category is None:
        legacy_cat = _detect_category_legacy(recent_for_category or "")
        # В старой схеме здесь были 'strawberry', 'raspberry', 'bush'.
        # Если у тебя в KB есть старые данные с такими категориями —
        # они всё ещё будут использоваться. В новой схеме лучше всегда
        # передавать consultation_category из сценария.
        rag_category = legacy_cat
        rag_subcategory = None

    # 4. RAG: подтягиваем выдержки из базы знаний
    kb_snippets: List[Dict] = []
    qa_found: bool = False  # НОВОЕ: флаг найденных Q&A
    embedding_tokens: int = 0
    embedding_model: Optional[str] = None

    # Определяем текст для RAG-поиска
    # Приоритет: composed_question > recent_for_category > text
    rag_query_text = composed_question or recent_for_category or text

    # Проверяем глобальный переключатель RAG
    from src.services.db.settings_repo import is_rag_enabled
    rag_globally_enabled = await is_rag_enabled()

    # Пропускаем RAG, если явно указано или глобально отключено
    if skip_rag or not rag_globally_enabled:
        reason = "skip_rag=True (этап уточняющих вопросов)" if skip_rag else "RAG глобально отключён (admin toggle)"
        print(f"\n{'='*60}")
        print(f"[RAG] Пропущен ({reason})")
        print(f"{'='*60}\n")
    elif rag_category is not None:
        print(f"\n{'='*60}")
        print(f"[RAG] Начинаем поиск в базе знаний")
        print(f"[RAG] Категория: {rag_category}")
        print(f"[RAG] Подкатегория (культура): {rag_subcategory or 'не указана'}")
        print(f"[RAG] Запрос для поиска: {rag_query_text}")

        try:
            await update_progress(2, "Готовлю запрос для поиска...")

            query_embedding, embedding_tokens, embedding_model = await get_gemini_embedding_with_usage(
                rag_query_text
            )
            print(f"[RAG] Получен эмбеддинг запроса (размер: {len(query_embedding)}, токенов: {embedding_tokens}, модель: {embedding_model})")

            await update_progress(3, "Ищу подходящую литературу...")

            kb_snippets, qa_found = await retrieve_unified_snippets(
                category=rag_category,
                subcategory=rag_subcategory,
                query_embedding=query_embedding,
                qa_limit=3,           # Уровень 1: Q&A (2-3 лучших результата)
                doc_limit=6,          # Уровень 3: Документы по культуре
                priority_doc_limit=6,  # Уровень 2: Приоритетные документы
                qa_distance_threshold=0.45,   # Порог для Q&A
                doc_distance_threshold=0.5,   # Порог для документов
            )

            print(f"[RAG] Q&A найдены на уровне 1: {qa_found}")
            print(f"[RAG] Найдено фрагментов: {len(kb_snippets)}")

            if kb_snippets:
                print(f"[RAG] Детали найденных фрагментов:")
                for idx, snippet in enumerate(kb_snippets, 1):
                    source_type = snippet.get("source_type", "unknown")
                    priority = snippet.get("priority_level", "?")
                    distance = snippet.get("distance", 0)
                    category = snippet.get("category", "?")
                    subcategory = snippet.get("subcategory", "?")

                    print(f"  #{idx} [УРОВЕНЬ {priority}] [{source_type}]")
                    print(f"      Категория: {category} / Подкатегория: {subcategory}")
                    print(f"      Distance: {distance:.4f}")
                    print(f"      Документ загружен")
            else:
                print(f"[RAG] ⚠️ НИЧЕГО НЕ НАЙДЕНО в базе знаний!")
                print(f"[RAG] Возможные причины:")
                print(f"      - База знаний пуста")
                print(f"      - Нет документов для категории '{rag_category}'")
                print(f"      - Нет документов для подкатегории '{rag_subcategory}'")
                print(f"      - Все найденные фрагменты за порогом distance (>0.6 для Q&A, >0.75 для документов)")

            print(f"{'='*60}\n")

        except Exception as e:
            print(f"[ask_consultation_llm][KB/RAG error] {e}")
            kb_snippets = []

    # 5. Собираем messages для LLM
    messages: List[Dict[str, str]] = []

    if kb_snippets:
        await update_progress(4, "Изучаю найденные материалы...")

    # Используем новый улучшенный системный промпт со стандартными параметрами
    system_prompt = await build_consultation_system_prompt(
        culture=culture or "не определено",
        kb_snippets=kb_snippets,
        qa_found=qa_found,  # НОВОЕ: передаем флаг найденных Q&A
        consultation_category=consultation_category or "",
        default_location=default_location,
        default_growing_type=default_growing_type,
    )

    # Инъекция фазовых инструкций (Тип B/C)
    if phase_mode and phase_key and phase_topic:
        from src.prompts.consultation_prompts import build_phase_instruction
        phase_instruction = build_phase_instruction(
            phase_key=phase_key,
            phase_topic=phase_topic,
            is_last_phase=is_last_phase,
        )
        system_prompt += phase_instruction
        print(f"[ask_consultation_llm] Phase instruction injected: mode={phase_mode}, phase={phase_key}, topic={phase_topic}, last={is_last_phase}")

    # Инъекция инструкции для краткого ответа (Тип A / downgrade)
    elif complexity_tier == "short_answer" and complexity_metadata:
        from src.prompts.consultation_prompts import build_short_answer_instruction
        short_instruction = build_short_answer_instruction()
        system_prompt += short_instruction
        user_downgraded = complexity_metadata.get("user_downgraded", False)
        print(f"[ask_consultation_llm] Short answer instruction injected (user_downgraded={user_downgraded})")

    messages.append(
        {
            "role": "system",
            "content": system_prompt,
        }
    )

    # История диалога
    for item in history:
        direction = item["direction"]
        text_item = item["text"]
        role = "user" if direction == "user" else "assistant"

        messages.append(
            {
                "role": role,
                "content": text_item,
            }
        )

    # Текущее сообщение (полный вопрос)
    # ВАЖНО: is_first_llm_call больше не используется - всегда даём финальный ответ
    current_message_text = text

    messages.append(
        {
            "role": "user",
            "content": current_message_text,
        }
    )

    # 6. Вызов модели с логированием
    start_time = time.perf_counter()

    if skip_rag:
        await update_progress(2, "Формирую уточняющий вопрос...")
    else:
        await update_progress(5, "Формирую ответ...")

    try:
        # Переход в стриминг-режим (если включён)
        on_stream_chunk = None
        if stream and streaming_transition:
            on_stream_chunk = await streaming_transition()

        if stream and on_stream_chunk:
            llm_response = await create_chat_completion_streaming(
                messages=messages,
                model=await get_model_for_task("consultation"),
                temperature=await get_temperature_for_task("consultation"),
                reasoning_effort=await get_reasoning_effort_for_task("consultation"),
                on_chunk=on_stream_chunk,
            )
        else:
            llm_response = await create_chat_completion_with_retry(
                messages=messages,
                model=await get_model_for_task("consultation"),
                temperature=await get_temperature_for_task("consultation"),
                reasoning_effort=await get_reasoning_effort_for_task("consultation"),
            )

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        response_text = llm_response["content"]

        if not response_text:
            return "Не удалось получить ответ от модели. Попробуйте ещё раз позже."

        # Логирование консультации (fire-and-forget, не блокирует ответ)
        asyncio.create_task(_log_consultation_async(
            user_id=user_id,
            topic_id=topic_id,
            user_message=text,
            bot_response=response_text,
            system_prompt=system_prompt,
            rag_snippets=kb_snippets,
            llm_response=llm_response,
            latency_ms=latency_ms,
            consultation_category=consultation_category,
            culture=culture,
            embedding_tokens=embedding_tokens,
            embedding_model=embedding_model,
            composed_question=composed_question,
            compose_cost_usd=compose_cost_usd,
            compose_tokens=compose_tokens,
            classification_cost_usd=total_classification_cost,
            classification_tokens=total_classification_tokens,
            complexity_tier=complexity_tier,
            complexity_metadata=complexity_metadata,
            complexity_classification_cost_usd=complexity_classification_cost_usd,
            complexity_classification_tokens=complexity_classification_tokens,
            phase_mode=phase_mode,
            phase_key=phase_key,
            phase_number=phase_number,
        ))

        return response_text.strip()

    except Exception as e:
        print(f"[ask_consultation_llm][OpenAI error] {e}")
        logger.error(f"[ask_consultation_llm][OpenAI error] {e}")
        raise  # Пробрасываем ошибку — вызывающий код возвращает токены


async def _log_consultation_async(
    user_id: int,
    topic_id: Optional[int],
    user_message: str,
    bot_response: str,
    system_prompt: str,
    rag_snippets: List[Dict],
    llm_response: Dict,
    latency_ms: int,
    consultation_category: Optional[str],
    culture: Optional[str],
    embedding_tokens: int = 0,
    embedding_model: Optional[str] = None,
    composed_question: Optional[str] = None,
    compose_cost_usd: float = 0.0,
    compose_tokens: int = 0,
    classification_cost_usd: float = 0.0,
    classification_tokens: int = 0,
    # Complexity tracking
    complexity_tier: Optional[str] = None,
    complexity_metadata: Optional[dict] = None,
    complexity_classification_cost_usd: float = 0.0,
    complexity_classification_tokens: int = 0,
    # Phase tracking
    phase_mode: Optional[str] = None,
    phase_key: Optional[str] = None,
    phase_number: int = 0,
) -> None:
    """
    Асинхронно логирует консультацию в БД.
    Выполняется в фоне, чтобы не замедлять ответ пользователю.
    """
    try:
        # Стоимость основного LLM вызова
        llm_cost_usd = calculate_cost(
            model=llm_response["model"],
            prompt_tokens=llm_response["prompt_tokens"],
            completion_tokens=llm_response["completion_tokens"],
        )

        # Расчёт стоимости embeddings
        embedding_cost_usd = 0.0
        if embedding_tokens > 0 and embedding_model:
            embedding_cost_usd = calculate_embedding_cost(embedding_model, embedding_tokens)

        # Общая стоимость = classification + compose_question + embeddings + LLM + complexity
        total_cost_usd = classification_cost_usd + compose_cost_usd + embedding_cost_usd + llm_cost_usd + complexity_classification_cost_usd

        await log_consultation(
            user_id=user_id,
            topic_id=topic_id,
            user_message=user_message,
            bot_response=bot_response,
            system_prompt=system_prompt,
            rag_snippets=rag_snippets,
            llm_params={
                "model": llm_response["model"],
                "temperature": await get_temperature_for_task("consultation"),
            },
            prompt_tokens=llm_response["prompt_tokens"],
            completion_tokens=llm_response["completion_tokens"],
            cost_usd=total_cost_usd,
            latency_ms=latency_ms,
            consultation_category=consultation_category,
            culture=culture,
            embedding_tokens=embedding_tokens,
            embedding_cost_usd=embedding_cost_usd,
            embedding_model=embedding_model,
            composed_question=composed_question,
            compose_cost_usd=compose_cost_usd,
            compose_tokens=compose_tokens,
            classification_cost_usd=classification_cost_usd,
            classification_tokens=classification_tokens,
            complexity_tier=complexity_tier,
            complexity_metadata=complexity_metadata,
            complexity_classification_cost_usd=complexity_classification_cost_usd,
            complexity_classification_tokens=complexity_classification_tokens,
            phase_mode=phase_mode,
            phase_key=phase_key,
            phase_number=phase_number,
        )

        logger.debug(
            f"[consultation_log] Записан лог: user={user_id}, topic={topic_id}, "
            f"tokens={llm_response['total_tokens']}, cost=${total_cost_usd:.6f}, latency={latency_ms}ms"
        )

    except Exception as e:
        logger.error(f"[consultation_log] Ошибка записи лога: {e}")
