# src/handlers/consultation/pitanie_rastenii.py

"""
Хендлеры для сценария консультации по питанию растений.

ЛОГИКА:
ЭТАП 1 (waiting_nutrition_root):
    - Пользователь пишет первый вопрос.
    - Определяем культуру через классификатор (всегда конкретная: "клубника летняя", "малина ремонтантная", и т.д.).
    - Вызываем LLM для получения ответа или уточняющих вопросов.
    - Если LLM задал уточняющие вопросы → переводим в "waiting_nutrition_details".
    - Если LLM дал финальный ответ → завершаем консультацию.

ЭТАП 2 (waiting_nutrition_details):
    - Пользователь отвечает на уточняющие вопросы LLM.
    - Вызываем LLM для финального ответа.
    - Отправляем Q&A в moderation_queue.
    - Очищаем состояние и контекст.
"""

from aiogram import Router, F
from aiogram.types import Message

from src.keyboards.consultation.common import CONSULTATION_ENTRY_TEXT, get_example_questions_keyboard

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

from src.services.llm.consultation_llm import ask_consultation_llm, compose_full_question
from src.services.llm.classification_llm import detect_culture_name

from src.handlers.consultation.entry import (
    send_long_message,
    finalize_streaming_message,
    is_rejection_response,
    is_clarification_question,
    _log_bot_msg,
    serialize_keyboard,
)

# Утилита форматирования Markdown → HTML
from src.utils.formatting import markdown_to_telegram_html

from src.keyboards.consultation.common import get_followup_keyboard
from src.utils.status_manager import StatusMessageManager

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
    classification_cost_usd: float = 0.0,
    classification_tokens: int = 0,
    correction_hint: str | None = None,
    complexity_result: dict | None = None,
    telegram_user_id_override: int | None = None,
    # Phase mode (Тип B/C)
    phase_mode: str | None = None,
    phase_key: str | None = None,
    phase_topic: str | None = None,
    is_last_phase: bool = False,
    phase_number: int = 0,
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
        classification_cost_usd: Стоимость классификации в USD (из unified_entry)
        classification_tokens: Токены классификации
        telegram_user_id_override: telegram ID при вызове из callback (где message.from_user = бот)
        phase_mode: Режим фазы (single_phase / seasonal_phase / None)
        phase_key: Ключ фазы (весна-цветение и т.д.)
        phase_topic: Тема фазы (питание / защита / уход)
        is_last_phase: Последняя ли это фаза
        phase_number: Номер фазы (1, 2, 3)
    """
    if telegram_user_id_override:
        telegram_user_id = telegram_user_id_override
        session_id = f"tg:{telegram_user_id}"
    else:
        user = message.from_user
        if user is None:
            return
        telegram_user_id = user.id
        session_id = build_session_id_from_message(message)

    # Complexity tracking kwargs
    _complexity_kwargs = {}
    if complexity_result:
        _complexity_kwargs = {
            "complexity_tier": complexity_result.get("tier"),
            "complexity_metadata": complexity_result.get("metadata"),
            "complexity_classification_cost_usd": complexity_result.get("cost_usd", 0.0),
            "complexity_classification_tokens": complexity_result.get("tokens", 0),
        }

    # Phase mode kwargs (phase_key может быть None — ИИ сам выберет фазу)
    _phase_kwargs = {}
    if phase_mode and phase_topic:
        _phase_kwargs = {
            "phase_mode": phase_mode,
            "phase_key": phase_key,  # None = ИИ сам выбирает
            "phase_topic": phase_topic,
            "is_last_phase": is_last_phase,
            "phase_number": phase_number,
        }

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

    # Привязываем ВСЕ промежуточные сообщения к топику
    _q_msg_id = CONSULTATION_CONTEXT.get(telegram_user_id, {}).get("question_msg_id")
    if _q_msg_id:
        try:
            from src.services.db.messages_repo import attach_pending_messages_to_topic
            await attach_pending_messages_to_topic(user_id, topic_id, since_msg_id=_q_msg_id)
        except Exception:
            pass

    # Сохраняем контекст консультации
    CONSULTATION_CONTEXT[telegram_user_id] = {
        "category": category,
        "root_question": root_question,
        "culture": culture,
        "user_id": user_id,
        "topic_id": topic_id,
        "session_id": session_id,
        "telegram_user_id": telegram_user_id,
        "classification_cost_usd": classification_cost_usd,
        "classification_tokens": classification_tokens,
    }

    # Вызываем LLM для получения ответа
    # (Больше не уточняем тип культуры — классификатор сразу определяет "летняя" или "ремонтантная")
    base_category = category

    # Определяем, нужен ли RAG
    use_rag = culture not in ("общая информация", "не определено", None)

    # Отправляем подсказку о коррекции культуры (если есть и RAG будет использован)
    if correction_hint and use_rag:
        hint = f"💡 {correction_hint}"
        await message.answer(hint)
        await _log_bot_msg(hint, user_id=user_id, session_id=session_id, topic_id=topic_id)

    # Показываем сообщение ожидания с динамическими обновлениями
    status_mgr = StatusMessageManager(message, use_rag=use_rag)
    await status_mgr.start()

    try:
        # Формируем красивый вопрос для RAG ТОЛЬКО если RAG используется
        # (не тратим токены на compose когда будем задавать уточняющие вопросы)
        if use_rag:
            composed_q, compose_cost, compose_tokens = await compose_full_question(root_question, [])
        else:
            composed_q = root_question
            compose_cost = 0.0
            compose_tokens = 0

        answer_text = await ask_consultation_llm(
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            text=root_question,
            session_id=session_id,
            topic_id=topic_id,
            consultation_category=base_category,
            culture=culture,
            default_location="средняя полоса",
            default_growing_type="открытый грунт",
            skip_rag=not use_rag,
            composed_question=composed_q if use_rag else None,
            compose_cost_usd=compose_cost,
            compose_tokens=compose_tokens,
            classification_cost_usd=classification_cost_usd,
            classification_tokens=classification_tokens,
            status_updater=status_mgr.update,
            stream=use_rag,
            streaming_transition=status_mgr.start_streaming if use_rag else None,
            **_complexity_kwargs,
            **_phase_kwargs,
        )
    finally:
        streaming_msg = status_mgr.get_streaming_message() if use_rag else None
        await status_mgr.complete()

    # Проверяем, является ли ответ уточняющим вопросом
    if not use_rag:
        is_clarification = is_clarification_question(answer_text)
    else:
        is_clarification = False

    # Отправляем ответ
    if is_clarification:
        await send_long_message(message, answer_text)
        CONSULTATION_STATE[telegram_user_id] = "waiting_nutrition_clarification"
        print(f"[process_nutrition] LLM asking clarification, state -> waiting_nutrition_clarification")
    else:
        # Выбираем клавиатуру: фазовая (любой phase_mode) или обычная
        from src.pricing import get_next_phase, get_phase_display_name
        from src.handlers.consultation.entry import detect_phase_from_response

        if phase_mode in ("seasonal_phase", "single_phase"):
            # Определяем фазу: если phase_key задан — используем, иначе определяем из ответа
            effective_phase_key = phase_key
            if not effective_phase_key and answer_text:
                effective_phase_key = detect_phase_from_response(answer_text)
                print(f"[process_nutrition] Auto-detected phase from response: {effective_phase_key}")

            from src.keyboards.consultation.common import get_next_phase_keyboard
            if effective_phase_key:
                next_phase = get_next_phase(effective_phase_key)
                if next_phase:
                    next_display = get_phase_display_name(next_phase)
                    kb = get_next_phase_keyboard(next_display)
                else:
                    kb = get_followup_keyboard(category)
            else:
                kb = get_followup_keyboard(category)
            next_state = "waiting_phase_continue"
        else:
            kb = get_followup_keyboard(category)
            next_state = "waiting_followup"

        # Enforcement длины ответа
        _is_extended_nutrition = phase_mode in ("seasonal_phase", "single_phase")
        if not _is_extended_nutrition and complexity_result:
            cr_tier = complexity_result.get("tier")
            if cr_tier == "short_answer":
                from src.handlers.consultation.entry import _truncate_to_single_message
                answer_text = _truncate_to_single_message(answer_text)
            elif cr_tier in ("extended_non_phase",):
                _is_extended_nutrition = True
        if _is_extended_nutrition:
            from src.handlers.consultation.entry import _enforce_two_message_format
            answer_text = _enforce_two_message_format(answer_text)

        await finalize_streaming_message(
            streaming_msg, message, answer_text,
            keyboard=kb,
            show_followup_prompt=(next_state == "waiting_followup"),
            force_two_parts=_is_extended_nutrition,
        )
        CONSULTATION_CONTEXT[telegram_user_id]["full_question"] = root_question
        CONSULTATION_STATE[telegram_user_id] = next_state
        print(f"[process_nutrition] state -> {next_state}, phase_mode={phase_mode}, use_rag={use_rag}")

        # Сохраняем контекст для фазового продолжения
        if phase_mode in ("seasonal_phase", "single_phase"):
            effective_phase_key = phase_key
            if not effective_phase_key and answer_text:
                effective_phase_key = detect_phase_from_response(answer_text)

            if effective_phase_key:
                existing_ctx = CONSULTATION_CONTEXT.get(telegram_user_id, {})
                if not existing_ctx.get("_phase_continuation"):
                    next_phase = get_next_phase(effective_phase_key)
                    CONSULTATION_CONTEXT[telegram_user_id] = {
                        **existing_ctx,
                        "_phase_continuation": True,
                        "current_phase": effective_phase_key,
                        "next_phase": next_phase,
                        "phases_delivered": [effective_phase_key],
                        "topic": category,
                        "question_text": root_question,
                        "internal_user_id": user_id,
                        "category": category,
                        "culture": culture,
                        "classification_cost": classification_cost_usd,
                        "classification_tokens": classification_tokens,
                        "complexity_result": complexity_result,
                        "telegram_user_id": telegram_user_id,
                    }
                else:
                    # Обновляем текущую фазу и delivered для последующих фаз
                    ctx = CONSULTATION_CONTEXT[telegram_user_id]
                    ctx["current_phase"] = effective_phase_key
                    ctx["next_phase"] = get_next_phase(effective_phase_key)
                    if effective_phase_key not in ctx.get("phases_delivered", []):
                        ctx.setdefault("phases_delivered", []).append(effective_phase_key)

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

    # Инициализируем стоимость классификации
    classification_cost_usd = 0.0
    classification_tokens = 0

    # Если это первое сообщение в топике - переопределяем культуру
    # Даже если культура есть (это означает, что топик был создан заново после закрытия старого)
    if is_first_message:
        print(f"[nutrition] Это первое сообщение (count_before={message_count_before}), переопределяем культуру (было: {culture!r})")
        detected_culture, class_cost, class_tokens = await detect_culture_name(root_question)
        classification_cost_usd += class_cost
        classification_tokens += class_tokens
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
        "classification_cost_usd": classification_cost_usd,
        "classification_tokens": classification_tokens,
    }

    # Вызываем LLM для получения ответа
    # (Больше не уточняем тип культуры — классификатор сразу определяет "летняя" или "ремонтантная")
    base_category = "питание растений"

    # Определяем, нужен ли RAG
    # Если культура конкретная (не "общая информация" и не "не определено") - используем RAG сразу
    # Если культура неопределённая - сначала без RAG (для уточняющих вопросов)
    use_rag = culture not in ("общая информация", "не определено", None)

    # Показываем сообщение ожидания с динамическими обновлениями
    status_mgr = StatusMessageManager(message, use_rag=use_rag)
    await status_mgr.start()

    try:
        # Формируем красивый вопрос для RAG ТОЛЬКО если RAG используется
        # (не тратим токены на compose когда будем задавать уточняющие вопросы)
        if use_rag:
            composed_q, compose_cost, compose_tokens = await compose_full_question(root_question, [])
        else:
            composed_q = root_question
            compose_cost = 0.0
            compose_tokens = 0

        answer_text = await ask_consultation_llm(
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            text=root_question,
            session_id=session_id,
            topic_id=topic_id,
            consultation_category=base_category,
            culture=culture,
            default_location="средняя полоса",
            default_growing_type="открытый грунт",
            skip_rag=not use_rag,  # Используем RAG только если культура определена
            composed_question=composed_q if use_rag else None,
            compose_cost_usd=compose_cost,
            compose_tokens=compose_tokens,
            classification_cost_usd=classification_cost_usd,
            classification_tokens=classification_tokens,
            status_updater=status_mgr.update,
            stream=use_rag,
            streaming_transition=status_mgr.start_streaming if use_rag else None,
        )
    finally:
        streaming_msg = status_mgr.get_streaming_message() if use_rag else None
        await status_mgr.complete()

    # Проверяем, является ли ответ уточняющим вопросом (только если RAG не использовался)
    if not use_rag:
        is_clarification = is_clarification_question(answer_text)
    else:
        # Если использовался RAG - это финальный ответ
        is_clarification = False

    # Отправляем ответ (с кнопками только если это финальный ответ)
    if is_clarification:
        answer_text = markdown_to_telegram_html(answer_text)
        await message.answer(answer_text)
        # Переводим в состояние ожидания ответа на уточняющий вопрос
        CONSULTATION_STATE[user.id] = "waiting_nutrition_clarification"
        print(f"[nutrition] STEP1 done, LLM asking for clarification, state -> waiting_nutrition_clarification")
    else:
        await finalize_streaming_message(
            streaming_msg, message, answer_text,
            keyboard=get_followup_keyboard(category),
            show_followup_prompt=True,
        )

        # Сохраняем полный вопрос в контекст для кнопок
        CONSULTATION_CONTEXT[user.id]["full_question"] = root_question

        # Переводим в режим ожидания follow-up (контекст сохраняем для кнопок)
        CONSULTATION_STATE[user.id] = "waiting_followup"
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

    # Получаем накопленную стоимость классификации из контекста
    classification_cost_usd: float = ctx.get("classification_cost_usd", 0.0)
    classification_tokens: int = ctx.get("classification_tokens", 0)

    # Переопределяем культуру на основе ответа
    combined_text = root_question + "\n" + clarification_answer
    culture, class_cost, class_tokens = await detect_culture_name(combined_text)
    classification_cost_usd += class_cost
    classification_tokens += class_tokens
    print(f"[nutrition] STEP1.5 re-classified culture: {ctx.get('culture')!r} -> {culture!r}")

    # Обновляем культуру в БД и контексте
    await set_topic_culture(topic_id, culture)
    ctx["culture"] = culture
    ctx["classification_cost_usd"] = classification_cost_usd
    ctx["classification_tokens"] = classification_tokens
    CONSULTATION_CONTEXT[user.id] = ctx

    # Вызываем LLM для финального ответа с RAG
    # (Больше не уточняем тип культуры — классификатор сразу определяет "летняя" или "ремонтантная")
    base_category = ctx.get("category", "питание растений")
    combined_question = root_question + "\n\n" + clarification_answer

    # Показываем сообщение ожидания с динамическими обновлениями
    status_mgr = StatusMessageManager(message)
    await status_mgr.start()

    # Формируем красивый вопрос для RAG
    composed_q, compose_cost, compose_tokens = await compose_full_question(combined_question, [])

    try:
        answer_text = await ask_consultation_llm(
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            text=combined_question,
            session_id=session_id,
            topic_id=topic_id,
            consultation_category=base_category,
            culture=culture,
            default_location="средняя полоса",
            default_growing_type="открытый грунт",
            skip_rag=False,  # Теперь используем RAG для финального ответа
            composed_question=composed_q,
            compose_cost_usd=compose_cost,
            compose_tokens=compose_tokens,
            classification_cost_usd=classification_cost_usd,
            classification_tokens=classification_tokens,
            status_updater=status_mgr.update,
            stream=True,
            streaming_transition=status_mgr.start_streaming,
        )
    except Exception as e:
        print(f"[nutrition] ERROR in ask_consultation_llm: {e}")
        await status_mgr.complete()
        llm_err = "Произошла ошибка при обращении к модели. Попробуйте отправить вопрос ещё раз."
        await message.answer(llm_err)
        if message.from_user:
            await _log_bot_msg(llm_err, telegram_user_id=message.from_user.id)
        return

    streaming_msg = status_mgr.get_streaming_message()
    await status_mgr.complete()

    # Отправляем ответ
    await finalize_streaming_message(
        streaming_msg, message, answer_text,
        keyboard=get_followup_keyboard(base_category),
        show_followup_prompt=True,
    )

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


    # Сохраняем полный вопрос в контекст для кнопок
    ctx["full_question"] = combined_question
    CONSULTATION_CONTEXT[user.id] = ctx

    # Переводим в режим ожидания follow-up (контекст сохраняем для кнопок)
    CONSULTATION_STATE[user.id] = "waiting_followup"
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

    # Получаем накопленную стоимость классификации из контекста
    classification_cost_usd: float = ctx.get("classification_cost_usd", 0.0)
    classification_tokens: int = ctx.get("classification_tokens", 0)

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
            culture, class_cost, class_tokens = await detect_culture_name(f"клубника {variety_answer}")
            classification_cost_usd += class_cost
            classification_tokens += class_tokens
            if culture == "общая информация" or culture == "не определено":
                culture = old_culture  # Оставляем как есть
    elif old_culture == "малина общая":
        if "ремонтант" in variety_answer_lower or "нсд" in variety_answer_lower or "nsd" in variety_answer_lower:
            culture = "малина ремонтантная"
        elif "летн" in variety_answer_lower or "обычн" in variety_answer_lower or "традицион" in variety_answer_lower:
            culture = "малина летняя"
        else:
            # Если не смогли определить - пробуем через классификатор с контекстом
            culture, class_cost, class_tokens = await detect_culture_name(f"малина {variety_answer}")
            classification_cost_usd += class_cost
            classification_tokens += class_tokens
            if culture == "общая информация" or culture == "не определено":
                culture = old_culture  # Оставляем как есть
    else:
        # Если это не клубника/малина общая - используем классификатор
        culture, class_cost, class_tokens = await detect_culture_name(root_question + "\n" + variety_answer)
        classification_cost_usd += class_cost
        classification_tokens += class_tokens

    print(f"[nutrition] STEP2 (variety) re-classified culture: {old_culture!r} -> {culture!r}")

    # Обновляем культуру в БД и контексте
    await set_topic_culture(topic_id, culture)
    ctx["culture"] = culture
    ctx["variety_answer"] = variety_answer
    ctx["classification_cost_usd"] = classification_cost_usd
    ctx["classification_tokens"] = classification_tokens
    CONSULTATION_CONTEXT[user.id] = ctx

    # Вызываем LLM с уточненной культурой для финального ответа
    base_category = ctx.get("category", "питание растений")

    # Формируем читабельный вопрос через LLM
    clarifications = [{"user": f"Тип культуры: {variety_answer}"}]
    composed_q, compose_cost, compose_tokens = await compose_full_question(root_question, clarifications)
    if compose_cost > 0:
        print(f"[nutrition] compose_full_question cost: ${compose_cost:.6f}")

    # Показываем сообщение ожидания с динамическими обновлениями
    status_mgr = StatusMessageManager(message)
    await status_mgr.start()

    try:
        answer_text = await ask_consultation_llm(
            user_id=user_id,
            telegram_user_id=ctx.get("telegram_user_id", user.id),
            text=composed_q,  # Используем сформированный вопрос
            session_id=session_id,
            topic_id=topic_id,
            consultation_category=base_category,
            culture=culture,
            default_location="средняя полоса",
            default_growing_type="открытый грунт",
            skip_rag=False,  # Используем RAG для финального ответа
            composed_question=composed_q,
            compose_cost_usd=compose_cost,
            compose_tokens=compose_tokens,
            classification_cost_usd=classification_cost_usd,
            classification_tokens=classification_tokens,
            status_updater=status_mgr.update,
            stream=True,
            streaming_transition=status_mgr.start_streaming,
        )
    except Exception as e:
        print(f"[nutrition] ERROR in ask_consultation_llm: {e}")
        await status_mgr.complete()
        llm_err = "Произошла ошибка при обращении к модели. Попробуйте отправить вопрос ещё раз."
        await message.answer(llm_err)
        if message.from_user:
            await _log_bot_msg(llm_err, telegram_user_id=message.from_user.id)
        return

    streaming_msg = status_mgr.get_streaming_message()
    await status_mgr.complete()

    # Отправляем ответ
    await finalize_streaming_message(
        streaming_msg, message, answer_text,
        keyboard=get_followup_keyboard(base_category),
        show_followup_prompt=True,
    )

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
            question=composed_q,
            answer=answer_text,
            category_guess=category_guess,
        )


    # Сохраняем полный вопрос в контекст для кнопок
    ctx["full_question"] = composed_q
    CONSULTATION_CONTEXT[user.id] = ctx

    # Переводим в режим ожидания follow-up (контекст сохраняем для кнопок)
    CONSULTATION_STATE[user.id] = "waiting_followup"
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

    # Просим задать вопрос с инлайн-кнопками примеров
    kb = get_example_questions_keyboard()
    await message.answer(CONSULTATION_ENTRY_TEXT, reply_markup=kb)
    if user:
        await _log_bot_msg(CONSULTATION_ENTRY_TEXT, telegram_user_id=user.id, meta=serialize_keyboard(kb))


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
        ctx_lost = "Контекст консультации утерян. Пожалуйста, задайте новый вопрос."
        await message.answer(ctx_lost)
        await _log_bot_msg(ctx_lost, telegram_user_id=user.id)
        return

    # Устанавливаем состояние ожидания новых параметров
    CONSULTATION_STATE[user.id] = "waiting_param_replacement"

    params_prompt = (
        "Укажите ваши параметры:\n"
        "Например: 'Теплица, Урал' или 'Южный регион, открытый грунт'\n\n"
        "Или задайте вопрос заново с другими условиями."
    )
    await message.answer(params_prompt)
    await _log_bot_msg(params_prompt, telegram_user_id=user.id)


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
        ctx_lost2 = "Контекст консультации утерян"
        await message.answer(ctx_lost2)
        await _log_bot_msg(ctx_lost2, telegram_user_id=user.id)
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

    # Показываем сообщение ожидания с динамическими обновлениями
    status_mgr = StatusMessageManager(message)
    await status_mgr.start("⏳ Подождите, формирую ответ с новыми параметрами...")

    # Формируем красивый вопрос для RAG (даже без уточнений)
    composed_q, compose_cost, compose_tokens = await compose_full_question(root_question, [])

    try:
        answer_text = await ask_consultation_llm(
            user_id=user_id,
            telegram_user_id=user.id,
            text=root_question,
            session_id=session_id,
            topic_id=ctx.get("topic_id"),
            consultation_category=category,
            culture=culture,
            default_location=location,
            default_growing_type=growing_type,
            composed_question=composed_q,
            compose_cost_usd=compose_cost,
            compose_tokens=compose_tokens,
            status_updater=status_mgr.update,
            stream=True,
            streaming_transition=status_mgr.start_streaming,
        )
    except Exception as e:
        print(f"[nutrition] ERROR in ask_consultation_llm: {e}")
        await status_mgr.complete()
        llm_err = "Произошла ошибка при обращении к модели. Попробуйте отправить вопрос ещё раз."
        await message.answer(llm_err)
        if message.from_user:
            await _log_bot_msg(llm_err, telegram_user_id=message.from_user.id)
        return

    streaming_msg = status_mgr.get_streaming_message()
    await status_mgr.complete()

    # Отправляем ответ
    await finalize_streaming_message(streaming_msg, message, answer_text)

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
        ctx_lost3 = "Контекст консультации утерян. Пожалуйста, задайте новый вопрос."
        await message.answer(ctx_lost3)
        await _log_bot_msg(ctx_lost3, telegram_user_id=user.id)
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

    # Показываем сообщение ожидания с динамическими обновлениями
    status_mgr = StatusMessageManager(message)
    await status_mgr.start("⏳ Формирую детальный план...")

    # Формируем красивый вопрос для RAG
    composed_q, compose_cost, compose_tokens = await compose_full_question(detailed_plan_request, [])

    try:
        detailed_plan = await ask_consultation_llm(
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            text=detailed_plan_request,
            session_id=session_id,
            topic_id=topic_id,
            consultation_category=category,
            culture=culture,
            default_location="средняя полоса",
            default_growing_type="открытый грунт",
            composed_question=composed_q,
            compose_cost_usd=compose_cost,
            compose_tokens=compose_tokens,
            status_updater=status_mgr.update,
            stream=True,
            streaming_transition=status_mgr.start_streaming,
        )
    except Exception as e:
        print(f"[nutrition] ERROR in ask_consultation_llm (detailed plan): {e}")
        await status_mgr.complete()
        llm_err = "Произошла ошибка при обращении к модели. Попробуйте отправить вопрос ещё раз."
        await message.answer(llm_err)
        if message.from_user:
            await _log_bot_msg(llm_err, telegram_user_id=message.from_user.id)
        return

    streaming_msg = status_mgr.get_streaming_message()
    await status_mgr.complete()

    # Enforcement: детальный план — расширенный формат (2 сообщения)
    from src.handlers.consultation.entry import _enforce_two_message_format
    detailed_plan = _enforce_two_message_format(detailed_plan)

    # Отправляем детальный план
    await finalize_streaming_message(
        streaming_msg, message, detailed_plan,
        keyboard=get_followup_keyboard(category),
        show_followup_prompt=True,
        force_two_parts=True,
    )

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
