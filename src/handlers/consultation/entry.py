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

import asyncio
import logging
import os

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, ReplyKeyboardMarkup

from src.shutdown import shutdown_coordinator

# Репозитории БД
from src.services.db.users_repo import get_or_create_user
from src.services.db.topics_repo import (
    get_or_create_open_topic,
    get_topic_culture,
)
from src.services.db.messages_repo import log_message, mark_message_processing, unmark_message_processing
from src.services.db.moderation_repo import moderation_add
from src.services.db.tokens_repo import has_sufficient_tokens, deduct_tokens, add_tokens, get_token_balance

# Прайсы токенов
from src.pricing import COST_NEW_TOPIC, PHASE_COST, get_complexity_cost, get_phase_display_name, get_next_phase, pluralize_questions

# LLM
from src.services.llm.consultation_llm import ask_consultation_llm, compose_full_question
from src.services.llm.classification_llm import detect_culture_name

# Complexity classification
from src.services.llm.complexity_llm import detect_answer_complexity

logger = logging.getLogger(__name__)

# Feature flag для классификации сложности
FEATURE_COMPLEXITY_ENABLED = os.getenv("FEATURE_COMPLEXITY_ENABLED", "true").lower() in ("true", "1", "yes")
# Обратная совместимость
FEATURE_COMPLEXITY_SHADOW = FEATURE_COMPLEXITY_ENABLED


def detect_phase_from_response(text: str) -> str | None:
    """Определяет фазу из ответа ИИ по ключевым словам в тексте."""
    text_lower = text.lower()
    if "ранняя весна" in text_lower or "весна — начало цветения" in text_lower or "весна-цветение" in text_lower:
        return "весна-цветение"
    if "цветение — окончание плодоношения" in text_lower or "цветение-плодоношение" in text_lower or "цветение — плодоношение" in text_lower:
        return "цветение-плодоношение"
    if "конец плодоношения" in text_lower or "уход в зиму" in text_lower or "плодоношение-зима" in text_lower or "плодоношение — зима" in text_lower:
        return "плодоношение-зима"
    return "весна-цветение"  # fallback — самая распространённая фаза


# Keyboards
from src.keyboards.consultation.common import (
    get_followup_keyboard,
    CONSULTATION_ENTRY_TEXT,
    get_example_questions_keyboard,
    get_complexity_confirm_keyboard,
    get_next_phase_keyboard,
    get_phase_select_keyboard,
    get_topic_select_keyboard,
    get_topup_keyboard,
)

# Утилита для session_id и управление состоянием
from src.handlers.common import (
    build_session_id_from_message,
    CONSULTATION_STATE,
    CONSULTATION_CONTEXT,
    set_consultation_state,
    clear_consultation_state,
)

# Утилита форматирования Markdown → HTML
from src.utils.formatting import markdown_to_telegram_html

# Менеджер статусных сообщений
from src.utils.status_manager import StatusMessageManager


router = Router()

# Промежуточные сообщения "Обрабатываю..." для удаления перед показом прогресс-бара
_PENDING_WAIT_MSGS: dict[int, Message] = {}


def serialize_keyboard(markup) -> dict | None:
    """Конвертирует Aiogram keyboard markup в dict для meta."""
    if markup is None:
        return None
    if isinstance(markup, InlineKeyboardMarkup):
        rows = []
        for row in markup.inline_keyboard:
            rows.append([{"text": btn.text, "callback_data": btn.callback_data} for btn in row])
        return {"keyboard": {"type": "inline", "buttons": rows}}
    if isinstance(markup, ReplyKeyboardMarkup):
        rows = []
        for row in markup.keyboard:
            rows.append([{"text": btn.text} for btn in row])
        return {"keyboard": {"type": "reply", "buttons": rows}}
    return None


async def _log_bot_msg(
    text: str,
    *,
    user_id: int | None = None,
    session_id: str | None = None,
    topic_id: int | None = None,
    telegram_user_id: int | None = None,
    meta: dict | None = None,
) -> None:
    """
    Логирует служебное сообщение бота в таблицу messages.
    Если user_id/session_id/topic_id не переданы — пытается извлечь из CONSULTATION_CONTEXT.
    """
    if telegram_user_id and (not user_id or not session_id):
        ctx = CONSULTATION_CONTEXT.get(telegram_user_id, {})
        user_id = user_id or ctx.get("user_id") or ctx.get("internal_user_id")
        session_id = session_id or ctx.get("session_id") or f"tg:{telegram_user_id}"
        topic_id = topic_id if topic_id is not None else ctx.get("topic_id")
    # Fallback: получить user_id из БД по telegram_user_id
    if not user_id and telegram_user_id:
        try:
            user_id = await get_or_create_user(
                telegram_user_id=telegram_user_id,
                username=None, first_name=None, last_name=None,
            )
            session_id = session_id or f"tg:{telegram_user_id}"
        except Exception:
            return
    if not user_id or not session_id:
        return
    try:
        await log_message(
            user_id=user_id,
            direction="bot",
            text=text,
            session_id=session_id,
            topic_id=topic_id,
            meta=meta,
        )
    except Exception as e:
        logger.warning(f"Failed to log bot service message: {e}")


async def _log_user_callback(
    text: str,
    *,
    callback: CallbackQuery,
    topic_id: int | None = None,
) -> None:
    """
    Логирует нажатие inline-кнопки пользователем в таблицу messages.
    Извлекает user_id/session_id/topic_id из CONSULTATION_CONTEXT (аналогично _log_bot_msg).
    """
    if callback.from_user is None:
        return
    telegram_user_id = callback.from_user.id

    ctx = CONSULTATION_CONTEXT.get(telegram_user_id, {})
    user_id = ctx.get("user_id") or ctx.get("internal_user_id")
    session_id = ctx.get("session_id") or f"tg:{telegram_user_id}"
    if topic_id is None:
        topic_id = ctx.get("topic_id")

    # Fallback: получить user_id из БД
    if not user_id:
        try:
            user_id = await get_or_create_user(
                telegram_user_id=telegram_user_id,
                username=callback.from_user.username,
                first_name=callback.from_user.first_name,
                last_name=callback.from_user.last_name,
            )
        except Exception:
            return

    if not user_id:
        return

    try:
        await log_message(
            user_id=user_id,
            direction="user",
            text=text,
            session_id=session_id,
            topic_id=topic_id,
            meta={"type": "callback", "callback_data": callback.data},
        )
    except Exception as e:
        logger.warning(f"Failed to log user callback: {e}")


async def _send_insufficient_tokens_error(
    *,
    target: Message | CallbackQuery,
    user_id: int,
    cost: int,
    telegram_user_id: int,
    session_id: str | None = None,
    topic_id: int | None = None,
    is_callback: bool = False,
) -> None:
    """
    Отправляет стандартную ошибку 'недостаточно токенов' пользователю.
    Используется когда deduct_tokens() возвращает False.
    """
    balance = await get_token_balance(user_id)
    insuf_text = (
        f"Не удалось списать токены — баланс изменился.\n\n"
        f"Стоимость: {pluralize_questions(cost)}\n"
        f"Ваш баланс: {pluralize_questions(balance)}\n\n"
        f"Для пополнения перейдите в «Мой профиль» → «Пополнить баланс»."
    )
    topup_kb = get_topup_keyboard()
    if is_callback:
        cb = target
        await cb.answer("Недостаточно токенов")
        if cb.message:
            await cb.message.answer(insuf_text, reply_markup=topup_kb)
            await _log_bot_msg(insuf_text, telegram_user_id=telegram_user_id)
    else:
        msg = target
        await msg.answer(insuf_text, reply_markup=topup_kb)
        await _log_bot_msg(
            insuf_text,
            user_id=user_id,
            session_id=session_id,
            telegram_user_id=telegram_user_id,
            topic_id=topic_id,
        )

    # Авто-переход в CRM: * → trial_ended (токены кончились)
    try:
        from src.services.db.funnel_repo import auto_move_client_in_crm
        asyncio.create_task(auto_move_client_in_crm(user_id, 'trial_ended'))
    except Exception as e:
        logger.warning(f"Auto-move to trial_ended failed: {e}")


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
    question_msg_id = context.get("question_msg_id")

    # Извлекаем complexity_result из контекста (shadow mode)
    cr = context.get("complexity_result")
    _complexity_kwargs = {}
    if cr:
        _complexity_kwargs = {
            "complexity_tier": cr.get("tier"),
            "complexity_metadata": cr.get("metadata"),
            "complexity_classification_cost_usd": cr.get("cost_usd", 0.0),
            "complexity_classification_tokens": cr.get("tokens", 0),
        }

    # Удаляем промежуточное "Обрабатываю..." перед показом прогресс-бара
    _wait = _PENDING_WAIT_MSGS.pop(telegram_user_id, None)
    if _wait:
        try:
            await _wait.delete()
        except Exception:
            pass

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
                **_complexity_kwargs,
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
            _add_clarification(context, "culture", reply_text)
            await set_consultation_state(telegram_user_id, "waiting_clarification_answer")

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

        # Phase параметры из контекста
        _phase_mode = context.get("phase_mode")
        _phase_key = context.get("phase_key")
        _phase_topic = context.get("phase_topic")
        _is_last_phase = context.get("is_last_phase", False)
        _phase_number = context.get("phase_number", 0)

        # Собираем phase kwargs для LLM
        # NB: _phase_key может быть None (ИИ сам выбирает фазу) — это нормально
        _phase_kwargs = {}
        if _phase_mode and _phase_topic:
            _phase_kwargs = {
                "phase_mode": _phase_mode,
                "phase_key": _phase_key,  # None = ИИ сам выберет фазу
                "phase_topic": _phase_topic,
                "is_last_phase": _is_last_phase,
                "phase_number": _phase_number,
            }

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
                **_complexity_kwargs,
                **_phase_kwargs,
            )
        except Exception as e:
            print(f"ERROR in ask_consultation_llm: {e}")
            await status_mgr.complete()
            raise  # Пробрасываем — unified_entry вернёт токены

        # Забираем стриминг-сообщение ДО complete() чтобы переиспользовать
        streaming_msg = status_mgr.get_streaming_message()
        await status_mgr.complete()

        # === Enforcement длины ответа ===
        cr_tier = _complexity_kwargs.get("complexity_tier")
        _is_extended = cr_tier in ("extended_non_phase",) or _phase_mode in ("seasonal_phase", "single_phase")
        if _is_extended:
            # Расширенный / фазовый ответ — ограничиваем макс 2 сообщения
            reply_text = _enforce_two_message_format(reply_text)
        # Стандартный ответ — не обрезаем, LLM сам контролирует длину через промпт

        # Определяем клавиатуру: фазовая (любой phase_mode) или стандартная
        if _phase_mode in ("seasonal_phase", "single_phase"):
            # Определяем фазу: если phase_key задан — используем его, иначе определяем из ответа
            effective_phase_key = _phase_key
            if not effective_phase_key and reply_text:
                # ИИ сам выбрал фазу — определяем из текста ответа
                effective_phase_key = detect_phase_from_response(reply_text)
                print(f"[_process_culture_and_respond] Auto-detected phase from response: {effective_phase_key}")

            if effective_phase_key:
                all_phases = ("весна-цветение", "цветение-плодоношение", "плодоношение-зима")
                next_phase = get_next_phase(effective_phase_key)

                # Обновляем контекст для фазового продолжения
                existing_ctx = CONSULTATION_CONTEXT.get(telegram_user_id, {})
                if existing_ctx.get("_phase_continuation"):
                    # Обновляем phases_delivered с определённой фазой
                    phases_delivered = existing_ctx.get("phases_delivered", [])
                    if effective_phase_key not in phases_delivered:
                        phases_delivered.append(effective_phase_key)
                    existing_ctx["current_phase"] = effective_phase_key
                    existing_ctx["next_phase"] = next_phase
                    existing_ctx["phases_delivered"] = phases_delivered
                    CONSULTATION_CONTEXT[telegram_user_id] = existing_ctx
                    # Есть ли ещё непройденные фазы?
                    delivered_set = set(phases_delivered)
                    has_more_phases = any(p not in delivered_set for p in all_phases)
                else:
                    CONSULTATION_CONTEXT[telegram_user_id] = {
                        **existing_ctx,
                        "_phase_continuation": True,
                        "current_phase": effective_phase_key,
                        "next_phase": next_phase,
                        "phases_delivered": [effective_phase_key],
                        "topic": _phase_topic or category,
                        "question_text": composed_q,
                        "internal_user_id": user_id,
                        "category": category,
                        "culture": culture,
                        "classification_cost": context["classification_cost_usd"],
                        "classification_tokens": context["classification_tokens"],
                        "complexity_result": cr,
                        "telegram_user_id": telegram_user_id,
                    }
                    # Первая фаза — всегда показываем кнопку выбора фазы
                    # (даже если это последняя фаза, у пользователя ещё есть 2 непройденные)
                    has_more_phases = True

                if has_more_phases:
                    next_phase_display = get_phase_display_name(next_phase) if next_phase else ""
                    response_keyboard = get_next_phase_keyboard(next_phase_display)
                else:
                    # Все фазы пройдены — клавиатура без кнопки "Следующая фаза"
                    response_keyboard = get_followup_keyboard(category)
                next_state = "waiting_phase_continue"
            else:
                # Не удалось определить фазу — стандартная клавиатура
                response_keyboard = get_followup_keyboard(category)
                next_state = "waiting_followup"
        else:
            # Стандартная клавиатура (без фаз)
            response_keyboard = get_followup_keyboard(category)
            next_state = "waiting_followup"

        # Финализируем: edit стриминг-сообщения с полным отформатированным текстом
        await finalize_streaming_message(
            streaming_msg, message, reply_text,
            keyboard=response_keyboard,
            show_followup_prompt=True,
            force_two_parts=_is_extended,
        )

        # Логируем ответ бота
        await log_message(
            user_id=user_id,
            direction="bot",
            text=reply_text,
            session_id=session_id,
            topic_id=topic_id,
        )
        # Снимаем флаг processing — ответ успешно отправлен
        if question_msg_id:
            await unmark_message_processing(question_msg_id)

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

        # Переводим в соответствующее состояние
        await set_consultation_state(telegram_user_id, next_state)

        # Авто-переход в CRM: new → tried (получил консультацию)
        try:
            from src.services.db.funnel_repo import auto_move_client_in_crm
            asyncio.create_task(auto_move_client_in_crm(user_id, 'tried'))
        except Exception as e:
            logger.warning(f"Auto-move to tried failed: {e}")


# Константа: максимальная длина сообщения в Telegram
TELEGRAM_MAX_MESSAGE_LENGTH = 4096


def _truncate_to_single_message(text: str, max_chars: int = 4070) -> str:
    """Обрезает markdown-текст чтобы HTML-конверсия уместилась в одно сообщение Telegram."""
    html = markdown_to_telegram_html(text)
    if len(html) <= max_chars:
        return text
    paragraphs = text.split("\n\n")
    result = ""
    for para in paragraphs:
        candidate = result + ("\n\n" if result else "") + para
        if len(markdown_to_telegram_html(candidate)) > max_chars - 50:
            break
        result = candidate
    return result if result else text[:max_chars - 200]


def _enforce_two_message_format(text: str) -> str:
    """Обрезает текст чтобы после HTML-конверсии получилось максимум 2 сообщения Telegram."""
    html = markdown_to_telegram_html(text)
    # Два сообщения по 4070 символов каждое, минус запас на [Часть X/Y] префиксы
    max_total = 4070 * 2 - 100
    if len(html) <= max_total:
        return text
    paragraphs = text.split("\n\n")
    result = ""
    for para in paragraphs:
        candidate = result + ("\n\n" if result else "") + para
        if len(markdown_to_telegram_html(candidate)) > max_total:
            break
        result = candidate
    return result if result else text[:max_total - 200]


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
    force_two_parts: bool = False,
) -> None:
    """
    Финализирует стриминг-сообщение: делает edit с полным отформатированным текстом.

    Если текст короткий (≤4070) — edit существующего сообщения (мгновенно).
    Если текст длинный — удаляем стриминг-сообщение и отправляем частями.
    Если streaming_msg=None — fallback на обычную отправку.
    Если force_two_parts=True — принудительно разбиваем на 2 части (для расширенных ответов).

    Args:
        streaming_msg: Стриминг-сообщение из StatusMessageManager.get_streaming_message()
        message: Оригинальное сообщение пользователя (для fallback ответа)
        text: Полный текст ответа (markdown)
        keyboard: Клавиатура для последнего сообщения
        show_followup_prompt: Показывать ли подсказку "Выберите вариант следующего вопроса"
        force_two_parts: Принудительно разбить на 2 сообщения (для расширенных ответов)
    """
    html_text = markdown_to_telegram_html(text)
    parts = split_long_message(html_text, max_length=4070)

    # Принудительное разбиение на 2 части для расширенных ответов
    if force_two_parts and len(parts) == 1 and len(html_text) > 2000:
        mid = len(html_text) // 2
        # Ищем ближайший разрыв абзаца к середине
        split_pos = html_text.rfind("\n\n", 0, mid + 500)
        if split_pos == -1 or split_pos < len(html_text) // 4:
            split_pos = html_text.rfind("\n", 0, mid + 500)
        if split_pos > 0:
            parts = [html_text[:split_pos].strip(), html_text[split_pos:].strip()]

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
        # Если parts уже разбиты (force_two_parts или split_long_message), отправляем их напрямую
        if len(parts) > 1:
            for i, part in enumerate(parts, 1):
                part_text = f"[Часть {i}/{len(parts)}]\n\n{part}"
                await message.answer(part_text)
        else:
            await send_long_message(message, text)

    # Показываем кнопки отдельным сообщением (всегда, если есть keyboard)
    if keyboard:
        prompt_text = "Выберите вариант следующего вопроса:" if show_followup_prompt else "Выберите действие:"
        await message.answer(prompt_text, reply_markup=keyboard)
        if message.from_user:
            await _log_bot_msg(prompt_text, telegram_user_id=message.from_user.id, meta=serialize_keyboard(keyboard))


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

    # Логируем вопрос пользователя сразу (до классификации),
    # чтобы он был виден в ленте админки
    question_msg_id = await log_message(
        user_id=internal_user_id,
        direction="user",
        text=question_text,
        session_id=f"tg:{telegram_user_id}",
    )
    # Флаг: вопрос начал обрабатываться. Снимается после отправки ответа.
    # Используется recovery при рестарте бота.
    await mark_message_processing(question_msg_id)

    # Graceful shutdown: регистрируем задачу для отслеживания.
    # НЕ делаем ранний выход — при shutdown мы ЖДЁМ завершения всех handler-задач,
    # чтобы пользователь получил ответ до остановки бота.
    current_task = asyncio.current_task()
    if current_task:
        shutdown_coordinator.register_task(current_task)

    # Быстрая проверка баланса (минимум 1 токен) — без LLM-вызова
    if not await has_sufficient_tokens(internal_user_id, 1):
        balance = await get_token_balance(internal_user_id)
        insufficient_text = (
            f"У вас недостаточно токенов для консультации.\n\n"
            f"Ваш баланс: {pluralize_questions(balance)}\n\n"
            f"Для пополнения перейдите в «Мой профиль» → «Пополнить баланс»."
        )
        await message.answer(insufficient_text, reply_markup=get_topup_keyboard())
        await _log_bot_msg(insufficient_text, user_id=internal_user_id, session_id=f"tg:{telegram_user_id}", telegram_user_id=telegram_user_id)
        # Авто-переход в CRM: * → trial_ended (токены кончились)
        try:
            from src.services.db.funnel_repo import auto_move_client_in_crm
            asyncio.create_task(auto_move_client_in_crm(internal_user_id, 'trial_ended'))
        except Exception as e:
            logger.warning(f"Auto-move to trial_ended failed: {e}")
        await clear_consultation_state(telegram_user_id)
        return

    # Автоматически определяем категорию + культуру
    from src.services.llm.classification_llm import detect_category_and_culture
    category, culture, correction_hint, classification_cost, classification_tokens = await detect_category_and_culture(question_text)

    print(f"[unified_entry] Detected category={category!r}, culture={culture!r}, correction={correction_hint!r}, cost=${classification_cost:.6f}, tokens={classification_tokens}")

    # Классификация сложности вопроса
    complexity_result = None
    if FEATURE_COMPLEXITY_SHADOW:
        try:
            complexity_result = await detect_answer_complexity(
                question=question_text,
                category=category,
                culture=culture,
            )
            print(
                f"[unified_entry] Complexity: tier={complexity_result['tier']}, "
                f"phase={complexity_result['metadata'].get('current_phase')}, "
                f"cost=${complexity_result['cost_usd']:.6f}"
            )
        except Exception as e:
            logger.warning(f"[unified_entry] Complexity classification failed: {e}")

    # Определяем стоимость по tier сложности (или fallback на категорию)
    tier = complexity_result["tier"] if complexity_result else "short_answer"
    # turnkey_solution временно отключен — трактуем как long_answer
    if tier == "turnkey_solution":
        tier = "long_answer"
    if tier == "long_answer":
        cost = get_complexity_cost("long_answer")  # 2
    else:
        cost = COST_NEW_TOPIC  # 1

    # Проверка баланса (минимум 1 токен для любого варианта)
    if not await has_sufficient_tokens(internal_user_id, 1):
        balance = await get_token_balance(internal_user_id)
        insufficient_text2 = (
            f"У вас недостаточно токенов для консультации.\n\n"
            f"Ваш баланс: {pluralize_questions(balance)}\n\n"
            f"Для пополнения перейдите в «Мой профиль» → «Пополнить баланс»."
        )
        await message.answer(insufficient_text2, reply_markup=get_topup_keyboard())
        await _log_bot_msg(insufficient_text2, user_id=internal_user_id, session_id=f"tg:{telegram_user_id}", telegram_user_id=telegram_user_id)
        await clear_consultation_state(telegram_user_id)
        return

    # === ПЕРЕХВАТ: long_answer / turnkey_solution → подтверждение стоимости ===
    if tier in ("long_answer", "turnkey_solution") and complexity_result:
        balance = await get_token_balance(internal_user_id)
        metadata = complexity_result.get("metadata", {})
        is_multi_topic = metadata.get("multi_topic", False)
        topics_list = metadata.get("topics", [])

        # === Multi-topic: просим выбрать одну тему ===
        if is_multi_topic and len(topics_list) > 1 and tier == "long_answer":
            CONSULTATION_CONTEXT[telegram_user_id] = {
                "_pending_topic_select": True,
                "question_text": question_text,
                "question_msg_id": question_msg_id,
                "internal_user_id": internal_user_id,
                "category": category,
                "culture": culture,
                "correction_hint": correction_hint,
                "classification_cost": classification_cost,
                "classification_tokens": classification_tokens,
                "complexity_result": complexity_result,
                "tier": tier,
                "telegram_user_id": telegram_user_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
            }
            await set_consultation_state(telegram_user_id, "waiting_topic_select")

            topics_str = ", ".join(topics_list)
            multi_topic_text = (
                f"Ваш вопрос затрагивает несколько тем: {topics_str}.\n\n"
                f"Я могу ответить по одной теме за раз. Выберите тему:"
            )
            kb = get_topic_select_keyboard(topics_list)
            await message.answer(multi_topic_text, reply_markup=kb)
            await _log_bot_msg(multi_topic_text, user_id=internal_user_id, session_id=f"tg:{telegram_user_id}", telegram_user_id=telegram_user_id, meta=serialize_keyboard(kb))
            print(f"[unified_entry] Multi-topic detected: {topics_list}, showing topic selection")
            return

        # Сохраняем контекст для callback-обработчика
        CONSULTATION_CONTEXT[telegram_user_id] = {
            "_pending_complexity": True,
            "question_text": question_text,
            "question_msg_id": question_msg_id,
            "internal_user_id": internal_user_id,
            "category": category,
            "culture": culture,
            "correction_hint": correction_hint,
            "classification_cost": classification_cost,
            "classification_tokens": classification_tokens,
            "complexity_result": complexity_result,
            "tier": tier,
            "telegram_user_id": telegram_user_id,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
        }
        await set_consultation_state(telegram_user_id, "waiting_complexity_confirm")

        # Персонализированное сообщение от LLM (fallback на шаблон)
        confirm_msg = complexity_result.get("confirm_message", "")
        phase_label = complexity_result.get("phase_button_label", "")

        # long_answer (Тип B или Тип C)
        has_enough_for_plan = await has_sufficient_tokens(internal_user_id, PHASE_COST)
        personal_text = confirm_msg or "Ваш вопрос предполагает развёрнутый план."

        if not has_enough_for_plan:
            insuf_plan_text = (
                f"{personal_text}\n\n"
                f"План на фазу стоит {pluralize_questions(PHASE_COST)}, "
                f"ваш баланс: {pluralize_questions(balance)} — недостаточно.\n\n"
                f"Для пополнения перейдите в «Мой профиль» → «Пополнить баланс»."
            )
            kb = get_complexity_confirm_keyboard(
                "long_answer_insufficient", 1, phase_button_label=phase_label,
            )
            await message.answer(insuf_plan_text, reply_markup=kb)
            await _log_bot_msg(insuf_plan_text, user_id=internal_user_id, session_id=f"tg:{telegram_user_id}", telegram_user_id=telegram_user_id, meta=serialize_keyboard(kb))
        else:
            choose_format_text = (
                f"{personal_text}\n\n"
                f"{phase_label or 'План на ближайшую фазу'} — {pluralize_questions(PHASE_COST)}"
            )
            kb = get_complexity_confirm_keyboard(
                "long_answer", PHASE_COST, phase_button_label=phase_label,
            )
            await message.answer(choose_format_text, reply_markup=kb)
            await _log_bot_msg(choose_format_text, user_id=internal_user_id, session_id=f"tg:{telegram_user_id}", telegram_user_id=telegram_user_id, meta=serialize_keyboard(kb))

        print(f"[unified_entry] Showing complexity confirmation for tier={tier}")
        return

    # === short_answer: показываем выбор формата ПЕРЕД ответом ===
    if complexity_result:
        balance = await get_token_balance(internal_user_id)

        # Сохраняем контекст для callback-обработчика
        CONSULTATION_CONTEXT[telegram_user_id] = {
            "_pending_complexity": True,
            "_simple_question_choice": True,  # Флаг: это выбор для простого вопроса
            "question_text": question_text,
            "question_msg_id": question_msg_id,
            "internal_user_id": internal_user_id,
            "category": category,
            "culture": culture,
            "correction_hint": correction_hint,
            "classification_cost": classification_cost,
            "classification_tokens": classification_tokens,
            "complexity_result": complexity_result,
            "tier": "short_answer",
            "telegram_user_id": telegram_user_id,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
        }
        await set_consultation_state(telegram_user_id, "waiting_complexity_confirm")

        # Проверяем хватает ли на расширенный ответ (2 токена)
        has_enough_extended = await has_sufficient_tokens(internal_user_id, PHASE_COST)

        from src.keyboards.consultation.common import get_simple_question_choice_keyboard
        kb = get_simple_question_choice_keyboard(
            standard_cost=COST_NEW_TOPIC,
            extended_cost=PHASE_COST,
        )

        # Новый шаблон сообщения выбора формата
        topic_case = complexity_result.get("topic_in_correct_case", "")
        if topic_case:
            choice_text = (
                f"Тема {topic_case} достаточно емкая.\n\n"
                "<b>Я могу дать стандартный ответ</b> - в него не войдут некоторые мелочи, "
                "но все будет понятно👍\n\n"
                "<b>А так же расширенный ответ - если Вы хотите разобрать эту тему детально</b>✅\n\n"
                "Выберите в меню как мне ответить👇"
            )
        else:
            choice_text = "Выберите в меню как мне ответить👇"
        if not has_enough_extended:
            choice_text += f"\n\n⚠️ Для расширенного ответа требуется {pluralize_questions(PHASE_COST)}."

        await message.answer(choice_text, reply_markup=kb, parse_mode="HTML")
        await _log_bot_msg(choice_text, user_id=internal_user_id, session_id=f"tg:{telegram_user_id}", telegram_user_id=telegram_user_id, meta=serialize_keyboard(kb))

        print(f"[unified_entry] Showing simple question choice keyboard (phase_eligible={complexity_result.get('phase_eligible', False)})")
        return

    # Fallback: классификатор не сработал — старое поведение (1 токен, ответить сразу)
    deduction_ok = await deduct_tokens(
        internal_user_id,
        cost,
        "new_topic",
        f"Консультация: {category}"
    )
    if not deduction_ok:
        await _send_insufficient_tokens_error(
            target=message,
            user_id=internal_user_id,
            cost=cost,
            telegram_user_id=telegram_user_id,
            session_id=f"tg:{telegram_user_id}",
        )
        await clear_consultation_state(telegram_user_id)
        return

    # Сохраняем question_msg_id для привязки к топику после его создания
    ctx = CONSULTATION_CONTEXT.get(telegram_user_id, {})
    ctx["question_msg_id"] = question_msg_id
    CONSULTATION_CONTEXT[telegram_user_id] = ctx

    # Маршрутизация на основе категории
    await _route_to_handler(
        message=message,
        internal_user_id=internal_user_id,
        telegram_user_id=telegram_user_id,
        category=category,
        culture=culture,
        question_text=question_text,
        classification_cost=classification_cost,
        classification_tokens=classification_tokens,
        correction_hint=correction_hint,
        complexity_result=complexity_result,
        cost=cost,
    )


async def _route_to_handler(
    message: Message,
    internal_user_id: int,
    telegram_user_id: int,
    category: str,
    culture: str,
    question_text: str,
    classification_cost: float,
    classification_tokens: int,
    correction_hint: str | None,
    complexity_result: dict | None,
    cost: int,
    # Phase mode parameters
    phase_mode: str | None = None,
    phase_key: str | None = None,
    phase_topic: str | None = None,
    is_last_phase: bool = False,
    phase_number: int = 0,
) -> None:
    """Маршрутизация на обработчик категории с обработкой ошибок."""
    # Если message.from_user — бот (вызов из callback), передаём telegram_user_id отдельно
    is_from_callback = (message.from_user is None or message.from_user.id != telegram_user_id)
    tg_override = telegram_user_id if is_from_callback else None

    try:
        if category == "питание растений":
            print(f"[unified_entry] Routing to NUTRITION handler (phase_mode={phase_mode})")

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
                complexity_result=complexity_result,
                telegram_user_id_override=tg_override,
                phase_mode=phase_mode,
                phase_key=phase_key,
                phase_topic=phase_topic,
                is_last_phase=is_last_phase,
                phase_number=phase_number,
            )
        else:
            print(f"[unified_entry] Routing to GENERAL handler (phase_mode={phase_mode})")

            await process_general_consultation(
                message=message,
                user_id=internal_user_id,
                category=category,
                culture=culture,
                root_question=question_text,
                classification_cost_usd=classification_cost,
                classification_tokens=classification_tokens,
                correction_hint=correction_hint,
                complexity_result=complexity_result,
                telegram_user_id_override=tg_override,
                phase_mode=phase_mode,
                phase_key=phase_key,
                phase_topic=phase_topic,
                is_last_phase=is_last_phase,
                phase_number=phase_number,
            )
    except Exception as e:
        print(f"[unified_entry] ERROR: {e}, returning questions to user {internal_user_id}")
        await add_tokens(internal_user_id, cost, "refund", "Возврат: ошибка модели")
        error_refund_text = "Произошла ошибка при обработке запроса. Вопросы возвращены на ваш баланс. Попробуйте ещё раз."
        await message.answer(error_refund_text)
        await _log_bot_msg(error_refund_text, user_id=internal_user_id, session_id=f"tg:{telegram_user_id}", telegram_user_id=telegram_user_id)


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
    await clear_consultation_state(user.id)

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


@router.message(
    lambda m: m.from_user is not None
    and CONSULTATION_STATE.get(m.from_user.id) == "waiting_root"
)
async def handle_waiting_root(message: Message) -> None:
    """
    Обработка первого вопроса после выбора категории (кроме питания).
    Категории: Посадка и уход, Защита растений, Улучшение почвы, Подбор сорта, Другая тема.
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
    Обрабатывает общую консультацию (не питание растений).

    Логика:
    - CASE 1: Культура неясна → уточняющие вопросы БЕЗ RAG, БЕЗ compose
    - CASE 2: УДАЛЕН (default летняя)
    - CASE 3: Культура конкретна → финальный ответ С RAG, С compose
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

    # Создаем или получаем топик
    topic_id = await get_or_create_open_topic(
        user_id=user_id,
        session_id=session_id,
    )

    # Обновляем категорию и культуру в БД
    from src.services.db.topics_repo import set_topic_culture, set_topic_category
    await set_topic_category(topic_id, category)
    await set_topic_culture(topic_id, culture)

    # Привязываем ВСЕ промежуточные сообщения к топику
    # (вопрос + "Предлагаю формат" + кнопки — залогированы без topic_id)
    _q_msg_id = CONSULTATION_CONTEXT.get(telegram_user_id, {}).get("question_msg_id")
    if _q_msg_id:
        try:
            from src.services.db.messages_repo import attach_pending_messages_to_topic
            await attach_pending_messages_to_topic(user_id, topic_id, since_msg_id=_q_msg_id)
        except Exception:
            pass

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

    # Сохраняем результат классификации сложности в контексте
    if complexity_result:
        context["complexity_result"] = complexity_result

    # Сохраняем phase параметры в контексте
    if phase_mode:
        context["phase_mode"] = phase_mode
        context["phase_key"] = phase_key
        context["phase_topic"] = phase_topic
        context["is_last_phase"] = is_last_phase
        context["phase_number"] = phase_number

    print(f"[process_general] category={category!r}, culture={culture!r}, phase_mode={phase_mode}")

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
    # Graceful shutdown: регистрируем задачу
    current_task = asyncio.current_task()
    if current_task:
        shutdown_coordinator.register_task(current_task)

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
        err_text = "Произошла ошибка. Попробуйте задать вопрос заново."
        await message.answer(err_text)
        await _log_bot_msg(err_text, telegram_user_id=telegram_user_id)
        return

    user_id = context["user_id"]
    topic_id = context["topic_id"]
    session_id = context["session_id"]
    root_question = context["root_question"]
    old_culture = context["culture"]

    # Сохраняем ответ пользователя в последнее уточнение
    _set_clarification_answer(context, variety_answer)

    # Сразу показываем пользователю что бот обрабатывает ответ
    _PENDING_WAIT_MSGS[telegram_user_id] = await message.answer("🔄 Обрабатываю ваш ответ...")

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
    # Graceful shutdown: регистрируем задачу
    current_task = asyncio.current_task()
    if current_task:
        shutdown_coordinator.register_task(current_task)

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
        err_text2 = "Произошла ошибка. Попробуйте задать вопрос заново."
        await message.answer(err_text2)
        await _log_bot_msg(err_text2, telegram_user_id=telegram_user_id)
        return

    user_id = context["user_id"]
    topic_id = context["topic_id"]
    session_id = context["session_id"]
    root_question = context["root_question"]

    # Сохраняем ответ пользователя в последнее уточнение
    _set_clarification_answer(context, clarification_answer)

    # Сразу показываем пользователю что бот обрабатывает ответ
    _PENDING_WAIT_MSGS[telegram_user_id] = await message.answer("🔄 Обрабатываю ваш ответ...")

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


# ==== ОБРАБОТЧИК: Текст в состоянии ожидания подтверждения сложности ====

@router.message(
    lambda m: m.from_user is not None
    and CONSULTATION_STATE.get(m.from_user.id) == "waiting_complexity_confirm"
)
async def handle_complexity_confirm_text(message: Message) -> None:
    """Блокирует текстовый ввод пока ждём нажатия кнопки подтверждения сложности."""
    block_text = "Пожалуйста, выберите один из вариантов выше, или нажмите «Отмена» для отмены консультации."
    await message.answer(block_text)
    if message.from_user:
        await _log_bot_msg(block_text, telegram_user_id=message.from_user.id)


# ==== ОБРАБОТЧИК 3: Follow-up вопросы (состояние waiting_followup) ====

@router.message(
    lambda m: m.from_user is not None
    and CONSULTATION_STATE.get(m.from_user.id) == "waiting_followup"
)
async def handle_followup_question(message: Message) -> None:
    """
    БЛОКИРУЕТ прямой текстовый ввод в состоянии waiting_followup.
    Требует нажатия инлайн-кнопки "Уточняющий вопрос" или "Новая тема".
    Сохраняет написанный текст для автоподгрузки после нажатия кнопки.
    """
    user = message.from_user
    if user is None:
        return

    # Сохраняем сообщение — чтобы пользователю не пришлось писать заново
    from src.handlers.common import PENDING_USER_MESSAGES
    PENDING_USER_MESSAGES[user.id] = message

    followup_block_text = (
        "Пожалуйста, выберите один из вариантов:\n"
        "• <b>Задать уточняющий вопрос</b> — продолжить текущую тему\n"
        "• <b>Задать вопрос по новой теме</b> — начать новую консультацию"
    )
    kb = get_followup_keyboard()
    await message.answer(followup_block_text, reply_markup=kb)
    await _log_bot_msg(followup_block_text, telegram_user_id=user.id, meta=serialize_keyboard(kb))


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
    # Graceful shutdown: регистрируем задачу
    current_task = asyncio.current_task()
    if current_task:
        shutdown_coordinator.register_task(current_task)

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

        # Короткие утвердительные сообщения не могут сменить тему — пропускаем классификацию
        SHORT_FOLLOWUP_TRIGGERS = {
            "давай", "да", "ок", "окей", "хорошо", "продолжай", "продолжи",
            "и что", "что ещё", "ещё", "дальше", "понял", "понятно", "ясно",
            "конечно", "угу", "ага", "го", "пиши", "говори", "рассказывай",
        }
        user_text_lower = user_text.strip().lower()
        is_short_affirmative = (
            len(user_text.strip()) < 20
            and user_text_lower in SHORT_FOLLOWUP_TRIGGERS
        )

        if is_short_affirmative:
            print(f"[followup] Short affirmative message — treating as same_topic, skipping classification")
            topic_change = "same_topic"
            new_culture = culture
            new_correction_hint = None
        elif culture in ("не определено", "общая информация"):
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

        if topic_change == "clear_change":
            print(f"[followup] CLEAR CULTURE CHANGE - creating new topic with same category")
            creating_msg_text = "📝 Создается новая тема консультации..."
            creating_message = await message.answer(creating_msg_text)
            await _log_bot_msg(creating_msg_text, user_id=user_id, session_id=session_id, topic_id=topic_id)
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

    # ПОСЛЕ логирования: классификация сложности и списание для follow-up (НЕ смена темы)
    _followup_complexity_kwargs = {}
    if is_potential_followup and not topic_changed:
        # Классификация сложности для определения стоимости follow-up
        followup_complexity = None
        if FEATURE_COMPLEXITY_ENABLED:
            try:
                followup_complexity = await detect_answer_complexity(
                    question=user_text,
                    category=detected_category,
                    culture=culture,
                )
                _followup_complexity_kwargs = {
                    "complexity_tier": followup_complexity.get("tier"),
                    "complexity_metadata": followup_complexity.get("metadata"),
                    "complexity_classification_cost_usd": followup_complexity.get("cost_usd", 0.0),
                    "complexity_classification_tokens": followup_complexity.get("tokens", 0),
                }
                print(
                    f"[followup] Complexity: tier={followup_complexity['tier']}, "
                    f"phase={followup_complexity['metadata'].get('current_phase')}, "
                    f"cost=${followup_complexity['cost_usd']:.6f}"
                )
            except Exception as e:
                logger.warning(f"[followup] Complexity classification failed: {e}")

        followup_tier = followup_complexity["tier"] if followup_complexity else "short_answer"
        # turnkey_solution временно отключен — трактуем как long_answer
        if followup_tier == "turnkey_solution":
            followup_tier = "long_answer"

        # long_answer → показать подтверждение (аналогично новому топику)
        if followup_tier == "long_answer" and followup_complexity:
            balance = await get_token_balance(user_id)
            phase_label = followup_complexity.get("phase_button_label", "")
            confirm_msg = followup_complexity.get("confirm_message", "")

            # Сохраняем контекст для callback (аналогично run_consultation_pipeline)
            CONSULTATION_CONTEXT[telegram_user_id] = {
                "_pending_complexity": True,
                "question_text": user_text,
                "internal_user_id": user_id,
                "category": detected_category,
                "culture": culture,
                "correction_hint": correction_hint,
                "classification_cost": classification_cost_usd,
                "classification_tokens": classification_tokens,
                "complexity_result": followup_complexity,
                "tier": followup_tier,
                "telegram_user_id": telegram_user_id,
                "_is_followup": True,
                "topic_id": topic_id,
                "session_id": session_id,
            }
            await set_consultation_state(telegram_user_id, "waiting_complexity_confirm")

            has_enough_for_plan = await has_sufficient_tokens(user_id, PHASE_COST)
            personal_text = confirm_msg or "Ваш уточняющий вопрос предполагает развёрнутый план."

            if not has_enough_for_plan:
                fu_insuf_text = (
                    f"{personal_text}\n\n"
                    f"План на фазу стоит {pluralize_questions(PHASE_COST)}, "
                    f"ваш баланс: {pluralize_questions(balance)} — недостаточно.\n\n"
                    f"Для пополнения перейдите в «Мой профиль» → «Пополнить баланс»."
                )
                kb = get_complexity_confirm_keyboard(
                    "long_answer_insufficient", 1, phase_button_label=phase_label,
                )
                await message.answer(fu_insuf_text, reply_markup=kb)
                await _log_bot_msg(fu_insuf_text, user_id=user_id, session_id=session_id, topic_id=topic_id, meta=serialize_keyboard(kb))
            else:
                fu_choose_text = (
                    f"{personal_text}\n\n"
                    f"{phase_label or 'План на ближайшую фазу'} — {pluralize_questions(PHASE_COST)}"
                )
                kb = get_complexity_confirm_keyboard(
                    "long_answer", PHASE_COST, phase_button_label=phase_label,
                )
                await message.answer(fu_choose_text, reply_markup=kb)
                await _log_bot_msg(fu_choose_text, user_id=user_id, session_id=session_id, topic_id=topic_id, meta=serialize_keyboard(kb))

            print(f"[followup] Showing complexity confirmation for tier={followup_tier}")
            return

        # phase_eligible: сразу отвечаем кратко, предложим фазы после ответа

        # short_answer → списываем 1 токен сразу (атомарная проверка + списание)
        followup_cost = COST_NEW_TOPIC  # 1
        deduction_ok = await deduct_tokens(user_id, followup_cost, "follow_up", f"Уточняющий вопрос: {detected_category}")
        if not deduction_ok:
            await _send_insufficient_tokens_error(
                target=message,
                user_id=user_id,
                cost=followup_cost,
                telegram_user_id=telegram_user_id,
                session_id=session_id,
                topic_id=topic_id,
            )
            return
        print(f"[followup] Charged {followup_cost} questions for follow-up (short_answer)")

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
            hint_text = f"💡 {correction_hint}"
            await message.answer(hint_text)
            await _log_bot_msg(hint_text, user_id=user_id, session_id=session_id, topic_id=topic_id)

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
                **_followup_complexity_kwargs,
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
            await set_consultation_state(telegram_user_id, "waiting_clarification_answer")

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
            hint_text2 = f"💡 {correction_hint}"
            await message.answer(hint_text2)
            await _log_bot_msg(hint_text2, user_id=user_id, session_id=session_id, topic_id=topic_id)

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
                **_followup_complexity_kwargs,
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
    await set_consultation_state(telegram_user_id, "waiting_followup")


# ==== CALLBACK: Подтверждение сложности (complexity_confirm) ====

@router.callback_query(F.data.startswith("complexity_confirm:"))
async def handle_complexity_confirm(callback: CallbackQuery) -> None:
    """
    Обработчик подтверждения/отмены после классификации сложности.
    Варианты: complexity_confirm:long | short | cancel | turnkey_info
    """
    if callback.from_user is None:
        await callback.answer("Ошибка: пользователь не определен")
        return

    telegram_user_id = callback.from_user.id
    action = callback.data.split(":")[-1]  # long | short | cancel | turnkey_info

    # Получаем сохранённый контекст
    ctx = CONSULTATION_CONTEXT.get(telegram_user_id, {})
    if not ctx.get("_pending_complexity"):
        await callback.answer("Запрос устарел. Задайте вопрос заново.")
        return

    # Логируем нажатие кнопки пользователем
    action_labels = {
        "long": "План на фазу",
        "short": "Краткий ответ",
        "cancel": "Отмена",
        "turnkey_info": "Готовое решение — подробнее",
    }
    await _log_user_callback(f"[Кнопка] {action_labels.get(action, action)}", callback=callback)

    # === turnkey_info: запустить бесплатную генерацию PDF-гайда ===
    if action == "turnkey_info":
        await callback.answer()

        culture = ctx.get("culture", "")
        internal_user_id = ctx.get("internal_user_id")

        if not culture or not internal_user_id:
            if callback.message:
                await callback.message.answer("Не удалось определить культуру. Задайте вопрос заново.")
            return

        # Убираем кнопки
        if callback.message:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass

        # culture_key — lowercase, culture_display — capitalized
        culture_key = culture.lower()
        culture_display = culture.capitalize()

        from src.services.payments.payment_service import generate_guide_free
        await generate_guide_free(
            user_id=internal_user_id,
            telegram_user_id=telegram_user_id,
            culture_key=culture_key,
            culture_display=culture_display,
        )

        # Очистить контекст
        await clear_consultation_state(telegram_user_id)
        return

    # Убираем кнопки (для всех остальных действий)
    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    if action == "cancel":
        await clear_consultation_state(telegram_user_id)
        await callback.answer("Отменено")
        if callback.message:
            cancel_text = "Консультация отменена. Вы можете задать другой вопрос."
            await callback.message.answer(cancel_text)
            await _log_bot_msg(cancel_text, telegram_user_id=telegram_user_id)
        return

    # Извлекаем данные из контекста
    internal_user_id = ctx["internal_user_id"]
    question_text = ctx["question_text"]
    category = ctx["category"]
    culture = ctx["culture"]
    correction_hint = ctx.get("correction_hint")
    classification_cost = ctx["classification_cost"]
    classification_tokens = ctx["classification_tokens"]
    complexity_result = ctx["complexity_result"]
    tier = ctx["tier"]
    metadata = complexity_result.get("metadata", {})

    # Phase параметры
    phase_mode = None
    phase_key = None
    phase_topic = None
    is_last_phase = False
    phase_number = 0

    # Флаг: это выбор для простого вопроса (short_answer) или для long_answer
    is_simple_choice = ctx.get("_simple_question_choice", False)
    phase_eligible = complexity_result.get("phase_eligible", False) if complexity_result else False

    # Определяем стоимость по выбору пользователя
    if action == "long":
        cost = PHASE_COST  # 2
        if is_simple_choice and phase_eligible:
            # === Простой вопрос + phase_eligible + расширенный → ответ по фазам (ИИ выбирает) ===
            topics_list = metadata.get("topics", [])
            phase_topic = topics_list[0] if topics_list else category
            phase_key = None  # ИИ сам выберет фазу
            phase_mode = "seasonal_phase"
            phase_number = 1
            is_last_phase = False

            # Сохраняем контекст для фазового продолжения
            CONSULTATION_CONTEXT[telegram_user_id] = {
                "_phase_continuation": True,
                "_phase_auto_detected": True,  # Фаза будет определена из ответа ИИ
                "current_phase": None,
                "next_phase": None,
                "phases_delivered": [],
                "total_phases": 3,
                "topic": phase_topic,
                "question_text": question_text,
                "internal_user_id": internal_user_id,
                "category": category,
                "culture": culture,
                "classification_cost": classification_cost,
                "classification_tokens": classification_tokens,
                "complexity_result": complexity_result,
                "telegram_user_id": telegram_user_id,
            }
            print(f"[complexity_confirm] Simple question extended (phase_eligible): phase_mode=seasonal_phase, phase_key=None (LLM decides), topic={phase_topic}")

        elif is_simple_choice and not phase_eligible:
            # === Простой вопрос + НЕ phase_eligible + расширенный → длинный ответ без фаз ===
            phase_mode = None
            phase_key = None
            phase_topic = None
            phase_number = 0
            is_last_phase = False

            # Переопределяем tier для extended_non_phase
            complexity_result = {
                **complexity_result,
                "tier": "extended_non_phase",
            }
            print(f"[complexity_confirm] Simple question extended (non-phase): extended_non_phase mode")

        else:
            # === Original long_answer (явный запрос на план/схему) ===
            current_phase = metadata.get("current_phase")  # None для Тип B, "весна-цветение" для Тип C
            next_phase = get_next_phase(current_phase) if current_phase else None
            topics_list = metadata.get("topics", [])
            total_phases = metadata.get("total_phases", 1)

            phase_topic = topics_list[0] if topics_list else category
            phase_key = current_phase  # None для Тип B (ИИ сам), "весна-цветение" для Тип C
            phase_number = 1
            phase_mode = "seasonal_phase"
            is_last_phase = (next_phase is None) if current_phase else False

            # Сохраняем контекст для фазового продолжения
            CONSULTATION_CONTEXT[telegram_user_id] = {
                "_phase_continuation": True,
                "_phase_auto_detected": current_phase is None,  # True если ИИ сам выбирает
                "current_phase": current_phase,
                "next_phase": next_phase,
                "phases_delivered": [current_phase] if current_phase else [],
                "total_phases": total_phases,
                "topic": phase_topic,
                "question_text": question_text,
                "internal_user_id": internal_user_id,
                "category": category,
                "culture": culture,
                "classification_cost": classification_cost,
                "classification_tokens": classification_tokens,
                "complexity_result": complexity_result,
                "telegram_user_id": telegram_user_id,
            }
            print(f"[complexity_confirm] Long answer: phase_mode=seasonal_phase, current={current_phase}, total_phases={total_phases}")

    else:
        # short — стандартный ответ за 1 токен
        cost = COST_NEW_TOPIC  # 1
        phase_mode = None
        phase_key = None
        phase_topic = None
        is_last_phase = False
        phase_number = 0
        # Переопределяем tier на short_answer для логирования
        if complexity_result:
            complexity_result = {
                **complexity_result,
                "tier": "short_answer",
                "metadata": {
                    **complexity_result.get("metadata", {}),
                    "user_downgraded": True,  # Пользователь выбрал стандартный ответ
                },
            }

    # Списываем токены (атомарная проверка + списание)
    reason = "Расширенный ответ" if action == "long" else "Стандартный ответ"
    deduction_ok = await deduct_tokens(
        internal_user_id,
        cost,
        "new_topic",
        f"Консультация ({reason}): {category}"
    )
    if not deduction_ok:
        await _send_insufficient_tokens_error(
            target=callback,
            user_id=internal_user_id,
            cost=cost,
            telegram_user_id=telegram_user_id,
            is_callback=True,
        )
        await clear_consultation_state(telegram_user_id)
        return

    # Очищаем pending контекст (если не фазовое продолжение)
    if not (action == "long" and phase_mode == "seasonal_phase"):
        CONSULTATION_CONTEXT.pop(telegram_user_id, None)
        await clear_consultation_state(telegram_user_id)
    else:
        # Фазовое продолжение: контекст сохраняем, только сбрасываем state
        CONSULTATION_STATE.pop(telegram_user_id, None)

    await callback.answer(f"Списано {pluralize_questions(cost)}")

    # Показываем пользователю что бот начал обработку
    if callback.message:
        _PENDING_WAIT_MSGS[telegram_user_id] = await callback.message.answer("🔄 Готовлю ответ на ваш вопрос...")

    # Маршрутизация на обработчик
    if callback.message:
        await _route_to_handler(
            message=callback.message,
            internal_user_id=internal_user_id,
            telegram_user_id=telegram_user_id,
            category=category,
            culture=culture,
            question_text=question_text,
            classification_cost=classification_cost,
            classification_tokens=classification_tokens,
            correction_hint=correction_hint,
            complexity_result=complexity_result,
            cost=cost,
            phase_mode=phase_mode,
            phase_key=phase_key,
            phase_topic=phase_topic,
            is_last_phase=is_last_phase,
            phase_number=phase_number,
        )


# ==== CALLBACK: Продолжение к следующей фазе (Тип C) ====

@router.callback_query(F.data.startswith("phase_continue:"))
async def handle_phase_continue(callback: CallbackQuery) -> None:
    """
    Обработчик кнопок фазового продолжения:
    - phase_continue:select — показать список фаз
    - phase_continue:stop — завершить
    """
    if callback.from_user is None:
        await callback.answer("Ошибка: пользователь не определен")
        return

    telegram_user_id = callback.from_user.id
    action = callback.data.split(":")[-1]  # select | stop

    ctx = CONSULTATION_CONTEXT.get(telegram_user_id, {})
    if not ctx.get("_phase_continuation"):
        await callback.answer("Запрос устарел. Задайте вопрос заново.")
        return

    # Логируем нажатие кнопки пользователем
    phase_action_labels = {"select": "Выбрать следующую фазу", "stop": "Завершить консультацию по фазам"}
    await _log_user_callback(f"[Кнопка] {phase_action_labels.get(action, action)}", callback=callback)

    if action == "stop":
        # Убираем кнопки
        if callback.message:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
        await clear_consultation_state(telegram_user_id)
        await callback.answer("Консультация завершена")
        if callback.message:
            phase_done_text = "Консультация по фазам завершена. Вы можете задать новый вопрос."
            kb = get_example_questions_keyboard()
            await callback.message.answer(phase_done_text, reply_markup=kb)
            await _log_bot_msg(phase_done_text, telegram_user_id=telegram_user_id, meta=serialize_keyboard(kb))
            await set_consultation_state(telegram_user_id, "waiting_consultation_question")
        return

    if action == "select":
        # Показать список фаз для выбора
        phases_delivered = ctx.get("phases_delivered", [])
        await callback.answer()
        if callback.message:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            phase_select_text = "Выберите фазу роста:"
            kb = get_phase_select_keyboard(phases_delivered)
            await callback.message.answer(phase_select_text, reply_markup=kb)
            await _log_bot_msg(phase_select_text, telegram_user_id=telegram_user_id, meta=serialize_keyboard(kb))
        await set_consultation_state(telegram_user_id, "waiting_phase_select")
        return

    # Legacy: action == "next" — для обратной совместимости
    await callback.answer("Используйте кнопки выбора фазы.")


@router.callback_query(F.data.startswith("phase_select:"))
async def handle_phase_select(callback: CallbackQuery) -> None:
    """
    Обработчик выбора конкретной фазы из списка.
    phase_select:{phase_key} — выбрана фаза
    phase_select:done:{phase_key} — уже пройденная фаза
    """
    if callback.from_user is None:
        await callback.answer("Ошибка: пользователь не определен")
        return

    telegram_user_id = callback.from_user.id
    data_parts = callback.data.split(":")  # ["phase_select", phase_key] или ["phase_select", "done", phase_key]

    ctx = CONSULTATION_CONTEXT.get(telegram_user_id, {})
    if not ctx.get("_phase_continuation"):
        await callback.answer("Запрос устарел. Задайте вопрос заново.")
        return

    # Уже пройденная фаза
    if len(data_parts) == 3 and data_parts[1] == "done":
        await callback.answer("Эта фаза уже пройдена")
        return

    selected_phase = data_parts[1]

    # Валидация фазы
    if selected_phase not in ("весна-цветение", "цветение-плодоношение", "плодоношение-зима"):
        await callback.answer("Неизвестная фаза")
        return

    # Логируем нажатие кнопки пользователем
    await _log_user_callback(f"[Кнопка] Фаза: {get_phase_display_name(selected_phase)}", callback=callback)

    # Убираем кнопки выбора фаз
    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    internal_user_id = ctx["internal_user_id"]
    phase_topic = ctx["topic"]
    question_text = ctx["question_text"]
    category = ctx["category"]
    culture = ctx["culture"]
    classification_cost = ctx["classification_cost"]
    classification_tokens = ctx["classification_tokens"]
    complexity_result = ctx["complexity_result"]
    phases_delivered = ctx.get("phases_delivered", [])

    # Списываем за фазу (атомарная проверка + списание)
    deduction_ok = await deduct_tokens(
        internal_user_id,
        PHASE_COST,
        "new_topic",
        f"Фаза {get_phase_display_name(selected_phase)}: {category}"
    )
    if not deduction_ok:
        await _send_insufficient_tokens_error(
            target=callback,
            user_id=internal_user_id,
            cost=PHASE_COST,
            telegram_user_id=telegram_user_id,
            is_callback=True,
        )
        return

    await callback.answer(f"Списано {pluralize_questions(PHASE_COST)}")

    # Обновляем контекст
    next_phase_after = get_next_phase(selected_phase)
    phases_delivered.append(selected_phase)
    phase_number = len(phases_delivered)
    is_last_phase = all(
        p in phases_delivered
        for p in ("весна-цветение", "цветение-плодоношение", "плодоношение-зима")
    )

    ctx["current_phase"] = selected_phase
    ctx["next_phase"] = next_phase_after
    ctx["phases_delivered"] = phases_delivered

    print(
        f"[phase_select] Phase {phase_number}: {selected_phase}, "
        f"delivered={phases_delivered}, is_last={is_last_phase}"
    )

    # Маршрутизация на обработчик с phase параметрами
    if callback.message:
        await _route_to_handler(
            message=callback.message,
            internal_user_id=internal_user_id,
            telegram_user_id=telegram_user_id,
            category=category,
            culture=culture,
            question_text=question_text,
            classification_cost=classification_cost,
            classification_tokens=classification_tokens,
            correction_hint=None,
            complexity_result=complexity_result,
            cost=PHASE_COST,
            phase_mode="seasonal_phase",
            phase_key=selected_phase,
            phase_topic=phase_topic,
            is_last_phase=is_last_phase,
            phase_number=phase_number,
        )


# ==== CALLBACK: Выбор темы (multi-topic) ====

@router.callback_query(F.data.startswith("topic_select:"))
async def handle_topic_select(callback: CallbackQuery) -> None:
    """Обработчик выбора темы из multi-topic запроса."""
    if callback.from_user is None:
        await callback.answer("Ошибка: пользователь не определен")
        return

    telegram_user_id = callback.from_user.id
    selected_topic = callback.data.split(":", 1)[-1]

    ctx = CONSULTATION_CONTEXT.get(telegram_user_id, {})
    if not ctx.get("_pending_topic_select"):
        await callback.answer("Запрос устарел. Задайте вопрос заново.")
        return

    # Логируем нажатие кнопки пользователем
    await _log_user_callback(f"[Кнопка] Тема: {selected_topic}", callback=callback)

    # Убираем кнопки
    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    # Обновляем complexity_result — оставляем только выбранную тему
    complexity_result = ctx["complexity_result"]
    complexity_result["metadata"]["topics"] = [selected_topic]
    complexity_result["metadata"]["multi_topic"] = False

    # Конвертируем в pending_complexity для стандартного flow подтверждения
    ctx["_pending_topic_select"] = False
    ctx["_pending_complexity"] = True
    ctx["complexity_result"] = complexity_result
    await set_consultation_state(telegram_user_id, "waiting_complexity_confirm")

    await callback.answer(f"Тема: {selected_topic}")

    # Показываем подтверждение стоимости
    balance = await get_token_balance(ctx["internal_user_id"])
    confirm_msg = complexity_result.get("confirm_message", "")
    phase_label = complexity_result.get("phase_button_label", "")
    has_enough_for_plan = await has_sufficient_tokens(ctx["internal_user_id"], PHASE_COST)

    personal_text = confirm_msg or f"Отвечаю по теме: {selected_topic}."

    if has_enough_for_plan:
        if callback.message:
            ts_choose_text = (
                f"{personal_text}\n\n"
                f"{phase_label or 'План на ближайшую фазу'} — {pluralize_questions(PHASE_COST)}"
            )
            kb = get_complexity_confirm_keyboard(
                "long_answer", PHASE_COST, phase_button_label=phase_label,
            )
            await callback.message.answer(ts_choose_text, reply_markup=kb)
            await _log_bot_msg(ts_choose_text, telegram_user_id=telegram_user_id, meta=serialize_keyboard(kb))
    else:
        if callback.message:
            ts_insuf_text = (
                f"{personal_text}\n\n"
                f"План на фазу стоит {pluralize_questions(PHASE_COST)}, "
                f"ваш баланс: {pluralize_questions(balance)} — недостаточно.\n\n"
                f"Для пополнения перейдите в «Мой профиль» → «Пополнить баланс»."
            )
            kb = get_complexity_confirm_keyboard(
                "long_answer_insufficient", 1, phase_button_label=phase_label,
            )
            await callback.message.answer(ts_insuf_text, reply_markup=kb)
            await _log_bot_msg(ts_insuf_text, telegram_user_id=telegram_user_id, meta=serialize_keyboard(kb))


# ==== БЛОКИРОВЩИКИ ТЕКСТА для новых состояний ====

@router.message(
    lambda m: m.from_user is not None
    and CONSULTATION_STATE.get(m.from_user.id) == "waiting_phase_continue"
)
async def handle_phase_continue_text(message: Message) -> None:
    """Блокируем текст, когда ждём кнопку продолжения фазы."""
    phase_block_text = "Пожалуйста, выберите действие: уточняющий вопрос, новая тема или выбор фазы роста."
    await message.answer(phase_block_text)
    if message.from_user:
        await _log_bot_msg(phase_block_text, telegram_user_id=message.from_user.id)


@router.message(
    lambda m: m.from_user is not None
    and CONSULTATION_STATE.get(m.from_user.id) == "waiting_phase_select"
)
async def handle_phase_select_text(message: Message) -> None:
    """Блокируем текст, когда ждём выбор фазы из списка."""
    phase_sel_block = "Пожалуйста, выберите фазу роста из предложенных вариантов выше."
    await message.answer(phase_sel_block)
    if message.from_user:
        await _log_bot_msg(phase_sel_block, telegram_user_id=message.from_user.id)


@router.message(
    lambda m: m.from_user is not None
    and CONSULTATION_STATE.get(m.from_user.id) == "waiting_topic_select"
)
async def handle_topic_select_text(message: Message) -> None:
    """Блокируем текст, когда ждём выбор темы."""
    topic_sel_block = "Пожалуйста, выберите тему из предложенных вариантов выше."
    await message.answer(topic_sel_block)
    if message.from_user:
        await _log_bot_msg(topic_sel_block, telegram_user_id=message.from_user.id)


# ==== CALLBACK ОБРАБОТЧИКИ ДЛЯ FOLLOW-UP КНОПОК =====

@router.callback_query(F.data == "followup_type:clarification")
async def handle_followup_clarification_callback(callback: CallbackQuery) -> None:
    """Обработчик кнопки "Задать уточняющий вопрос"."""
    if callback.from_user is None:
        await callback.answer("Ошибка: пользователь не определен")
        return

    telegram_user_id = callback.from_user.id

    # Логируем нажатие кнопки пользователем
    await _log_user_callback("[Кнопка] Задать уточняющий вопрос", callback=callback)

    # Переводим в состояние ожидания уточняющего вопроса
    await set_consultation_state(telegram_user_id, "waiting_followup_text")

    # Проверяем: пользователь уже написал вопрос до нажатия кнопки?
    from src.handlers.common import PENDING_USER_MESSAGES
    pending = PENDING_USER_MESSAGES.pop(telegram_user_id, None)

    if pending and pending.text:
        # Автоподгружаем написанный текст — пользователю не нужно писать заново
        if callback.message:
            notification = f"Принимаю ваш вопрос:\n«{pending.text}»"
            await callback.message.answer(notification)
            await _log_bot_msg(notification, telegram_user_id=telegram_user_id)
        await callback.answer()
        await process_followup_question_logic(pending)
    else:
        # Обычный флоу — просим написать вопрос
        if callback.message:
            clarif_prompt = "Напишите уточняющий вопрос:"
            await callback.message.answer(clarif_prompt)
            await _log_bot_msg(clarif_prompt, telegram_user_id=telegram_user_id)
        await callback.answer()


@router.callback_query(F.data == "followup_type:new_topic")
async def handle_followup_new_topic_callback(callback: CallbackQuery) -> None:
    """Обработчик кнопки "Задать вопрос по новой теме"."""
    if callback.from_user is None:
        await callback.answer("Ошибка: пользователь не определен")
        return

    telegram_user_id = callback.from_user.id

    # Логируем нажатие кнопки пользователем (ДО закрытия топиков)
    await _log_user_callback("[Кнопка] Задать вопрос по новой теме", callback=callback)

    # Забираем pending-сообщение (если пользователь написал текст до нажатия кнопки)
    from src.handlers.common import PENDING_USER_MESSAGES
    pending = PENDING_USER_MESSAGES.pop(telegram_user_id, None)

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

    # Очищаем контекст и переводим в состояние ожидания нового вопроса
    await clear_consultation_state(telegram_user_id)
    await set_consultation_state(telegram_user_id, "waiting_consultation_question")

    if pending and pending.text and pending.from_user:
        # Автоподгружаем написанный текст — запускаем пайплайн сразу
        if callback.message:
            notification = f"Принимаю ваш вопрос:\n«{pending.text}»"
            await callback.message.answer(notification)
            await _log_bot_msg(notification, telegram_user_id=telegram_user_id)
        await callback.answer("✅ Начинаем новую тему")
        await run_consultation_pipeline(
            message=pending,
            telegram_user_id=pending.from_user.id,
            username=pending.from_user.username,
            first_name=pending.from_user.first_name,
            last_name=pending.from_user.last_name,
            question_text=pending.text.strip(),
        )
    else:
        # Обычный флоу — запрос нового вопроса с инлайн-кнопками примеров
        if callback.message:
            kb = get_example_questions_keyboard()
            await callback.message.answer(CONSULTATION_ENTRY_TEXT, reply_markup=kb)
            await _log_bot_msg(CONSULTATION_ENTRY_TEXT, telegram_user_id=telegram_user_id, meta=serialize_keyboard(kb))
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
    menu_prompt = "Пожалуйста, выберите пункт из меню."
    kb = get_main_keyboard()
    await message.answer(menu_prompt, reply_markup=kb)
    if message.from_user:
        await _log_bot_msg(menu_prompt, telegram_user_id=message.from_user.id, meta=serialize_keyboard(kb))



# ===== CALLBACK ОБРАБОТЧИКИ ДЛЯ КНОПОК =====

@router.callback_query(F.data == "new_consultation_topic")
async def handle_new_topic_callback(callback: CallbackQuery) -> None:
    """Обработчик кнопки "Новая тема консультации"."""
    if callback.from_user is None:
        await callback.answer("Ошибка: пользователь не определен")
        return

    telegram_user_id = callback.from_user.id

    # Логируем нажатие кнопки пользователем (ДО закрытия топиков)
    await _log_user_callback("[Кнопка] Новая тема консультации", callback=callback)

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

    # Очищаем контекст и переводим в состояние ожидания нового вопроса
    await clear_consultation_state(telegram_user_id)
    await set_consultation_state(telegram_user_id, "waiting_consultation_question")

    # Запрос нового вопроса с инлайн-кнопками примеров
    if callback.message:
        kb = get_example_questions_keyboard()
        await callback.message.answer(CONSULTATION_ENTRY_TEXT, reply_markup=kb)
        await _log_bot_msg(CONSULTATION_ENTRY_TEXT, telegram_user_id=telegram_user_id, meta=serialize_keyboard(kb))

    await callback.answer("✅ Начинаем новую тему")
    print(f"[new_topic_callback] New topic for user {telegram_user_id}")
