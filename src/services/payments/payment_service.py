"""
Сервис для управления платежами.

Основные функции:
    - create_token_payment — создать платеж для покупки токенов
    - create_subscription_payment — создать платеж для подписки
    - process_payment_success — обработать успешный платеж
    - process_payment_canceled — обработать отмену платежа
"""

import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from decimal import Decimal

from src.services.payments.yookassa_client import yookassa_client
from src.services.db import payment_repo, token_package_repo, subscription_plan_repo, user_subscription_repo, client_crm_repo
from src.services.db.tokens_repo import add_tokens
from src.config import settings

logger = logging.getLogger(__name__)


async def create_payment_activity_event(user_id: int, payment_id: int):
    """
    Создать событие 'payment' в activity feed.

    Args:
        user_id: ID пользователя
        payment_id: ID платежа
    """
    try:
        payment = await payment_repo.get_by_id(payment_id)
        if not payment:
            logger.warning(f"Payment {payment_id} not found for activity event")
            return

        # Определить product_name
        product_name = "Платёж"
        if payment['payment_type'] == 'subscription':
            plan = await subscription_plan_repo.get_by_id(payment['subscription_plan_id'])
            product_name = plan['name'] if plan else 'Подписка'
        elif payment['payment_type'] == 'tokens':
            package = await token_package_repo.get_by_id(payment['token_package_id'])
            product_name = package['name'] if package else 'Токены'

        event_data = {
            'payment_id': payment_id,
            'amount_rub': float(payment['amount_rub']),
            'payment_type': payment['payment_type'],
            'paid': payment['paid'],
            'product_name': product_name,
            'paid_at': payment['paid_at'].isoformat() if payment['paid_at'] else None,
        }

        await client_crm_repo.create_activity_event(
            user_id=user_id,
            event_type='payment',
            event_data=event_data,
        )

        logger.info(f"Created payment activity event for user {user_id}, payment {payment_id}")
    except Exception as e:
        logger.error(f"Failed to create payment activity event: {e}", exc_info=True)


async def create_token_payment(
    user_id: int,
    telegram_user_id: int,
    package_id: int,
    return_url: Optional[str] = None,
    user_email: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Создает платеж для покупки пакета токенов.

    Args:
        user_id: Внутренний ID пользователя
        telegram_user_id: Telegram ID пользователя
        package_id: ID пакета токенов
        return_url: URL для возврата (по умолчанию - бот)
        user_email: Email пользователя для чека

    Returns:
        Словарь с данными платежа: payment_id, confirmation_url

    Raises:
        ValueError: Если пакет не найден или неактивен
    """
    # Получить пакет токенов
    package = await token_package_repo.get_by_id(package_id)
    if not package:
        raise ValueError(f"Token package {package_id} not found")

    if not package["is_active"]:
        raise ValueError(f"Token package {package_id} is not active")

    # Генерировать ключ идемпотентности
    idempotency_key = f"tokens_{user_id}_{package_id}_{int(datetime.now().timestamp())}"

    # Создать элементы чека
    receipt_items = yookassa_client.create_receipt_items(
        description=package["description"],
        amount_rub=Decimal(str(package["price_rub"])),
        quantity=1,
    )

    # Метаданные для webhook
    metadata = {
        "user_id": str(user_id),
        "telegram_user_id": str(telegram_user_id),
        "payment_type": "tokens",
        "package_id": str(package_id),
    }

    try:
        # Создать платеж в YooKassa
        yookassa_payment = await yookassa_client.create_payment(
            amount_rub=Decimal(str(package["price_rub"])),
            description=f"Покупка: {package['name']}",
            return_url=return_url or settings.YOOKASSA_RETURN_URL,
            user_telegram_id=telegram_user_id,
            user_email=user_email,
            receipt_items=receipt_items if settings.YOOKASSA_SEND_RECEIPT else None,
            metadata=metadata,
            idempotence_key=idempotency_key,
        )

        # Сохранить в БД
        payment = await payment_repo.create_payment(
            user_id=user_id,
            yookassa_payment_id=yookassa_payment["id"],
            idempotency_key=idempotency_key,
            payment_type="tokens",
            amount_rub=float(package["price_rub"]),
            description=f"Покупка: {package['name']}",
            confirmation_url=yookassa_payment["confirmation"]["confirmation_url"],
            token_package_id=package_id,
            metadata=metadata,
        )

        # Создать событие в activity feed для pending платежа
        await create_payment_activity_event(user_id, payment["id"])

        logger.info(
            f"Token payment created: payment_id={payment['id']}, "
            f"yookassa_id={yookassa_payment['id']}, user={user_id}, package={package_id}"
        )

        return {
            "payment_id": payment["id"],
            "yookassa_payment_id": yookassa_payment["id"],
            "confirmation_url": yookassa_payment["confirmation"]["confirmation_url"],
            "amount": package["price_rub"],
            "description": package["name"],
        }

    except Exception as e:
        logger.error(f"Failed to create token payment: {e}", exc_info=True)
        await payment_repo.log_payment_error(
            user_id=user_id,
            payment_id=None,
            error_code="payment_creation_failed",
            error_message=str(e),
        )
        raise


async def create_subscription_payment(
    user_id: int,
    telegram_user_id: int,
    plan_id: int,
    return_url: Optional[str] = None,
    user_email: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Создает платеж для подписки.

    Args:
        user_id: Внутренний ID пользователя
        telegram_user_id: Telegram ID пользователя
        plan_id: ID тарифного плана
        return_url: URL для возврата (по умолчанию - бот)
        user_email: Email пользователя для чека

    Returns:
        Словарь с данными платежа: payment_id, confirmation_url

    Raises:
        ValueError: Если план не найден или неактивен
    """
    # Получить план подписки
    plan = await subscription_plan_repo.get_by_id(plan_id)
    if not plan:
        raise ValueError(f"Subscription plan {plan_id} not found")

    if not plan["is_active"]:
        raise ValueError(f"Subscription plan {plan_id} is not active")

    # Генерировать ключ идемпотентности
    idempotency_key = f"subscription_{user_id}_{plan_id}_{int(datetime.now().timestamp())}"

    # Создать элементы чека
    receipt_items = yookassa_client.create_receipt_items(
        description=f"Подписка {plan['name']} ({plan['duration_days']} дней)",
        amount_rub=Decimal(str(plan["price_rub"])),
        quantity=1,
    )

    # Метаданные для webhook
    metadata = {
        "user_id": str(user_id),
        "telegram_user_id": str(telegram_user_id),
        "payment_type": "subscription",
        "plan_id": str(plan_id),
    }

    try:
        # Создать платеж в YooKassa с сохранением способа оплаты для автопродления
        yookassa_payment = await yookassa_client.create_payment(
            amount_rub=Decimal(str(plan["price_rub"])),
            description=f"Подписка {plan['name']}",
            return_url=return_url or settings.YOOKASSA_RETURN_URL,
            user_telegram_id=telegram_user_id,
            user_email=user_email,
            receipt_items=receipt_items if settings.YOOKASSA_SEND_RECEIPT else None,
            metadata=metadata,
            idempotence_key=idempotency_key,
            save_payment_method=True,  # Сохранить способ оплаты для автоплатежей
        )

        # Сохранить в БД
        payment = await payment_repo.create_payment(
            user_id=user_id,
            yookassa_payment_id=yookassa_payment["id"],
            idempotency_key=idempotency_key,
            payment_type="subscription",
            amount_rub=float(plan["price_rub"]),
            description=f"Подписка {plan['name']}",
            confirmation_url=yookassa_payment["confirmation"]["confirmation_url"],
            subscription_plan_id=plan_id,
            metadata=metadata,
        )

        # Создать событие в activity feed для pending платежа
        await create_payment_activity_event(user_id, payment["id"])

        logger.info(
            f"Subscription payment created: payment_id={payment['id']}, "
            f"yookassa_id={yookassa_payment['id']}, user={user_id}, plan={plan_id}"
        )

        return {
            "payment_id": payment["id"],
            "yookassa_payment_id": yookassa_payment["id"],
            "confirmation_url": yookassa_payment["confirmation"]["confirmation_url"],
            "amount": plan["price_rub"],
            "description": f"Подписка {plan['name']}",
        }

    except Exception as e:
        logger.error(f"Failed to create subscription payment: {e}", exc_info=True)
        await payment_repo.log_payment_error(
            user_id=user_id,
            payment_id=None,
            error_code="payment_creation_failed",
            error_message=str(e),
        )
        raise


async def create_recurrent_subscription_payment(
    user_id: int,
    subscription_id: int,
    plan_id: int,
    payment_method_id: str,
) -> Dict[str, Any]:
    """
    Создает рекуррентный платеж для автоматического продления подписки.

    Args:
        user_id: ID пользователя в нашей БД
        subscription_id: ID текущей подписки
        plan_id: ID тарифного плана
        payment_method_id: ID сохраненного способа оплаты

    Returns:
        Словарь с данными созданного платежа

    Raises:
        ValueError: Если план не найден
        aiohttp.ClientError: При ошибке API
    """
    try:
        # Получить план
        plan = await subscription_plan_repo.get_by_id(plan_id)
        if not plan:
            raise ValueError(f"Subscription plan {plan_id} not found")

        # Получить данные пользователя
        pool = get_pool()
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT telegram_user_id, email FROM users WHERE id = $1",
                user_id,
            )

        if not user:
            raise ValueError(f"User {user_id} not found")

        # Идемпотентность: генерируем уникальный ключ на основе subscription_id
        idempotency_key = f"renewal-{subscription_id}-{datetime.now().strftime('%Y%m%d')}"

        metadata = {
            "user_id": str(user_id),
            "telegram_user_id": str(user["telegram_user_id"]),
            "payment_type": "subscription_renewal",
            "subscription_id": str(subscription_id),
            "subscription_plan_id": str(plan_id),
        }

        # Создать чек для 54-ФЗ
        receipt_items = None
        if settings.YOOKASSA_SEND_RECEIPT:
            receipt_items = yookassa_client.create_receipt_items(
                description=f"Продление подписки {plan['name']}",
                amount_rub=Decimal(str(plan["price_rub"])),
                quantity=1,
            )

        # Создать платеж через YooKassa API с сохраненным способом оплаты
        yookassa_payment = await yookassa_client.create_payment(
            amount_rub=Decimal(str(plan["price_rub"])),
            description=f"Продление подписки {plan['name']}",
            return_url=settings.YOOKASSA_RETURN_URL,
            user_telegram_id=user["telegram_user_id"],
            user_email=user["email"],
            receipt_items=receipt_items if settings.YOOKASSA_SEND_RECEIPT else None,
            metadata=metadata,
            idempotence_key=idempotency_key,
            payment_method_id=payment_method_id,  # Использовать сохраненный способ оплаты
        )

        # Сохранить платеж в БД
        payment = await payment_repo.create(
            user_id=user_id,
            payment_type="subscription_renewal",
            amount_rub=Decimal(str(plan["price_rub"])),
            yookassa_payment_id=yookassa_payment["id"],
            status=yookassa_payment["status"],
            paid=yookassa_payment.get("paid", False),
            subscription_plan_id=plan_id,
            metadata=metadata,
        )

        # Обновить next_billing_date в подписке (сдвинуть на период плана)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE user_subscriptions
                SET next_billing_date = next_billing_date + INTERVAL '1 day' * $2,
                    updated_at = NOW()
                WHERE id = $1
                """,
                subscription_id,
                plan["duration_days"],
            )

        logger.info(
            f"Recurrent payment created: payment_id={payment['id']}, "
            f"yookassa_id={yookassa_payment['id']}, subscription={subscription_id}"
        )

        return {
            "payment_id": payment["id"],
            "yookassa_payment_id": yookassa_payment["id"],
            "amount": plan["price_rub"],
            "subscription_id": subscription_id,
        }

    except Exception as e:
        logger.error(f"Failed to create recurrent payment: {e}", exc_info=True)
        await payment_repo.log_payment_error(
            user_id=user_id,
            payment_id=None,
            error_code="recurrent_payment_failed",
            error_message=str(e),
        )
        raise


async def process_payment_success(
    yookassa_payment_id: str,
    yookassa_payment_object: Dict[str, Any],
) -> bool:
    """
    Обрабатывает успешный платеж.

    КРИТИЧНО: Идемпотентная обработка с проверками безопасности.

    Args:
        yookassa_payment_id: ID платежа в YooKassa
        yookassa_payment_object: Полный объект платежа от YooKassa

    Returns:
        True если обработка прошла успешно

    Raises:
        ValueError: При ошибках валидации
    """
    # Получить платеж из БД
    payment = await payment_repo.get_by_yookassa_id(yookassa_payment_id)
    if not payment:
        logger.error(f"Payment not found in DB: {yookassa_payment_id}")
        raise ValueError(f"Payment {yookassa_payment_id} not found")

    # Проверка идемпотентности
    if payment["status"] == "succeeded" and payment["paid"]:
        logger.info(f"Payment {payment['id']} already processed, skipping")
        return True

    # Верификация платежа через API YooKassa (КРИТИЧНО для безопасности)
    verified_payment = await yookassa_client.get_payment(yookassa_payment_id)

    if verified_payment["status"] != "succeeded" or not verified_payment.get("paid"):
        logger.error(
            f"Payment verification failed: {yookassa_payment_id}, "
            f"status={verified_payment['status']}, paid={verified_payment.get('paid')}"
        )
        raise ValueError("Payment verification failed")

    # Проверка суммы
    expected_amount = float(payment["amount_rub"])
    actual_amount = float(verified_payment["amount"]["value"])

    if abs(actual_amount - expected_amount) > 0.01:
        logger.error(
            f"Amount mismatch: expected={expected_amount}, actual={actual_amount}"
        )
        raise ValueError("Payment amount mismatch")

    # Проверка владельца
    metadata_user_id = int(verified_payment.get("metadata", {}).get("user_id", 0))
    if metadata_user_id != payment["user_id"]:
        logger.error(
            f"User mismatch: expected={payment['user_id']}, metadata={metadata_user_id}"
        )
        raise ValueError("Payment user mismatch")

    try:
        # Обработка в зависимости от типа платежа
        if payment["payment_type"] == "tokens":
            await _process_token_payment_success(payment, verified_payment)
        elif payment["payment_type"] == "subscription":
            await _process_subscription_payment_success(payment, verified_payment)
        elif payment["payment_type"] == "subscription_renewal":
            await _process_subscription_renewal_success(payment, verified_payment)
        else:
            raise ValueError(f"Unknown payment type: {payment['payment_type']}")

        # Обновить статус платежа
        await payment_repo.update_status(
            payment_id=payment["id"],
            status="succeeded",
            paid=True,
            paid_at=datetime.now(),
            yookassa_payment_object=verified_payment,
            webhook_verified=True,
            receipt_registration=verified_payment.get("receipt_registration"),
            fiscal_document_number=verified_payment.get("fiscal_document_number"),
        )

        # Создать событие в activity feed
        await create_payment_activity_event(payment["user_id"], payment["id"])

        logger.info(f"Payment {payment['id']} processed successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to process payment {payment['id']}: {e}", exc_info=True)
        await payment_repo.log_payment_error(
            user_id=payment["user_id"],
            payment_id=yookassa_payment_id,
            error_code="payment_processing_failed",
            error_message=str(e),
            yookassa_error_data=verified_payment,
        )
        raise


async def _process_token_payment_success(
    payment: Dict[str, Any],
    yookassa_payment: Dict[str, Any],
) -> None:
    """Обрабатывает успешный платеж за токены."""
    package = await token_package_repo.get_by_id(payment["token_package_id"])
    if not package:
        raise ValueError(f"Token package {payment['token_package_id']} not found")

    # Начислить токены
    new_balance = await add_tokens(
        user_id=payment["user_id"],
        amount=package["tokens_amount"],
        operation_type="payment_yookassa",
        description=f"Оплата пакета: {package['name']} (платеж {payment['yookassa_payment_id']})",
    )

    logger.info(
        f"Tokens credited: user={payment['user_id']}, "
        f"amount={package['tokens_amount']}, new_balance={new_balance}"
    )

    # Отправить уведомление в Telegram
    await _send_token_payment_notification(payment, package, new_balance)


async def _process_subscription_payment_success(
    payment: Dict[str, Any],
    yookassa_payment: Dict[str, Any],
) -> None:
    """Обрабатывает успешный платеж за подписку."""
    from src.services.payments.subscription_service import activate_subscription

    # Получить payment_method_id для автоплатежей
    payment_method_id = None
    if "payment_method" in yookassa_payment and yookassa_payment["payment_method"]:
        payment_method_id = yookassa_payment["payment_method"].get("id")

    await activate_subscription(
        user_id=payment["user_id"],
        plan_id=payment["subscription_plan_id"],
        payment_id=payment["id"],
        payment_method_id=payment_method_id,  # Передать для сохранения
    )


async def _process_subscription_renewal_success(
    payment: Dict[str, Any],
    yookassa_payment: Dict[str, Any],
) -> None:
    """Обрабатывает успешный платеж за продление подписки."""
    from src.services.payments.subscription_service import activate_subscription

    # Получить subscription_id из metadata
    metadata = payment.get("metadata", {})
    if isinstance(metadata, str):
        import json
        metadata = json.loads(metadata)

    subscription_id = metadata.get("subscription_id")
    if not subscription_id:
        logger.error(f"No subscription_id in renewal payment {payment['id']} metadata")
        raise ValueError("Missing subscription_id in renewal payment")

    # Продлить подписку - создается новая активация
    await activate_subscription(
        user_id=payment["user_id"],
        plan_id=payment["subscription_plan_id"],
        payment_id=payment["id"],
        payment_method_id=None,  # payment_method_id уже сохранен в подписке
    )

    logger.info(f"Subscription {subscription_id} renewed via payment {payment['id']}")


async def process_payment_canceled(
    yookassa_payment_id: str,
    yookassa_payment_object: Dict[str, Any],
) -> bool:
    """
    Обрабатывает отмену платежа.

    Args:
        yookassa_payment_id: ID платежа в YooKassa
        yookassa_payment_object: Полный объект платежа от YooKassa

    Returns:
        True если обработка прошла успешно
    """
    payment = await payment_repo.get_by_yookassa_id(yookassa_payment_id)
    if not payment:
        logger.warning(f"Canceled payment not found in DB: {yookassa_payment_id}")
        return False

    # Проверка идемпотентности
    if payment["status"] == "canceled":
        logger.info(f"Payment {payment['id']} already canceled, skipping")
        return True

    # Обновить статус
    await payment_repo.update_status(
        payment_id=payment["id"],
        status="canceled",
        paid=False,
        canceled_at=datetime.now(),
        yookassa_payment_object=yookassa_payment_object,
    )

    logger.info(f"Payment {payment['id']} canceled")
    return True


async def _send_token_payment_notification(
    payment: Dict[str, Any],
    package: Dict[str, Any],
    new_balance: int,
) -> None:
    """Отправляет уведомление в Telegram о успешной покупке токенов."""
    try:
        from src.bot import get_bot

        # Получить telegram_user_id из users
        from src.services.db.pool import get_pool
        pool = get_pool()
        async with pool.acquire() as conn:
            telegram_user_id = await conn.fetchval(
                "SELECT telegram_user_id FROM users WHERE id = $1",
                payment["user_id"]
            )

        if not telegram_user_id:
            logger.warning(f"Could not find telegram_user_id for user {payment['user_id']}")
            return

        # Получить глобальный экземпляр бота
        bot = get_bot()

        message_text = (
            "✅ <b>Оплата успешно завершена!</b>\n\n"
            f"📦 Пакет: {package['name']}\n"
            f"💰 Сумма: {int(payment['amount_rub'])}₽\n"
            f"🎁 Начислено токенов: {package['tokens_amount']}\n"
            f"🪙 Новый баланс: {new_balance} токенов\n\n"
            "Токены доступны для использования прямо сейчас!"
        )

        await bot.send_message(
            chat_id=telegram_user_id,
            text=message_text,
            parse_mode="HTML"
        )

        logger.info(f"Payment notification sent to user {telegram_user_id}")

    except Exception as e:
        logger.error(f"Failed to send payment notification: {e}", exc_info=True)


async def _send_subscription_notification(
    payment: Dict[str, Any],
    subscription: Dict[str, Any],
    plan: Dict[str, Any],
) -> None:
    """Отправляет уведомление в Telegram об активации подписки."""
    try:
        from src.bot import get_bot

        # Получить telegram_user_id из users
        from src.services.db.pool import get_pool
        pool = get_pool()
        async with pool.acquire() as conn:
            telegram_user_id = await conn.fetchval(
                "SELECT telegram_user_id FROM users WHERE id = $1",
                payment["user_id"]
            )

        if not telegram_user_id:
            logger.warning(f"Could not find telegram_user_id for user {payment['user_id']}")
            return

        # Получить глобальный экземпляр бота
        bot = get_bot()

        expires_at = subscription["expires_at"]
        expires_str = expires_at.strftime("%d.%m.%Y") if hasattr(expires_at, "strftime") else str(expires_at)

        message_text = (
            "🎉 <b>Подписка активирована!</b>\n\n"
            f"📅 План: {plan['name']}\n"
            f"💰 Стоимость: {int(payment['amount_rub'])}₽\n"
            f"⏱ Действует до: {expires_str}\n"
            f"🎁 Начислено токенов: {plan['tokens_included']}\n\n"
            "Спасибо за вашу поддержку! 🌱"
        )

        await bot.send_message(
            chat_id=telegram_user_id,
            text=message_text,
            parse_mode="HTML"
        )

        logger.info(f"Subscription notification sent to user {telegram_user_id}")

    except Exception as e:
        logger.error(f"Failed to send subscription notification: {e}", exc_info=True)
