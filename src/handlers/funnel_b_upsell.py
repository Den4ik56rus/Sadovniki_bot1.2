"""
Воронка Б — upsell после оплаты quiz_plan.

Сценарий (запускается через 90 сек после доставки плана):
    1. Триггер-сообщение (уникальный текст по problem_key)
    2. Опрос из 3 вопросов (срочность, цель, график)
    3. Диагноз (шаблон + LLM)
    4. Оффер (программа на сезон)
    5. CTA: «Программа» или «Подписка» (заглушки + аналитика)

Ответы сохраняются в таблицу user_quiz_survey2.
"""

import asyncio
import logging

from aiogram import Router, F, Bot
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
)
from aiogram.enums import ChatAction

from src.handlers.common import (
    CONSULTATION_STATE,
    CONSULTATION_CONTEXT,
    set_consultation_state,
    clear_consultation_state,
)

logger = logging.getLogger(__name__)

router = Router(name="funnel_b_upsell")

# ---------------------------------------------------------------------------
# Константы опроса
# ---------------------------------------------------------------------------

_URGENCY_OPTIONS = [
    ("early", "🟢 Только заметил первые признаки"),
    ("progressing", "🟡 Уже прогрессирует (видно ухудшение)"),
    ("urgent", "🔴 Срочно спасать (теряю куст/урожай)"),
]

_GOAL_OPTIONS = [
    ("close_now", "Только сейчас закрыть проблему"),
    ("stable_season", "Хочу стабильный урожай весь сезон"),
]

_SCHEDULE_OPTIONS = [
    ("ready_system", "Получить готовую систему"),
    ("ask_answers", "Возможность спрашивать и получать ответы"),
]

# Человекочитаемые лейблы для LLM
_URGENCY_LABELS = {
    "early": "только заметил первые признаки",
    "progressing": "уже прогрессирует",
    "urgent": "срочно спасать",
}
_GOAL_LABELS = {
    "close_now": "только сейчас закрыть проблему",
    "stable_season": "хочет стабильный урожай весь сезон",
}
_SCHEDULE_LABELS = {
    "ready_system": "хочет готовую систему",
    "ask_answers": "хочет возможность спрашивать и получать ответы",
}

# Названия культур в дательном падеже (для оффера «Программа по ...»)
_CULTURE_DATIVE = {
    "strawberry": "клубнике",
    "raspberry": "малине",
    "currant": "смородине",
    "honeysuckle": "жимолости",
    "blackberry": "ежевике",
    "blueberry": "голубике",
}

UPSELL_DELAY_SECONDS = 90


# ---------------------------------------------------------------------------
# Клавиатуры
# ---------------------------------------------------------------------------

def _get_q1_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=f"quiz_us_q1_{key}")]
        for key, label in _URGENCY_OPTIONS
    ])


def _get_q2_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=f"quiz_us_q2_{key}")]
        for key, label in _GOAL_OPTIONS
    ])


def _get_q3_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=f"quiz_us_q3_{key}")]
        for key, label in _SCHEDULE_OPTIONS
    ])


def _get_cta_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Хочу системно (программа на сезон)",
            callback_data="quiz_us_cta_seasonal",
        )],
        [InlineKeyboardButton(
            text="💬 Хочу, чтобы отвечали и вели (подписка на консультации)",
            callback_data="quiz_us_cta_consult",
        )],
    ])


def _mark_selected(markup: InlineKeyboardMarkup, selected_data: str) -> InlineKeyboardMarkup:
    """Заменяет клавиатуру на одну кнопку с галочкой — выбранный вариант."""
    for row in markup.inline_keyboard:
        for btn in row:
            if btn.callback_data == selected_data:
                return InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=f"✅ {btn.text}", callback_data="quiz_us_noop")]
                ])
    return markup


# ---------------------------------------------------------------------------
# Точка входа: запуск upsell через 90 секунд
# ---------------------------------------------------------------------------

async def schedule_upsell_trigger(bot: Bot, telegram_user_id: int, internal_user_id: int) -> None:
    """Планирует отправку upsell-триггера через UPSELL_DELAY_SECONDS после оплаты."""

    async def _delayed() -> None:
        try:
            await asyncio.sleep(UPSELL_DELAY_SECONDS)
            await _send_upsell_trigger(bot, telegram_user_id, internal_user_id)
        except asyncio.CancelledError:
            logger.info(f"[upsell] Задача отменена для user_id={internal_user_id}")
        except Exception as e:
            logger.error(f"[upsell] Ошибка триггера для user_id={internal_user_id}: {e}", exc_info=True)

    asyncio.create_task(_delayed())
    logger.info(f"[upsell] Запланирован триггер через {UPSELL_DELAY_SECONDS}с для user_id={internal_user_id}")


async def _send_upsell_trigger(bot: Bot, telegram_user_id: int, internal_user_id: int) -> None:
    """Отправляет триггер-сообщение и первый вопрос опроса."""
    from src.services.db.pool import get_pool
    from src.data.quiz_upsell_texts import get_upsell_trigger_text

    # Очищаем предыдущие ответы (при повторной оплате — новый опрос)
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM user_upsell_choice WHERE user_id = $1",
            internal_user_id,
        )
        await conn.execute(
            "DELETE FROM user_quiz_survey2 WHERE user_id = $1",
            internal_user_id,
        )

    # Получаем problem_key из quiz_answers
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT problem_key, culture, problem FROM user_quiz_answers WHERE user_id = $1",
            internal_user_id,
        )

    problem_key = row["problem_key"] if row else ""

    # Отправляем триггер-текст
    trigger_text = get_upsell_trigger_text(problem_key)

    await bot.send_chat_action(chat_id=telegram_user_id, action=ChatAction.TYPING)
    await asyncio.sleep(2)
    await bot.send_message(chat_id=telegram_user_id, text=trigger_text)

    # Сразу отправляем Q1
    await asyncio.sleep(1)
    await bot.send_message(
        chat_id=telegram_user_id,
        text="Насколько всё плохо прямо сейчас?",
        reply_markup=_get_q1_keyboard(),
    )

    # Устанавливаем состояние
    ctx = CONSULTATION_CONTEXT.get(telegram_user_id, {})
    ctx["upsell_answers"] = {}
    await set_consultation_state(telegram_user_id, "quiz_upsell_q1", ctx)


# ---------------------------------------------------------------------------
# Обработчики ответов на вопросы
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("quiz_us_q1_"))
async def handle_upsell_q1(callback: CallbackQuery) -> None:
    """Q1: Срочность."""
    tg_id = callback.from_user.id
    state = CONSULTATION_STATE.get(tg_id)
    if state != "quiz_upsell_q1":
        await callback.answer()
        return

    answer_key = callback.data.replace("quiz_us_q1_", "")

    # Отмечаем выбранный вариант
    await callback.message.edit_reply_markup(
        reply_markup=_mark_selected(callback.message.reply_markup, callback.data)
    )
    await callback.answer()

    # Сохраняем ответ
    ctx = CONSULTATION_CONTEXT.get(tg_id, {})
    ctx.setdefault("upsell_answers", {})["q1_urgency"] = answer_key

    # Удаляем сообщение с вопросом
    try:
        await callback.message.delete()
    except Exception:
        pass

    # Отправляем Q2
    await asyncio.sleep(0.5)
    await callback.message.answer(
        text="Вам нужно решить только эту проблему или хотите стабильный урожай весь сезон?",
        reply_markup=_get_q2_keyboard(),
    )
    await set_consultation_state(tg_id, "quiz_upsell_q2", ctx)


@router.callback_query(F.data.startswith("quiz_us_q2_"))
async def handle_upsell_q2(callback: CallbackQuery) -> None:
    """Q2: Цель."""
    tg_id = callback.from_user.id
    state = CONSULTATION_STATE.get(tg_id)
    if state != "quiz_upsell_q2":
        await callback.answer()
        return

    answer_key = callback.data.replace("quiz_us_q2_", "")

    await callback.message.edit_reply_markup(
        reply_markup=_mark_selected(callback.message.reply_markup, callback.data)
    )
    await callback.answer()

    ctx = CONSULTATION_CONTEXT.get(tg_id, {})
    ctx.setdefault("upsell_answers", {})["q2_goal"] = answer_key

    # Удаляем сообщение с вопросом
    try:
        await callback.message.delete()
    except Exception:
        pass

    # Отправляем Q3
    await asyncio.sleep(0.5)
    await callback.message.answer(
        text="Какой вариант Вам больше подходит?",
        reply_markup=_get_q3_keyboard(),
    )
    await set_consultation_state(tg_id, "quiz_upsell_q3", ctx)


@router.callback_query(F.data.startswith("quiz_us_q3_"))
async def handle_upsell_q3(callback: CallbackQuery) -> None:
    """Q3: График → сохранение + диагноз + оффер."""
    tg_id = callback.from_user.id
    state = CONSULTATION_STATE.get(tg_id)
    if state != "quiz_upsell_q3":
        await callback.answer()
        return

    answer_key = callback.data.replace("quiz_us_q3_", "")

    await callback.message.edit_reply_markup(
        reply_markup=_mark_selected(callback.message.reply_markup, callback.data)
    )
    await callback.answer()

    # Удаляем сообщение с вопросом
    try:
        await callback.message.delete()
    except Exception:
        pass

    ctx = CONSULTATION_CONTEXT.get(tg_id, {})
    answers = ctx.setdefault("upsell_answers", {})
    answers["q3_schedule"] = answer_key

    urgency = answers.get("q1_urgency", "early")
    goal = answers.get("q2_goal", "save")
    schedule = answers.get("q3_schedule", "regular")

    # Сохраняем в БД
    internal_user_id = await _get_internal_user_id(tg_id)
    if internal_user_id:
        await _save_survey2(internal_user_id, urgency, goal, schedule)

    # Показываем «печатает...»
    await callback.message.bot.send_chat_action(chat_id=tg_id, action=ChatAction.TYPING)

    # Генерируем диагноз (LLM)
    culture, problem = await _get_culture_problem(tg_id)
    diagnosis = await _generate_diagnosis(urgency, goal, schedule, culture, problem)

    # Отправляем диагноз
    diagnosis_text = f"По вашим ответам:\n\n{diagnosis}\n\nЯ рекомендую вам вариант ниже:"
    await callback.message.answer(text=diagnosis_text)

    # Оффер
    culture_dative = _get_culture_dative(tg_id)
    offer_text = (
        f"Программа по {culture_dative} на сезон: протоколы по 6 проблемам + видео + "
        f"календарь работ по вашему региону + шпаргалки.\n\n"
        f"Для покупателей плана — бонус/спецусловие 24 часа."
    )
    await asyncio.sleep(1)
    await callback.message.answer(text=offer_text)

    # CTA
    await asyncio.sleep(1)
    await callback.message.answer(
        text="Как вам удобнее?",
        reply_markup=_get_cta_keyboard(),
    )

    await set_consultation_state(tg_id, "quiz_upsell_cta", ctx)


# ---------------------------------------------------------------------------
# CTA-обработчики
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "quiz_us_cta_seasonal")
async def handle_cta_seasonal(callback: CallbackQuery) -> None:
    """CTA: Хочу системно (программа на сезон)."""
    tg_id = callback.from_user.id

    await callback.message.edit_reply_markup(
        reply_markup=_mark_selected(callback.message.reply_markup, callback.data)
    )
    await callback.answer()

    internal_user_id = await _get_internal_user_id(tg_id)
    if internal_user_id:
        await _save_upsell_choice(internal_user_id, "seasonal_program")

    await callback.message.answer(
        "Мы сейчас готовим этот продукт. Как только будет готов — вы узнаете первыми! 🌱"
    )
    await clear_consultation_state(tg_id)


@router.callback_query(F.data == "quiz_us_cta_consult")
async def handle_cta_consult(callback: CallbackQuery) -> None:
    """CTA: Хочу чтобы вели (подписка на консультации)."""
    tg_id = callback.from_user.id

    await callback.message.edit_reply_markup(
        reply_markup=_mark_selected(callback.message.reply_markup, callback.data)
    )
    await callback.answer()

    internal_user_id = await _get_internal_user_id(tg_id)
    if internal_user_id:
        await _save_upsell_choice(internal_user_id, "consultation_subscription")

    await callback.message.answer(
        "Мы сейчас готовим этот продукт. Как только будет готов — вы узнаете первыми! 🌱"
    )
    await clear_consultation_state(tg_id)


@router.callback_query(F.data == "quiz_us_noop")
async def handle_noop(callback: CallbackQuery) -> None:
    """Заглушка для уже выбранных кнопок."""
    await callback.answer()


# ---------------------------------------------------------------------------
# Guard: текстовые сообщения во время upsell-опроса
# ---------------------------------------------------------------------------

@router.message(
    F.text,
    lambda msg: CONSULTATION_STATE.get(msg.from_user.id, "").startswith("quiz_upsell_"),
)
async def handle_text_during_upsell(message: Message) -> None:
    """Перехватываем текст, когда ожидаем нажатие кнопки."""
    await message.answer("Пожалуйста, выберите один из вариантов выше 👆")


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

async def _get_internal_user_id(telegram_user_id: int) -> int | None:
    """Возвращает внутренний user_id по telegram_user_id."""
    from src.services.db.pool import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT id FROM users WHERE telegram_user_id = $1",
            telegram_user_id,
        )


async def _save_survey2(user_id: int, urgency: str, goal: str, schedule: str) -> None:
    """Сохраняет ответы второго опроса в user_quiz_survey2."""
    from src.services.db.pool import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_quiz_survey2 (user_id, urgency, goal, schedule)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE SET
                urgency = EXCLUDED.urgency,
                goal = EXCLUDED.goal,
                schedule = EXCLUDED.schedule,
                updated_at = NOW()
            """,
            user_id, urgency, goal, schedule,
        )


async def _save_upsell_choice(user_id: int, choice: str) -> None:
    """Сохраняет выбор CTA в user_upsell_choice."""
    from src.services.db.pool import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_upsell_choice (user_id, choice)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET
                choice = EXCLUDED.choice,
                created_at = NOW()
            """,
            user_id, choice,
        )


async def _get_culture_problem(telegram_user_id: int) -> tuple[str, str]:
    """Возвращает (culture, problem) из user_quiz_answers по telegram_user_id."""
    from src.services.db.pool import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT qa.culture, qa.problem
            FROM user_quiz_answers qa
            JOIN users u ON u.id = qa.user_id
            WHERE u.telegram_user_id = $1
            """,
            telegram_user_id,
        )
    if row:
        return row["culture"] or "ягодной культуры", row["problem"] or "текущей проблемы"
    return "ягодной культуры", "текущей проблемы"


def _get_culture_dative(telegram_user_id: int) -> str:
    """Возвращает культуру в дательном падеже из контекста."""
    ctx = CONSULTATION_CONTEXT.get(telegram_user_id, {})
    culture_key = ctx.get("quiz_culture_key", "")
    return _CULTURE_DATIVE.get(culture_key, "вашей культуре")


async def _generate_diagnosis(
    urgency: str,
    goal: str,
    schedule: str,
    culture: str,
    problem: str,
) -> str:
    """Генерирует 3-строчный диагноз через LLM."""
    from src.services.llm.core_llm import create_chat_completion_with_usage

    urgency_label = _URGENCY_LABELS.get(urgency, urgency)
    goal_label = _GOAL_LABELS.get(goal, goal)
    schedule_label = _SCHEDULE_LABELS.get(schedule, schedule)

    system_prompt = (
        "Ты агроном-консультант бота «Садовники».\n"
        "Дай короткую диагностику из ровно 3 строк в ответ на данные пользователя.\n"
        "Формат строго:\n"
        "1. Уровень риска (на основе срочности).\n"
        "2. Что даст разовый план — и чего не закроет.\n"
        "3. Что нужно для гарантированного результата (не продавай — констатируй факт).\n"
        "Без лишнего текста, без вводных слов. Каждая строка — одно законченное предложение.\n"
        "Пиши на русском, обращение на «вы»."
    )

    user_msg = (
        f"Культура: {culture}\n"
        f"Проблема: {problem}\n"
        f"Срочность: {urgency_label}\n"
        f"Цель: {goal_label}\n"
        f"График: {schedule_label}"
    )

    try:
        result = await create_chat_completion_with_usage(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            model="gpt-4.1-mini",
            temperature=0.4,
        )
        diagnosis = result["content"].strip()
        logger.info(f"[upsell] Диагноз сгенерирован ({result['total_tokens']} токенов)")
        return diagnosis
    except Exception as e:
        logger.error(f"[upsell] Ошибка генерации диагноза: {e}")
        # Fallback на шаблон
        return _fallback_diagnosis(urgency, goal)


def _fallback_diagnosis(urgency: str, goal: str) -> str:
    """Шаблонный диагноз на случай сбоя LLM."""
    risk = {
        "early": "Ситуация пока стабильная, но без действий может ухудшиться.",
        "progressing": "Проблема уже развивается — каждая неделя промедления увеличивает потери.",
        "urgent": "Ситуация критическая — нужно действовать немедленно, каждый день на счету.",
    }
    goal_text = {
        "close_now": "закрыть текущую проблему",
        "stable_season": "получить стабильный урожай весь сезон",
    }
    target = goal_text.get(goal, "решить проблему")
    return (
        f"{risk.get(urgency, risk['early'])}\n"
        f"Разовый план решит «здесь и сейчас», но чтобы {target} — "
        "нужно закрыть 4 блока: питание, защита, почва и календарь по фазам.\n"
        "Системный подход даёт гарантированный результат на весь сезон."
    )
