# src/services/tripwire_followup_sender.py

"""
Отправка сообщений воронки дожима tripwire.

process_pending_followups() вызывается каждые 30 сек из main.py
через _trigger_scheduler_loop.
"""

import logging

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from src.bot import get_bot
from src.services.db.tripwire_followup_repo import (
    get_pending_due,
    mark_sent,
    mark_failed,
    cancel_all_pending,
    has_user_paid_quiz_plan,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# ТЕКСТЫ СООБЩЕНИЙ
# ═══════════════════════════════════════════════════════════════════

STAGE_1_TEXT = (
    "Похоже, вы пока не забрали решение по проблеме: {problem}.\n\n"
    "Обычно это по одной из 3 причин:\n\n"
    "1. Не уверен(а), что проблема определена верно\n"
    "2. Хочу понять, что внутри\n"
    "3. Пока не срочно\n\n"
    "Выберите, что ближе👇"
)

# Ветки 1 и 2 — одинаковый текст
STAGE_2_DIAGNOSIS_OR_DETAILS = (
    "Это нормальный вопрос.\n\n"
    "Одна и та же проблема у {culture} может выглядеть похоже, "
    "но причины бывают разными.\n\n"
    "Поэтому в решении мы даём не просто совет, а:\n"
    "— как распознать симптом\n"
    "— как отличить от похожих проблем\n"
    "— что делать пошагово\n"
    "— чего нельзя делать, чтобы не ухудшить ситуацию\n\n"
    "Если после изучения материала вы поймёте, что ситуация другая "
    "— напишите в поддержку, и мы поможем разобраться."
)

# Ветка 3 — «Пока не срочно»
STAGE_2_NOT_URGENT = (
    "Часто кажется, что с такой проблемой можно подождать.\n\n"
    "Но на практике задержка может привести к тому, что:\n"
    "— состояние растений ухудшится\n"
    "— часть урожая потеряется\n"
    "— придётся потратить больше денег на исправление последствий\n\n"
    "Именно поэтому мы сделали это решение доступным всего за 99 ₽ "
    "вместо 500 ₽, чтобы можно было быстро разобраться и не тянуть."
)

STAGE_3_TEXT = (
    "Вы выбрали проблему: {problem} у культуры {culture}.\n\n"
    "Самая частая ошибка в такой ситуации — пробовать случайные советы "
    "из интернета, терять время и делать лишние обработки.\n\n"
    "Мы собрали готовое решение, в котором понятно:\n"
    "— что происходит\n"
    "— что делать\n"
    "— в какой последовательности действовать\n"
    "— чего избегать, чтобы не навредить\n\n"
    "Если хотите быстро разобраться без хаоса — заберите решение за 99 ₽."
)

STAGE_4_TEXT = (
    'Напоминаем: решение по проблеме "{problem}" для культуры {culture} '
    "ещё доступно за 99 ₽.\n\n"
    "Позже стоимость вернётся к обычной цене — 500 ₽.\n\n"
    "Если хотите быстро понять, что делать без ошибок и лишних трат "
    "— заберите сейчас."
)


# ═══════════════════════════════════════════════════════════════════
# КЛАВИАТУРЫ
# ═══════════════════════════════════════════════════════════════════

def _stage_1_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура stage 1: три причины."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Не уверен, что диагноз верный",
            callback_data="quiz_fu_reason_diagnosis",
        )],
        [InlineKeyboardButton(
            text="Хочу понять, что внутри",
            callback_data="quiz_fu_reason_details",
        )],
        [InlineKeyboardButton(
            text="Пока не срочно",
            callback_data="quiz_fu_reason_not_urgent",
        )],
    ])


def _cta_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура CTA: только кнопка оплаты."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Получить решение за 99 ₽",
            callback_data="quiz_fu_cta_payment",
        )],
    ])


# ═══════════════════════════════════════════════════════════════════
# ЛОГИКА ОТПРАВКИ
# ═══════════════════════════════════════════════════════════════════

# Маппинг event_name для логирования
_STAGE_LOG_EVENTS = {
    1: "tripwire_not_paid_15min",
    2: "non_buyer_branch_sent",
    3: "followup_2h_sent",
    4: "followup_24h_sent",
}


def _build_message(record: dict) -> tuple[str, InlineKeyboardMarkup]:
    """Собрать текст и клавиатуру по stage и reason."""
    stage = record['stage']
    culture = record.get('culture', 'ягодных культур')
    problem = record.get('problem', 'уход')
    reason = record.get('non_buyer_reason', '')

    ctx = {"culture": culture, "problem": problem}

    if stage == 1:
        return STAGE_1_TEXT.format(**ctx), _stage_1_keyboard()

    elif stage == 2:
        if reason == "not_urgent":
            return STAGE_2_NOT_URGENT.format(**ctx), _cta_keyboard()
        else:
            # diagnosis_wrong и want_details — одинаковый текст
            return STAGE_2_DIAGNOSIS_OR_DETAILS.format(**ctx), _cta_keyboard()

    elif stage == 3:
        return STAGE_3_TEXT.format(**ctx), _cta_keyboard()

    elif stage == 4:
        return STAGE_4_TEXT.format(**ctx), _cta_keyboard()

    return "", _cta_keyboard()


async def process_pending_followups() -> int:
    """
    Обработать pending follow-up сообщения.
    Вызывается каждые 30 сек из _trigger_scheduler_loop в main.py.
    Возвращает количество обработанных записей.
    """
    try:
        due = await get_pending_due(limit=50)
        if not due:
            return 0

        bot = get_bot()
        processed = 0

        for record in due:
            followup_id = record['id']
            user_id = record['user_id']
            telegram_user_id = record['telegram_user_id']
            stage = record['stage']

            # Safety check: если оплатил — отменяем все pending
            if await has_user_paid_quiz_plan(user_id):
                cancelled = await cancel_all_pending(user_id)
                logger.info(
                    f"[followup] tripwire_paid_after_followup: "
                    f"user {user_id}, cancelled {cancelled} pending"
                )
                processed += 1
                continue

            # Собираем и отправляем сообщение
            try:
                text, keyboard = _build_message(record)
                if not text:
                    await mark_failed(followup_id, "empty message text")
                    processed += 1
                    continue

                await bot.send_message(
                    chat_id=telegram_user_id,
                    text=text,
                    reply_markup=keyboard,
                )
                await mark_sent(followup_id)

                event_name = _STAGE_LOG_EVENTS.get(stage, f"followup_stage_{stage}")
                reason_suffix = ""
                if stage == 2:
                    reason = record.get('non_buyer_reason', 'unknown')
                    reason_suffix = f", reason={reason}"
                logger.info(
                    f"[followup] {event_name}: user {user_id}, stage {stage}{reason_suffix}"
                )

            except Exception as e:
                error_msg = str(e)[:500]
                await mark_failed(followup_id, error_msg)
                logger.warning(
                    f"[followup] Failed to send stage {stage} to user {user_id}: {error_msg}"
                )

            processed += 1

        return processed

    except Exception as e:
        logger.error(f"[followup] process_pending_followups error: {e}", exc_info=True)
        return 0
