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
from src.services.rag.kb_retriever import retrieve_kb_snippets   # RAG-поиск по KB
from src.services.llm.embeddings_llm import get_text_embedding   # Эмбеддинги текста
from src.services.llm.core_llm import create_chat_completion     # Вызов ChatGPT

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
                                например: 'малина', 'голубика', 'общая информация', 'не определено'.

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
    kb_context: str = ""

    if rag_category is not None:
        try:
            query_embedding: List[float] = await get_text_embedding(
                recent_for_category or text
            )

            snippets = await retrieve_kb_snippets(
                category=rag_category,
                subcategory=rag_subcategory,
                query_embedding=query_embedding,
                limit=3,
                distance_threshold=0.4,
            )

            if snippets:
                parts: List[str] = [item["answer"] for item in snippets]
                kb_context = "\n\n---\n\n".join(parts)

        except Exception as e:
            print(f"[ask_consultation_llm][KB/RAG error] {e}")
            kb_context = ""

    # 5. Собираем messages для LLM
    messages: List[Dict[str, str]] = []

    base_system_prompt = (
        "Ты — вежливый и понятный ассистент-садовник.\n"
        "Отвечай простым, понятным языком, на русском.\n"
        "Отвечай по делу, без лишней воды, по шагам и с конкретикой.\n"
        "Не добавляй в конце ответа никаких общих фраз типа "
        "«если будут ещё вопросы» или «могу также помочь с этим и тем» — "
        "просто дай законченный ответ по текущему вопросу.\n\n"
        "КОНСУЛЬТАЦИОННЫЙ РЕЖИМ:\n"
        "1) Если информации недостаточно, сначала задай несколько уточняющих вопросов,\n"
        "   чтобы лучше понять ситуацию (регион, культура и сорт, тип посадочного материала,\n"
        "   сроки, условия участка, цель — урожай, растянуть плодоношение и т.п.).\n"
        "2) ВСЕ уточняющие вопросы формулируй ОДНИМ сообщением, в виде пронумерованного списка.\n"
        "3) В конце такого сообщения ОБЯЗАТЕЛЬНО явно напиши пользователю просьбу:\n"
        "   «Пожалуйста, ответьте на все вопросы одним сообщением, по пунктам».\n"
        "4) Когда клиент ответил на уточняющие вопросы, дай один подробный итоговый ответ:\n"
        "   - сначала коротко сформулируй, чем именно он интересуется,\n"
        "   - потом дай структуру: пошаговый план, сроки, нюансы и предупреждения.\n\n"
        "ТЕМАТИЧЕСКОЕ ОГРАНИЧЕНИЕ:\n"
        "5) Ты консультируешь ТОЛЬКО по ягодным культурам и связанным с ними вопросам:\n"
        "   посадка, уход, хранение, отправка и получение саженцев, планировка посадок.\n"
        "6) Если текущий вопрос явно не про ягодные растения и не про эти темы,\n"
        "   ответь ОДНОЙ короткой фразой вида:\n"
        "   «Я могу дать консультацию только по ягодным культурам и вопросам их посадки и ухода. "
        "Пожалуйста, задайте вопрос по ягодным.»\n"
        "   Не пытайся подробно отвечать на такие вопросы и не уходи в другие темы."
    )

    messages.append(
        {
            "role": "system",
            "content": base_system_prompt,
        }
    )

    if kb_context:
        kb_system_prompt = (
            "Ниже приведены выдержки из внутренней базы знаний магазина.\n"
            "Считай их приоритетным источником фактов и не противоречь им:\n\n"
            f"{kb_context}"
        )
        messages.append(
            {
                "role": "system",
                "content": kb_system_prompt,
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
    messages.append(
        {
            "role": "user",
            "content": text,
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
