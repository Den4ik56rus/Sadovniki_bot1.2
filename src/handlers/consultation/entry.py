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
from aiogram.types import Message, CallbackQuery

# Репозитории БД
from src.services.db.users_repo import get_or_create_user
from src.services.db.topics_repo import (
    get_or_create_open_topic,
    get_topic_culture,
)
from src.services.db.messages_repo import log_message
from src.services.db.moderation_repo import moderation_add
from src.services.db.tokens_repo import has_sufficient_tokens, deduct_tokens, add_tokens, get_token_balance

# Прайсы вопросов
from src.pricing import COST_NEW_TOPIC, get_consultation_cost, pluralize_questions

# LLM
from src.services.llm.consultation_llm import ask_consultation_llm, compose_full_question
from src.services.llm.classification_llm import detect_culture_name

# Keyboards
from src.keyboards.consultation.common import get_followup_keyboard, CONSULTATION_ENTRY_TEXT, get_example_questions_keyboard

# Утилита для session_id и управление состоянием
from src.handlers.common import (
    build_session_id_from_message,
    CONSULTATION_STATE,
    CONSULTATION_CONTEXT,
)

# Утилита форматирования Markdown → HTML
from src.utils.formatting import markdown_to_telegram_html

# Менеджер статусных сообщений
from src.utils.status_manager import StatusMessageManager


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
    correction_hint: str | None = None,
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
        "correction_hint": correction_hint,
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
    - CASE 2: УДАЛЕН — "клубника общая" / "малина общая" больше не существует (default летняя)
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

        status_mgr = StatusMessageManager(message, use_rag=False)
        await status_mgr.start()

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
                status_updater=status_mgr.update,
            )
        except Exception as e:
            print(f"ERROR in ask_consultation_llm: {e}")
            await status_mgr.complete()
            raise  # Пробрасываем — unified_entry вернёт токены
        finally:
            await status_mgr.complete()

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

    # CASE 2 УДАЛЕН: "клубника общая" / "малина общая" больше не существует

    # CASE 3: Культура конкретна → финальный ответ (С RAG, С compose)
    else:
        print(f"[_process_culture] CASE 3: Specific culture - final answer WITH RAG")

        status_mgr = StatusMessageManager(message)
        await status_mgr.start()

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
                status_updater=status_mgr.update,
                stream=True,
                streaming_transition=status_mgr.start_streaming,
            )
        except Exception as e:
            print(f"ERROR in ask_consultation_llm: {e}")
            await status_mgr.complete()
            raise  # Пробрасываем — unified_entry вернёт токены

        # Забираем стриминг-сообщение ДО complete() чтобы переиспользовать
        streaming_msg = status_mgr.get_streaming_message()
        await status_mgr.complete()

        # Финализируем: edit стриминг-сообщения с полным отформатированным текстом
        await finalize_streaming_message(
            streaming_msg, message, reply_text,
            keyboard=get_followup_keyboard(category),
            show_followup_prompt=True,
        )

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

        # Переводим в режим ожидания follow-up вопроса (остаёмся в консультации)
        CONSULTATION_STATE[telegram_user_id] = "waiting_followup"


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


async def send_long_message_with_keyboard(
    message: Message,
    text: str,
    keyboard=None
) -> None:
    """
    Отправляет длинное сообщение, разбивая на части.
    Клавиатура добавляется только к последней части.

    Args:
        message: Сообщение от пользователя (для ответа)
        text: Текст для отправки
        keyboard: Клавиатура (InlineKeyboardMarkup), добавляется к последнему сообщению
    """
    # Конвертируем Markdown → HTML для Telegram
    text = markdown_to_telegram_html(text)

    # Резервируем место для префикса "[Часть X/Y]\n\n" (максимум ~20 символов)
    parts = split_long_message(text, max_length=4070)

    if len(parts) > 1:
        print(f"[send_long_message_with_keyboard] Сообщение разбито на {len(parts)} частей")

    for i, part in enumerate(parts, 1):
        is_last = (i == len(parts))

        if len(parts) > 1:
            # Добавляем номер части, если сообщение разбито
            part_text = f"[Часть {i}/{len(parts)}]\n\n{part}"
        else:
            part_text = part

        # Клавиатуру добавляем только к последней части
        if is_last and keyboard:
            await message.answer(part_text, reply_markup=keyboard)
        else:
            await message.answer(part_text)


async def finalize_streaming_message(
    streaming_msg: "Message | None",
    message: Message,
    text: str,
    keyboard=None,
    show_followup_prompt: bool = False,
) -> None:
    """
    Финализирует стриминг-сообщение: делает edit с полным отформатированным текстом.

    Если текст короткий (≤4070) — edit существующего сообщения (мгновенно).
    Если текст длинный — удаляем стриминг-сообщение и отправляем частями.
    Если streaming_msg=None — fallback на обычную отправку.

    Args:
        streaming_msg: Стриминг-сообщение из StatusMessageManager.get_streaming_message()
        message: Оригинальное сообщение пользователя (для fallback ответа)
        text: Полный текст ответа (markdown)
        keyboard: Клавиатура для последнего сообщения
        show_followup_prompt: Показывать ли подсказку "Выберите вариант следующего вопроса"
    """
    html_text = markdown_to_telegram_html(text)
    parts = split_long_message(html_text, max_length=4070)

    if streaming_msg and len(parts) == 1:
        # Короткий ответ — edit стриминг-сообщения (мгновенно, без мигания)
        try:
            await streaming_msg.edit_text(parts[0])
        except Exception:
            # Если edit не удался — fallback на обычную отправку
            try:
                await streaming_msg.delete()
            except Exception:
                pass
            await send_long_message(message, text)
    else:
        # Длинный ответ или fallback — удаляем стриминг и отправляем частями
        if streaming_msg:
            try:
                await streaming_msg.delete()
            except Exception:
                pass
        await send_long_message(message, text)

    # Показываем подсказку с кнопками отдельным сообщением
    if show_followup_prompt and keyboard:
        await message.answer(
            "Выберите вариант следующего вопроса:",
            reply_markup=keyboard,
        )


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

    Двухуровневая логика:
    - Короткие ответы (<300): достаточно "?" или ключевой фразы
    - Средние ответы (300-600): нужна ключевая фраза уточнения
    - Длинные ответы (>600): всегда считаются финальным ответом
    """
    text_lower = text.lower()
    text_len = len(text)

    # Длинный ответ — точно не уточняющий вопрос
    if text_len >= 600:
        return False

    clarification_keywords = [
        "уточните",
        "о какой культуре",
        "какая у вас",
        "какую культуру",
        "подскажите, о какой",
        "подскажите, какую",
        "какое растение",
        "какую ягоду",
        "какая именно",
        "что именно вы имеете в виду",
        "что вы имеете в виду",
        "имеете в виду",
        "можете уточнить",
        "не могу определить",
        "не удалось определить",
        "какой именно",
        "какая конкретно",
        "о каком растении",
    ]

    has_keyword = any(kw in text_lower for kw in clarification_keywords)
    has_question_mark = "?" in text

    # Короткий ответ: "?" или ключевая фраза
    if text_len < 300 and (has_keyword or has_question_mark):
        return True

    # Средний ответ: только ключевая фраза
    if has_keyword:
        return True

    return False


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

async def run_consultation_pipeline(
    message: Message,
    telegram_user_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
    question_text: str,
) -> None:
    """
    Универсальный пайплайн консультации.
    Вызывается из текстового хендлера и из callback инлайн-кнопок примеров.
    """
    print(f"[unified_entry] Получен вопрос от user {telegram_user_id}: {question_text!r}")

    # Получаем внутренний user_id
    internal_user_id = await get_or_create_user(
        telegram_user_id=telegram_user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
    )

    # Быстрая проверка баланса (минимум 1 вопрос) — без LLM-вызова
    if not await has_sufficient_tokens(internal_user_id, 1):
        balance = await get_token_balance(internal_user_id)
        await message.answer(
            f"У вас недостаточно вопросов для консультации.\n\n"
            f"Ваш баланс: {pluralize_questions(balance)}\n\n"
            f"Для пополнения перейдите в «Мой профиль» → «Пополнить баланс»."
        )
        CONSULTATION_STATE.pop(telegram_user_id, None)
        return

    # Автоматически определяем категорию + культуру
    from src.services.llm.classification_llm import detect_category_and_culture
    category, culture, correction_hint, classification_cost, classification_tokens = await detect_category_and_culture(question_text)

    print(f"[unified_entry] Detected category={category!r}, culture={culture!r}, correction={correction_hint!r}, cost=${classification_cost:.6f}, tokens={classification_tokens}")

    # Определяем стоимость по категории
    cost = get_consultation_cost(category)

    # Точная проверка баланса с учётом категории
    if not await has_sufficient_tokens(internal_user_id, cost):
        balance = await get_token_balance(internal_user_id)
        await message.answer(
            f"Консультация по теме «{category}» стоит {pluralize_questions(cost)}.\n"
            f"Ваш баланс: {pluralize_questions(balance)}.\n\n"
            f"Для пополнения перейдите в «Мой профиль» → «Пополнить баланс»."
        )
        CONSULTATION_STATE.pop(telegram_user_id, None)
        return

    # Списываем вопросы за консультацию
    await deduct_tokens(
        internal_user_id,
        cost,
        "new_topic",
        f"Консультация: {category}"
    )

    # Маршрутизация на основе категории
    try:
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
                correction_hint=correction_hint,
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
                correction_hint=correction_hint,
            )
    except Exception as e:
        print(f"[unified_entry] ERROR: {e}, returning questions to user {internal_user_id}")
        await add_tokens(internal_user_id, cost, "refund", "Возврат: ошибка модели")
        await message.answer(
            "Произошла ошибка при обработке запроса. "
            "Вопросы возвращены на ваш баланс. Попробуйте ещё раз."
        )


@router.message(
    lambda m: m.from_user is not None
    and CONSULTATION_STATE.get(m.from_user.id) == "waiting_example_details"
)
async def handle_example_details(message: Message) -> None:
    """
    Пользователь выбрал пример вопроса и теперь уточняет детали.
    Объединяем пример + уточнения в полный вопрос и запускаем пайплайн.
    """
    user = message.from_user
    if user is None or not message.text:
        return

    context = CONSULTATION_CONTEXT.get(user.id, {})
    example = context.get("example_question", "")

    # Собираем полный вопрос: пример + уточнения пользователя
    details = message.text.strip()
    full_question = f"{example}: {details}"

    # Очищаем временный контекст примера
    CONSULTATION_CONTEXT.pop(user.id, None)

    await run_consultation_pipeline(
        message=message,
        telegram_user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        question_text=full_question,
    )


@router.message(
    lambda m: m.from_user is not None
    and CONSULTATION_STATE.get(m.from_user.id) == "waiting_consultation_question"
)
async def handle_consultation_question_unified(message: Message) -> None:
    """
    Единая точка входа для обработки вопроса консультации (текст от пользователя).
    """
    user = message.from_user
    if user is None or not message.text:
        return

    await run_consultation_pipeline(
        message=message,
        telegram_user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        question_text=message.text.strip(),
    )


async def process_general_consultation(
    message: Message,
    user_id: int,
    category: str,
    culture: str,
    root_question: str,
    classification_cost_usd: float = 0.0,
    classification_tokens: int = 0,
    correction_hint: str | None = None,
) -> None:
    """
    Обрабатывает общую консультацию (не питание растений).

    Логика:
    - CASE 1: Культура неясна → уточняющие вопросы БЕЗ RAG, БЕЗ compose
    - CASE 2: УДАЛЕН (default летняя)
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
        correction_hint=correction_hint,
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


# ==== ОБРАБОТЧИК 3: Follow-up вопросы (состояние waiting_followup) ====

@router.message(
    lambda m: m.from_user is not None
    and CONSULTATION_STATE.get(m.from_user.id) == "waiting_followup"
)
async def handle_followup_question(message: Message) -> None:
    """
    БЛОКИРУЕТ прямой текстовый ввод в состоянии waiting_followup.
    Требует нажатия инлайн-кнопки "Уточняющий вопрос" или "Новая тема".
    """
    user = message.from_user
    if user is None:
        return

    await message.answer(
        "Пожалуйста, выберите один из вариантов:\n"
        "• <b>Задать уточняющий вопрос</b> — продолжить текущую тему\n"
        "• <b>Задать вопрос по новой теме</b> — начать новую консультацию",
        reply_markup=get_followup_keyboard(),
    )


# ==== ОБРАБОТЧИК 3.1: Логика follow-up вопроса (вызывается из callback) ====

async def process_followup_question_logic(message: Message) -> None:
    """
    Обработка follow-up вопросов в режиме консультации.
    Вызывается только когда пользователь уже получил ответ и задаёт уточняющий вопрос.

    Логика:
    1. Проверяем открытый топик с историей
    2. Определяем смену темы через LLM
    3. CASE 1: Культура неясна → уточняющие вопросы БЕЗ RAG
    4. CASE 3: Культура конкретна → финальный ответ С RAG
    """

    print("DEBUG: process_followup_question_logic получил сообщение:", message.text)

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
        close_open_topics,
    )
    from src.services.llm.classification_llm import compare_topics_for_change, detect_category_and_culture

    message_count_before = await get_topic_message_count(topic_id)
    topic_status = await get_topic_status(topic_id)
    culture = await get_topic_culture(topic_id)
    saved_category = await get_topic_category(topic_id)

    print(f"[followup] BEFORE: topic_id={topic_id}, msg_count={message_count_before}, status={topic_status}, culture={culture!r}")

    # Определяем, является ли это потенциальным follow-up (есть история в топике)
    is_potential_followup = (
        topic_status == "open"
        and culture is not None
        and message_count_before > 0
    )

    # Переменная для отслеживания смены темы
    topic_changed = False
    creating_message = None
    correction_hint = None
    classification_cost_usd = 0.0
    classification_tokens = 0

    if is_potential_followup:
        print(f"[followup] Potential follow-up detected, checking topic change...")
        print(f"[followup] Saved category: {saved_category!r}, saved culture: {culture!r}")

        detected_category = saved_category or "не определена"

        if culture in ("не определено", "общая информация"):
            print(f"[followup] Culture not yet defined - treating as same_topic, skipping topic change check")
            topic_change = "same_topic"
            new_culture = culture
            new_correction_hint = None
        else:
            context_text = await get_message_context(topic_id, limit=3)

            new_category, new_culture, new_correction_hint, class_cost, class_tokens = await detect_category_and_culture(user_text)
            classification_cost_usd += class_cost
            classification_tokens += class_tokens
            print(f"[followup] New classification: category={new_category!r}, culture={new_culture!r}, cost=${class_cost:.6f}")
            print(f"[followup] BUT keeping saved category: {detected_category!r}")

            topic_change, compare_cost, compare_tokens = await compare_topics_for_change(
                old_category=detected_category,
                old_culture=culture,
                new_question=user_text,
                context_messages=context_text,
            )
            classification_cost_usd += compare_cost
            classification_tokens += compare_tokens

        print(f"[followup] Culture change decision: {topic_change!r}")

        if new_correction_hint and topic_change != "clear_change":
            print(f"[followup] CORRECTION HINT detected in follow-up — forcing clear_change")
            topic_change = "clear_change"
            new_culture = "не определено"

        if topic_change == "clear_change":
            print(f"[followup] CLEAR CULTURE CHANGE - creating new topic with same category")
            creating_message = await message.answer("📝 Создается новая тема консультации...")
            await close_open_topics(user_id)
            topic_id = await get_or_create_open_topic(
                user_id=user_id,
                session_id=session_id,
            )
            await set_topic_category(topic_id, detected_category)
            await set_topic_culture(topic_id, new_culture)
            culture = new_culture
            correction_hint = new_correction_hint
            topic_changed = True
            print(f"[followup] NEW topic created: topic_id={topic_id}, category={detected_category!r}, culture={culture!r}")

        elif topic_change == "same_topic":
            print(f"[followup] SAME TOPIC - follow-up question")
            detected_category = saved_category or "не определена"

        else:  # unclear
            print(f"[followup] UNCLEAR - staying on same topic")
            detected_category = saved_category or "не определена"
    else:
        # Нет истории в топике — первый вопрос в этом follow-up (редкий случай)
        print(f"[followup] No history in topic, detecting category and culture")
        detected_category, detected_culture, correction_hint, class_cost, class_tokens = await detect_category_and_culture(user_text)
        classification_cost_usd += class_cost
        classification_tokens += class_tokens

        await set_topic_category(topic_id, detected_category)

        if detected_culture:
            await set_topic_culture(topic_id, detected_culture)
            culture = detected_culture
            print(f"[followup] Detected: category={detected_category!r}, culture={culture}, cost=${class_cost:.6f}")
        else:
            await set_topic_culture(topic_id, "не определено")
            culture = "не определено"
            print(f"[followup] Culture not detected, saved: {culture}")

    # Логируем сообщение пользователя
    await log_message(
        user_id=user_id,
        direction="user",
        text=user_text,
        session_id=session_id,
        topic_id=topic_id,
    )

    # ПОСЛЕ логирования: списываем вопросы если это follow-up (НЕ смена темы)
    if is_potential_followup and not topic_changed:
        followup_cost = get_consultation_cost(detected_category)
        if not await has_sufficient_tokens(user_id, followup_cost):
            balance = await get_token_balance(user_id)
            await message.answer(
                f"У вас недостаточно вопросов.\n\n"
                f"Стоимость: {pluralize_questions(followup_cost)}\n"
                f"Ваш баланс: {pluralize_questions(balance)}\n\n"
                f"Для пополнения перейдите в «Мой профиль» → «Пополнить баланс»."
            )
            return
        await deduct_tokens(user_id, followup_cost, "follow_up", f"Уточняющий вопрос: {detected_category}")
        print(f"[followup] Charged {followup_cost} questions for follow-up question")

    # ==== ГИБРИДНЫЙ ПОТОК: 3 варианта в зависимости от культуры ====

    print(f"[HYBRID_FLOW_FOLLOWUP] category={detected_category!r}, culture={culture!r}")

    # CASE 1: Культура неясна → уточняющие вопросы БЕЗ RAG
    # НО: для follow-up вопросов НЕ задаем уточняющие вопросы повторно
    should_skip_clarification = is_potential_followup and not topic_changed
    if should_skip_clarification:
        print(f"[HYBRID_FLOW_FOLLOWUP] This is a follow-up question - skipping clarification, using CASE 3")

    if culture in ("не определено", "общая информация") and not should_skip_clarification:
        print(f"[HYBRID_FLOW_FOLLOWUP] CASE 1: Vague culture - asking clarification WITHOUT RAG")

        if correction_hint:
            await message.answer(f"💡 {correction_hint}")

        status_mgr = StatusMessageManager(message, use_rag=False)
        await status_mgr.start()

        try:
            reply_text: str = await ask_consultation_llm(
                user_id=user_id,
                telegram_user_id=telegram_user_id,
                text=user_text,
                session_id=session_id,
                topic_id=topic_id,
                consultation_category=detected_category,
                culture=culture,
                skip_rag=True,
                classification_cost_usd=classification_cost_usd,
                classification_tokens=classification_tokens,
                status_updater=status_mgr.update,
            )
        except Exception as e:
            print(f"ERROR in ask_consultation_llm: {e}")
            await status_mgr.complete()
            reply_text = (
                "Произошла ошибка при обращении к модели. "
                "Попробуйте отправить вопрос ещё раз."
            )
        finally:
            await status_mgr.complete()

        await send_long_message(message, reply_text)

        if is_clarification_question(reply_text):
            print(f"[HYBRID_FLOW_FOLLOWUP] LLM asked clarification question, setting state")
            CONSULTATION_STATE[telegram_user_id] = "waiting_clarification_answer"

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

            await log_message(
                user_id=user_id,
                direction="bot",
                text=reply_text,
                session_id=session_id,
                topic_id=topic_id,
            )
            return

    # CASE 3: Культура конкретна → финальный ответ С RAG
    else:
        print(f"[HYBRID_FLOW_FOLLOWUP] CASE 3: Specific culture - final answer WITH RAG")

        if correction_hint:
            await message.answer(f"💡 {correction_hint}")

        status_mgr = StatusMessageManager(message)
        await status_mgr.start()

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
                skip_rag=False,
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
            print(f"ERROR in ask_consultation_llm: {e}")
            await status_mgr.complete()
            reply_text = (
                "Произошла ошибка при обращении к модели. "
                "Попробуйте отправить вопрос ещё раз."
            )

        streaming_msg = status_mgr.get_streaming_message()
        await status_mgr.complete()

        if creating_message:
            try:
                await creating_message.delete()
            except Exception as e:
                print(f"[followup] Failed to delete creating_message: {e}")

        await finalize_streaming_message(
            streaming_msg, message, reply_text,
            keyboard=get_followup_keyboard(detected_category),
            show_followup_prompt=True,
        )

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

    # Переводим в состояние ожидания выбора типа вопроса (инлайн-кнопки)
    CONSULTATION_STATE[telegram_user_id] = "waiting_followup"


# ==== CALLBACK ОБРАБОТЧИКИ ДЛЯ FOLLOW-UP КНОПОК =====

@router.callback_query(F.data == "followup_type:clarification")
async def handle_followup_clarification_callback(callback: CallbackQuery) -> None:
    """Обработчик кнопки "Задать уточняющий вопрос"."""
    if callback.from_user is None:
        await callback.answer("Ошибка: пользователь не определен")
        return

    telegram_user_id = callback.from_user.id

    # Переводим в состояние ожидания уточняющего вопроса
    CONSULTATION_STATE[telegram_user_id] = "waiting_followup_text"

    if callback.message:
        await callback.message.answer("Напишите уточняющий вопрос:")

    await callback.answer()


@router.callback_query(F.data == "followup_type:new_topic")
async def handle_followup_new_topic_callback(callback: CallbackQuery) -> None:
    """Обработчик кнопки "Задать вопрос по новой теме"."""
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

    # Запрос нового вопроса с инлайн-кнопками примеров
    if callback.message:
        await callback.message.answer(CONSULTATION_ENTRY_TEXT, reply_markup=get_example_questions_keyboard())

    await callback.answer("✅ Начинаем новую тему")


# ==== ОБРАБОТЧИК 3.2: Текст уточняющего вопроса после нажатия кнопки ====

@router.message(
    lambda m: m.from_user is not None
    and CONSULTATION_STATE.get(m.from_user.id) == "waiting_followup_text"
)
async def handle_followup_text(message: Message) -> None:
    """Обработка текста уточняющего вопроса после нажатия кнопки."""
    await process_followup_question_logic(message)


# ==== ОБРАБОТЧИК 4: Корневой обработчик (без активного состояния — НЕ вызывает LLM) ====

@router.message(F.text & ~F.text.startswith("/"))
async def handle_consultation_root(message: Message) -> None:
    """
    Catch-all для текстовых сообщений без активного состояния консультации.
    НЕ вызывает LLM — просто просит выбрать пункт меню.
    """
    from src.keyboards.main.main_menu import get_main_keyboard
    await message.answer(
        "Пожалуйста, выберите пункт из меню.",
        reply_markup=get_main_keyboard(),
    )



# ===== CALLBACK ОБРАБОТЧИКИ ДЛЯ КНОПОК =====

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

    # Запрос нового вопроса с инлайн-кнопками примеров
    if callback.message:
        await callback.message.answer(CONSULTATION_ENTRY_TEXT, reply_markup=get_example_questions_keyboard())

    await callback.answer("✅ Начинаем новую тему")
    print(f"[new_topic_callback] New topic for user {telegram_user_id}")
