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
from src.services.db.topics_repo import (
    get_or_create_open_topic,
    get_topic_culture,
    set_topic_culture,
)
from src.services.db.messages_repo import log_message
from src.services.db.moderation_repo import moderation_add

from src.services.llm.consultation_llm import ask_consultation_llm
from src.services.llm.classification_llm import detect_culture_name

# Импортируем функции для отправки информации о счётчике и проверки отказа
from src.handlers.consultation.entry import (
    send_followup_count_message,
    send_long_message,
    is_rejection_response,
)

from src.keyboards.consultation.common import get_followup_keyboard

from aiogram import F
from aiogram.types import CallbackQuery

router = Router()

print("[nutrition] router imported")


# ==== НОВАЯ ФУНКЦИЯ: Обработка консультации по питанию (для унифицированного entry) ====

async def process_nutrition_consultation(
    message: Message,
    user_id: int,
    category: str,
    culture: str,
    root_question: str,
) -> None:
    """
    Обрабатывает консультацию по питанию растений.
    Может быть вызвана из unified handler или из старого handle_nutrition_root.

    Args:
        message: Сообщение от пользователя
        user_id: Внутренний ID пользователя из БД
        category: Категория консультации (должна быть "питание растений")
        culture: Определенная культура
        root_question: Текст вопроса пользователя
    """
    user = message.from_user
    if user is None:
        return

    telegram_user_id = user.id
    session_id = build_session_id_from_message(message)

    print(f"[process_nutrition] user_id={user_id}, category={category!r}, culture={culture!r}")

    # Создаем или получаем топик
    topic_id = await get_or_create_open_topic(
        user_id=user_id,
        session_id=session_id,
    )

    # Обновляем категорию и культуру в БД
    from src.services.db.topics_repo import set_topic_category
    await set_topic_category(topic_id, category)
    await set_topic_culture(topic_id, culture)

    # Логируем вопрос пользователя
    await log_message(
        user_id=user_id,
        direction="user",
        text=root_question,
        session_id=session_id,
        topic_id=topic_id,
    )

    # Сохраняем контекст консультации
    CONSULTATION_CONTEXT[telegram_user_id] = {
        "category": category,
        "root_question": root_question,
        "culture": culture,
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
        CONSULTATION_STATE[telegram_user_id] = "waiting_variety_clarification"
        print(f"[process_nutrition] Asking variety, state -> waiting_variety_clarification")
        return

    # Вызываем LLM для получения ответа
    base_category = category

    # Определяем, нужен ли RAG
    use_rag = culture not in ("общая информация", "не определено", None)

    # Показываем сообщение ожидания
    status_message = await message.answer("⏳ Подождите, рекомендация формируется...")

    try:
        answer_text = await ask_consultation_llm(
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            text=root_question,
            session_id=session_id,
            consultation_category=base_category,
            culture=culture,
            default_location="средняя полоса",
            default_growing_type="открытый грунт",
            skip_rag=not use_rag,
        )
    finally:
        try:
            await status_message.delete()
        except Exception:
            pass

    # Проверяем, является ли ответ уточняющим вопросом
    if not use_rag:
        is_clarification = (
            len(answer_text) < 300
            and (
                "уточните" in answer_text.lower()
                or "о какой культуре" in answer_text.lower()
                or "какая у вас" in answer_text.lower()
                or "?" in answer_text
            )
        )
    else:
        is_clarification = False

    # Отправляем ответ
    if is_clarification:
        await send_long_message(message, answer_text)
        CONSULTATION_STATE[telegram_user_id] = "waiting_nutrition_clarification"
        print(f"[process_nutrition] LLM asking clarification, state -> waiting_nutrition_clarification")
    else:
        await send_long_message(message, answer_text)
        # Отправляем клавиатуру отдельным сообщением если ответ был длинным
        # (клавиатура не поддерживается при разбивке на несколько сообщений)
        CONSULTATION_CONTEXT[telegram_user_id]["full_question"] = root_question
        CONSULTATION_STATE.pop(telegram_user_id, None)
        print(f"[process_nutrition] Showing followup buttons, use_rag={use_rag}")

    # Логируем ответ бота
    await log_message(
        user_id=user_id,
        direction="bot",
        text=answer_text,
        session_id=session_id,
        topic_id=topic_id,
    )

    # Добавляем в moderation (только если финальный ответ и НЕ отказ)
    if not is_clarification and not is_rejection_response(answer_text):
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

        # Отправляем информацию о количестве оставшихся вопросов
        from src.services.db.topics_repo import get_follow_up_questions_left
        questions_left = await get_follow_up_questions_left(topic_id)
        await send_followup_count_message(message, questions_left, topic_id)


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
    # Новая тема создана уже при выборе категории консультации через close_open_topics()
    topic_id = await get_or_create_open_topic(
        user_id=user_id,
        session_id=session_id,
    )
    print(f"[nutrition] topic_id={topic_id}, user_id={user_id}")

    # Корневой вопрос пользователя
    root_question = message.text or ""

    # КРИТИЧНО: Проверяем message_count и culture ДО логирования сообщения!
    from src.services.db.topics_repo import get_topic_message_count
    message_count_before = await get_topic_message_count(topic_id)
    culture = await get_topic_culture(topic_id)

    print(f"[nutrition] ДО логирования: topic_id={topic_id}, message_count={message_count_before}, culture={culture!r}")

    # Определяем: это первое сообщение в топике?
    is_first_message = (message_count_before == 0)

    # Логируем корневой вопрос
    await log_message(
        user_id=user_id,
        direction="user",
        text=root_question,
        session_id=session_id,
        topic_id=topic_id,
    )

    # Если это первое сообщение в топике - переопределяем культуру
    # Даже если культура есть (это означает, что топик был создан заново после закрытия старого)
    if is_first_message:
        print(f"[nutrition] Это первое сообщение (count_before={message_count_before}), переопределяем культуру (было: {culture!r})")
        detected_culture = await detect_culture_name(root_question)
        if detected_culture and detected_culture != "не определено":
            await set_topic_culture(topic_id, detected_culture)
            culture = detected_culture
            print(f"[CULTURE] Автоматически определена культура: {culture}")
        else:
            await set_topic_culture(topic_id, "не определено")
            culture = "не определено"
            print(f"[CULTURE] Культура не определена, сохранено: {culture}")
    else:
        print(f"[nutrition] Продолжение диалога (count_before={message_count_before}), используем сохраненную культуру: {culture!r}")

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
        # Вызываем LLM для получения ответа
        base_category = "питание растений"

        # Определяем, нужен ли RAG
        # Если культура конкретная (не "общая информация" и не "не определено") - используем RAG сразу
        # Если культура неопределённая - сначала без RAG (для уточняющих вопросов)
        use_rag = culture not in ("общая информация", "не определено", None)

        # Показываем сообщение ожидания
        status_message = await message.answer("⏳ Подождите, рекомендация формируется...")

        try:
            answer_text = await ask_consultation_llm(
                user_id=user_id,
                telegram_user_id=telegram_user_id,
                text=root_question,
                session_id=session_id,
                consultation_category=base_category,
                culture=culture,
                default_location="средняя полоса",
                default_growing_type="открытый грунт",
                skip_rag=not use_rag,  # Используем RAG только если культура определена
            )
        finally:
            # Удаляем сообщение ожидания
            try:
                await status_message.delete()
            except Exception:
                pass

        # Проверяем, является ли ответ уточняющим вопросом (только если RAG не использовался)
        if not use_rag:
            is_clarification = (
                len(answer_text) < 300  # Короткий ответ
                and (
                    "уточните" in answer_text.lower()
                    or "о какой культуре" in answer_text.lower()
                    or "какая у вас" in answer_text.lower()
                    or "?" in answer_text
                )
            )
        else:
            # Если использовался RAG - это финальный ответ
            is_clarification = False

        # Отправляем ответ (с кнопками только если это финальный ответ)
        if is_clarification:
            await message.answer(answer_text)
            # Переводим в состояние ожидания ответа на уточняющий вопрос
            CONSULTATION_STATE[user.id] = "waiting_nutrition_clarification"
            print(f"[nutrition] STEP1 done, LLM asking for clarification, state -> waiting_nutrition_clarification")
        else:
            await message.answer(answer_text, reply_markup=get_followup_keyboard(category))

            # Сохраняем полный вопрос в контекст для кнопок
            CONSULTATION_CONTEXT[user.id]["full_question"] = root_question

            # Очищаем состояние ожидания (контекст сохраняем для кнопок)
            CONSULTATION_STATE.pop(user.id, None)
            print(f"[nutrition] STEP1 done, showing followup buttons, use_rag={use_rag}")

        # Логируем ответ бота
        await log_message(
            user_id=user_id,
            direction="bot",
            text=answer_text,
            session_id=session_id,
            topic_id=topic_id,
        )

        # Формируем category_guess для moderation (только если финальный ответ и НЕ отказ)
        if not is_clarification and not is_rejection_response(answer_text):
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

            # Отправляем информацию о количестве оставшихся вопросов
            from src.services.db.topics_repo import get_follow_up_questions_left
            questions_left = await get_follow_up_questions_left(topic_id)
            await send_followup_count_message(message, questions_left, topic_id)


# ==== ЭТАП 1.5: ответ на уточняющий вопрос LLM ====


@router.message(
    lambda m: m.from_user is not None
    and CONSULTATION_STATE.get(m.from_user.id) == "waiting_nutrition_clarification"
)
async def handle_nutrition_clarification(message: Message) -> None:
    """
    Обрабатывает ответ на уточняющий вопрос LLM.
    """

    user = message.from_user
    if user is None:
        return

    print(f"[nutrition] STEP1.5 (clarification) enter, telegram_user_id={user.id}")

    ctx = CONSULTATION_CONTEXT.get(user.id)
    if not ctx:
        print(f"[nutrition] STEP1.5 no context for user_id={user.id}, reset state")
        CONSULTATION_STATE.pop(user.id, None)
        return

    root_question: str = ctx.get("root_question", "")
    user_id: int = ctx.get("user_id")
    topic_id: int = ctx.get("topic_id")
    session_id: str = ctx.get("session_id", "")
    telegram_user_id: int = ctx.get("telegram_user_id", user.id)

    # Дополнительная проверка валидности контекста
    if not all([user_id, topic_id, root_question]):
        print(f"[nutrition] STEP1.5 invalid context for user_id={user.id}, reset state and context")
        CONSULTATION_STATE.pop(user.id, None)
        CONSULTATION_CONTEXT.pop(user.id, None)
        return

    # Ответ пользователя на уточняющий вопрос
    clarification_answer = message.text or ""

    # Логируем ответ пользователя
    await log_message(
        user_id=user_id,
        direction="user",
        text=clarification_answer,
        session_id=session_id,
        topic_id=topic_id,
    )

    # Переопределяем культуру на основе ответа
    combined_text = root_question + "\n" + clarification_answer
    culture = await detect_culture_name(combined_text)
    print(f"[nutrition] STEP1.5 re-classified culture: {ctx.get('culture')!r} -> {culture!r}")

    # Обновляем культуру в БД и контексте
    await set_topic_culture(topic_id, culture)
    ctx["culture"] = culture
    CONSULTATION_CONTEXT[user.id] = ctx

    # Проверяем, нужно ли уточнять тип культуры
    if culture in ("клубника общая", "малина общая"):
        # Задаем вопрос о типе культуры
        if culture == "клубника общая":
            variety_question = "Какая у вас клубника: летняя (июньская) или ремонтантная (НСД)?"
        else:  # малина общая
            variety_question = "Какая у вас малина: летняя (обычная) или ремонтантная?"

        await message.answer(variety_question)
        CONSULTATION_STATE[user.id] = "waiting_variety_clarification"
        print(f"[nutrition] STEP1.5 done, state -> waiting_variety_clarification")
        return

    # Вызываем LLM для финального ответа с RAG
    base_category = ctx.get("category", "питание растений")
    combined_question = root_question + "\n\n" + clarification_answer

    # Показываем сообщение ожидания
    status_message = await message.answer("⏳ Подождите, рекомендация формируется...")

    try:
        answer_text = await ask_consultation_llm(
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            text=combined_question,
            session_id=session_id,
            consultation_category=base_category,
            culture=culture,
            default_location="средняя полоса",
            default_growing_type="открытый грунт",
            skip_rag=False,  # Теперь используем RAG для финального ответа
        )
    finally:
        # Удаляем сообщение ожидания
        try:
            await status_message.delete()
        except Exception:
            pass

    # Отправляем ответ
    await send_long_message(message, answer_text)

    # Логируем ответ бота
    await log_message(
        user_id=user_id,
        direction="bot",
        text=answer_text,
        session_id=session_id,
        topic_id=topic_id,
    )

    # Формируем category_guess для moderation (только если НЕ отказ)
    if not is_rejection_response(answer_text):
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

        # Отправляем информацию о количестве оставшихся вопросов
        from src.services.db.topics_repo import get_follow_up_questions_left
        questions_left = await get_follow_up_questions_left(topic_id)
        await send_followup_count_message(message, questions_left, topic_id)

    # Сохраняем полный вопрос в контекст для кнопок
    ctx["full_question"] = combined_question
    CONSULTATION_CONTEXT[user.id] = ctx

    # Очищаем состояние (контекст сохраняем для кнопок)
    CONSULTATION_STATE.pop(user.id, None)
    print(f"[nutrition] STEP1.5 done, showing followup buttons")


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

    # Проверяем, что контекст содержит все необходимые поля
    root_question: str = ctx.get("root_question", "")
    old_culture: str = ctx.get("culture", "")
    user_id: int = ctx.get("user_id")
    topic_id: int = ctx.get("topic_id")
    session_id: str = ctx.get("session_id", "")

    # Дополнительная проверка валидности контекста
    if not all([user_id, topic_id, old_culture]):
        print(f"[nutrition] STEP2 (variety) invalid context for user_id={user.id}, reset state and context")
        CONSULTATION_STATE.pop(user.id, None)
        CONSULTATION_CONTEXT.pop(user.id, None)
        return

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

    # Определяем тип культуры на основе ответа пользователя
    variety_answer_lower = variety_answer.lower()

    # Определяем, какой тип указал пользователь
    if old_culture == "клубника общая":
        if "ремонтант" in variety_answer_lower or "нсд" in variety_answer_lower or "nsd" in variety_answer_lower:
            culture = "клубника ремонтантная"
        elif "летн" in variety_answer_lower or "июньск" in variety_answer_lower or "обычн" in variety_answer_lower or "традицион" in variety_answer_lower:
            culture = "клубника летняя"
        else:
            # Если не смогли определить - пробуем через классификатор с контекстом
            culture = await detect_culture_name(f"клубника {variety_answer}")
            if culture == "общая информация" or culture == "не определено":
                culture = old_culture  # Оставляем как есть
    elif old_culture == "малина общая":
        if "ремонтант" in variety_answer_lower or "нсд" in variety_answer_lower or "nsd" in variety_answer_lower:
            culture = "малина ремонтантная"
        elif "летн" in variety_answer_lower or "обычн" in variety_answer_lower or "традицион" in variety_answer_lower:
            culture = "малина летняя"
        else:
            # Если не смогли определить - пробуем через классификатор с контекстом
            culture = await detect_culture_name(f"малина {variety_answer}")
            if culture == "общая информация" or culture == "не определено":
                culture = old_culture  # Оставляем как есть
    else:
        # Если это не клубника/малина общая - используем классификатор
        culture = await detect_culture_name(root_question + "\n" + variety_answer)

    print(f"[nutrition] STEP2 (variety) re-classified culture: {old_culture!r} -> {culture!r}")

    # Обновляем культуру в БД и контексте
    await set_topic_culture(topic_id, culture)
    ctx["culture"] = culture
    ctx["variety_answer"] = variety_answer
    CONSULTATION_CONTEXT[user.id] = ctx

    # Вызываем LLM с уточненной культурой для финального ответа
    base_category = ctx.get("category", "питание растений")
    combined_question = root_question + "\n\nТип культуры: " + variety_answer

    # Показываем сообщение ожидания
    status_message = await message.answer("⏳ Подождите, рекомендация формируется...")

    try:
        answer_text = await ask_consultation_llm(
            user_id=user_id,
            telegram_user_id=ctx.get("telegram_user_id", user.id),
            text=combined_question,
            session_id=session_id,
            consultation_category=base_category,
            culture=culture,
            default_location="средняя полоса",
            default_growing_type="открытый грунт",
            skip_rag=False,  # Используем RAG для финального ответа
        )
    finally:
        # Удаляем сообщение ожидания
        try:
            await status_message.delete()
        except Exception:
            pass

    # Отправляем ответ
    await send_long_message(message, answer_text)

    # Логируем ответ бота
    await log_message(
        user_id=user_id,
        direction="bot",
        text=answer_text,
        session_id=session_id,
        topic_id=topic_id,
    )

    # Формируем category_guess для moderation (только если НЕ отказ)
    if not is_rejection_response(answer_text):
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

        # Отправляем информацию о количестве оставшихся вопросов
        from src.services.db.topics_repo import get_follow_up_questions_left
        questions_left = await get_follow_up_questions_left(topic_id)
        await send_followup_count_message(message, questions_left, topic_id)

    # Сохраняем полный вопрос в контекст для кнопок
    ctx["full_question"] = combined_question
    CONSULTATION_CONTEXT[user.id] = ctx

    # Очищаем состояние (контекст сохраняем для кнопок)
    CONSULTATION_STATE.pop(user.id, None)
    print(f"[nutrition] STEP2 (variety) done, showing followup buttons")


# ==== Обработчики кнопок после получения ответа ====


@router.message(F.text == "🔄 Вопрос по новой теме")
async def handle_nutrition_new_topic(message: Message) -> None:
    """
    Обработчик кнопки "Вопрос по новой теме".
    Закрывает текущий топик, очищает контекст и сразу просит задать новый вопрос.
    Теперь без выбора категории - категория и культура определяются автоматически.
    """
    user = message.from_user
    if user is None:
        return

    print(f"[nutrition_new_topic] Нажата кнопка 'Новая тема' для user {user.id}")

    # Получаем внутренний user_id
    from src.services.db.users_repo import get_or_create_user
    internal_user_id = await get_or_create_user(
        telegram_user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    # Закрываем все открытые топики пользователя
    from src.services.db.topics_repo import close_open_topics
    await close_open_topics(internal_user_id)
    print(f"[nutrition_new_topic] Закрыты все топики для internal_user_id={internal_user_id} (telegram_user_id={user.id})")

    # Очищаем контекст и состояние
    CONSULTATION_CONTEXT.pop(user.id, None)

    # Устанавливаем новое состояние - ждем вопрос
    CONSULTATION_STATE[user.id] = "waiting_consultation_question"

    # Просим задать вопрос (без выбора категории)
    text = (
        "Опишите, пожалуйста, ваш вопрос одним сообщением:\n"
        "— какая культура (и сорт, если знаете);\n"
        "— в каком регионе/климате вы находитесь;\n"
        "— что именно вас волнует (питание, посадка, болезни и т.п.)."
    )

    await message.answer(text)


@router.message(F.text == "✏️ Заменить параметры")
async def handle_nutrition_replace_params(message: Message) -> None:
    """
    Обработчик кнопки "Заменить параметры".
    Позволяет пользователю указать новые параметры (местоположение, тип выращивания).
    """
    user = message.from_user
    if user is None:
        return

    ctx = CONSULTATION_CONTEXT.get(user.id)
    if not ctx:
        await message.answer("Контекст консультации утерян. Пожалуйста, задайте новый вопрос.")
        return

    # Устанавливаем состояние ожидания новых параметров
    CONSULTATION_STATE[user.id] = "waiting_param_replacement"

    await message.answer(
        "Укажите ваши параметры:\n"
        "Например: 'Теплица, Урал' или 'Южный регион, открытый грунт'\n\n"
        "Или задайте вопрос заново с другими условиями."
    )


@router.message(
    lambda m: m.from_user is not None
    and CONSULTATION_STATE.get(m.from_user.id) == "waiting_param_replacement"
)
async def handle_param_replacement(message: Message) -> None:
    """
    Обрабатывает ввод новых параметров пользователем.
    """
    user = message.from_user
    if user is None:
        return

    ctx = CONSULTATION_CONTEXT.get(user.id)
    if not ctx:
        await message.answer("Контекст консультации утерян")
        CONSULTATION_STATE.pop(user.id, None)
        return

    # Извлекаем параметры из текста пользователя
    text_lower = (message.text or "").lower()

    # По умолчанию используем стандартные значения
    location = "средняя полоса"
    growing_type = "открытый грунт"

    # Парсим местоположение
    if "урал" in text_lower or "сибир" in text_lower:
        location = "Урал/Сибирь"
    elif "юг" in text_lower or "южн" in text_lower:
        location = "южные регионы"
    elif "север" in text_lower or "северн" in text_lower:
        location = "северные регионы"
    elif "дальн" in text_lower and "восток" in text_lower:
        location = "Дальний Восток"
    elif "подмосков" in text_lower or "москв" in text_lower:
        location = "Подмосковье"
    elif "петербург" in text_lower or "ленинград" in text_lower:
        location = "Санкт-Петербург"

    # Парсим тип выращивания
    if "теплиц" in text_lower:
        growing_type = "теплица"
    elif "контейнер" in text_lower or "горшк" in text_lower or "кашпо" in text_lower:
        growing_type = "контейнерное выращивание"
    elif "закрыт" in text_lower and "грунт" in text_lower:
        growing_type = "закрытый грунт"

    # Сохраняем параметры в контексте
    if "default_params" not in ctx:
        ctx["default_params"] = {}
    ctx["default_params"]["location"] = location
    ctx["default_params"]["growing_type"] = growing_type
    CONSULTATION_CONTEXT[user.id] = ctx

    # Получаем оригинальный вопрос
    root_question = ctx.get("root_question", "")
    culture = ctx.get("culture", "не определено")
    category = ctx.get("category", "питание растений")
    user_id = ctx.get("user_id")
    session_id = ctx.get("session_id", "")

    # Показываем сообщение ожидания
    status_message = await message.answer("⏳ Подождите, формирую ответ с новыми параметрами...")

    try:
        answer_text = await ask_consultation_llm(
            user_id=user_id,
            telegram_user_id=user.id,
            text=root_question,
            session_id=session_id,
            consultation_category=category,
            culture=culture,
            default_location=location,
            default_growing_type=growing_type,
        )
    finally:
        try:
            await status_message.delete()
        except Exception:
            pass

    # Отправляем ответ
    await send_long_message(message, answer_text)

    # Логируем сообщения
    await log_message(
        user_id=user_id,
        direction="user",
        text=f"Новые параметры: {location}, {growing_type}",
        session_id=session_id,
        topic_id=ctx.get("topic_id"),
    )

    await log_message(
        user_id=user_id,
        direction="bot",
        text=answer_text,
        session_id=session_id,
        topic_id=ctx.get("topic_id"),
    )

    # Очищаем состояние
    CONSULTATION_STATE.pop(user.id, None)


# Маппинг категорий на тексты запросов для детального плана
CATEGORY_PLAN_REQUESTS = {
    "питание растений": "Составь детальный план подкормок с указанием конкретных дат, препаратов, дозировок и способов внесения.",
    "улучшение почвы": "Составь детальный план улучшения почвы с конкретными мероприятиями, сроками и материалами.",
    "посадка и уход": "Составь детальный план ухода с конкретными мероприятиями по месяцам.",
    "защита растений": "Составь детальный план защиты растений с указанием препаратов, сроков обработки и дозировок.",
    "подбор сорта": "Составь детальный план подбора сортов с рекомендациями и критериями выбора.",
}


@router.message(F.text.startswith("📋 Детальный план"))
async def handle_detailed_plan(message: Message) -> None:
    """
    Обработчик кнопки "Детальный план" для всех категорий.
    Формирует детальный план на основе предыдущего контекста и категории.
    """
    user = message.from_user
    if user is None:
        return

    ctx = CONSULTATION_CONTEXT.get(user.id)
    if not ctx:
        await message.answer("Контекст консультации утерян. Пожалуйста, задайте новый вопрос.")
        return

    full_question = ctx.get("full_question", ctx.get("root_question", ""))
    culture = ctx.get("culture", "не определено")
    category = ctx.get("category", "питание растений")
    user_id = ctx.get("user_id")
    topic_id = ctx.get("topic_id")
    session_id = ctx.get("session_id", "")
    telegram_user_id = ctx.get("telegram_user_id", user.id)

    # Получаем текст запроса для категории
    plan_request_text = CATEGORY_PLAN_REQUESTS.get(
        category, "Составь детальный план."
    )

    # Формируем запрос на детальный план
    detailed_plan_request = (
        f"На основе предыдущего вопроса:\n{full_question}\n\n{plan_request_text}"
    )

    # Показываем сообщение ожидания
    status_message = await message.answer("⏳ Формирую детальный план...")

    try:
        detailed_plan = await ask_consultation_llm(
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            text=detailed_plan_request,
            session_id=session_id,
            consultation_category=category,
            culture=culture,
            default_location="средняя полоса",
            default_growing_type="открытый грунт",
        )
    finally:
        try:
            await status_message.delete()
        except Exception:
            pass

    # Отправляем детальный план
    await send_long_message(message, detailed_plan)

    # Логируем запрос и ответ
    await log_message(
        user_id=user_id,
        direction="user",
        text=detailed_plan_request,
        session_id=session_id,
        topic_id=topic_id,
    )

    await log_message(
        user_id=user_id,
        direction="bot",
        text=detailed_plan,
        session_id=session_id,
        topic_id=topic_id,
    )
