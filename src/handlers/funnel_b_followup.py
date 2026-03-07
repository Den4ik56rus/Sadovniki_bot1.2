# src/handlers/funnel_b_followup.py

"""
Воронка дожима tripwire — callback-хендлеры.

Обрабатывает:
  - Выбор причины отказа (stage 1 → stage 2): убирает кнопки и сразу отправляет ответ
  - CTA «Получить решение за 99₽» → создание платежа
"""

import logging

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from src.services.db.tripwire_followup_repo import (
    set_reason_and_create_stage2,
)

logger = logging.getLogger(__name__)

router = Router(name="funnel_b_followup")


# ═══════════════════════════════════════════════════════════════════
# Получение internal user_id
# ═══════════════════════════════════════════════════════════════════

async def _get_internal_user_id(telegram_user_id: int) -> int:
    """Получить internal user_id из таблицы users."""
    from src.services.db.pool import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_user_id = $1",
            telegram_user_id,
        )
    if not row:
        logger.warning(f"[followup] User not found for tg_id={telegram_user_id}")
        return 0
    return row['id']


# ═══════════════════════════════════════════════════════════════════
# Обработчики выбора причины (stage 1)
# ═══════════════════════════════════════════════════════════════════

# Маппинг callback_data → reason key
_REASON_MAP = {
    "quiz_fu_reason_diagnosis": "diagnosis_wrong",
    "quiz_fu_reason_details": "want_details",
    "quiz_fu_reason_not_urgent": "not_urgent",
}


@router.callback_query(F.data.startswith("quiz_fu_reason_"))
async def handle_followup_reason(callback: CallbackQuery) -> None:
    """Пользователь выбрал причину отказа → убираем кнопки, сразу отправляем ответ."""
    await callback.answer()

    reason = _REASON_MAP.get(callback.data)
    if not reason:
        return

    tg_user = callback.from_user
    internal_user_id = await _get_internal_user_id(tg_user.id)
    if not internal_user_id:
        return

    logger.info(
        f"[followup] non_buyer_reason_selected: user {internal_user_id}, reason={reason}"
    )

    # Убираем кнопки из сообщения stage 1
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass  # Сообщение могло быть слишком старым

    # Сохраняем причину и помечаем stage 2 в БД
    result = await set_reason_and_create_stage2(
        user_id=internal_user_id,
        telegram_user_id=tg_user.id,
        reason=reason,
    )

    if not result:
        logger.warning(
            f"[followup] No stage 1 record found for user {internal_user_id}"
        )
        return

    # Сразу отправляем ответ (stage 2) — не ждём scheduler
    from src.services.tripwire_followup_sender import (
        STAGE_2_DIAGNOSIS_OR_DETAILS,
        STAGE_2_NOT_URGENT,
        _cta_keyboard,
    )

    culture = result.get('culture', 'ягодных культур')
    problem = result.get('problem', 'уход')
    ctx = {"culture": culture, "problem": problem}

    if reason == "not_urgent":
        text = STAGE_2_NOT_URGENT.format(**ctx)
    else:
        text = STAGE_2_DIAGNOSIS_OR_DETAILS.format(**ctx)

    await callback.message.answer(
        text=text,
        reply_markup=_cta_keyboard(),
    )


# ═══════════════════════════════════════════════════════════════════
# CTA — создание платежа
# ═══════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "quiz_fu_cta_payment")
async def handle_followup_cta_payment(callback: CallbackQuery) -> None:
    """CTA «Получить решение за 99₽» → создаём платёж в ЮКассе."""
    await callback.answer()

    tg_user = callback.from_user
    internal_user_id = await _get_internal_user_id(tg_user.id)
    if not internal_user_id:
        return

    logger.info(f"[followup] cta_payment_clicked: user {internal_user_id}")

    # Достаём данные квиза из БД
    from src.services.db.pool import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        quiz = await conn.fetchrow(
            "SELECT culture, problem, problem_key FROM user_quiz_answers WHERE user_id = $1",
            internal_user_id,
        )

    culture_display = quiz["culture"] if quiz and quiz["culture"] else "ягодных культур"
    problem_display = quiz["problem"] if quiz and quiz["problem"] else "уход"
    problem_key = quiz["problem_key"] if quiz and quiz["problem_key"] else ""

    payment_text = (
        f"Персональный план по проблеме «{problem_display}» "
        f"для {culture_display}\n\n"
        f"<s>490 ₽</s> → <b>99 ₽</b>"
    )

    # Проверяем тестовый режим
    from src.handlers.funnel_b import SKIP_PAYMENT
    if SKIP_PAYMENT:
        payment_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="Оплатить 99 ₽ (тест)",
                callback_data="quiz_fake_payment",
            )],
        ])
        await callback.message.answer(payment_text, reply_markup=payment_keyboard, parse_mode="HTML")
        return

    # Создаём платёж в ЮКассе
    try:
        from src.services.payments.payment_service import create_quiz_plan_payment
        result = await create_quiz_plan_payment(
            user_id=internal_user_id,
            telegram_user_id=tg_user.id,
            culture_display=culture_display,
            problem_display=problem_display,
            problem_key=problem_key,
        )

        payment_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="Оплатить 99 ₽",
                url=result["confirmation_url"],
            )],
        ])

        await callback.message.answer(
            payment_text,
            reply_markup=payment_keyboard,
            parse_mode="HTML",
        )

    except Exception as e:
        logger.error(f"[followup] Payment creation error for user {internal_user_id}: {e}")
        await callback.message.answer(
            "Произошла ошибка при создании платежа. Попробуйте ещё раз позже."
        )
