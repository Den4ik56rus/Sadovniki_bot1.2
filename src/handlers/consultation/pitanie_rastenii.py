# src/handlers/consultation/pitanie_rastenii.py

"""
Хендлеры для сценария консультации по питанию растений.

ЭТАП 1:
    - Пользователь выбрал в меню категорию "Питание растений".
    - В CONSULTATION_STATE[user_id] установлено состояние "waiting_nutrition_root".
    - Пользователь пишет первый (корневой) вопрос.
    - Мы:
        * сохраняем этот корневой вопрос в CONSULTATION_CONTEXT,
        * логируем его в БД,
        * отправляем пользователю уточняющие вопросы одним сообщением,
        * переводим состояние в "waiting_nutrition_details".

ЭТАП 2:
    - В CONSULTATION_STATE[user_id] уже "waiting_nutrition_details".
    - Пользователь отвечает на уточняющие вопросы одним сообщением.
    - Мы:
        * собираем ПОЛНЫЙ ВОПРОС (root + детали) через LLM,
        * определяем культуру (через LLM-классификатор),
        * логируем полный вопрос,
        * вызываем ask_consultation_llm (внутри — RAG и база знаний),
        * отправляем ответ пользователю,
        * отправляем Q&A в moderation_queue,
        * очищаем состояние и контекст.
"""

from aiogram import Router
from aiogram.types import Message

from src.handlers.common import (
    CONSULTATION_STATE,
    CONSULTATION_CONTEXT,
    build_session_id_from_message,
)

from src.services.db.users_repo import get_or_create_user
from src.services.db.topics_repo import get_or_create_open_topic
from src.services.db.messages_repo import log_message
from src.services.db.moderation_repo import moderation_add

from src.services.llm.consultation_llm import (
    build_nutrition_clarification_questions,
    ask_consultation_llm,
)
from src.services.llm.classification_llm import detect_culture_name
from src.services.llm.question_builder_llm import build_full_question  # Сборка полного вопроса через LLM

router = Router()

print("[nutrition] router imported")


# ==== ЭТАП 1: корневой вопрос по питанию ====


@router.message(
    lambda m: m.from_user is not None
    and CONSULTATION_STATE.get(m.from_user.id) == "waiting_nutrition_root"
)
async def handle_nutrition_root(message: Message) -> None:
    """
    Обрабатывает ПЕРВЫЙ (корневой) вопрос по питанию растений.
    """

    user = message.from_user
    if user is None:
        return

    print(f"[nutrition] STEP1 enter, telegram_user_id={user.id}")

    # Строим session_id на основе апдейта (chat_id + message_id)
    session_id = build_session_id_from_message(message)

    telegram_user_id = user.id
    username = user.username
    first_name = user.first_name
    last_name = user.last_name

    # Регистрируем/находим пользователя в БД
    user_id = await get_or_create_user(
        telegram_user_id=telegram_user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
    )

    # Ищем/создаём открытую "тему" диалога
    topic_id = await get_or_create_open_topic(
        user_id=user_id,
        session_id=session_id,
    )

    # Корневой вопрос пользователя
    root_question = message.text or ""

    # Логируем корневой вопрос
    await log_message(
        user_id=user_id,
        direction="user",
        text=root_question,
        session_id=session_id,
        topic_id=topic_id,
    )

    # Сохраняем контекст консультации в памяти процесса
    CONSULTATION_CONTEXT[user.id] = {
        "category": "питание растений",  # тип консультации (для RAG / KB)
        "root_question": root_question,  # корневой вопрос
        "user_id": user_id,
        "topic_id": topic_id,
        "session_id": session_id,
        "telegram_user_id": telegram_user_id,
    }

    # Текст уточняющих вопросов по питанию
    clarifications_text = build_nutrition_clarification_questions(root_question)

    # Отправляем уточняющие
    await message.answer(clarifications_text)

    # Переводим пользователя во 2-й этап
    CONSULTATION_STATE[user.id] = "waiting_nutrition_details"
    print(f"[nutrition] STEP1 done, state -> waiting_nutrition_details, user_id={user.id}")


# ==== ЭТАП 2: ответы на уточняющие вопросы ====


@router.message(
    lambda m: m.from_user is not None
    and CONSULTATION_STATE.get(m.from_user.id) == "waiting_nutrition_details"
)
async def handle_nutrition_details(message: Message) -> None:
    """
    Обрабатывает ответы на уточняющие вопросы по питанию растений.
    """

    user = message.from_user
    if user is None:
        return

    print(f"[nutrition] STEP2 enter, telegram_user_id={user.id}")

    ctx = CONSULTATION_CONTEXT.get(user.id)
    if not ctx:
        # Если по какой-то причине контекст потеряли — сбрасываем состояние
        print(f"[nutrition] STEP2 no context for user_id={user.id}, reset state")
        CONSULTATION_STATE.pop(user.id, None)
        return

    root_question: str = ctx.get("root_question", "")
    user_id: int = ctx.get("user_id")
    topic_id: int = ctx.get("topic_id")
    session_id: str = ctx.get("session_id", "")
    telegram_user_id: int = ctx.get("telegram_user_id", user.id)

    # Ответ пользователя на уточняющие (всё одним сообщением)
    details_text = message.text or ""

    # Для классификатора культуры используем "сырые" root + детали
    text_for_culture = root_question + "\n" + details_text
    print(f"[nutrition] text_for_culture={text_for_culture!r}")

    # Определяем культуру (малина, голубика и т.п. или 'общая информация' / 'не определено')
    culture = await detect_culture_name(text_for_culture)
    print(f"[nutrition] culture_from_llm={culture!r}")

    # ПОЛНЫЙ ВОПРОС строим через отдельный LLM-хелпер
    full_question = await build_full_question(
        root_question=root_question,
        details_text=details_text,
        topic="питание растений",
    )
    print(f"[nutrition] full_question={full_question!r}")

    # Обновляем контекст консультации
    ctx["full_question"] = full_question
    ctx["culture"] = culture
    CONSULTATION_CONTEXT[user.id] = ctx

    # Логируем ПОЛНЫЙ ВОПРОС как сообщение пользователя
    await log_message(
        user_id=user_id,
        direction="user",
        text=full_question,
        session_id=session_id,
        topic_id=topic_id,
    )

    # Базовый тип консультации для этого сценария
    base_category = ctx.get("category", "питание растений")

    # То, что попадёт в moderation_queue.category_guess
    if culture and culture != "не определено":
        # пример: "питание растений / малина"
        category_guess = f"{base_category} / {culture}"
    else:
        # просто "питание растений"
        category_guess = base_category

    print(f"[nutrition] category_guess={category_guess!r}")

    # В LLM-консультацию тоже отправляем ПОЛНЫЙ ВОПРОС
    # ВАЖНО: сюда теперь передаём:
    #   consultation_category = 'питание растений'
    #   culture               = детектированная культура (или 'общая информация' / 'не определено')
    answer_text = await ask_consultation_llm(
        user_id=user_id,
        telegram_user_id=telegram_user_id,
        text=full_question,
        session_id=session_id,
        consultation_category=base_category,
        culture=culture,
    )

    # Отвечаем пользователю
    await message.answer(answer_text)

    # Логируем ответ бота в messages
    await log_message(
        user_id=user_id,
        direction="bot",
        text=answer_text,
        session_id=session_id,
        topic_id=topic_id,
    )

    # Отправляем диалог (full_question + answer) в очередь модерации
    await moderation_add(
        user_id=user_id,
        topic_id=topic_id,
        question=full_question,
        answer=answer_text,
        category_guess=category_guess,
    )

    # Чистим состояние и контекст для этого пользователя
    CONSULTATION_STATE.pop(user.id, None)
    CONSULTATION_CONTEXT.pop(user.id, None)
    print(f"[nutrition] STEP2 done, state cleared for telegram_user_id={user.id}")
