# src/handlers/consultation/entry.py

"""
Хендлер для обработки обычных текстовых сообщений (кроме команд).

Задачи:
    - перехватить ввод категории от админа (когда он меняет категорию кандидата)
    - для всех остальных текстов:
        * найти/создать пользователя
        * найти/создать открытую тему (topic)
        * проверить наличие культуры в теме
        * если это первое сообщение и культура не определена - попросить выбрать культуру
        * залогировать сообщение
        * вызвать LLM (ask_consultation_llm)
        * отправить ответ
        * залогировать ответ
        * добавить пару вопрос-ответ в очередь модерации
"""

from aiogram import Router, F
from aiogram.types import Message

# Репозитории БД
from src.services.db.users_repo import get_or_create_user
from src.services.db.topics_repo import (
    get_or_create_open_topic,
    get_topic_culture,
)
from src.services.db.messages_repo import log_message
from src.services.db.moderation_repo import moderation_add
from src.services.db.tokens_repo import has_sufficient_tokens, deduct_tokens, get_token_balance

# Прайсы токенов
from src.pricing import COST_NEW_TOPIC, COST_ADDITIONAL_QUESTIONS

# LLM
from src.services.llm.consultation_llm import ask_consultation_llm
from src.services.llm.classification_llm import detect_culture_name

# Keyboards
from src.keyboards.consultation.common import get_nutrition_followup_keyboard

# Утилита для session_id и управление состоянием
from src.handlers.common import (
    build_session_id_from_message,
    CONSULTATION_STATE,
    CONSULTATION_CONTEXT,
)


router = Router()


# Константа: максимальная длина сообщения в Telegram
TELEGRAM_MAX_MESSAGE_LENGTH = 4096


def split_long_message(text: str, max_length: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> list[str]:
    """
    Разбивает длинное сообщение на части, не превышающие max_length.

    Старается разбивать по абзацам, чтобы не разрывать смысловые блоки.

    Args:
        text: Исходный текст
        max_length: Максимальная длина одной части (по умолчанию 4096)

    Returns:
        Список частей сообщения
    """
    if len(text) <= max_length:
        return [text]

    parts = []
    current_part = ""

    # Разбиваем по абзацам
    paragraphs = text.split("\n\n")

    for para in paragraphs:
        # Если добавление этого абзаца превысит лимит
        if len(current_part) + len(para) + 2 > max_length:  # +2 для "\n\n"
            if current_part:
                parts.append(current_part.strip())
                current_part = ""

            # Если сам абзац слишком длинный, разбиваем по строкам
            if len(para) > max_length:
                lines = para.split("\n")
                for line in lines:
                    if len(current_part) + len(line) + 1 > max_length:  # +1 для "\n"
                        if current_part:
                            parts.append(current_part.strip())
                        current_part = line + "\n"
                    else:
                        current_part += line + "\n"
            else:
                current_part = para + "\n\n"
        else:
            current_part += para + "\n\n"

    # Добавляем последнюю часть
    if current_part:
        parts.append(current_part.strip())

    return parts


async def send_long_message(message: Message, text: str) -> None:
    """
    Отправляет сообщение, автоматически разбивая на части если оно слишком длинное.

    Args:
        message: Сообщение от пользователя (для ответа)
        text: Текст для отправки
    """
    parts = split_long_message(text)

    if len(parts) > 1:
        print(f"[send_long_message] Сообщение разбито на {len(parts)} частей")

    for i, part in enumerate(parts, 1):
        if len(parts) > 1:
            # Добавляем номер части, если сообщение разбито
            part_text = f"[Часть {i}/{len(parts)}]\n\n{part}"
        else:
            part_text = part

        await message.answer(part_text)


async def send_followup_count_message(message: Message, questions_left: int, topic_id: int) -> None:
    """
    Отправляет информационное сообщение о количестве оставшихся уточняющих вопросов.

    Args:
        message: Сообщение от пользователя
        questions_left: Количество оставшихся вопросов (0-3)
        topic_id: ID топика
    """
    if questions_left > 0:
        # Склонение слова "вопрос"
        if questions_left == 1:
            word = "уточняющий вопрос"
        elif questions_left in (2, 3, 4):
            word = "уточняющих вопроса"
        else:
            word = "уточняющих вопросов"

        text = f"Вы можете задать {questions_left} {word} на эту тему."
        # Показываем клавиатуру с кнопками для дополнительных действий
        from src.keyboards.consultation.common import get_nutrition_followup_keyboard
        await message.answer(text, reply_markup=get_nutrition_followup_keyboard())
    else:
        # Показываем кнопку для получения дополнительных вопросов
        from src.keyboards.consultation.common import get_more_questions_keyboard
        text = "Уточняющие вопросы по этой теме исчерпаны."
        await message.answer(text, reply_markup=get_more_questions_keyboard())

    print(f"[followup_count] Sent: questions_left={questions_left}, topic_id={topic_id}")


async def get_message_context(topic_id: int, limit: int = 3) -> str:
    """Получает последние N сообщений для контекста классификации."""
    from src.services.db.messages_repo import get_recent_messages
    try:
        messages = await get_recent_messages(topic_id, limit)
        return "\n".join([f"{m['direction']}: {m['text'][:100]}" for m in messages])
    except Exception as e:
        print(f"[get_message_context][ERROR] {e}")
        return ""


def is_clarification_question(text: str) -> bool:
    """
    Определяет, является ли ответ LLM уточняющим вопросом.

    Признаки уточняющего вопроса:
    - Короткий ответ (< 300 символов)
    - Содержит типичные фразы или вопросительный знак
    """
    return (
        len(text) < 300 and
        (
            "уточните" in text.lower()
            or "о какой культуре" in text.lower()
            or "какая у вас" in text.lower()
            or "?" in text
        )
    )


# ==== НОВЫЙ УНИФИЦИРОВАННЫЙ ОБРАБОТЧИК: Автоопределение категории + культуры ====

@router.message(
    lambda m: m.from_user is not None
    and CONSULTATION_STATE.get(m.from_user.id) == "waiting_consultation_question"
)
async def handle_consultation_question_unified(message: Message) -> None:
    """
    Единая точка входа для обработки вопроса консультации.
    Автоматически определяет категорию + культуру и маршрутизирует в соответствующий обработчик.

    После нажатия кнопки "Консультация" пользователь сразу пишет вопрос.
    Бот определяет ОБЕ вещи:
    - КАТЕГОРИЮ (питание растений, посадка и уход, etc.)
    - КУЛЬТУРУ (клубника летняя, малина общая, etc.)

    Затем маршрутизирует в:
    - Специализированный обработчик для "питание растений" (с кнопками follow-up)
    - Общий обработчик для всех остальных категорий
    """
    user = message.from_user
    if user is None or not message.text:
        return

    question_text = message.text.strip()
    telegram_user_id = user.id

    print(f"[unified_entry] Получен вопрос от user {telegram_user_id}: {question_text!r}")

    # Получаем внутренний user_id
    internal_user_id = await get_or_create_user(
        telegram_user_id=telegram_user_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    # Проверяем баланс токенов
    if not await has_sufficient_tokens(internal_user_id, COST_NEW_TOPIC):
        balance = await get_token_balance(internal_user_id)
        await message.answer(
            f"У вас недостаточно токенов для консультации.\n\n"
            f"Стоимость: {COST_NEW_TOPIC} токен\n"
            f"Ваш баланс: {balance} токенов\n\n"
            f"Для пополнения обратитесь к администратору."
        )
        # Сбрасываем состояние ожидания
        CONSULTATION_STATE.pop(telegram_user_id, None)
        return

    # Автоматически определяем категорию + культуру
    from src.services.llm.classification_llm import detect_category_and_culture
    category, culture = await detect_category_and_culture(question_text)

    print(f"[unified_entry] Detected category={category!r}, culture={culture!r}")

    # Списываем токен за консультацию
    await deduct_tokens(
        internal_user_id,
        COST_NEW_TOPIC,
        "new_topic",
        f"Консультация: {category}"
    )

    # Маршрутизация на основе категории
    if category == "питание растений":
        # Специализированный обработчик для питания (с кнопками follow-up)
        print(f"[unified_entry] Routing to NUTRITION handler")

        from src.handlers.consultation.pitanie_rastenii import process_nutrition_consultation
        await process_nutrition_consultation(
            message=message,
            user_id=internal_user_id,
            category=category,
            culture=culture,
            root_question=question_text,
        )
    else:
        # Общий обработчик для остальных категорий
        print(f"[unified_entry] Routing to GENERAL handler")

        await process_general_consultation(
            message=message,
            user_id=internal_user_id,
            category=category,
            culture=culture,
            root_question=question_text,
        )


async def process_general_consultation(
    message: Message,
    user_id: int,
    category: str,
    culture: str,
    root_question: str,
) -> None:
    """
    Обрабатывает общую консультацию (не питание растений).
    Извлечено из старого handle_consultation_root для переиспользования.

    Логика:
    - CASE 1: Культура неясна → уточняющие вопросы БЕЗ RAG
    - CASE 2: Культура общая (клубника/малина общая) → запрос типа (летняя/ремонтантная)
    - CASE 3: Культура конкретна → финальный ответ С RAG
    """
    user = message.from_user
    if user is None:
        return

    telegram_user_id = user.id
    session_id = build_session_id_from_message(message)

    # Создаем или получаем топик
    topic_id = await get_or_create_open_topic(
        user_id=user_id,
        session_id=session_id,
    )

    # Обновляем культуру в БД
    from src.services.db.topics_repo import set_topic_culture
    await set_topic_culture(topic_id, culture)

    # Логируем вопрос пользователя
    await log_message(
        user_id=user_id,
        direction="user",
        text=root_question,
        session_id=session_id,
        topic_id=topic_id,
    )

    print(f"[process_general] category={category!r}, culture={culture!r}")

    # CASE 1: Культура неясна → уточняющие вопросы БЕЗ RAG
    if culture in ("не определено", "общая информация"):
        print(f"[process_general] CASE 1: Vague culture - asking clarification WITHOUT RAG")

        status_message = await message.answer("⏳ Подождите, рекомендация формируется...")

        try:
            reply_text: str = await ask_consultation_llm(
                user_id=user_id,
                telegram_user_id=telegram_user_id,
                text=root_question,
                session_id=session_id,
                consultation_category=category,
                culture=culture,
                skip_rag=True,  # БЕЗ RAG для уточняющих вопросов!
            )
        except Exception as e:
            print(f"ERROR in ask_consultation_llm: {e}")
            reply_text = (
                "Сейчас не получается обработать запрос через модель. "
                "Попробуйте ещё раз чуть позже."
            )
        finally:
            try:
                await status_message.delete()
            except Exception:
                pass

        # Отправляем ответ (уточняющий вопрос или финальный ответ)
        await send_long_message(message, reply_text)

        # Если LLM задал уточняющий вопрос - переводим в состояние ожидания ответа
        if is_clarification_question(reply_text):
            print(f"[process_general] LLM asked clarification question, setting state")
            CONSULTATION_STATE[telegram_user_id] = "waiting_clarification_answer"
            CONSULTATION_CONTEXT[telegram_user_id] = {
                "category": category,
                "root_question": root_question,
                "culture": culture,
                "user_id": user_id,
                "topic_id": topic_id,
                "session_id": session_id,
                "telegram_user_id": telegram_user_id,
            }

            # Логируем только ответ бота (уточняющий вопрос)
            await log_message(
                user_id=user_id,
                direction="bot",
                text=reply_text,
                session_id=session_id,
                topic_id=topic_id,
            )

            # НЕ добавляем в moderation для уточняющих вопросов
            # Очищаем состояние ожидания вопроса
            CONSULTATION_STATE[telegram_user_id] = "waiting_clarification_answer"
            return

        # Если это был финальный ответ (не уточняющий вопрос) - продолжаем логирование ниже

    # CASE 2: Культура общая (клубника общая / малина общая) → запрос типа
    elif culture in ("клубника общая", "малина общая"):
        print(f"[process_general] CASE 2: General culture - asking variety")

        if culture == "клубника общая":
            variety_question = "Какая у вас клубника: летняя (июньская) или ремонтантная (НСД)?"
        else:  # малина общая
            variety_question = "Какая у вас малина: летняя (обычная) или ремонтантная?"

        # Сохраняем контекст и переводим в состояние ожидания ответа
        CONSULTATION_STATE[telegram_user_id] = "waiting_variety_clarification"
        CONSULTATION_CONTEXT[telegram_user_id] = {
            "category": category,
            "root_question": root_question,
            "culture": culture,
            "user_id": user_id,
            "topic_id": topic_id,
            "session_id": session_id,
            "telegram_user_id": telegram_user_id,
        }

        await message.answer(variety_question)
        return  # Не логируем ответ бота здесь, т.к. это системный вопрос

    # CASE 3: Культура конкретна → финальный ответ С RAG
    else:
        print(f"[process_general] CASE 3: Specific culture - final answer WITH RAG")

        status_message = await message.answer("⏳ Подождите, рекомендация формируется...")

        try:
            reply_text: str = await ask_consultation_llm(
                user_id=user_id,
                telegram_user_id=telegram_user_id,
                text=root_question,
                session_id=session_id,
                consultation_category=category,
                culture=culture,
                skip_rag=False,  # С RAG для финального ответа!
            )
        except Exception as e:
            print(f"ERROR in ask_consultation_llm: {e}")
            reply_text = (
                "Сейчас не получается обработать запрос через модель. "
                "Попробуйте ещё раз чуть позже."
            )
        finally:
            try:
                await status_message.delete()
            except Exception:
                pass

        # ВАЖНО: В CASE 3 (конкретная культура) НЕ проверяем на уточняющий вопрос!
        # Культура уже определена, поэтому отправляем ответ как финальный
        # Добавляем follow-up кнопки (новый вопрос, заменить параметры, детальный план)
        await message.answer(reply_text, reply_markup=get_nutrition_followup_keyboard())

    # Логируем ответ бота
    await log_message(
        user_id=user_id,
        direction="bot",
        text=reply_text,
        session_id=session_id,
        topic_id=topic_id,
    )

    # Кандидат в базу знаний (очередь модерации)
    try:
        await moderation_add(
            user_id=user_id,
            topic_id=topic_id,
            question=root_question,
            answer=reply_text,
            category_guess=category if category != "не определена" else None,
        )
    except Exception as e:
        print(f"ERROR in moderation_add: {e}")

    # Очищаем состояние
    CONSULTATION_STATE.pop(telegram_user_id, None)
    CONSULTATION_CONTEXT.pop(telegram_user_id, None)


# ==== ОБРАБОТЧИК 1: Ответ на вопрос о типе культуры (летняя/ремонтантная) ====

@router.message(
    lambda m: m.from_user is not None
    and CONSULTATION_STATE.get(m.from_user.id) == "waiting_variety_clarification"
)
async def handle_variety_clarification(message: Message) -> None:
    """
    Обрабатывает ответ пользователя на вопрос о типе культуры.

    Пользователь ответил на вопрос "Какая у вас клубника/малина: летняя или ремонтантная?"
    Переопределяем культуру и даём финальный ответ С RAG.
    """
    user = message.from_user
    if user is None:
        return

    telegram_user_id = user.id
    variety_answer = (message.text or "").lower()

    print(f"[VARIETY_CLARIFICATION] user_id={telegram_user_id}, answer={variety_answer!r}")

    # Получаем сохранённый контекст
    context = CONSULTATION_CONTEXT.get(telegram_user_id, {})
    if not context:
        print(f"[VARIETY_CLARIFICATION] WARNING: No context found for user {telegram_user_id}")
        await message.answer("Произошла ошибка. Попробуйте задать вопрос заново.")
        return

    user_id = context["user_id"]
    topic_id = context["topic_id"]
    session_id = context["session_id"]
    root_question = context["root_question"]
    old_culture = context["culture"]

    # Определяем новую культуру на основе ответа
    if "ремонтант" in variety_answer or "нсд" in variety_answer:
        if old_culture == "клубника общая":
            new_culture = "клубника ремонтантная"
        else:  # малина общая
            new_culture = "малина ремонтантная"
    elif "летн" in variety_answer or "обычн" in variety_answer or "традицион" in variety_answer or "июньск" in variety_answer:
        if old_culture == "клубника общая":
            new_culture = "клубника летняя"
        else:  # малина общая
            new_culture = "малина летняя"
    else:
        # Не удалось распознать - пробуем классификатор
        combined_text = f"{root_question} {variety_answer}"
        new_culture = await detect_culture_name(combined_text)
        print(f"[VARIETY_CLARIFICATION] Failed to parse answer, re-classified: {new_culture!r}")

    print(f"[VARIETY_CLARIFICATION] Refined culture: {old_culture!r} -> {new_culture!r}")

    # Обновляем культуру в БД
    from src.services.db.topics_repo import set_topic_culture
    await set_topic_culture(topic_id, new_culture)

    # Логируем ответ пользователя
    await log_message(
        user_id=user_id,
        direction="user",
        text=variety_answer,
        session_id=session_id,
        topic_id=topic_id,
    )

    # Формируем полный вопрос (корневой + ответ)
    full_question = f"{root_question} ({variety_answer})"

    # Показываем статус ожидания
    status_message = await message.answer("⏳ Подождите, рекомендация формируется...")

    # Вызываем LLM с финальным ответом и RAG
    try:
        reply_text = await ask_consultation_llm(
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            text=full_question,
            session_id=session_id,
            consultation_category="общая консультация",
            culture=new_culture,
            skip_rag=False,  # С RAG для финального ответа!
        )
    except Exception as e:
        print(f"ERROR in ask_consultation_llm: {e}")
        reply_text = (
            "Сейчас не получается обработать запрос через модель. "
            "Попробуйте ещё раз чуть позже."
        )
    finally:
        try:
            await status_message.delete()
        except Exception:
            pass

    # Отправляем ответ
    await send_long_message(message, reply_text)

    # Логируем ответ бота
    await log_message(
        user_id=user_id,
        direction="bot",
        text=reply_text,
        session_id=session_id,
        topic_id=topic_id,
    )

    # Добавляем в очередь модерации
    try:
        await moderation_add(
            user_id=user_id,
            topic_id=topic_id,
            question=full_question,
            answer=reply_text,
            category_guess=None,
        )
    except Exception as e:
        print(f"ERROR in moderation_add: {e}")

    # Очищаем состояние
    CONSULTATION_STATE.pop(telegram_user_id, None)
    CONSULTATION_CONTEXT.pop(telegram_user_id, None)


# ==== ОБРАБОТЧИК 2: Ответ на уточняющие вопросы LLM ====

@router.message(
    lambda m: m.from_user is not None
    and CONSULTATION_STATE.get(m.from_user.id) == "waiting_clarification_answer"
)
async def handle_clarification_answer(message: Message) -> None:
    """
    Обрабатывает ответ пользователя на уточняющие вопросы LLM.

    LLM спросил "О какой культуре речь?" и пользователь ответил.
    Переопределяем культуру и решаем, что делать дальше.
    """
    user = message.from_user
    if user is None:
        return

    telegram_user_id = user.id
    clarification_answer = message.text or ""

    print(f"[CLARIFICATION_ANSWER] user_id={telegram_user_id}, answer={clarification_answer!r}")

    # Получаем сохранённый контекст
    context = CONSULTATION_CONTEXT.get(telegram_user_id, {})
    if not context:
        print(f"[CLARIFICATION_ANSWER] WARNING: No context found for user {telegram_user_id}")
        await message.answer("Произошла ошибка. Попробуйте задать вопрос заново.")
        return

    user_id = context["user_id"]
    topic_id = context["topic_id"]
    session_id = context["session_id"]
    root_question = context["root_question"]

    # Логируем ответ пользователя
    await log_message(
        user_id=user_id,
        direction="user",
        text=clarification_answer,
        session_id=session_id,
        topic_id=topic_id,
    )

    # Переопределяем культуру на основе комбинированного текста
    combined_text = f"{root_question} {clarification_answer}"
    new_culture = await detect_culture_name(combined_text)
    print(f"[CLARIFICATION_ANSWER] Re-classified culture: {new_culture!r}")

    # Обновляем культуру в БД
    from src.services.db.topics_repo import set_topic_culture
    await set_topic_culture(topic_id, new_culture)

    # Формируем полный вопрос
    full_question = f"{root_question} {clarification_answer}"

    # Проверяем новую культуру и действуем соответственно

    # Если культура всё ещё неясна - запрашиваем снова (но это редко)
    if new_culture in ("не определено", "общая информация"):
        print(f"[CLARIFICATION_ANSWER] Still vague, asking again")
        await message.answer("Уточните, пожалуйста, о какой конкретно культуре идёт речь?")
        # Оставляем состояние без изменений
        return

    # Если культура общая (клубника общая / малина общая) - спрашиваем тип
    elif new_culture in ("клубника общая", "малина общая"):
        print(f"[CLARIFICATION_ANSWER] General culture, asking variety")

        if new_culture == "клубника общая":
            variety_question = "Какая у вас клубника: летняя (июньская) или ремонтантная (НСД)?"
        else:  # малина общая
            variety_question = "Какая у вас малина: летняя (обычная) или ремонтантная?"

        # Обновляем контекст и состояние
        CONSULTATION_STATE[telegram_user_id] = "waiting_variety_clarification"
        CONSULTATION_CONTEXT[telegram_user_id]["culture"] = new_culture
        CONSULTATION_CONTEXT[telegram_user_id]["root_question"] = full_question

        await message.answer(variety_question)
        return

    # Культура конкретна - даём финальный ответ с RAG
    else:
        print(f"[CLARIFICATION_ANSWER] Specific culture, final answer WITH RAG")

        status_message = await message.answer("⏳ Подождите, рекомендация формируется...")

        try:
            reply_text = await ask_consultation_llm(
                user_id=user_id,
                telegram_user_id=telegram_user_id,
                text=full_question,
                session_id=session_id,
                consultation_category="общая консультация",
                culture=new_culture,
                skip_rag=False,  # С RAG для финального ответа!
            )
        except Exception as e:
            print(f"ERROR in ask_consultation_llm: {e}")
            reply_text = (
                "Сейчас не получается обработать запрос через модель. "
                "Попробуйте ещё раз чуть позже."
            )
        finally:
            try:
                await status_message.delete()
            except Exception:
                pass

        # Отправляем ответ
        await send_long_message(message, reply_text)

        # Логируем ответ бота
        await log_message(
            user_id=user_id,
            direction="bot",
            text=reply_text,
            session_id=session_id,
            topic_id=topic_id,
        )

        # Добавляем в очередь модерации
        try:
            await moderation_add(
                user_id=user_id,
                topic_id=topic_id,
                question=full_question,
                answer=reply_text,
                category_guess=None,
            )
        except Exception as e:
            print(f"ERROR in moderation_add: {e}")

        # Очищаем состояние
        CONSULTATION_STATE.pop(telegram_user_id, None)
        CONSULTATION_CONTEXT.pop(telegram_user_id, None)


# ==== ОБРАБОТЧИК 3: Корневой обработчик (без активного состояния) ====

@router.message(F.text & ~F.text.startswith("/"))
async def handle_consultation_root(message: Message) -> None:
    """
    Обработка текстовых сообщений без активного состояния.
    Это начальная точка входа для консультаций.

    Логика:
    1. Определяем культуру
    2. CASE 1: Культура неясна (не определено / общая информация) → уточняющие вопросы БЕЗ RAG
    3. CASE 2: Культура общая (клубника общая / малина общая) → запрос типа (летняя/ремонтантная)
    4. CASE 3: Культура конкретна → финальный ответ С RAG
    """

    print("DEBUG: handle_consultation_root получил сообщение:", message.text)

    user = message.from_user
    session_id = build_session_id_from_message(message)

    if user is not None:
        telegram_user_id = user.id
        username = user.username
        first_name = user.first_name
        last_name = user.last_name
    else:
        telegram_user_id = 0
        username = None
        first_name = None
        last_name = None

    # Пользователь
    user_id = await get_or_create_user(
        telegram_user_id=telegram_user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
    )

    # Тема
    topic_id = await get_or_create_open_topic(
        user_id=user_id,
        session_id=session_id,
    )

    user_text: str = message.text or ""

    # КРИТИЧНО: Проверяем статус, message_count и culture ДО логирования сообщения!
    from src.services.db.topics_repo import (
        get_topic_message_count,
        get_topic_status,
        set_topic_culture,
        get_topic_category,
        set_topic_category,
        get_follow_up_questions_left,
        decrement_follow_up_questions,
        close_open_topics,
    )
    from src.services.llm.classification_llm import compare_topics_for_change, detect_category_and_culture

    message_count_before = await get_topic_message_count(topic_id)
    topic_status = await get_topic_status(topic_id)
    culture = await get_topic_culture(topic_id)
    saved_category = await get_topic_category(topic_id)
    questions_left = await get_follow_up_questions_left(topic_id)

    print(f"[entry] BEFORE: topic_id={topic_id}, msg_count={message_count_before}, status={topic_status}, culture={culture!r}, questions_left={questions_left}")

    # Определяем, является ли это потенциальным follow-up
    is_potential_followup = (
        topic_status == "open"
        and culture is not None
        and telegram_user_id not in CONSULTATION_STATE
        and message_count_before > 0
    )

    # Переменная для отслеживания смены темы
    topic_changed = False
    creating_message = None

    # Если это потенциальный follow-up - проверяем смену темы через LLM
    if is_potential_followup:
        print(f"[entry] Potential follow-up detected, checking topic change...")
        print(f"[entry] Saved category: {saved_category!r}, saved culture: {culture!r}")

        # ВАЖНО: Категория НЕ меняется для follow-up, используем сохраненную
        detected_category = saved_category or "общая консультация"

        # Получаем контекст предыдущих сообщений
        context_text = await get_message_context(topic_id, limit=3)

        # Классифицируем новый вопрос ТОЛЬКО для определения культуры
        new_category, new_culture = await detect_category_and_culture(user_text)
        print(f"[entry] New classification: category={new_category!r}, culture={new_culture!r}")
        print(f"[entry] BUT keeping saved category: {detected_category!r}")

        # Сравниваем ТОЛЬКО культуры (категория фиксирована)
        topic_change = await compare_topics_for_change(
            old_category=detected_category,  # Используем СОХРАНЕННУЮ категорию
            old_culture=culture,
            new_question=user_text,
            context_messages=context_text,
        )

        print(f"[entry] Culture change decision: {topic_change!r}")

        if topic_change == "clear_change":
            # ЯВНАЯ СМЕНА КУЛЬТУРЫ - создаем новый топик С ТОЙ ЖЕ КАТЕГОРИЕЙ
            print(f"[entry] CLEAR CULTURE CHANGE - creating new topic with same category")

            # Показываем сообщение о создании новой темы
            creating_message = await message.answer("📝 Создается новая тема консультации...")

            # Закрываем старый топик
            await close_open_topics(user_id)

            # Создаем новый топик (счётчик автоматически = 3)
            topic_id = await get_or_create_open_topic(
                user_id=user_id,
                session_id=session_id,
            )

            # Устанавливаем ТУ ЖЕ категорию и новую культуру
            await set_topic_category(topic_id, detected_category)  # СОХРАНЯЕМ категорию!
            await set_topic_culture(topic_id, new_culture)
            culture = new_culture
            topic_changed = True

            print(f"[entry] NEW topic created: topic_id={topic_id}, category={detected_category!r}, culture={culture!r}")

        elif topic_change == "same_topic":
            # ТА ЖЕ ТЕМА - уточняющий вопрос
            print(f"[entry] SAME TOPIC - follow-up question")
            # Используем сохраненную категорию из топика
            detected_category = saved_category or "общая консультация"

        else:  # unclear
            # НЕОПРЕДЕЛЕННО - остаемся на той же теме
            print(f"[entry] UNCLEAR - staying on same topic")
            # Используем сохраненную категорию из топика
            detected_category = saved_category or "общая консультация"
    else:
        # Это первый вопрос - переопределяем культуру И категорию
        print(f"[entry] First question or new consultation, detecting category and culture")
        detected_category, detected_culture = await detect_category_and_culture(user_text)

        # Сохраняем категорию в топике
        await set_topic_category(topic_id, detected_category)

        if detected_culture:
            await set_topic_culture(topic_id, detected_culture)
            culture = detected_culture
            print(f"[entry] Detected: category={detected_category!r}, culture={culture}")
        else:
            await set_topic_culture(topic_id, "не определено")
            culture = "не определено"
            print(f"[entry] Culture not detected, saved: {culture}")

    # Логируем сообщение пользователя
    await log_message(
        user_id=user_id,
        direction="user",
        text=user_text,
        session_id=session_id,
        topic_id=topic_id,
    )

    # ПОСЛЕ логирования: уменьшаем счётчик если это follow-up (НЕ смена темы)
    if is_potential_followup and not topic_changed:
        questions_left = await decrement_follow_up_questions(topic_id)
        print(f"[entry] Decremented counter: questions_left={questions_left}")

    # ==== ГИБРИДНЫЙ ПОТОК: 3 варианта в зависимости от культуры ====

    print(f"[HYBRID_FLOW] category={detected_category!r}, culture={culture!r}")

    # CASE 1: Культура неясна → уточняющие вопросы БЕЗ RAG
    # НО: для follow-up вопросов НЕ задаем уточняющие вопросы повторно
    should_skip_clarification = is_potential_followup and not topic_changed
    if should_skip_clarification:
        print(f"[HYBRID_FLOW] This is a follow-up question - skipping clarification, using CASE 3")

    if culture in ("не определено", "общая информация") and not should_skip_clarification:
        print(f"[HYBRID_FLOW] CASE 1: Vague culture - asking clarification WITHOUT RAG")

        status_message = await message.answer("⏳ Подождите, рекомендация формируется...")

        try:
            reply_text: str = await ask_consultation_llm(
                user_id=user_id,
                telegram_user_id=telegram_user_id,
                text=user_text,
                session_id=session_id,
                consultation_category=detected_category,
                culture=culture,
                skip_rag=True,  # БЕЗ RAG для уточняющих вопросов!
            )
        except Exception as e:
            print(f"ERROR in ask_consultation_llm: {e}")
            reply_text = (
                "Сейчас не получается обработать запрос через модель. "
                "Попробуйте ещё раз чуть позже."
            )
        finally:
            try:
                await status_message.delete()
            except Exception:
                pass

        # Отправляем ответ (уточняющий вопрос или финальный ответ)
        await send_long_message(message, reply_text)

        # Если LLM задал уточняющий вопрос - переводим в состояние ожидания ответа
        if is_clarification_question(reply_text):
            print(f"[HYBRID_FLOW] LLM asked clarification question, setting state")
            CONSULTATION_STATE[telegram_user_id] = "waiting_clarification_answer"
            CONSULTATION_CONTEXT[telegram_user_id] = {
                "category": detected_category,
                "root_question": user_text,
                "culture": culture,
                "user_id": user_id,
                "topic_id": topic_id,
                "session_id": session_id,
                "telegram_user_id": telegram_user_id,
            }

            # Логируем только ответ бота (уточняющий вопрос)
            await log_message(
                user_id=user_id,
                direction="bot",
                text=reply_text,
                session_id=session_id,
                topic_id=topic_id,
            )

            # НЕ добавляем в moderation для уточняющих вопросов
            # Завершаем обработку - ждём ответа пользователя
            return

        # Если это был финальный ответ (не уточняющий вопрос) - продолжаем логирование ниже

    # CASE 2: Культура общая (клубника общая / малина общая) → запрос типа
    # НО: для follow-up вопросов НЕ задаем уточняющие вопросы повторно
    elif culture in ("клубника общая", "малина общая") and not should_skip_clarification:
        print(f"[HYBRID_FLOW] CASE 2: General culture - asking variety")

        if culture == "клубника общая":
            variety_question = "Какая у вас клубника: летняя (июньская) или ремонтантная (НСД)?"
        else:  # малина общая
            variety_question = "Какая у вас малина: летняя (обычная) или ремонтантная?"

        # Сохраняем контекст и переводим в состояние ожидания ответа
        CONSULTATION_STATE[telegram_user_id] = "waiting_variety_clarification"
        CONSULTATION_CONTEXT[telegram_user_id] = {
            "category": detected_category,
            "root_question": user_text,
            "culture": culture,
            "user_id": user_id,
            "topic_id": topic_id,
            "session_id": session_id,
            "telegram_user_id": telegram_user_id,
        }

        await message.answer(variety_question)
        return  # Не логируем ответ бота здесь, т.к. это системный вопрос

    # CASE 3: Культура конкретна → финальный ответ С RAG
    else:
        print(f"[HYBRID_FLOW] CASE 3: Specific culture - final answer WITH RAG")

        status_message = await message.answer("⏳ Подождите, рекомендация формируется...")

        try:
            reply_text: str = await ask_consultation_llm(
                user_id=user_id,
                telegram_user_id=telegram_user_id,
                text=user_text,
                session_id=session_id,
                consultation_category=detected_category,
                culture=culture,
                skip_rag=False,  # С RAG для финального ответа!
            )
        except Exception as e:
            print(f"ERROR in ask_consultation_llm: {e}")
            reply_text = (
                "Сейчас не получается обработать запрос через модель. "
                "Попробуйте ещё раз чуть позже."
            )
        finally:
            try:
                await status_message.delete()
            except Exception:
                pass

            # Удаляем сообщение "Создается новая тема" если оно есть
            if creating_message:
                try:
                    await creating_message.delete()
                except Exception as e:
                    print(f"[entry] Failed to delete creating_message: {e}")

        await send_long_message(message, reply_text)

    # Логируем ответ бота
    await log_message(
        user_id=user_id,
        direction="bot",
        text=reply_text,
        session_id=session_id,
        topic_id=topic_id,
    )

    # Кандидат в базу знаний (очередь модерации)
    try:
        await moderation_add(
            user_id=user_id,
            topic_id=topic_id,
            question=user_text,
            answer=reply_text,
            category_guess=None,
        )
    except Exception as e:
        print(f"ERROR in moderation_add: {e}")

    # Отправляем информацию о количестве оставшихся вопросов
    # ТОЛЬКО если это финальный ответ (не уточняющий вопрос LLM из CASE 1)
    if culture not in ("не определено", "общая информация"):
        questions_left = await get_follow_up_questions_left(topic_id)
        await send_followup_count_message(message, questions_left, topic_id)


# ===== CALLBACK ОБРАБОТЧИКИ ДЛЯ КНОПОК =====

from aiogram.types import CallbackQuery

@router.callback_query(F.data == "get_more_followup_questions")
async def handle_get_more_questions(callback: CallbackQuery) -> None:
    """Обработчик кнопки "Получить еще 3 уточняющих вопроса"."""
    if callback.from_user is None:
        await callback.answer("Ошибка: пользователь не определен")
        return

    telegram_user_id = callback.from_user.id

    # Получаем внутренний user_id
    user_id = await get_or_create_user(
        telegram_user_id=telegram_user_id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
    )

    # Проверяем баланс токенов
    if not await has_sufficient_tokens(user_id, COST_ADDITIONAL_QUESTIONS):
        balance = await get_token_balance(user_id)
        await callback.answer(
            f"Недостаточно токенов! Нужно: {COST_ADDITIONAL_QUESTIONS}, у вас: {balance}",
            show_alert=True
        )
        return

    # Списываем токен
    success = await deduct_tokens(
        user_id,
        COST_ADDITIONAL_QUESTIONS,
        "buy_questions",
        "3 дополнительных вопроса"
    )
    if not success:
        await callback.answer("Ошибка списания токенов", show_alert=True)
        return

    # Получаем session_id из callback.message
    if callback.message is None:
        await callback.answer("Ошибка: сообщение не найдено")
        return

    session_id = build_session_id_from_message(callback.message)

    # Получаем топик
    from src.services.db.topics_repo import reset_follow_up_questions
    topic_id = await get_or_create_open_topic(user_id=user_id, session_id=session_id)

    # Сбрасываем счётчик
    await reset_follow_up_questions(topic_id)
    questions_left = await get_follow_up_questions_left(topic_id)

    print(f"[get_more_questions] Reset: user={telegram_user_id}, topic={topic_id}, left={questions_left}")

    # Подтверждение
    await callback.answer(f"✅ Получено 3 вопроса за {COST_ADDITIONAL_QUESTIONS} токен!")

    # Обновляем сообщение
    if callback.message:
        try:
            await callback.message.edit_text(
                f"{callback.message.text}\n\n✅ Получено еще 3 уточняющих вопроса."
            )
        except Exception as e:
            print(f"[get_more_questions] Failed to edit: {e}")


@router.callback_query(F.data == "new_consultation_topic")
async def handle_new_topic_callback(callback: CallbackQuery) -> None:
    """Обработчик кнопки "Новая тема консультации"."""
    if callback.from_user is None:
        await callback.answer("Ошибка: пользователь не определен")
        return

    telegram_user_id = callback.from_user.id

    # Получаем user_id
    user_id = await get_or_create_user(
        telegram_user_id=telegram_user_id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
    )

    # Закрываем все топики
    from src.services.db.topics_repo import close_open_topics
    await close_open_topics(user_id)

    # Очищаем контекст и состояние
    CONSULTATION_CONTEXT.pop(telegram_user_id, None)
    CONSULTATION_STATE[telegram_user_id] = "waiting_consultation_question"

    # Запрос нового вопроса
    text = (
        "Опишите, пожалуйста, ваш вопрос одним сообщением:\n"
        "— какая культура (и сорт, если знаете);\n"
        "— в каком регионе/климате вы находитесь;\n"
        "— что именно вас волнует (питание, посадка, болезни и т.п.)."
    )

    if callback.message:
        await callback.message.answer(text)

    await callback.answer("✅ Начинаем новую тему")
    print(f"[new_topic_callback] New topic for user {telegram_user_id}")
