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
from src.services.llm.consultation_llm import ask_consultation_llm, compose_full_question
from src.services.llm.classification_llm import detect_culture_name

# Keyboards
from src.keyboards.consultation.common import get_followup_keyboard

# Утилита для session_id и управление состоянием
from src.handlers.common import (
    build_session_id_from_message,
    CONSULTATION_STATE,
    CONSULTATION_CONTEXT,
)

# Утилита форматирования Markdown → HTML
from src.utils.formatting import markdown_to_telegram_html


router = Router()


# ==== HELPER-ФУНКЦИИ ДЛЯ РАБОТЫ С КОНТЕКСТОМ УТОЧНЕНИЙ ====

def _init_consultation_context(
    telegram_user_id: int,
    root_question: str,
    category: str,
    culture: str,
    user_id: int,
    topic_id: int,
    session_id: str,
    classification_cost_usd: float,
    classification_tokens: int,
) -> dict:
    """
    Инициализирует контекст консультации с накоплением уточнений.

    ВАЖНО: root_question НЕ мутируется! Все уточнения накапливаются в clarifications.
    """
    context = {
        "root_question": root_question,  # Оригинальный вопрос (НЕ мутируется!)
        "clarifications": [],             # Накапливаем ВСЕ уточнения
        "category": category,
        "culture": culture,
        "user_id": user_id,
        "topic_id": topic_id,
        "session_id": session_id,
        "telegram_user_id": telegram_user_id,
        "classification_cost_usd": classification_cost_usd,
        "classification_tokens": classification_tokens,
    }
    CONSULTATION_CONTEXT[telegram_user_id] = context
    return context


def _add_clarification(context: dict, clarification_type: str, bot_question: str) -> None:
    """
    Добавляет уточняющий вопрос в контекст.

    Args:
        context: Контекст консультации
        clarification_type: Тип уточнения ("culture" | "variety")
        bot_question: Вопрос, который бот задал пользователю
    """
    context["clarifications"].append({
        "type": clarification_type,
        "bot": bot_question,
        "user": "",  # Заполнится когда пользователь ответит
    })


def _set_clarification_answer(context: dict, user_answer: str) -> None:
    """
    Заполняет ответ пользователя на последнее уточнение.

    Args:
        context: Контекст консультации
        user_answer: Ответ пользователя
    """
    if context["clarifications"]:
        context["clarifications"][-1]["user"] = user_answer


def _update_context_culture(context: dict, new_culture: str) -> None:
    """Обновляет культуру в контексте."""
    context["culture"] = new_culture


def _add_classification_cost(context: dict, cost_usd: float, tokens: int) -> None:
    """Добавляет стоимость дополнительной классификации к контексту."""
    context["classification_cost_usd"] = context.get("classification_cost_usd", 0.0) + cost_usd
    context["classification_tokens"] = context.get("classification_tokens", 0) + tokens


async def _process_culture_and_respond(message: Message, context: dict) -> None:
    """
    Универсальная логика: проверяем культуру и решаем что делать.

    Вызывается из:
    - process_general_consultation (новый вопрос)
    - handle_clarification_answer (после ответа на уточнение)
    - handle_variety_clarification (после ответа о типе)

    Логика:
    - CASE 1: Культура "не определено" → LLM спрашивает культуру (БЕЗ RAG, БЕЗ compose)
    - CASE 2: Культура "общая" → бот спрашивает тип (БЕЗ RAG, БЕЗ compose)
    - CASE 3: Культура конкретная → финальный ответ (С RAG, С compose)
    """
    culture = context["culture"]
    telegram_user_id = context["telegram_user_id"]
    user_id = context["user_id"]
    topic_id = context["topic_id"]
    session_id = context["session_id"]
    category = context["category"]
    root_question = context["root_question"]

    # CASE 1: Культура неясна → LLM спрашивает уточнение (БЕЗ RAG, БЕЗ compose)
    if culture in ("не определено", "общая информация"):
        print(f"[_process_culture] CASE 1: Vague culture - asking clarification WITHOUT RAG")

        status_message = await message.answer("⏳ Подождите, рекомендация формируется...")

        try:
            reply_text: str = await ask_consultation_llm(
                user_id=user_id,
                telegram_user_id=telegram_user_id,
                text=root_question,
                session_id=session_id,
                topic_id=topic_id,
                consultation_category=category,
                culture=culture,
                skip_rag=True,  # БЕЗ RAG!
                classification_cost_usd=context["classification_cost_usd"],
                classification_tokens=context["classification_tokens"],
            )
        except Exception as e:
            print(f"ERROR in ask_consultation_llm: {e}")
            reply_text = "Сейчас не получается обработать запрос. Попробуйте позже."
        finally:
            try:
                await status_message.delete()
            except Exception:
                pass

        await send_long_message(message, reply_text)

        # Если LLM задал уточняющий вопрос
        if is_clarification_question(reply_text):
            print(f"[_process_culture] LLM asked clarification, setting state")
            CONSULTATION_STATE[telegram_user_id] = "waiting_clarification_answer"
            _add_clarification(context, "culture", reply_text)

            await log_message(
                user_id=user_id,
                direction="bot",
                text=reply_text,
                session_id=session_id,
                topic_id=topic_id,
            )
            return

    # CASE 2: Культура общая → бот спрашивает тип (БЕЗ RAG, БЕЗ compose)
    elif culture in ("клубника общая", "малина общая"):
        print(f"[_process_culture] CASE 2: General culture - asking variety")

        if culture == "клубника общая":
            variety_question = "Какая у вас клубника: летняя (июньская) или ремонтантная (НСД)?"
        else:
            variety_question = "Какая у вас малина: летняя (обычная) или ремонтантная?"

        CONSULTATION_STATE[telegram_user_id] = "waiting_variety_clarification"
        _add_clarification(context, "variety", variety_question)

        await message.answer(variety_question)
        await log_message(
            user_id=user_id,
            direction="bot",
            text=variety_question,
            session_id=session_id,
            topic_id=topic_id,
        )
        return

    # CASE 3: Культура конкретна → финальный ответ (С RAG, С compose)
    else:
        print(f"[_process_culture] CASE 3: Specific culture - final answer WITH RAG")

        status_message = await message.answer("⏳ Подождите, рекомендация формируется...")

        # Формируем полный вопрос из root + ВСЕ уточнения (ОДИН раз в конце!)
        clarifications = context.get("clarifications", [])
        if clarifications:
            composed_q, compose_cost, compose_tokens = await compose_full_question(
                root_question,
                clarifications,
            )
            print(f"[_process_culture] Composed question: {composed_q[:100]}...")
        else:
            # Нет уточнений — используем оригинальный вопрос
            composed_q = root_question
            compose_cost = 0.0
            compose_tokens = 0

        try:
            reply_text: str = await ask_consultation_llm(
                user_id=user_id,
                telegram_user_id=telegram_user_id,
                text=composed_q,
                session_id=session_id,
                topic_id=topic_id,
                consultation_category=category,
                culture=culture,
                skip_rag=False,  # С RAG!
                composed_question=composed_q,
                compose_cost_usd=compose_cost,
                compose_tokens=compose_tokens,
                classification_cost_usd=context["classification_cost_usd"],
                classification_tokens=context["classification_tokens"],
            )
        except Exception as e:
            print(f"ERROR in ask_consultation_llm: {e}")
            reply_text = "Сейчас не получается обработать запрос. Попробуйте позже."
        finally:
            try:
                await status_message.delete()
            except Exception:
                pass

        # Отправляем финальный ответ с кнопками follow-up
        reply_text_html = markdown_to_telegram_html(reply_text)
        await message.answer(reply_text_html, reply_markup=get_followup_keyboard(category))

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
                question=composed_q,
                answer=reply_text,
                category_guess=None,
            )
        except Exception as e:
            print(f"ERROR in moderation_add: {e}")

        # Очищаем состояние
        CONSULTATION_STATE.pop(telegram_user_id, None)
        CONSULTATION_CONTEXT.pop(telegram_user_id, None)


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
    # Конвертируем Markdown → HTML для Telegram
    text = markdown_to_telegram_html(text)

    # Резервируем место для префикса "[Часть X/Y]\n\n" (максимум ~20 символов)
    parts = split_long_message(text, max_length=4070)

    if len(parts) > 1:
        print(f"[send_long_message] Сообщение разбито на {len(parts)} частей")

    for i, part in enumerate(parts, 1):
        if len(parts) > 1:
            # Добавляем номер части, если сообщение разбито
            part_text = f"[Часть {i}/{len(parts)}]\n\n{part}"
        else:
            part_text = part

        await message.answer(part_text)


async def send_followup_count_message(
    message: Message,
    questions_left: int,
    topic_id: int,
    category: str = "питание растений"
) -> None:
    """
    Отправляет информационное сообщение о количестве оставшихся уточняющих вопросов.

    Args:
        message: Сообщение от пользователя
        questions_left: Количество оставшихся вопросов (0-3)
        topic_id: ID топика
        category: Категория консультации для выбора текста кнопки
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
        await message.answer(text, reply_markup=get_followup_keyboard(category))
    else:
        # Показываем кнопку для получения дополнительных вопросов
        from src.keyboards.consultation.common import get_more_questions_keyboard
        text = "Уточняющие вопросы по этой теме исчерпаны."
        await message.answer(text, reply_markup=get_more_questions_keyboard())

    print(f"[followup_count] Sent: questions_left={questions_left}, topic_id={topic_id}, category={category}")


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


def is_rejection_response(text: str) -> bool:
    """
    Определяет, является ли ответ LLM отказом (вопрос не по теме ягодных).

    Признаки отказа:
    - Содержит типичные фразы отказа
    """
    text_lower = text.lower()
    return (
        "могу помочь только" in text_lower
        or "только по ягодным" in text_lower
        or "не относится к ягодным" in text_lower
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
    category, culture, classification_cost, classification_tokens = await detect_category_and_culture(question_text)

    print(f"[unified_entry] Detected category={category!r}, culture={culture!r}, cost=${classification_cost:.6f}, tokens={classification_tokens}")

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
            classification_cost_usd=classification_cost,
            classification_tokens=classification_tokens,
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
            classification_cost_usd=classification_cost,
            classification_tokens=classification_tokens,
        )


async def process_general_consultation(
    message: Message,
    user_id: int,
    category: str,
    culture: str,
    root_question: str,
    classification_cost_usd: float = 0.0,
    classification_tokens: int = 0,
) -> None:
    """
    Обрабатывает общую консультацию (не питание растений).

    Логика:
    - CASE 1: Культура неясна → уточняющие вопросы БЕЗ RAG, БЕЗ compose
    - CASE 2: Культура общая (клубника/малина общая) → запрос типа БЕЗ RAG, БЕЗ compose
    - CASE 3: Культура конкретна → финальный ответ С RAG, С compose
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

    # Обновляем категорию и культуру в БД
    from src.services.db.topics_repo import set_topic_culture, set_topic_category
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

    # Инициализируем контекст с новой структурой (clarifications = [])
    context = _init_consultation_context(
        telegram_user_id=telegram_user_id,
        root_question=root_question,
        category=category,
        culture=culture,
        user_id=user_id,
        topic_id=topic_id,
        session_id=session_id,
        classification_cost_usd=classification_cost_usd,
        classification_tokens=classification_tokens,
    )

    print(f"[process_general] category={category!r}, culture={culture!r}")

    # Вызываем универсальную логику обработки культуры
    # (moderation_add и очистка состояния происходят внутри _process_culture_and_respond)
    await _process_culture_and_respond(message, context)


# ==== ОБРАБОТЧИК 1: Ответ на вопрос о типе культуры (летняя/ремонтантная) ====

@router.message(
    lambda m: m.from_user is not None
    and CONSULTATION_STATE.get(m.from_user.id) == "waiting_variety_clarification"
)
async def handle_variety_clarification(message: Message) -> None:
    """
    Обрабатывает ответ пользователя на вопрос о типе культуры.

    Пользователь ответил на вопрос "Какая у вас клубника/малина: летняя или ремонтантная?"
    Сохраняем ответ в clarifications и переопределяем культуру.
    Затем вызываем _process_culture_and_respond для финального ответа.
    """
    user = message.from_user
    if user is None:
        return

    telegram_user_id = user.id
    variety_answer = (message.text or "").strip()

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

    # Сохраняем ответ пользователя в последнее уточнение
    _set_clarification_answer(context, variety_answer)

    # Определяем новую культуру на основе ответа
    variety_answer_lower = variety_answer.lower()
    if "ремонтант" in variety_answer_lower or "нсд" in variety_answer_lower:
        if old_culture == "клубника общая":
            new_culture = "клубника ремонтантная"
        else:  # малина общая
            new_culture = "малина ремонтантная"
    elif "летн" in variety_answer_lower or "обычн" in variety_answer_lower or "традицион" in variety_answer_lower or "июньск" in variety_answer_lower:
        if old_culture == "клубника общая":
            new_culture = "клубника летняя"
        else:  # малина общая
            new_culture = "малина летняя"
    else:
        # Не удалось распознать - пробуем классификатор
        combined_text = f"{root_question} {variety_answer}"
        new_culture, additional_class_cost, additional_class_tokens = await detect_culture_name(combined_text)
        _add_classification_cost(context, additional_class_cost, additional_class_tokens)
        print(f"[VARIETY_CLARIFICATION] Failed to parse answer, re-classified: {new_culture!r}")

    print(f"[VARIETY_CLARIFICATION] Refined culture: {old_culture!r} -> {new_culture!r}")

    # Обновляем культуру в контексте и БД
    _update_context_culture(context, new_culture)
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

    # Вызываем универсальную логику - теперь культура конкретна, будет CASE 3 с RAG
    await _process_culture_and_respond(message, context)


# ==== ОБРАБОТЧИК 2: Ответ на уточняющие вопросы LLM ====

@router.message(
    lambda m: m.from_user is not None
    and CONSULTATION_STATE.get(m.from_user.id) == "waiting_clarification_answer"
)
async def handle_clarification_answer(message: Message) -> None:
    """
    Обрабатывает ответ пользователя на уточняющие вопросы LLM.

    LLM спросил "О какой культуре речь?" и пользователь ответил.
    Сохраняем ответ в clarifications, переопределяем культуру и вызываем
    _process_culture_and_respond для дальнейшей обработки.
    """
    user = message.from_user
    if user is None:
        return

    telegram_user_id = user.id
    clarification_answer = (message.text or "").strip()

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

    # Сохраняем ответ пользователя в последнее уточнение
    _set_clarification_answer(context, clarification_answer)

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
    new_culture, new_class_cost, new_class_tokens = await detect_culture_name(combined_text)
    _add_classification_cost(context, new_class_cost, new_class_tokens)
    print(f"[CLARIFICATION_ANSWER] Re-classified culture: {new_culture!r}, cost=${new_class_cost:.6f}")

    # Обновляем культуру в контексте и БД
    _update_context_culture(context, new_culture)
    from src.services.db.topics_repo import set_topic_culture
    await set_topic_culture(topic_id, new_culture)

    # Вызываем универсальную логику - она сама решит CASE 1/2/3
    await _process_culture_and_respond(message, context)


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

    # Проверяем, есть ли у пользователя активное состояние консультации
    has_active_state = telegram_user_id in CONSULTATION_STATE

    # Пользователь
    user_id = await get_or_create_user(
        telegram_user_id=telegram_user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
    )

    # Проверяем, есть ли открытый топик с сообщениями (активная консультация)
    from src.services.db.topics_repo import get_topic_message_count
    from src.services.db.pool import get_pool

    pool = get_pool()
    async with pool.acquire() as conn:
        # Ищем открытый топик
        row = await conn.fetchrow(
            """
            SELECT id FROM topics
            WHERE user_id = $1 AND status = 'open'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id,
        )

    # Если нет активного состояния и нет открытого топика с историей — просим выбрать пункт меню
    if not has_active_state:
        if row is None:
            # Нет открытого топика вообще
            from src.keyboards.main.main_menu import get_main_keyboard
            await message.answer(
                "Пожалуйста, выберите пункт из меню.",
                reply_markup=get_main_keyboard(),
            )
            return
        else:
            # Есть топик — проверяем, есть ли в нём сообщения
            topic_id_check = row["id"]
            msg_count = await get_topic_message_count(topic_id_check)
            if msg_count == 0:
                # Топик пустой — просим выбрать пункт меню
                from src.keyboards.main.main_menu import get_main_keyboard
                await message.answer(
                    "Пожалуйста, выберите пункт из меню.",
                    reply_markup=get_main_keyboard(),
                )
                return

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
    # Накапливаем стоимость классификации
    classification_cost_usd = 0.0
    classification_tokens = 0

    # Если это потенциальный follow-up - проверяем смену темы через LLM
    if is_potential_followup:
        print(f"[entry] Potential follow-up detected, checking topic change...")
        print(f"[entry] Saved category: {saved_category!r}, saved culture: {culture!r}")

        # ВАЖНО: Категория НЕ меняется для follow-up, используем сохраненную
        detected_category = saved_category or "не определена"

        # Если культура ещё не определена - НЕ проверяем смену темы,
        # просто продолжаем как same_topic (уточняющий вопрос)
        if culture in ("не определено", "общая информация"):
            print(f"[entry] Culture not yet defined - treating as same_topic, skipping topic change check")
            topic_change = "same_topic"
            new_culture = culture
        else:
            # Получаем контекст предыдущих сообщений
            context_text = await get_message_context(topic_id, limit=3)

            # Классифицируем новый вопрос ТОЛЬКО для определения культуры
            new_category, new_culture, class_cost, class_tokens = await detect_category_and_culture(user_text)
            classification_cost_usd += class_cost
            classification_tokens += class_tokens
            print(f"[entry] New classification: category={new_category!r}, culture={new_culture!r}, cost=${class_cost:.6f}")
            print(f"[entry] BUT keeping saved category: {detected_category!r}")

            # Сравниваем ТОЛЬКО культуры (категория фиксирована)
            topic_change, compare_cost, compare_tokens = await compare_topics_for_change(
                old_category=detected_category,  # Используем СОХРАНЕННУЮ категорию
                old_culture=culture,
                new_question=user_text,
                context_messages=context_text,
            )
            classification_cost_usd += compare_cost
            classification_tokens += compare_tokens

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
            detected_category = saved_category or "не определена"

        else:  # unclear
            # НЕОПРЕДЕЛЕННО - остаемся на той же теме
            print(f"[entry] UNCLEAR - staying on same topic")
            # Используем сохраненную категорию из топика
            detected_category = saved_category or "не определена"
    else:
        # Это первый вопрос - переопределяем культуру И категорию
        print(f"[entry] First question or new consultation, detecting category and culture")
        detected_category, detected_culture, class_cost, class_tokens = await detect_category_and_culture(user_text)
        classification_cost_usd += class_cost
        classification_tokens += class_tokens

        # Сохраняем категорию в топике
        await set_topic_category(topic_id, detected_category)

        if detected_culture:
            await set_topic_culture(topic_id, detected_culture)
            culture = detected_culture
            print(f"[entry] Detected: category={detected_category!r}, culture={culture}, cost=${class_cost:.6f}")
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
                topic_id=topic_id,
                consultation_category=detected_category,
                culture=culture,
                skip_rag=True,  # БЕЗ RAG для уточняющих вопросов!
                classification_cost_usd=classification_cost_usd,
                classification_tokens=classification_tokens,
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

            # Используем новую структуру контекста с clarifications
            context = _init_consultation_context(
                telegram_user_id=telegram_user_id,
                root_question=user_text,
                category=detected_category,
                culture=culture,
                user_id=user_id,
                topic_id=topic_id,
                session_id=session_id,
                classification_cost_usd=classification_cost_usd,
                classification_tokens=classification_tokens,
            )
            _add_clarification(context, "culture", reply_text)

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

        # Сохраняем контекст с новой структурой clarifications
        CONSULTATION_STATE[telegram_user_id] = "waiting_variety_clarification"
        context = _init_consultation_context(
            telegram_user_id=telegram_user_id,
            root_question=user_text,
            category=detected_category,
            culture=culture,
            user_id=user_id,
            topic_id=topic_id,
            session_id=session_id,
            classification_cost_usd=classification_cost_usd,
            classification_tokens=classification_tokens,
        )
        _add_clarification(context, "variety", variety_question)

        await message.answer(variety_question)
        # Логируем уточняющий вопрос бота
        await log_message(
            user_id=user_id,
            direction="bot",
            text=variety_question,
            session_id=session_id,
            topic_id=topic_id,
        )
        return

    # CASE 3: Культура конкретна → финальный ответ С RAG
    else:
        print(f"[HYBRID_FLOW] CASE 3: Specific culture - final answer WITH RAG")

        status_message = await message.answer("⏳ Подождите, рекомендация формируется...")

        # Формируем красивый вопрос для RAG (даже без уточнений)
        # Для follow-up вопросов добавляем культурный контекст
        culture_context = culture if (is_potential_followup and not topic_changed) else None
        composed_q, compose_cost, compose_tokens = await compose_full_question(
            user_text,
            [],
            culture_context=culture_context
        )

        try:
            reply_text: str = await ask_consultation_llm(
                user_id=user_id,
                telegram_user_id=telegram_user_id,
                text=user_text,
                session_id=session_id,
                topic_id=topic_id,
                consultation_category=detected_category,
                culture=culture,
                skip_rag=False,  # С RAG для финального ответа!
                composed_question=composed_q,  # Красиво сформированный вопрос
                compose_cost_usd=compose_cost,  # Стоимость формирования вопроса
                compose_tokens=compose_tokens,  # Токены формирования вопроса
                classification_cost_usd=classification_cost_usd,
                classification_tokens=classification_tokens,
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
        await send_followup_count_message(message, questions_left, topic_id, detected_category)


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
