# src/services/funnel_trigger_sender.py

"""
Отправка триггерных сообщений при смене этапа воронки.

Когда пользователь перемещается на этап с привязанным триггером,
ему отправляется контент из рассылки (текст, фото, опрос, кнопки)
или платёжный оффер (если trigger.payment_config установлен).

Отложенные триггеры (delay_minutes > 0) записываются в funnel_trigger_log
со status='pending' и обрабатываются фоновым планировщиком в main.py.
"""

import logging
from decimal import Decimal
from typing import Optional

from src.services.db.funnel_trigger_repo import (
    get_active_triggers_for_stage,
    has_trigger_been_sent,
    log_trigger_sent,
    get_pending_triggers_due,
    update_trigger_log_status,
    is_user_on_stage,
    delete_trigger_log_entry,
)

logger = logging.getLogger(__name__)


async def execute_stage_triggers(
    user_id: int,
    telegram_user_id: int,
    funnel_id: str,
    stage_key: str,
) -> None:
    """
    Проверить и выполнить триггеры для этапа воронки.

    Вызывается после перемещения пользователя на новый этап.
    Для каждого активного триггера:
      - Проверяет, был ли уже отправлен/запланирован этому пользователю
      - Если delay_minutes > 0 — записывает как pending (планировщик отправит позже)
      - Иначе — отправляет сразу и логирует
    """
    try:
        triggers = await get_active_triggers_for_stage(funnel_id, stage_key)
        if not triggers:
            return

        for trigger in triggers:
            trigger_id = trigger['id']
            broadcast_id = trigger['broadcast_id']
            delay_minutes = trigger.get('delay_minutes', 0) or 0
            payment_config = trigger.get('payment_config')

            # Не отправляем повторно если уже отправили/запланировали
            already = await has_trigger_been_sent(trigger_id, user_id)
            if already:
                continue

            if delay_minutes > 0:
                # Отложенная отправка — сохраняем pending в БД, планировщик отправит позже
                await log_trigger_sent(
                    trigger_id, user_id,
                    status='pending',
                    send_at_offset_minutes=delay_minutes,
                )
                logger.info(
                    f"Trigger {trigger_id} scheduled for user {user_id} "
                    f"in {delay_minutes} min"
                )
            else:
                # Немедленная отправка
                try:
                    if payment_config:
                        success = await send_payment_offer(
                            telegram_user_id=telegram_user_id,
                            user_id=user_id,
                            payment_config=payment_config,
                        )
                    else:
                        from src.services.broadcast_sender import send_to_single_user
                        success = await send_to_single_user(
                            broadcast_id=broadcast_id,
                            user_id=user_id,
                            telegram_user_id=telegram_user_id,
                        )

                    if success:
                        await log_trigger_sent(trigger_id, user_id, 'sent')
                        logger.info(
                            f"Trigger {trigger_id} (broadcast={broadcast_id}) sent to user {user_id}"
                        )
                    else:
                        await log_trigger_sent(trigger_id, user_id, 'failed', 'send returned false')

                except Exception as e:
                    error_msg = str(e)[:500]
                    await log_trigger_sent(trigger_id, user_id, 'failed', error_msg)
                    logger.warning(
                        f"Trigger {trigger_id} failed for user {user_id}: {error_msg}"
                    )

    except Exception as e:
        logger.error(f"execute_stage_triggers error: {e}", exc_info=True)


async def process_pending_triggers() -> int:
    """
    Обработать отложенные триггеры у которых наступило время отправки.

    Вызывается фоновым планировщиком в main.py каждые 30 секунд.
    Возвращает количество обработанных триггеров.
    """
    try:
        due = await get_pending_triggers_due(limit=100)
        if not due:
            return 0

        processed = 0
        for record in due:
            log_id = record['log_id']
            broadcast_id = record['broadcast_id']
            user_id = record['user_id']
            telegram_user_id = record['telegram_user_id']
            payment_config = record.get('payment_config')
            funnel_id = record['funnel_id']
            stage_key = record['stage_key']

            # Safety check: пользователь всё ещё на этапе триггера?
            still_on_stage = await is_user_on_stage(user_id, funnel_id, stage_key)
            if not still_on_stage:
                await delete_trigger_log_entry(log_id)
                logger.info(
                    f"Trigger log_id={log_id} deleted: user {user_id} "
                    f"no longer on {funnel_id}/{stage_key}"
                )
                processed += 1
                continue

            try:
                if payment_config:
                    success = await send_payment_offer(
                        telegram_user_id=telegram_user_id,
                        user_id=user_id,
                        payment_config=payment_config,
                    )
                else:
                    from src.services.broadcast_sender import send_to_single_user
                    success = await send_to_single_user(
                        broadcast_id=broadcast_id,
                        user_id=user_id,
                        telegram_user_id=telegram_user_id,
                    )

                if success:
                    await update_trigger_log_status(log_id, 'sent')
                    logger.info(
                        f"Scheduled trigger log_id={log_id} sent to user {user_id}"
                    )
                else:
                    await update_trigger_log_status(log_id, 'failed', 'send returned false')

            except Exception as e:
                error_msg = str(e)[:500]
                await update_trigger_log_status(log_id, 'failed', error_msg)
                logger.warning(f"Scheduled trigger log_id={log_id} failed: {error_msg}")

            processed += 1

        return processed

    except Exception as e:
        logger.error(f"process_pending_triggers error: {e}", exc_info=True)
        return 0


async def send_payment_offer(
    telegram_user_id: int,
    user_id: int,
    payment_config: dict,
) -> bool:
    """
    Отправить платёжный оффер пользователю (как нажатие "купить подписку" из профиля,
    но с кастомной ценой/бонусом из payment_config).

    payment_config:
        plan_id: int       — ID тарифного плана
        custom_price: int  — цена в рублях (optional, иначе цена плана)
        bonus_tokens: int  — доп. токены (optional, иначе 0)
    """
    from src.services.db import subscription_plan_repo
    from src.services.payments import payment_service
    from src.pricing import pluralize_questions
    from src.config import settings
    from src.bot import get_bot
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.enums import ParseMode

    plan_id = payment_config.get('plan_id')
    if not plan_id:
        logger.warning("send_payment_offer: plan_id not set in payment_config")
        return False

    plan = await subscription_plan_repo.get_by_id(plan_id)
    if not plan or not plan.get('is_active'):
        logger.warning(f"send_payment_offer: plan {plan_id} not found or inactive")
        return False

    original_price = int(plan['price_rub'])
    custom_price = payment_config.get('custom_price')
    bonus_tokens = payment_config.get('bonus_tokens', 0) or 0
    pay_price = int(custom_price) if custom_price else original_price
    tokens = plan['tokens_included'] + bonus_tokens

    try:
        payment = await payment_service.create_subscription_payment_custom(
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            plan_id=plan_id,
            custom_price=pay_price if custom_price else None,
            bonus_tokens=bonus_tokens if bonus_tokens else None,
            return_url=settings.YOOKASSA_RETURN_URL,
        )
    except Exception as e:
        logger.warning(f"send_payment_offer: failed to create payment: {e}")
        return False

    # Формируем текст сообщения
    has_discount = pay_price < original_price
    if has_discount:
        discount_pct = round((1 - pay_price / original_price) * 100)
        price_line = (
            f"💰 Цена: <s>{original_price}₽</s> → <b>{pay_price}₽</b>/мес "
            f"(скидка {discount_pct}%)"
        )
    else:
        price_line = f"💰 Цена: {pay_price}₽/мес"

    tokens_line = f"🎁 Лимит: {pluralize_questions(tokens)} в месяц"
    if bonus_tokens:
        tokens_line += f" (+{bonus_tokens} бонус)"

    text = (
        f"📅 Подписка: <b>{plan['name']}</b>\n"
        f"{price_line}\n"
        f"⏱ Срок: {plan['duration_days']} дней\n"
        f"{tokens_line}\n\n"
        f"Нажмите кнопку ниже для оплаты.\n"
        f"После успешной оплаты подписка будет активирована автоматически."
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"💳 Оплатить {pay_price}₽",
            url=payment["confirmation_url"],
        )],
    ])

    bot = get_bot()
    try:
        await bot.send_message(
            chat_id=telegram_user_id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
        return True
    except Exception as e:
        logger.warning(f"send_payment_offer: failed to send message to {telegram_user_id}: {e}")
        return False


async def _broadcast_progress_sse(
    broadcast_id: int,
    sent: int,
    failed: int,
    total: int,
) -> None:
    """Отправить SSE событие прогресса рассылки."""
    from src.api.sse_manager import sse_manager
    await sse_manager.broadcast(
        event_type='broadcast_progress',
        data={
            'broadcast_id': broadcast_id,
            'sent_count': sent,
            'failed_count': failed,
            'total_recipients': total,
        },
        endpoint_type='broadcast',
        entity_id=broadcast_id,
    )
