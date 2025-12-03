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

from typing import Optional, List, Dict

from src.services.db.messages_repo import get_last_messages      # История сообщений
from src.services.rag.unified_retriever import retrieve_unified_snippets  # Объединенный RAG-поиск (Q&A + документы)
from src.services.llm.embeddings_llm import get_text_embedding   # Эмбеддинги текста
from src.services.llm.core_llm import create_chat_completion     # Вызов ChatGPT
from src.prompts.consultation_prompts import build_consultation_system_prompt  # Системный промпт

from src.config import settings


def build_nutrition_clarification_questions(root_question: str) -> str:
    """
    Возвращает текст уточняющих вопросов по питанию растений.

    Обычная синхронная функция — БЕЗ async/await.
    """
    return (
        "Чтобы подробно подсказать по питанию ваших ягодных растений, ответьте, пожалуйста, на вопросы:\n\n"
        "1️⃣ Какая культура и сорт (если знаете)?\n"
        "2️⃣ В каком регионе/климате вы находитесь?\n"
        "3️⃣ Растения в открытом грунте, теплице, в контейнерах или на приподнятых грядках?\n"
        "4️⃣ Возраст посадок (первый год, второй, старше)?\n"
        "5️⃣ В чём вопрос по питанию: чем и как подкармливать, схема удобрений, недостаток/избыток питания и т.п.?\n"
        "6️⃣ Есть ли сейчас видимые проблемы (бледные листья, покраснение, жёлтые края, пятна, слабый рост и т.п.)?\n\n"
        "Пожалуйста, ответьте на все вопросы одним сообщением, по пунктам."
    )


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
    consultation_category: Optional[str] = None,  # Тип консультации: 'питание растений', 'посадка и уход' и т.п.
    culture: Optional[str] = None,                # Культура: 'малина', 'голубика' и т.п. (может быть 'не определено')
    is_first_llm_call: bool = False,              # Флаг, что это первое обращение к LLM (должен задать уточняющие вопросы)
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
        is_first_llm_call    — флаг, что это первое обращение к LLM (должен задать уточняющие вопросы).

    Если consultation_category/culture не переданы, будет использоваться
    старая логика _detect_category_legacy (в основном для совместимости).
    """

    # 1. История диалога
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

    if rag_category is not None:
        print(f"\n{'='*60}")
        print(f"[RAG] Начинаем поиск в базе знаний")
        print(f"[RAG] Категория: {rag_category}")
        print(f"[RAG] Подкатегория (культура): {rag_subcategory or 'не указана'}")
        print(f"[RAG] Запрос пользователя: {text[:100]}...")

        try:
            query_embedding: List[float] = await get_text_embedding(
                recent_for_category or text
            )
            print(f"[RAG] Получен эмбеддинг запроса (размер: {len(query_embedding)})")

            kb_snippets = await retrieve_unified_snippets(
                category=rag_category,
                subcategory=rag_subcategory,
                query_embedding=query_embedding,
                qa_limit=20,          # Уровень 1: Q&A (увеличено в 10 раз)
                level2_limit=20,      # Уровень 2: Специфичные документы (увеличено в 10 раз)
                level3_limit=20,      # Уровень 3: Общие документы (увеличено в 10 раз)
                qa_distance_threshold=0.6,    # Увеличен порог для Q&A
                doc_distance_threshold=0.75,  # Увеличен порог для документов
            )

            print(f"[RAG] Найдено фрагментов: {len(kb_snippets)}")

            if kb_snippets:
                print(f"[RAG] Детали найденных фрагментов:")
                for idx, snippet in enumerate(kb_snippets, 1):
                    source_type = snippet.get("source_type", "unknown")
                    priority = snippet.get("priority_level", "?")
                    distance = snippet.get("distance", 0)
                    category = snippet.get("category", "?")
                    subcategory = snippet.get("subcategory", "?")
                    content_preview = snippet.get("content", "")[:150]

                    print(f"  #{idx} [УРОВЕНЬ {priority}] [{source_type}]")
                    print(f"      Категория: {category} / Подкатегория: {subcategory}")
                    print(f"      Distance: {distance:.4f}")
                    print(f"      Контент: {content_preview}...")
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

    # Используем новый улучшенный системный промпт с обязательными уточняющими вопросами
    system_prompt = await build_consultation_system_prompt(
        culture=culture or "не определено",
        kb_snippets=kb_snippets,
        consultation_category=consultation_category or "",
    )

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
    current_message_text = text

    # Если это первое обращение к LLM - добавляем явную инструкцию задать уточняющие вопросы
    if is_first_llm_call:
        current_message_text = (
            f"{text}\n\n"
            "(Это первое обращение по данному вопросу. Пожалуйста, задай уточняющие вопросы согласно ЭТАПУ 1, "
            "если информации недостаточно для полноценного ответа.)"
        )

    messages.append(
        {
            "role": "user",
            "content": current_message_text,
        }
    )

    # 6. Вызов модели
    try:
        response_text = await create_chat_completion(
            messages=messages,
            model=settings.openai_model,
            temperature=0.4,
        )

        if not response_text:
            return "Не удалось получить ответ от модели. Попробуйте ещё раз позже."

        return response_text.strip()

    except Exception as e:
        print(f"[ask_consultation_llm][OpenAI error] {e}")
        return "Сейчас не получается связаться с моделью. Попробуйте ещё раз чуть позже."
