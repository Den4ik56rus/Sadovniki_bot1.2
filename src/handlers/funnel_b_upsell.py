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
    FSInputFile,
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

# Карточки офферов (порядок: система → 1 блок → подписка)
_UPSELL_CARD_SYSTEM = "data/images/upsell_card_system.png"
_UPSELL_CARD_SYSTEM_ANIM = "data/images/upsell_card_system.mp4"
_UPSELL_CARD_BLOCK = "data/images/upsell_card_block.png"
_UPSELL_CARD_BLOCK_ANIM = "data/images/upsell_card_block.mp4"
_UPSELL_CARD_CONSULT = "data/images/upsell_card_consult.png"
_UPSELL_CARD_CONSULT_ANIM = "data/images/upsell_card_consult.mp4"

# Картинки сезонных программ (по культурам)
_SEASONAL_OFFER_IMAGES: dict[str, str] = {
    "strawberry_summer": "data/images/seasonal_strawberry_summer.png",
    "strawberry_remontant": "data/images/seasonal_strawberry_remontant.png",
    "raspberry_summer": "data/images/seasonal_raspberry_summer.png",
    "raspberry_remontant": "data/images/seasonal_raspberry_remontant.png",
    "currant": "data/images/seasonal_currant.png",
    "honeysuckle": "data/images/seasonal_honeysuckle.png",
    "blackberry": "data/images/seasonal_blackberry.png",
    "blueberry": "data/images/seasonal_blueberry.png",
}

# Названия продуктов для оффера
_SEASONAL_TITLES: dict[str, str] = {
    "strawberry_summer": "Сезонная система ухода за летней клубникой",
    "strawberry_remontant": "Сезонная система ухода за ремонтантной клубникой",
    "raspberry_summer": "Сезонная система ухода за летней малиной",
    "raspberry_remontant": "Сезонная система ухода за ремонтантной малиной",
    "currant": "Сезонная система ухода за смородиной",
    "honeysuckle": "Сезонная система ухода за жимолостью",
    "blackberry": "Сезонная система ухода за ежевикой",
    "blueberry": "Сезонная система ухода за голубикой",
}

_SEASONAL_FULL_PRICE = 3990
_SEASONAL_DISCOUNT_PRICE = 2000

# Цены для одного блока (темы)
_BLOCK_FULL_PRICE = 1990
_BLOCK_DISCOUNT_PRICE = 990

# Эмодзи для категорий (тем)
_TOPIC_EMOJI = {
    "nutrition": "🥗",
    "planting_care": "🌱",
    "protection": "🛡",
    "soil": "🌍",
    "varieties": "🫐",
    "pruning": "✂️",
}

# Картинки для подписки на консультации
_CONSULT_PROMO_IMAGE = "data/images/consult_promo.png"
_CONSULT_TARIFFS_IMAGE = "data/images/consult_tariffs.png"


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
            text="✅ Хочу систему",
            callback_data="quiz_us_cta_seasonal",
        )],
        [InlineKeyboardButton(
            text="📂 Выбрать тему",
            callback_data="quiz_us_cta_block",
        )],
        [InlineKeyboardButton(
            text="💬 Подключить поддержку",
            callback_data="quiz_us_cta_consult",
        )],
    ])


_ALL_CULTURES = [
    ("strawberry", "Клубника"),
    ("raspberry", "Малина"),
    ("currant", "Смородина"),
    ("honeysuckle", "Жимолость"),
    ("blackberry", "Ежевика"),
    ("blueberry", "Голубика"),
]

# Культуры с выбором летняя/ремонтантная
_CULTURES_WITH_VARIETY = {"strawberry", "raspberry"}


def _get_culture_picker_keyboard(callback_prefix: str) -> InlineKeyboardMarkup:
    """Клавиатура выбора культуры (все 6). callback_prefix — например 'quiz_us_culture_sys_'."""
    pairs = list(_ALL_CULTURES)
    buttons = []
    for i in range(0, len(pairs), 2):
        row = [InlineKeyboardButton(text=pairs[i][1], callback_data=f"{callback_prefix}{pairs[i][0]}")]
        if i + 1 < len(pairs):
            row.append(InlineKeyboardButton(text=pairs[i+1][1], callback_data=f"{callback_prefix}{pairs[i+1][0]}"))
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="quiz_us_back_to_cta")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _get_variety_picker_keyboard(culture_key: str, callback_prefix: str) -> InlineKeyboardMarkup:
    """Клавиатура выбора летняя/ремонтантная для клубники и малины."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="☀️ Летняя",
            callback_data=f"{callback_prefix}{culture_key}_summer",
        )],
        [InlineKeyboardButton(
            text="🔄 Ремонтантная",
            callback_data=f"{callback_prefix}{culture_key}_remontant",
        )],
        [InlineKeyboardButton(
            text="⬅️ Назад к культурам",
            callback_data=f"{callback_prefix}back_cultures",
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

    # Генерируем короткий диагноз (LLM)
    culture, problem = await _get_culture_problem(tg_id)
    diagnosis = await _generate_diagnosis(urgency, goal, schedule, culture, problem)

    # Рекомендация зависит от Q2 (цель) и Q3 (формат)
    if goal == "close_now":
        # Хочет решить только текущую проблему → рекомендуем 1 блок
        recommendation = "Рекомендую вам выбрать одну тему — это закроет вашу проблему точечно 👇"
        recommended = _UPSELL_CARD_BLOCK
        recommended_anim = _UPSELL_CARD_BLOCK_ANIM
    elif schedule == "ready_system":
        recommendation = "Рекомендую вам «Систему на сезон» — это закроет все направления сразу 👇"
        recommended = _UPSELL_CARD_SYSTEM
        recommended_anim = _UPSELL_CARD_SYSTEM_ANIM
    else:
        recommendation = "Рекомендую вам «Сопровождение» — будем вести вас лично 👇"
        recommended = _UPSELL_CARD_CONSULT
        recommended_anim = _UPSELL_CARD_CONSULT_ANIM

    # Отправляем диагноз + рекомендацию
    diagnosis_text = f"{diagnosis}\n\n{recommendation}"
    await callback.message.answer(text=diagnosis_text)

    # Рекомендованная карточка — анимация с золотым бликом, остальные — статичные
    cards = (_UPSELL_CARD_SYSTEM, _UPSELL_CARD_BLOCK, _UPSELL_CARD_CONSULT)
    for card_path in cards:
        await asyncio.sleep(1)
        try:
            if card_path == recommended:
                import os
                if os.path.exists(recommended_anim):
                    anim = FSInputFile(recommended_anim)
                    await callback.message.answer_animation(
                        animation=anim, caption="⭐ Рекомендуем для вас",
                    )
                else:
                    # Fallback: статичная картинка с подписью
                    photo = FSInputFile(card_path)
                    await callback.message.answer_photo(
                        photo=photo, caption="⭐ Рекомендуем для вас",
                    )
            else:
                photo = FSInputFile(card_path)
                await callback.message.answer_photo(photo=photo)
        except Exception as e:
            logger.warning(f"[upsell] Не удалось отправить карточку {card_path}: {e}")

    # CTA
    await asyncio.sleep(1)
    await callback.message.answer(
        text="Выберите подходящий вариант:",
        reply_markup=_get_cta_keyboard(),
    )

    await set_consultation_state(tg_id, "quiz_upsell_cta", ctx)


# ---------------------------------------------------------------------------
# CTA-обработчики
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "quiz_us_cta_seasonal")
async def handle_cta_seasonal(callback: CallbackQuery) -> None:
    """CTA: Хочу систему — показываем картинку по культуре + оффер с ценой."""
    tg_id = callback.from_user.id

    await callback.message.edit_reply_markup(
        reply_markup=_mark_selected(callback.message.reply_markup, callback.data)
    )
    await callback.answer()

    internal_user_id = await _get_internal_user_id(tg_id)
    if internal_user_id:
        await _save_upsell_choice(internal_user_id, "seasonal_program")

    # Определяем product_key по культуре из quiz
    product_key = await _resolve_product_key(tg_id)
    await _show_seasonal_offer(callback, tg_id, product_key)


@router.callback_query(F.data == "quiz_us_pick_culture_sys")
async def handle_pick_culture_for_system(callback: CallbackQuery) -> None:
    """Показывает выбор культуры для сезонной системы."""
    await callback.answer()
    await callback.message.edit_text(
        text="Выберите культуру:",
        reply_markup=_get_culture_picker_keyboard("quiz_us_culture_sys_"),
    )


@router.callback_query(F.data == "quiz_us_culture_sys_back_cultures")
async def handle_sys_back_to_cultures(callback: CallbackQuery) -> None:
    """Назад к выбору культуры (из выбора летняя/ремонтантная)."""
    await callback.answer()
    await callback.message.edit_text(
        text="Выберите культуру:",
        reply_markup=_get_culture_picker_keyboard("quiz_us_culture_sys_"),
    )


@router.callback_query(F.data.startswith("quiz_us_culture_sys_"))
async def handle_culture_selected_for_system(callback: CallbackQuery) -> None:
    """Выбор культуры для системы — если клубника/малина, спрашиваем сорт."""
    tg_id = callback.from_user.id
    await callback.answer()

    raw_key = callback.data.replace("quiz_us_culture_sys_", "")

    # Если это уже финальный product_key (strawberry_summer и т.п.) — показываем оффер
    if raw_key in _SEASONAL_OFFER_IMAGES:
        await _show_seasonal_offer(callback, tg_id, raw_key)
        return

    culture_key = raw_key

    # Если клубника/малина — показываем выбор летняя/ремонтантная
    if culture_key in _CULTURES_WITH_VARIETY:
        culture_label = dict(_ALL_CULTURES).get(culture_key, culture_key)
        await callback.message.edit_text(
            text=f"{culture_label} — выберите тип:",
            reply_markup=_get_variety_picker_keyboard(culture_key, "quiz_us_culture_sys_"),
        )
        return

    # Для культур без выбора сорта — показываем оффер напрямую
    await _show_seasonal_offer(callback, tg_id, culture_key)


async def _show_seasonal_offer(callback: CallbackQuery, tg_id: int, product_key: str) -> None:
    """Показывает оффер сезонной системы: картинка + описание + кнопки."""
    ctx = CONSULTATION_CONTEXT.get(tg_id, {})
    ctx["upsell_product_key"] = product_key

    internal_user_id = await _get_internal_user_id(tg_id)

    # Проверить, не куплен ли уже
    from src.services.db.flagship_repo import check_access
    if internal_user_id and await check_access(internal_user_id, product_key):
        await callback.message.answer(
            "У вас уже есть доступ к этой программе!\n"
            "Нажмите «👤 Мой профиль» → «📂 Мои материалы», чтобы открыть."
        )
        await clear_consultation_state(tg_id)
        return

    # Картинка
    image_path = _SEASONAL_OFFER_IMAGES.get(product_key)
    if image_path:
        try:
            photo = FSInputFile(image_path)
            await callback.message.answer_photo(photo=photo)
        except Exception as e:
            logger.warning(f"[upsell] Не удалось отправить картинку {image_path}: {e}")

    # Оффер
    title = _SEASONAL_TITLES.get(product_key, "Сезонная система ухода")
    offer_text = (
        f"<b>{title}</b>\n\n"
        f"📋 Календарь работ по фазам\n"
        f"📖 6 ключевых направлений ухода\n"
        f"🎥 Короткие видео ролики\n"
        f"📊 Презентации со схемами\n"
        f"📝 Подробные статьи по каждой теме\n\n"
        f"<s>{_SEASONAL_FULL_PRICE} ₽</s>  →  <b>{_SEASONAL_DISCOUNT_PRICE} ₽</b> только сегодня!"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"💳 Оплатить {_SEASONAL_DISCOUNT_PRICE} ₽",
            callback_data="quiz_us_pay_seasonal",
        )],
        [InlineKeyboardButton(
            text="🔄 Выбрать другую культуру",
            callback_data="quiz_us_pick_culture_sys",
        )],
        [InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="quiz_us_back_to_cta",
        )],
    ])

    await callback.message.answer(
        text=offer_text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )

    ctx["upsell_product_key"] = product_key
    await set_consultation_state(tg_id, "quiz_upsell_offer", ctx)


@router.callback_query(F.data == "quiz_us_pay_seasonal")
async def handle_pay_seasonal(callback: CallbackQuery) -> None:
    """Создаёт платёж за сезонную систему и отправляет ссылку."""
    tg_id = callback.from_user.id
    await callback.answer()

    ctx = CONSULTATION_CONTEXT.get(tg_id, {})
    product_key = ctx.get("upsell_product_key") or await _resolve_product_key(tg_id)

    internal_user_id = await _get_internal_user_id(tg_id)
    if not internal_user_id:
        await callback.message.answer("Произошла ошибка. Попробуйте позже.")
        return

    from src.services.payments.payment_service import create_flagship_payment
    from decimal import Decimal

    title = _SEASONAL_TITLES.get(product_key, "Сезонная система ухода")

    try:
        result = await create_flagship_payment(
            user_id=internal_user_id,
            telegram_user_id=tg_id,
            product_key=product_key,
            product_title=title,
            price_rub=Decimal(str(_SEASONAL_DISCOUNT_PRICE)),
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"💳 Перейти к оплате — {_SEASONAL_DISCOUNT_PRICE} ₽",
                url=result["confirmation_url"],
            )],
        ])
        await callback.message.answer(
            "Нажмите кнопку ниже для перехода к оплате 👇",
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.error(f"[upsell] Ошибка создания платежа за флагман: {e}")
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже или напишите нам."
        )

    await clear_consultation_state(tg_id)


@router.callback_query(F.data == "quiz_us_back_to_cta")
async def handle_back_to_cta(callback: CallbackQuery) -> None:
    """Возврат к выбору CTA (Система / Блок / Подписка)."""
    tg_id = callback.from_user.id
    await callback.answer()

    # Заменяем текущее сообщение на CTA-выбор
    try:
        await callback.message.edit_text(
            text="Выберите подходящий вариант:",
            reply_markup=_get_cta_keyboard(),
        )
    except Exception:
        # Если edit не сработал (например, сообщение с фото), отправляем новое
        await callback.message.answer(
            text="Выберите подходящий вариант:",
            reply_markup=_get_cta_keyboard(),
        )

    ctx = CONSULTATION_CONTEXT.get(tg_id, {})
    await set_consultation_state(tg_id, "quiz_upsell_cta", ctx)


@router.callback_query(F.data == "quiz_us_cta_block")
async def handle_cta_block(callback: CallbackQuery) -> None:
    """CTA: Выбрать тему (1 блок) — показываем выбор культуры."""
    tg_id = callback.from_user.id

    await callback.message.edit_reply_markup(
        reply_markup=_mark_selected(callback.message.reply_markup, callback.data)
    )
    await callback.answer()

    internal_user_id = await _get_internal_user_id(tg_id)
    if internal_user_id:
        await _save_upsell_choice(internal_user_id, "single_block")

    await callback.message.answer(
        text="Выберите культуру:",
        reply_markup=_get_culture_picker_keyboard("quiz_us_culture_blk_"),
    )

    ctx = CONSULTATION_CONTEXT.get(tg_id, {})
    await set_consultation_state(tg_id, "quiz_upsell_block_culture", ctx)


@router.callback_query(F.data == "quiz_us_culture_blk_back_cultures")
async def handle_blk_back_to_cultures(callback: CallbackQuery) -> None:
    """Назад к выбору культуры (из выбора летняя/ремонтантная) для блока."""
    await callback.answer()
    await callback.message.edit_text(
        text="Выберите культуру:",
        reply_markup=_get_culture_picker_keyboard("quiz_us_culture_blk_"),
    )


@router.callback_query(F.data.startswith("quiz_us_culture_blk_"))
async def handle_culture_selected_for_block(callback: CallbackQuery) -> None:
    """Выбор культуры для 1 блока — если клубника/малина, спрашиваем сорт."""
    tg_id = callback.from_user.id
    await callback.answer()

    raw_key = callback.data.replace("quiz_us_culture_blk_", "")

    # Если это финальный product_key (strawberry_summer, etc.) — показываем темы
    if raw_key not in dict(_ALL_CULTURES):
        await _show_block_topics(callback, tg_id, raw_key)
        return

    culture_key = raw_key

    # Если клубника/малина — выбор летняя/ремонтантная
    if culture_key in _CULTURES_WITH_VARIETY:
        culture_label = dict(_ALL_CULTURES).get(culture_key, culture_key)
        await callback.message.edit_text(
            text=f"{culture_label} — выберите тип:",
            reply_markup=_get_variety_picker_keyboard(culture_key, "quiz_us_culture_blk_"),
        )
        return

    # Для культур без сорта — сразу показываем темы
    await _show_block_topics(callback, tg_id, culture_key)


async def _show_block_topics(callback: CallbackQuery, tg_id: int, product_key: str) -> None:
    """Показывает 6 тем (блоков) для выбранной культуры."""
    from src.services.flagship.flagship_service import load_product_config

    try:
        config = load_product_config(product_key)
    except FileNotFoundError:
        # Если конфиг не найден — заглушка
        culture_labels = dict(_ALL_CULTURES)
        label = _SEASONAL_TITLES.get(product_key, culture_labels.get(product_key, product_key))
        await callback.message.edit_text(
            f"Вы выбрали: <b>{label}</b>\n\n"
            f"Тематические блоки для этой культуры скоро будут доступны! 🌱",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="🔄 Выбрать другую культуру",
                    callback_data="quiz_us_pick_culture_blk",
                )],
                [InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="quiz_us_back_to_cta",
                )],
            ]),
            parse_mode="HTML",
        )
        return

    title = config.get("title", product_key)
    articles = config.get("articles", [])

    # 6 кнопок в 2 ряда (по 2 в ряд)
    buttons = []
    for i in range(0, len(articles), 2):
        row = []
        for article in articles[i:i+2]:
            emoji = _TOPIC_EMOJI.get(article["key"], "📖")
            row.append(InlineKeyboardButton(
                text=f"{emoji} {article['title']}",
                callback_data=f"quiz_us_blk_topic:{product_key}:{article['key']}",
            ))
        buttons.append(row)

    # Кнопка «Выбрать другую культуру» — отдельный ряд
    buttons.append([InlineKeyboardButton(
        text="🔄 Выбрать другую культуру",
        callback_data="quiz_us_pick_culture_blk",
    )])

    await callback.message.edit_text(
        f"<b>{title}</b>\n\n"
        f"Выберите тему:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )

    ctx = CONSULTATION_CONTEXT.get(tg_id, {})
    ctx["upsell_block_product_key"] = product_key
    await set_consultation_state(tg_id, "quiz_upsell_block_topics", ctx)


@router.callback_query(F.data.startswith("quiz_us_blk_topic:"))
async def handle_block_topic_selected(callback: CallbackQuery) -> None:
    """Выбрана тема — показываем оффер с ценой 1990₽ → 990₽."""
    tg_id = callback.from_user.id
    await callback.answer()

    parts = callback.data.split(":")
    product_key = parts[1]  # e.g. strawberry_summer
    topic_key = parts[2]    # e.g. nutrition

    await _show_block_offer(callback, tg_id, product_key, topic_key)


async def _show_block_offer(
    callback: CallbackQuery, tg_id: int, product_key: str, topic_key: str,
) -> None:
    """Показывает оффер для одного блока: тема + цена + кнопка оплаты."""
    from src.services.flagship.flagship_service import load_product_config

    try:
        config = load_product_config(product_key)
    except FileNotFoundError:
        await callback.message.answer("Продукт не найден. Попробуйте другую культуру.")
        return

    # Найти тему
    topic_title = topic_key
    topic_data = None
    for article in config.get("articles", []):
        if article["key"] == topic_key:
            topic_title = article["title"]
            topic_data = article
            break

    if not topic_data:
        await callback.message.answer("Тема не найдена.")
        return

    # Проверить, не куплен ли уже
    internal_user_id = await _get_internal_user_id(tg_id)
    block_product_key = f"{product_key}__{topic_key}"
    if internal_user_id:
        from src.services.db.flagship_repo import check_access
        if await check_access(internal_user_id, block_product_key):
            await callback.message.edit_text(
                f"У вас уже есть доступ к теме «{topic_title}»!\n"
                f"Нажмите «👤 Мой профиль» → «📂 Мои материалы», чтобы открыть.",
                parse_mode="HTML",
            )
            await clear_consultation_state(tg_id)
            return

    emoji = _TOPIC_EMOJI.get(topic_key, "📖")
    culture_title = _SEASONAL_TITLES.get(product_key, config.get("title", ""))

    # Содержимое блока
    content_lines = []
    if topic_data.get("article_pdf"):
        content_lines.append("📝 Подробная статья с рекомендациями")
    if topic_data.get("presentation_pdf"):
        content_lines.append("📊 Презентация со схемами")
    if topic_data.get("video"):
        content_lines.append("🎥 Видео с практическими приёмами")

    content_text = "\n".join(content_lines)

    offer_text = (
        f"{emoji} <b>{topic_title}</b>\n"
        f"<i>{culture_title}</i>\n\n"
        f"{content_text}\n\n"
        f"Доступ <b>бессрочный</b>.\n\n"
        f"<s>{_BLOCK_FULL_PRICE} ₽</s>  →  <b>{_BLOCK_DISCOUNT_PRICE} ₽</b> только сегодня!"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"💳 Оплатить {_BLOCK_DISCOUNT_PRICE} ₽",
            callback_data=f"quiz_us_pay_block:{product_key}:{topic_key}",
        )],
        [InlineKeyboardButton(
            text="🔄 Выбрать другую тему",
            callback_data=f"quiz_us_blk_back_topics:{product_key}",
        )],
        [InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="quiz_us_back_to_cta",
        )],
    ])

    await callback.message.edit_text(
        text=offer_text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )

    ctx = CONSULTATION_CONTEXT.get(tg_id, {})
    ctx["upsell_block_product_key"] = product_key
    ctx["upsell_block_topic_key"] = topic_key
    await set_consultation_state(tg_id, "quiz_upsell_block_offer", ctx)


@router.callback_query(F.data.startswith("quiz_us_blk_back_topics:"))
async def handle_back_to_block_topics(callback: CallbackQuery) -> None:
    """Назад к выбору темы."""
    tg_id = callback.from_user.id
    await callback.answer()

    product_key = callback.data.split(":", 1)[1]
    await _show_block_topics(callback, tg_id, product_key)


@router.callback_query(F.data.startswith("quiz_us_pay_block:"))
async def handle_pay_block(callback: CallbackQuery) -> None:
    """Создаёт платёж за один тематический блок и отправляет ссылку."""
    tg_id = callback.from_user.id
    await callback.answer()

    parts = callback.data.split(":")
    product_key = parts[1]
    topic_key = parts[2]

    internal_user_id = await _get_internal_user_id(tg_id)
    if not internal_user_id:
        await callback.message.answer("Произошла ошибка. Попробуйте позже.")
        return

    from src.services.flagship.flagship_service import load_product_config

    try:
        config = load_product_config(product_key)
    except FileNotFoundError:
        await callback.message.answer("Продукт не найден.")
        return

    # Найти название темы
    topic_title = topic_key
    for article in config.get("articles", []):
        if article["key"] == topic_key:
            topic_title = article["title"]
            break

    culture_title = _SEASONAL_TITLES.get(product_key, config.get("title", ""))
    full_title = f"{topic_title} — {culture_title}"
    block_product_key = f"{product_key}__{topic_key}"

    from src.services.payments.payment_service import create_flagship_payment
    from decimal import Decimal

    try:
        result = await create_flagship_payment(
            user_id=internal_user_id,
            telegram_user_id=tg_id,
            product_key=block_product_key,
            product_title=full_title,
            price_rub=Decimal(str(_BLOCK_DISCOUNT_PRICE)),
            product_type="single_block",
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"💳 Перейти к оплате — {_BLOCK_DISCOUNT_PRICE} ₽",
                url=result["confirmation_url"],
            )],
        ])
        await callback.message.answer(
            "Нажмите кнопку ниже для перехода к оплате 👇",
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.error(f"[upsell] Ошибка создания платежа за блок: {e}")
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже или напишите нам."
        )

    await clear_consultation_state(tg_id)


@router.callback_query(F.data == "quiz_us_pick_culture_blk")
async def handle_pick_culture_for_block(callback: CallbackQuery) -> None:
    """Показывает выбор культуры для 1 блока."""
    await callback.answer()
    await callback.message.edit_text(
        text="Выберите культуру:",
        reply_markup=_get_culture_picker_keyboard("quiz_us_culture_blk_"),
    )


@router.callback_query(F.data == "quiz_us_cta_consult")
async def handle_cta_consult(callback: CallbackQuery) -> None:
    """CTA: Подключить поддержку — показываем промо + тарифы + кнопки."""
    tg_id = callback.from_user.id

    await callback.message.edit_reply_markup(
        reply_markup=_mark_selected(callback.message.reply_markup, callback.data)
    )
    await callback.answer()

    internal_user_id = await _get_internal_user_id(tg_id)
    if internal_user_id:
        await _save_upsell_choice(internal_user_id, "consultation_subscription")

    # 1. Промо-картинка «Агроном 24/7»
    try:
        promo = FSInputFile(_CONSULT_PROMO_IMAGE)
        await callback.message.answer_photo(photo=promo)
    except Exception as e:
        logger.warning(f"[upsell] Не удалось отправить промо: {e}")

    await asyncio.sleep(1)

    # 2. Картинка тарифов
    try:
        tariffs = FSInputFile(_CONSULT_TARIFFS_IMAGE)
        await callback.message.answer_photo(photo=tariffs)
    except Exception as e:
        logger.warning(f"[upsell] Не удалось отправить тарифы: {e}")

    await asyncio.sleep(0.5)

    # 3. Кнопки выбора тарифа с персональной скидкой
    keyboard = await _build_consult_tariff_keyboard(internal_user_id)

    await callback.message.answer(
        text=(
            "Режим консультаций работает по системе токенов.\n"
            "Стандартный ответ — 1 токен\n"
            "Подробный ответ — 2 токена\n\n"
            "Выберите подходящий тариф — большой пакет токенов выгоднее! 👇"
        ),
        reply_markup=keyboard,
    )

    ctx = CONSULTATION_CONTEXT.get(tg_id, {})
    await set_consultation_state(tg_id, "quiz_upsell_consult_tariff", ctx)


@router.callback_query(F.data.startswith("quiz_us_consult_plan_"))
async def handle_consult_plan_detail(callback: CallbackQuery) -> None:
    """Показывает описание выбранного тарифа подписки + кнопку оплаты."""
    import math
    tg_id = callback.from_user.id
    await callback.answer()

    plan_id = int(callback.data.replace("quiz_us_consult_plan_", ""))

    from src.services.db import subscription_plan_repo
    plan = await subscription_plan_repo.get_by_id(plan_id)
    if not plan:
        await callback.message.answer("Тариф не найден. Попробуйте ещё раз.")
        return

    internal_user_id = await _get_internal_user_id(tg_id)
    original_price = int(plan["price_rub"])
    qty = plan.get("tokens_included", 0)
    carryover = plan.get("max_carryover", 0)

    # Получаем персональную скидку
    discount_pct, bonus_tokens = await _get_user_discount(internal_user_id, plan)
    discounted_price = _apply_discount(original_price, discount_pct)

    # Формируем описание
    from src.pricing import pluralize_questions
    lines = [
        f"<b>📅 {plan['name']}</b>\n",
    ]

    if discount_pct > 0:
        lines.append(
            f"💰 Цена: <s>{original_price} ₽</s> → <b>{discounted_price} ₽</b>/мес "
            f"(скидка {discount_pct}%)"
        )
    else:
        lines.append(f"💰 Цена: <b>{original_price} ₽</b>/мес")

    lines.append(f"⏱ Срок: {plan['duration_days']} дней")

    if bonus_tokens > 0:
        lines.append(
            f"🎁 Лимит: {qty} + {bonus_tokens} бонус = "
            f"<b>{qty + bonus_tokens} токенов</b> в месяц"
        )
    else:
        lines.append(f"🎁 Лимит: {pluralize_questions(qty)} в месяц")

    if carryover > 0:
        lines.append(f"🔄 Перенос: до {carryover} неиспользованных на след. месяц")

    lines.append("")
    lines.append("Нажмите кнопку ниже для оплаты.")

    detail_text = "\n".join(lines)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"💳 Оплатить {discounted_price} ₽",
            callback_data=f"quiz_us_pay_consult_{plan_id}",
        )],
        [InlineKeyboardButton(
            text="⬅️ Назад к тарифам",
            callback_data="quiz_us_back_to_consult_tariffs",
        )],
    ])

    await callback.message.edit_text(
        text=detail_text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )

    ctx = CONSULTATION_CONTEXT.get(tg_id, {})
    ctx["upsell_consult_plan_id"] = plan_id
    await set_consultation_state(tg_id, "quiz_upsell_consult_detail", ctx)


@router.callback_query(F.data.startswith("quiz_us_pay_consult_"))
async def handle_pay_consult(callback: CallbackQuery) -> None:
    """Создаёт платёж за подписку и отправляет ссылку."""
    tg_id = callback.from_user.id
    await callback.answer()

    plan_id = int(callback.data.replace("quiz_us_pay_consult_", ""))

    internal_user_id = await _get_internal_user_id(tg_id)
    if not internal_user_id:
        await callback.message.answer("Произошла ошибка. Попробуйте позже.")
        return

    from src.services.payments import payment_service
    from src.config import settings

    try:
        payment = await payment_service.create_subscription_payment(
            user_id=internal_user_id,
            telegram_user_id=tg_id,
            plan_id=plan_id,
            return_url=settings.YOOKASSA_RETURN_URL,
        )

        pay_amount = int(payment["amount"])
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"💳 Перейти к оплате — {pay_amount} ₽",
                url=payment["confirmation_url"],
            )],
        ])
        await callback.message.answer(
            "Нажмите кнопку ниже для перехода к оплате 👇",
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.error(f"[upsell] Ошибка создания платежа за подписку: {e}")
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже или напишите нам."
        )

    await clear_consultation_state(tg_id)


@router.callback_query(F.data == "quiz_us_back_to_consult_tariffs")
async def handle_back_to_consult_tariffs(callback: CallbackQuery) -> None:
    """Возврат к выбору тарифа подписки."""
    tg_id = callback.from_user.id
    await callback.answer()

    internal_user_id = await _get_internal_user_id(tg_id)
    keyboard = await _build_consult_tariff_keyboard(internal_user_id)

    tariff_text = (
        "Режим консультаций работает по системе токенов.\n"
        "Стандартный ответ — 1 токен\n"
        "Подробный ответ — 2 токена\n\n"
        "Выберите подходящий тариф — большой пакет токенов выгоднее! 👇"
    )
    try:
        await callback.message.edit_text(
            text=tariff_text,
            reply_markup=keyboard,
        )
    except Exception:
        await callback.message.answer(
            text=tariff_text,
            reply_markup=keyboard,
        )

    ctx = CONSULTATION_CONTEXT.get(tg_id, {})
    await set_consultation_state(tg_id, "quiz_upsell_consult_tariff", ctx)


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


async def _resolve_product_key(telegram_user_id: int) -> str:
    """Определяет product_key по культуре пользователя из quiz-контекста и БД."""
    # Сначала из контекста
    ctx = CONSULTATION_CONTEXT.get(telegram_user_id, {})
    culture = ctx.get("quiz_culture_key", "")
    variety = ctx.get("quiz_variety_key", "")

    if culture and variety:
        key = f"{culture}_{variety}"
        if key in _SEASONAL_OFFER_IMAGES:
            return key

    # Fallback: парсим текстовое поле culture из БД
    # Формат в БД: "🍓 Клубника (Ремонтантная)" или "🍓 Клубника (Летняя)"
    from src.services.db.pool import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT qa.culture
            FROM user_quiz_answers qa
            JOIN users u ON u.id = qa.user_id
            WHERE u.telegram_user_id = $1
            """,
            telegram_user_id,
        )

    if row and row["culture"]:
        return _parse_product_key_from_culture_text(row["culture"])

    return "strawberry_summer"


def _parse_product_key_from_culture_text(culture_text: str) -> str:
    """Парсит product_key из текстового названия культуры в БД."""
    text = culture_text.lower()
    culture = ""
    variety = "summer"  # default

    if "клубник" in text:
        culture = "strawberry"
    elif "малин" in text:
        culture = "raspberry"
    else:
        return "strawberry_summer"

    if "ремонтант" in text:
        variety = "remontant"
    elif "летн" in text:
        variety = "summer"

    return f"{culture}_{variety}"


async def _get_user_discount(
    user_id: int | None,
    plan: dict,
) -> tuple[int, int]:
    """Возвращает (discount_percent, bonus_tokens) для пользователя."""
    import math
    if not user_id:
        return 0, 0

    from src.services.db.discount_repo import get_user_active_broadcast_discount
    from src.services.db.invite_link_repo import get_user_active_discount, get_user_active_token_bonus

    # Broadcast discount
    broadcast_disc = await get_user_active_broadcast_discount(user_id)
    broadcast_pct = broadcast_disc["discount_percent"] if broadcast_disc else 0
    broadcast_bonus = 0
    if broadcast_disc:
        raw_bonus = broadcast_disc.get("bonus_tokens", 0) or 0
        bonus_mode = broadcast_disc.get("bonus_tokens_mode", "absolute")
        if bonus_mode == "percent" and raw_bonus > 0:
            broadcast_bonus = math.ceil(plan.get("tokens_included", 0) * raw_bonus / 100)
        else:
            broadcast_bonus = raw_bonus

    # Invite link discount
    inv = await get_user_active_discount(user_id)
    invite_pct = inv["discount_percent"] if inv else 0
    invite_token_bonus_pct = await get_user_active_token_bonus(user_id) or 0
    invite_bonus = (
        math.ceil(plan.get("tokens_included", 0) * invite_token_bonus_pct / 100)
        if invite_token_bonus_pct > 0
        else 0
    )

    best_pct = max(broadcast_pct, invite_pct)
    best_bonus = max(broadcast_bonus, invite_bonus)
    return best_pct, best_bonus


def _apply_discount(price: int, discount_pct: int) -> int:
    """Применяет скидку, минимум 1₽."""
    if discount_pct <= 0:
        return price
    discounted = int(price * (100 - discount_pct) / 100)
    return max(discounted, 1)


async def _build_consult_tariff_keyboard(user_id: int | None) -> InlineKeyboardMarkup:
    """Строит клавиатуру с тарифами подписки и персональной скидкой."""
    from src.services.db import subscription_plan_repo

    plans = await subscription_plan_repo.get_all_active()
    buttons = []

    for plan in plans:
        price = int(plan["price_rub"])
        discount_pct, _ = await _get_user_discount(user_id, plan)

        if discount_pct > 0:
            discounted = _apply_discount(price, discount_pct)
            text = f"{plan['name']}  {price}₽ → {discounted}₽/мес"
        else:
            text = f"{plan['name']}  {price}₽/мес"

        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"quiz_us_consult_plan_{plan['id']}",
        )])

    buttons.append([InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data="quiz_us_back_to_cta",
    )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


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
        "Напиши 1-2 коротких предложения: что даст разовый план по проблеме пользователя "
        "и чего он не закроет (долгосрочная защита, системный уход и т.п.).\n"
        "Пиши конкретно про культуру и проблему пользователя, без общих фраз.\n"
        "Без вводных слов типа «По вашим ответам». Просто констатация.\n"
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
    return (
        "Разовый план поможет разобраться с текущей ситуацией, "
        "но не обеспечит долгосрочную защиту — для этого нужен системный подход."
    )


# ---------------------------------------------------------------------------
# Public API для shop.py
# ---------------------------------------------------------------------------

UPSELL_CARD_SYSTEM = _UPSELL_CARD_SYSTEM
UPSELL_CARD_SYSTEM_ANIM = _UPSELL_CARD_SYSTEM_ANIM
UPSELL_CARD_BLOCK = _UPSELL_CARD_BLOCK
UPSELL_CARD_CONSULT = _UPSELL_CARD_CONSULT
CONSULT_PROMO_IMAGE = _CONSULT_PROMO_IMAGE
CONSULT_TARIFFS_IMAGE = _CONSULT_TARIFFS_IMAGE

SEASONAL_OFFER_IMAGES = _SEASONAL_OFFER_IMAGES
SEASONAL_TITLES = _SEASONAL_TITLES
SEASONAL_FULL_PRICE = _SEASONAL_FULL_PRICE
BLOCK_FULL_PRICE = _BLOCK_FULL_PRICE
TOPIC_EMOJI = _TOPIC_EMOJI

ALL_CULTURES = _ALL_CULTURES
CULTURES_WITH_VARIETY = _CULTURES_WITH_VARIETY

get_culture_picker = _get_culture_picker_keyboard
get_variety_picker = _get_variety_picker_keyboard
build_consult_tariffs = _build_consult_tariff_keyboard
get_discount = _get_user_discount
calc_discount = _apply_discount
get_internal_user_id = _get_internal_user_id
mark_selected = _mark_selected
