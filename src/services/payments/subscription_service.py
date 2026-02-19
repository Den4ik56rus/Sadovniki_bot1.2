"""
Сервис для управления подписками.

Основные функции:
    - activate_subscription — активировать подписку после оплаты
    - get_active_subscription — получить активную подписку пользователя
    - check_subscription_status — проверить статус подписки
    - cancel_subscription — отменить подписку
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from src.services.db import user_subscription_repo, subscription_plan_repo
from src.services.db.tokens_repo import add_tokens, reset_subscription_tokens_with_carryover
from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


async def activate_subscription(
    user_id: int,
    plan_id: int,
    payment_id: int,
    payment_method_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Активирует подписку после успешной оплаты.

    Args:
        user_id: ID пользователя
        plan_id: ID тарифного плана
        payment_id: ID платежа

    Returns:
        Созданная подписка

    Raises:
        ValueError: Если план не найден
    """
    plan = await subscription_plan_repo.get_by_id(plan_id)
    if not plan:
        raise ValueError(f"Subscription plan {plan_id} not found")

    # Рассчитать срок действия
    started_at = datetime.now()
    expires_at = started_at + timedelta(days=plan["duration_days"])

    # Рассчитать дату следующего списания (за 3 дня до окончания)
    next_billing_date = expires_at - timedelta(days=3)

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Создать подписку
            subscription = await user_subscription_repo.create(
                user_id=user_id,
                subscription_plan_id=plan_id,
                payment_id=payment_id,
                started_at=started_at,
                expires_at=expires_at,
                tokens_granted=plan["tokens_included"],
                status="active",
                payment_method_id=payment_method_id,  # Сохранить способ оплаты
                auto_renew=True,  # Всегда включено
                next_billing_date=next_billing_date,  # Дата следующего автоплатежа
            )

            # Обновить статус пользователя
            await conn.execute(
                """
                UPDATE users
                SET subscription_status = 'active',
                    subscription_expires_at = $2
                WHERE id = $1
                """,
                user_id,
                expires_at,
            )

            # Начислить токены с учётом переноса
            max_carryover = plan.get("max_carryover", 0)
            carryover_result = await reset_subscription_tokens_with_carryover(
                user_id=user_id,
                new_amount=plan["tokens_included"],
                max_carryover=max_carryover,
            )

            logger.info(
                f"Subscription activated: user={user_id}, plan={plan['name']}, "
                f"expires={expires_at}, tokens={plan['tokens_included']}, "
                f"carryover={carryover_result['carryover']}, "
                f"new_balance={carryover_result['total_balance']}"
            )

            # Обновить Buyers секцию если есть запись
            try:
                await conn.execute(
                    """
                    UPDATE buyer_status
                    SET status = 'paid',
                        updated_at = NOW()
                    WHERE client_id IN (
                        SELECT id FROM client_crm WHERE user_id = $1
                    )
                    """,
                    user_id,
                )
            except Exception as e:
                # Не критично если buyers секции нет
                logger.debug(f"Could not update buyer status: {e}")

            # Отправить уведомление в Telegram
            await _send_subscription_notification(
                user_id, subscription, plan, carryover_result
            )

            return subscription


async def get_active_subscription(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Получает активную подписку пользователя.

    Args:
        user_id: ID пользователя

    Returns:
        Активная подписка или None
    """
    subscription = await user_subscription_repo.get_active_subscription(user_id)

    if subscription:
        # Дополнить данными о плане
        plan = await subscription_plan_repo.get_by_id(subscription["subscription_plan_id"])
        if plan:
            subscription["plan"] = plan

    return subscription


async def check_subscription_status(user_id: int) -> bool:
    """
    Проверяет, активна ли подписка пользователя.

    Args:
        user_id: ID пользователя

    Returns:
        True если есть активная подписка
    """
    subscription = await user_subscription_repo.get_active_subscription(user_id)
    return subscription is not None


async def cancel_subscription(
    user_id: int,
    reason: str = "user_request",
) -> bool:
    """
    Отменяет активную подписку пользователя.

    Args:
        user_id: ID пользователя
        reason: Причина отмены

    Returns:
        True если подписка была отменена
    """
    subscription = await user_subscription_repo.get_active_subscription(user_id)
    if not subscription:
        logger.warning(f"No active subscription to cancel for user {user_id}")
        return False

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Обновить подписку
            await user_subscription_repo.update_status(
                subscription_id=subscription["id"],
                status="canceled",
                is_active=False,
                cancellation_reason=reason,
            )

            # Обновить статус пользователя
            await conn.execute(
                """
                UPDATE users
                SET subscription_status = 'none',
                    subscription_expires_at = NULL
                WHERE id = $1
                """,
                user_id,
            )

            logger.info(
                f"Subscription canceled: user={user_id}, "
                f"subscription_id={subscription['id']}, reason={reason}"
            )

            return True


async def expire_old_subscriptions() -> int:
    """
    Фоновая задача для истечения просроченных подписок.

    Returns:
        Количество истекших подписок
    """
    count = await user_subscription_repo.expire_old_subscriptions()

    if count > 0:
        logger.info(f"Expired {count} old subscriptions")

        # Обновить статусы пользователей
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE users
                SET subscription_status = 'expired'
                WHERE subscription_expires_at < NOW()
                AND subscription_status = 'active'
                """
            )

    return count


async def get_expiring_soon(days: int = 3) -> list:
    """
    Получает подписки, истекающие в ближайшие N дней.

    Args:
        days: Количество дней

    Returns:
        Список подписок с данными о пользователях
    """
    subscriptions = await user_subscription_repo.get_expiring_soon(days)

    # Дополнить данными о планах
    result = []
    for sub in subscriptions:
        plan = await subscription_plan_repo.get_by_id(sub["subscription_plan_id"])
        if plan:
            sub["plan"] = plan
            result.append(sub)

    return result


async def process_auto_renewals() -> int:
    """
    Фоновая задача для обработки автоматических продлений подписок.
    Создает рекуррентные платежи за 3 дня до истечения подписки.

    Returns:
        Количество созданных платежей для продления
    """
    from src.services.payments.payment_service import create_recurrent_subscription_payment

    # Получить подписки, требующие продления (next_billing_date <= NOW)
    pool = get_pool()
    async with pool.acquire() as conn:
        subscriptions = await conn.fetch(
            """
            SELECT us.*, sp.name as plan_name, sp.price_rub, sp.duration_days, sp.tokens_included
            FROM user_subscriptions us
            JOIN subscription_plans sp ON us.subscription_plan_id = sp.id
            WHERE us.status = 'active'
            AND us.auto_renew = true
            AND us.payment_method_id IS NOT NULL
            AND us.next_billing_date <= NOW()
            """,
        )

    count = 0
    for sub in subscriptions:
        try:
            # Создать рекуррентный платеж
            await create_recurrent_subscription_payment(
                user_id=sub["user_id"],
                subscription_id=sub["id"],
                plan_id=sub["subscription_plan_id"],
                payment_method_id=sub["payment_method_id"],
            )
            count += 1
            logger.info(f"Auto-renewal payment created for subscription {sub['id']}")

        except Exception as e:
            logger.error(
                f"Failed to create auto-renewal payment for subscription {sub['id']}: {e}",
                exc_info=True,
            )

    if count > 0:
        logger.info(f"Created {count} auto-renewal payments")

    return count


async def _send_subscription_notification(
    user_id: int,
    subscription: Dict[str, Any],
    plan: Dict[str, Any],
    carryover_result: Optional[Dict[str, int]] = None,
) -> None:
    """Отправляет уведомление в Telegram об активации подписки."""
    try:
        from src.bot import get_bot
        from src.services.db.pool import get_pool

        # Получить telegram_user_id
        pool = get_pool()
        async with pool.acquire() as conn:
            telegram_user_id = await conn.fetchval(
                "SELECT telegram_user_id FROM users WHERE id = $1",
                user_id
            )

        if not telegram_user_id:
            logger.warning(f"Could not find telegram_user_id for user {user_id}")
            return

        # Получить глобальный экземпляр бота
        bot = get_bot()

        expires_at = subscription["expires_at"]
        expires_str = expires_at.strftime("%d.%m.%Y") if hasattr(expires_at, "strftime") else str(expires_at)

        carryover = carryover_result.get("carryover", 0) if carryover_result else 0
        carryover_line = f"\n🔄 Перенесено с прошлого периода: {carryover}" if carryover > 0 else ""

        message_text = (
            "🎉 <b>Подписка активирована!</b>\n\n"
            f"📅 План: {plan['name']}\n"
            f"⏱ Действует до: {expires_str}\n"
            f"🎁 Начислено токенов: {plan['tokens_included']}"
            f"{carryover_line}\n\n"
            "Спасибо за вашу поддержку! 🌱"
        )

        await bot.send_message(
            chat_id=telegram_user_id,
            text=message_text,
            parse_mode="HTML"
        )

        # Логируем уведомление в БД для отображения в админке
        try:
            from src.services.db.messages_repo import log_message
            await log_message(
                user_id=user_id,
                direction="bot",
                text=message_text,
                session_id=f"tg:{telegram_user_id}",
            )
        except Exception:
            pass

        logger.info(f"Subscription notification sent to user {telegram_user_id}")

    except Exception as e:
        logger.error(f"Failed to send subscription notification: {e}", exc_info=True)
