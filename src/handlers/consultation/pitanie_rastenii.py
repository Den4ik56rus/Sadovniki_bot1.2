# src/handlers/consultation/pitanie_rastenii.py

"""
Хендлеры для сценария консультации по питанию растений.

НОВАЯ ЛОГИКА:
ЭТАП 1 (waiting_nutrition_root):
    - Пользователь пишет первый вопрос.
    - Определяем культуру через классификатор.
    - Если культура "клубника общая" или "малина общая":
        * задаем ТОЛЬКО вопрос о типе (ремонтантная/летняя),
        * переводим в состояние "waiting_variety_clarification".
    - Иначе:
        * вызываем LLM для получения ответа или уточняющих вопросов,
        * если LLM задал уточняющие вопросы → переводим в "waiting_nutrition_details",
        * если LLM дал финальный ответ → завершаем консультацию.

ЭТАП 2 (waiting_variety_clarification):
    - Пользователь отвечает на вопрос о типе культуры.
    - Переопределяем культуру на основе ответа.
    - Вызываем LLM для получения ответа или уточняющих вопросов.
    - Если LLM задал уточняющие вопросы → переводим в "waiting_nutrition_details".

ЭТАП 3 (waiting_nutrition_details):
    - Пользователь отвечает на уточняющие вопросы LLM.
    - Вызываем LLM для финального ответа.
    - Отправляем Q&A в moderation_queue.
    - Очищаем состояние и контекст.
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

from src.services.llm.consultation_llm import ask_consultation_llm
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

    # Определяем культуру из корневого вопроса
    culture = await detect_culture_name(root_question)
    print(f"[nutrition] STEP1 culture={culture!r}")

    # Сохраняем контекст консультации в памяти процесса
    CONSULTATION_CONTEXT[user.id] = {
        "category": "питание растений",  # тип консультации (для RAG / KB)
        "root_question": root_question,  # корневой вопрос
        "culture": culture,              # определенная культура
        "user_id": user_id,
        "topic_id": topic_id,
        "session_id": session_id,
        "telegram_user_id": telegram_user_id,
    }

    # Проверяем, нужно ли уточнять тип культуры
    if culture in ("клубника общая", "малина общая"):
        # Задаем ТОЛЬКО вопрос о типе культуры
        if culture == "клубника общая":
            variety_question = "Какая у вас клубника: летняя (июньская) или ремонтантная (НСД)?"
        else:  # малина общая
            variety_question = "Какая у вас малина: летняя (обычная) или ремонтантная?"

        await message.answer(variety_question)
        CONSULTATION_STATE[user.id] = "waiting_variety_clarification"
        print(f"[nutrition] STEP1 done, state -> waiting_variety_clarification, user_id={user.id}")
    else:
        # Вызываем LLM для получения ответа или уточняющих вопросов
        base_category = "питание растений"

        # Показываем сообщение ожидания (формируются уточняющие вопросы)
        status_message = await message.answer("⏳ Подождите...")

        try:
            answer_text = await ask_consultation_llm(
                user_id=user_id,
                telegram_user_id=telegram_user_id,
                text=root_question,
                session_id=session_id,
                consultation_category=base_category,
                culture=culture,
                is_first_llm_call=True,  # Это первое обращение к LLM - должен задать уточняющие вопросы
            )
        finally:
            # Удаляем сообщение ожидания
            try:
                await status_message.delete()
            except Exception:
                pass

        await message.answer(answer_text)

        # Логируем ответ бота
        await log_message(
            user_id=user_id,
            direction="bot",
            text=answer_text,
            session_id=session_id,
            topic_id=topic_id,
        )

        # Проверяем, задал ли LLM уточняющие вопросы
        # Эвристика: если в ответе есть фраза "ответьте на вопросы" - это уточняющие вопросы
        if "ответьте на" in answer_text.lower() or "уточните" in answer_text.lower():
            # LLM задал уточняющие вопросы - ждем ответа
            CONSULTATION_STATE[user.id] = "waiting_nutrition_details"
            print(f"[nutrition] STEP1 LLM asked clarification questions, state -> waiting_nutrition_details")
        else:
            # LLM дал финальный ответ - завершаем консультацию
            # Формируем category_guess для moderation
            if culture and culture != "не определено":
                category_guess = f"{base_category} / {culture}"
            else:
                category_guess = base_category

            await moderation_add(
                user_id=user_id,
                topic_id=topic_id,
                question=root_question,
                answer=answer_text,
                category_guess=category_guess,
            )

            # Очищаем состояние
            CONSULTATION_STATE.pop(user.id, None)
            CONSULTATION_CONTEXT.pop(user.id, None)
            print(f"[nutrition] STEP1 LLM gave final answer, consultation completed")


# ==== ЭТАП 2: уточнение типа культуры (для клубники/малины общей) ====


@router.message(
    lambda m: m.from_user is not None
    and CONSULTATION_STATE.get(m.from_user.id) == "waiting_variety_clarification"
)
async def handle_variety_clarification(message: Message) -> None:
    """
    Обрабатывает ответ на вопрос о типе культуры (ремонтантная/летняя).
    """

    user = message.from_user
    if user is None:
        return

    print(f"[nutrition] STEP2 (variety) enter, telegram_user_id={user.id}")

    ctx = CONSULTATION_CONTEXT.get(user.id)
    if not ctx:
        print(f"[nutrition] STEP2 (variety) no context for user_id={user.id}, reset state")
        CONSULTATION_STATE.pop(user.id, None)
        return

    root_question: str = ctx.get("root_question", "")
    old_culture: str = ctx.get("culture", "")
    user_id: int = ctx.get("user_id")
    topic_id: int = ctx.get("topic_id")
    session_id: str = ctx.get("session_id", "")

    # Ответ пользователя о типе культуры
    variety_answer = message.text or ""

    # Логируем ответ пользователя
    await log_message(
        user_id=user_id,
        direction="user",
        text=variety_answer,
        session_id=session_id,
        topic_id=topic_id,
    )

    # Переопределяем культуру на основе ответа
    culture = await detect_culture_name(root_question + "\n" + variety_answer)
    print(f"[nutrition] STEP2 (variety) re-classified culture: {old_culture!r} -> {culture!r}")

    # Обновляем контекст с новой культурой
    ctx["culture"] = culture
    ctx["variety_answer"] = variety_answer
    CONSULTATION_CONTEXT[user.id] = ctx

    # Вызываем LLM с уточненной культурой
    base_category = ctx.get("category", "питание растений")
    combined_question = root_question + "\n\nТип культуры: " + variety_answer

    # Показываем сообщение ожидания (формируются уточняющие вопросы)
    status_message = await message.answer("⏳ Подождите...")

    try:
        answer_text = await ask_consultation_llm(
            user_id=user_id,
            telegram_user_id=ctx.get("telegram_user_id", user.id),
            text=combined_question,
            session_id=session_id,
            consultation_category=base_category,
            culture=culture,
            is_first_llm_call=True,  # Указываем, что это первое обращение к LLM - он должен задать уточняющие вопросы
        )
    finally:
        # Удаляем сообщение ожидания
        try:
            await status_message.delete()
        except Exception:
            pass

    await message.answer(answer_text)

    # Логируем ответ бота
    await log_message(
        user_id=user_id,
        direction="bot",
        text=answer_text,
        session_id=session_id,
        topic_id=topic_id,
    )

    # Проверяем, задал ли LLM уточняющие вопросы
    if "ответьте на" in answer_text.lower() or "уточните" in answer_text.lower():
        # LLM задал уточняющие вопросы - ждем ответа
        CONSULTATION_STATE[user.id] = "waiting_nutrition_details"
        print(f"[nutrition] STEP2 (variety) LLM asked clarification questions, state -> waiting_nutrition_details")
    else:
        # LLM дал финальный ответ - завершаем консультацию
        if culture and culture != "не определено":
            category_guess = f"{base_category} / {culture}"
        else:
            category_guess = base_category

        await moderation_add(
            user_id=user_id,
            topic_id=topic_id,
            question=combined_question,
            answer=answer_text,
            category_guess=category_guess,
        )

        # Очищаем состояние
        CONSULTATION_STATE.pop(user.id, None)
        CONSULTATION_CONTEXT.pop(user.id, None)
        print(f"[nutrition] STEP2 (variety) LLM gave final answer, consultation completed")


# ==== ЭТАП 3: ответы на уточняющие вопросы по питанию ====


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

    print(f"[nutrition] STEP3 enter, telegram_user_id={user.id}")

    ctx = CONSULTATION_CONTEXT.get(user.id)
    if not ctx:
        print(f"[nutrition] STEP3 no context for user_id={user.id}, reset state")
        CONSULTATION_STATE.pop(user.id, None)
        return

    root_question: str = ctx.get("root_question", "")
    culture: str = ctx.get("culture", "не определено")  # Берем УЖЕ определенную культуру
    user_id: int = ctx.get("user_id")
    topic_id: int = ctx.get("topic_id")
    session_id: str = ctx.get("session_id", "")
    telegram_user_id: int = ctx.get("telegram_user_id", user.id)

    # Ответ пользователя на уточняющие вопросы по питанию
    details_text = message.text or ""

    # Если был промежуточный ответ о типе культуры - включаем его в детали
    variety_answer: str = ctx.get("variety_answer", "")
    if variety_answer:
        details_text = variety_answer + "\n" + details_text

    print(f"[nutrition] STEP3 using culture={culture!r}")

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

    # Показываем сообщение ожидания
    status_message = await message.answer("⏳ Подождите, рекомендация формируется...")

    try:
        answer_text = await ask_consultation_llm(
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            text=full_question,
            session_id=session_id,
            consultation_category=base_category,
            culture=culture,
        )
    finally:
        # Удаляем сообщение ожидания
        try:
            await status_message.delete()
        except Exception:
            pass

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
