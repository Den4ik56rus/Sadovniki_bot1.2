"""
Сервис для управления платежами.

Основные функции:
    - create_token_payment — создать платеж для покупки токенов
    - create_subscription_payment — создать платеж для подписки
    - create_guide_payment — создать платеж для гайда (готовое решение)
    - process_payment_success — обработать успешный платеж
    - process_payment_canceled — обработать отмену платежа
"""

import asyncio
import json
import logging
import os
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from decimal import Decimal

from src.services.payments.yookassa_client import yookassa_client
from src.services.db import payment_repo, token_package_repo, subscription_plan_repo, user_subscription_repo, client_crm_repo, guide_repo
from src.services.db.pool import get_pool
from src.services.db.tokens_repo import add_tokens, add_purchased_tokens
from src.config import settings

logger = logging.getLogger(__name__)


async def _apply_invite_discount(user_id: int, original_price: Decimal) -> tuple:
    """
    Проверяет наличие скидки по инвайт-ссылке и применяет.
    Возвращает (final_price, discount_percent или None).
    """
    from src.services.db.invite_link_repo import get_user_active_discount
    _inv = await get_user_active_discount(user_id)
    discount_percent = _inv["discount_percent"] if _inv else None
    if discount_percent and discount_percent > 0:
        discount_amount = original_price * Decimal(discount_percent) / Decimal(100)
        final_price = original_price - discount_amount
        # Минимальная цена 1 рубль (требование ЮKassa)
        if final_price < Decimal('1.00'):
            final_price = Decimal('1.00')
        return final_price, discount_percent
    return original_price, None


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
        elif payment['payment_type'] == 'guide':
            guide_order = await guide_repo.get_by_payment_id(payment['id'])
            product_name = f"Готовое решение: {guide_order['culture_display']}" if guide_order else 'Готовое решение'

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
    # Проверить активную подписку — допы только для подписчиков
    from src.services.payments.subscription_service import get_active_subscription
    active_sub = await get_active_subscription(user_id)
    if not active_sub:
        raise ValueError("Покупка дополнительных токенов доступна только подписчикам")

    # Получить пакет токенов
    package = await token_package_repo.get_by_id(package_id)
    if not package:
        raise ValueError(f"Token package {package_id} not found")

    if not package["is_active"]:
        raise ValueError(f"Token package {package_id} is not active")

    # Применить скидку: подписочная или инвайтовая (берём максимальную)
    original_price = Decimal(str(package["price_rub"]))

    sub_discount = 0
    plan_data = active_sub.get("plan")
    if plan_data:
        sub_discount = plan_data.get("token_discount_percent", 0) or 0

    _, invite_discount = await _apply_invite_discount(user_id, original_price)
    invite_discount = invite_discount or 0

    discount_percent = max(sub_discount, invite_discount) if (sub_discount or invite_discount) else 0

    if discount_percent > 0:
        discount_amount = original_price * Decimal(discount_percent) / Decimal(100)
        final_price = original_price - discount_amount
        if final_price < Decimal('1.00'):
            final_price = Decimal('1.00')
    else:
        final_price = original_price
        discount_percent = None

    # Генерировать ключ идемпотентности
    idempotency_key = f"tokens_{user_id}_{package_id}_{int(datetime.now().timestamp())}"

    # Описание для чека
    description_text = package["description"]
    if discount_percent:
        description_text = f"{package['description']} (скидка {discount_percent}%)"

    # Создать элементы чека
    receipt_items = yookassa_client.create_receipt_items(
        description=description_text,
        amount_rub=final_price,
        quantity=1,
    )

    # Метаданные для webhook
    metadata = {
        "user_id": str(user_id),
        "telegram_user_id": str(telegram_user_id),
        "payment_type": "tokens",
        "package_id": str(package_id),
    }
    if discount_percent:
        metadata["discount_percent"] = str(discount_percent)
        metadata["original_price_rub"] = str(original_price)

    try:
        # Создать платеж в YooKassa
        yookassa_payment = await yookassa_client.create_payment(
            amount_rub=final_price,
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
            amount_rub=float(final_price),
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
            f"{f', discount={discount_percent}%' if discount_percent else ''}"
        )

        return {
            "payment_id": payment["id"],
            "yookassa_payment_id": yookassa_payment["id"],
            "confirmation_url": yookassa_payment["confirmation"]["confirmation_url"],
            "amount": float(final_price),
            "original_amount": float(original_price) if discount_percent else None,
            "discount_percent": discount_percent,
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

    # Применить скидку по инвайт-ссылке
    original_price = Decimal(str(plan["price_rub"]))
    final_price, discount_percent = await _apply_invite_discount(user_id, original_price)

    # Генерировать ключ идемпотентности
    idempotency_key = f"subscription_{user_id}_{plan_id}_{int(datetime.now().timestamp())}"

    # Описание для чека
    description_text = f"Подписка {plan['name']} ({plan['duration_days']} дней)"
    if discount_percent:
        description_text = f"{description_text} (скидка {discount_percent}%)"

    # Создать элементы чека
    receipt_items = yookassa_client.create_receipt_items(
        description=description_text,
        amount_rub=final_price,
        quantity=1,
    )

    # Метаданные для webhook
    metadata = {
        "user_id": str(user_id),
        "telegram_user_id": str(telegram_user_id),
        "payment_type": "subscription",
        "plan_id": str(plan_id),
    }
    if discount_percent:
        metadata["discount_percent"] = str(discount_percent)
        metadata["original_price_rub"] = str(original_price)

    try:
        # Создать платеж в YooKassa с сохранением способа оплаты для автопродления
        yookassa_payment = await yookassa_client.create_payment(
            amount_rub=final_price,
            description=f"Подписка {plan['name']}",
            return_url=return_url or settings.YOOKASSA_RETURN_URL,
            user_telegram_id=telegram_user_id,
            user_email=user_email,
            receipt_items=receipt_items if settings.YOOKASSA_SEND_RECEIPT else None,
            metadata=metadata,
            idempotence_key=idempotency_key,
            save_payment_method=False,  # Рекуррентные платежи требуют отдельного разрешения от ЮКассы
        )

        # Сохранить в БД
        payment = await payment_repo.create_payment(
            user_id=user_id,
            yookassa_payment_id=yookassa_payment["id"],
            idempotency_key=idempotency_key,
            payment_type="subscription",
            amount_rub=float(final_price),
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
            f"{f', discount={discount_percent}%' if discount_percent else ''}"
        )

        return {
            "payment_id": payment["id"],
            "yookassa_payment_id": yookassa_payment["id"],
            "confirmation_url": yookassa_payment["confirmation"]["confirmation_url"],
            "amount": float(final_price),
            "original_amount": float(original_price) if discount_percent else None,
            "discount_percent": discount_percent,
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


async def create_guide_payment(
    user_id: int,
    telegram_user_id: int,
    culture_key: str,
    culture_display: str,
    return_url: Optional[str] = None,
    user_email: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Создает платеж для гайда (готовое решение).

    Args:
        user_id: Внутренний ID пользователя
        telegram_user_id: Telegram ID пользователя
        culture_key: Ключ культуры ("малина летняя")
        culture_display: Отображаемое название ("Малина летняя")
        return_url: URL для возврата (по умолчанию - бот)
        user_email: Email пользователя для чека

    Returns:
        Словарь с данными платежа + guide_order_id

    Raises:
        Exception: При ошибке создания платежа
    """
    from src.pricing import COMPLEXITY_TIERS
    turnkey = COMPLEXITY_TIERS["turnkey_solution"]
    price_rub = Decimal(str(turnkey["price_rub"]))

    # Создать заказ на гайд
    guide_order = await guide_repo.create_order(
        user_id=user_id,
        culture_key=culture_key,
        culture_display=culture_display,
        status="payment_pending",
    )

    # Ключ идемпотентности
    idempotency_key = f"guide_{user_id}_{culture_key}_{int(datetime.now().timestamp())}"

    # Чек для 54-ФЗ
    receipt_items = yookassa_client.create_receipt_items(
        description=f"Готовое решение: уход за {culture_display} на сезон",
        amount_rub=price_rub,
        quantity=1,
    )

    # Метаданные
    metadata = {
        "user_id": str(user_id),
        "telegram_user_id": str(telegram_user_id),
        "payment_type": "guide",
        "guide_order_id": str(guide_order["id"]),
        "culture_key": culture_key,
    }

    try:
        # Создать платёж в YooKassa
        yookassa_payment = await yookassa_client.create_payment(
            amount_rub=price_rub,
            description=f"Готовое решение: {culture_display}",
            return_url=return_url or settings.YOOKASSA_RETURN_URL,
            user_telegram_id=telegram_user_id,
            user_email=user_email,
            receipt_items=receipt_items if settings.YOOKASSA_SEND_RECEIPT else None,
            metadata=metadata,
            idempotence_key=idempotency_key,
        )

        # Сохранить платёж в БД
        payment = await payment_repo.create_payment(
            user_id=user_id,
            yookassa_payment_id=yookassa_payment["id"],
            idempotency_key=idempotency_key,
            payment_type="guide",
            amount_rub=float(price_rub),
            description=f"Готовое решение: {culture_display}",
            confirmation_url=yookassa_payment["confirmation"]["confirmation_url"],
            metadata=metadata,
        )

        # Привязать платёж к заказу
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE guide_orders SET payment_id = $1 WHERE id = $2",
                payment["id"], guide_order["id"],
            )

        # Событие в activity feed
        await create_payment_activity_event(user_id, payment["id"])

        logger.info(
            f"Guide payment created: payment_id={payment['id']}, "
            f"guide_order_id={guide_order['id']}, culture={culture_key}"
        )

        return {
            "payment_id": payment["id"],
            "yookassa_payment_id": yookassa_payment["id"],
            "confirmation_url": yookassa_payment["confirmation"]["confirmation_url"],
            "amount": float(price_rub),
            "description": f"Готовое решение: {culture_display}",
            "guide_order_id": guide_order["id"],
        }

    except Exception as e:
        logger.error(f"Failed to create guide payment: {e}", exc_info=True)
        await guide_repo.update_status(guide_order["id"], "failed", error_message=str(e))
        await payment_repo.log_payment_error(
            user_id=user_id,
            payment_id=None,
            error_code="guide_payment_creation_failed",
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
        elif payment["payment_type"] == "guide":
            await _process_guide_payment_success(payment, verified_payment)
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

    # Начислить купленные токены
    new_balance = await add_purchased_tokens(
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
            f"🔑 Новый баланс: {new_balance} токенов\n\n"
            "Токены доступны для использования прямо сейчас!"
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
                user_id=payment["user_id"],
                direction="bot",
                text=message_text,
                session_id=f"tg:{telegram_user_id}",
            )
        except Exception:
            pass

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

        # Логируем уведомление в БД для отображения в админке
        try:
            from src.services.db.messages_repo import log_message
            await log_message(
                user_id=payment["user_id"],
                direction="bot",
                text=message_text,
                session_id=f"tg:{telegram_user_id}",
            )
        except Exception:
            pass

        logger.info(f"Subscription notification sent to user {telegram_user_id}")

    except Exception as e:
        logger.error(f"Failed to send subscription notification: {e}", exc_info=True)


# ─── Обработка платежей за гайды (Готовое решение) ───

async def _process_guide_payment_success(
    payment: Dict[str, Any],
    yookassa_payment: Dict[str, Any],
) -> None:
    """Обрабатывает успешный платеж за гайд — запускает генерацию в фоне."""
    # Найти заказ на гайд
    guide_order = await guide_repo.get_by_payment_id(payment["id"])
    if not guide_order:
        # Попробовать через metadata
        metadata = payment.get("metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        order_id = metadata.get("guide_order_id")
        if order_id:
            guide_order = await guide_repo.get_by_id(int(order_id))

    if not guide_order:
        raise ValueError(f"Guide order not found for payment {payment['id']}")

    # Обновить статус → generating
    await guide_repo.update_status(guide_order["id"], "generating")

    # Уведомить пользователя о начале генерации
    await _send_guide_started_notification(payment, guide_order)

    # Запустить генерацию в фоновой задаче (не блокировать webhook)
    asyncio.create_task(
        _generate_and_deliver_guide(payment, guide_order)
    )


async def _generate_and_deliver_guide(
    payment: Dict[str, Any],
    guide_order: Dict[str, Any],
) -> None:
    """
    Фоновая задача: генерация контента LLM → PDF-книга → доставка.

    Выполняется как asyncio.create_task() чтобы не блокировать webhook.
    """
    order_id = guide_order["id"]

    try:
        from src.services.llm.guide_generation_llm import generate_full_guide
        from src.services.pdf_generator import generate_guide_pdf

        culture = guide_order["culture_key"]
        culture_display = guide_order["culture_display"]

        # 1. Генерация контента через LLM (5 последовательных запросов)
        logger.info(f"[guide] Шаг 1/2: Генерация LLM контента для заказа {order_id}")
        guide_data = await generate_full_guide(culture=culture)

        # Сохранить контент в БД (для повторной генерации PDF при ошибке)
        await guide_repo.update_content_with_meta(
            order_id=order_id,
            content_json=guide_data,
            sections_meta=guide_data.get("sections_meta", {}),
            total_llm_cost_usd=guide_data["total_cost_usd"],
            total_llm_tokens=guide_data["total_tokens"],
            llm_model=guide_data.get("model", ""),
        )

        # 2. Генерация PDF-книги из контента
        logger.info(f"[guide] Шаг 2/2: Генерация PDF для заказа {order_id}")
        pdf_path = await generate_guide_pdf(
            sections=guide_data["sections"],
            culture=culture,
            culture_display=culture_display,
        )

        file_size = os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 0

        # Сохранить информацию о файле
        await guide_repo.update_file(
            order_id=order_id,
            file_path=pdf_path,
            file_format="pdf",
            file_size_bytes=file_size,
        )

        # 3. Доставить пользователю через Telegram
        telegram_file_id = await _deliver_guide_to_user(payment, guide_order, pdf_path)

        # 4. Отметить как завершённый
        await guide_repo.update_delivery(order_id, telegram_file_id or "")

        logger.info(
            f"[guide] Заказ {order_id} завершён: culture={culture}, "
            f"cost=${guide_data['total_cost_usd']:.4f}, file_size={file_size}"
        )

    except Exception as e:
        logger.error(f"[guide] Ошибка генерации заказа {order_id}: {e}", exc_info=True)
        await guide_repo.update_status(order_id, "failed", error_message=str(e))
        await _send_guide_error_notification(payment, guide_order, str(e))


# ── Бесплатная генерация гайда (без оплаты) ────────────────────────────────

async def generate_guide_free(
    user_id: int,
    telegram_user_id: int,
    culture_key: str,
    culture_display: str,
) -> int:
    """
    Запускает генерацию гайда без оплаты.

    Создаёт guide_order со статусом "generating" и запускает
    фоновую задачу генерации + доставки PDF.

    Returns:
        ID созданного заказа
    """
    # Создать заказ сразу со статусом "generating"
    guide_order = await guide_repo.create_order(
        user_id=user_id,
        culture_key=culture_key,
        culture_display=culture_display,
        payment_id=None,
        status="generating",
    )
    order_id = guide_order["id"]

    logger.info(
        f"[guide-free] Создан бесплатный заказ {order_id}: "
        f"user={user_id}, culture={culture_key}"
    )

    # Уведомить пользователя
    try:
        from src.bot import get_bot
        bot = get_bot()
        text = (
            f"Готовлю ваше руководство...\n\n"
            f"Культура: {culture_display}\n\n"
            f"Генерация может занять до 10 минут — мы тщательно прорабатываем "
            f"каждый раздел, чтобы информация была максимально полной и без повторов.\n\n"
            f"Включите уведомления, чтобы не пропустить готовый документ!"
        )
        await bot.send_message(chat_id=telegram_user_id, text=text)

        try:
            from src.services.db.messages_repo import log_message
            await log_message(
                user_id=user_id,
                direction="bot",
                text=text,
                session_id=f"tg:{telegram_user_id}",
            )
        except Exception:
            pass
    except Exception as e:
        logger.error(f"[guide-free] Ошибка уведомления: {e}")

    # Запустить генерацию в фоне
    asyncio.create_task(
        _generate_and_deliver_guide_free(user_id, telegram_user_id, guide_order)
    )

    return order_id


async def _generate_and_deliver_guide_free(
    user_id: int,
    telegram_user_id: int,
    guide_order: Dict[str, Any],
) -> None:
    """Фоновая генерация + доставка гайда (без привязки к платежу)."""
    order_id = guide_order["id"]

    try:
        from src.services.llm.guide_generation_llm import generate_full_guide
        from src.services.pdf_generator import generate_guide_pdf

        culture = guide_order["culture_key"]
        culture_display = guide_order["culture_display"]

        # 1. Генерация контента через LLM
        logger.info(f"[guide-free] Шаг 1/2: LLM контент для заказа {order_id}")
        guide_data = await generate_full_guide(culture=culture)

        await guide_repo.update_content_with_meta(
            order_id=order_id,
            content_json=guide_data,
            sections_meta=guide_data.get("sections_meta", {}),
            total_llm_cost_usd=guide_data["total_cost_usd"],
            total_llm_tokens=guide_data["total_tokens"],
            llm_model=guide_data.get("model", ""),
        )

        # 2. Генерация PDF
        logger.info(f"[guide-free] Шаг 2/2: PDF для заказа {order_id}")
        pdf_path = await generate_guide_pdf(
            sections=guide_data["sections"],
            culture=culture,
            culture_display=culture_display,
        )

        file_size = os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 0
        await guide_repo.update_file(
            order_id=order_id,
            file_path=pdf_path,
            file_format="pdf",
            file_size_bytes=file_size,
        )

        # 3. Доставить пользователю
        from src.bot import get_bot
        from aiogram.types import FSInputFile

        bot = get_bot()
        caption = (
            f"Ваше готовое решение «Уход за {culture_display} на сезон» готово!\n\n"
            f"Включает: питание, защита, уходные работы, чек-лист по месяцам."
        )
        document = FSInputFile(pdf_path, filename=f"Уход за {culture_display} — руководство.pdf")
        result = await bot.send_document(
            chat_id=telegram_user_id,
            document=document,
            caption=caption,
        )

        try:
            from src.services.db.messages_repo import log_message
            await log_message(
                user_id=user_id,
                direction="bot",
                text=caption,
                session_id=f"tg:{telegram_user_id}",
            )
        except Exception:
            pass

        telegram_file_id = result.document.file_id if result.document else ""

        # 4. Отметить как завершённый
        await guide_repo.update_delivery(order_id, telegram_file_id)

        logger.info(
            f"[guide-free] Заказ {order_id} завершён: culture={culture}, "
            f"cost=${guide_data['total_cost_usd']:.4f}, file_size={file_size}"
        )

    except Exception as e:
        logger.error(f"[guide-free] Ошибка генерации заказа {order_id}: {e}", exc_info=True)
        await guide_repo.update_status(order_id, "failed", error_message=str(e))

        # Уведомить об ошибке
        try:
            from src.bot import get_bot
            bot = get_bot()
            text = (
                "К сожалению, при генерации документа произошла ошибка.\n\n"
                "Попробуйте снова позже или свяжитесь с поддержкой: @sadovniki_support"
            )
            await bot.send_message(chat_id=telegram_user_id, text=text)
        except Exception:
            pass


async def _deliver_guide_to_user(
    payment: Dict[str, Any],
    guide_order: Dict[str, Any],
    file_path: str,
) -> Optional[str]:
    """Отправляет PDF файл пользователю в Telegram."""
    try:
        from src.bot import get_bot
        from aiogram.types import FSInputFile

        pool = get_pool()
        async with pool.acquire() as conn:
            telegram_user_id = await conn.fetchval(
                "SELECT telegram_user_id FROM users WHERE id = $1",
                payment["user_id"],
            )

        if not telegram_user_id:
            logger.warning(f"[guide] telegram_user_id не найден для user {payment['user_id']}")
            return None

        bot = get_bot()
        culture = guide_order["culture_display"]

        caption = (
            f"Ваше готовое решение «Уход за {culture} на сезон» готово!\n\n"
            f"Включает: питание, защита, уходные работы, чек-лист по месяцам."
        )

        document = FSInputFile(file_path, filename=f"Уход за {culture} — руководство.pdf")
        result = await bot.send_document(
            chat_id=telegram_user_id,
            document=document,
            caption=caption,
        )

        # Логируем в историю сообщений
        try:
            from src.services.db.messages_repo import log_message
            await log_message(
                user_id=payment["user_id"],
                direction="bot",
                text=caption,
                session_id=f"tg:{telegram_user_id}",
            )
        except Exception:
            pass

        logger.info(f"[guide] PDF доставлен пользователю {telegram_user_id}")
        return result.document.file_id if result.document else None

    except Exception as e:
        logger.error(f"[guide] Ошибка доставки PDF: {e}", exc_info=True)
        return None


async def _send_guide_started_notification(
    payment: Dict[str, Any],
    guide_order: Dict[str, Any],
) -> None:
    """Уведомляет пользователя о начале генерации гайда."""
    try:
        from src.bot import get_bot

        pool = get_pool()
        async with pool.acquire() as conn:
            telegram_user_id = await conn.fetchval(
                "SELECT telegram_user_id FROM users WHERE id = $1",
                payment["user_id"],
            )

        if not telegram_user_id:
            return

        bot = get_bot()
        culture = guide_order["culture_display"]

        text = (
            f"Оплата подтверждена! Готовлю ваше руководство...\n\n"
            f"Культура: {culture}\n"
            f"Сумма: {int(payment['amount_rub'])}₽\n\n"
            f"Генерация может занять до 10 минут — мы тщательно прорабатываем "
            f"каждый раздел, чтобы информация была максимально полной и без повторов.\n\n"
            f"Включите уведомления, чтобы не пропустить готовый документ!"
        )
        await bot.send_message(chat_id=telegram_user_id, text=text)

        try:
            from src.services.db.messages_repo import log_message
            await log_message(
                user_id=payment["user_id"],
                direction="bot",
                text=text,
                session_id=f"tg:{telegram_user_id}",
            )
        except Exception:
            pass

    except Exception as e:
        logger.error(f"[guide] Ошибка отправки уведомления о начале: {e}", exc_info=True)


async def _send_guide_error_notification(
    payment: Dict[str, Any],
    guide_order: Dict[str, Any],
    error: str,
) -> None:
    """Уведомляет пользователя об ошибке генерации."""
    try:
        from src.bot import get_bot

        pool = get_pool()
        async with pool.acquire() as conn:
            telegram_user_id = await conn.fetchval(
                "SELECT telegram_user_id FROM users WHERE id = $1",
                payment["user_id"],
            )

        if not telegram_user_id:
            return

        bot = get_bot()
        text = (
            "К сожалению, при генерации документа произошла ошибка.\n\n"
            "Мы уже знаем о проблеме и подготовим ваш документ в ближайшее время.\n"
            "Если у вас есть вопросы, свяжитесь с поддержкой: @sadovniki_support"
        )
        await bot.send_message(chat_id=telegram_user_id, text=text)

        try:
            from src.services.db.messages_repo import log_message
            await log_message(
                user_id=payment["user_id"],
                direction="bot",
                text=text,
                session_id=f"tg:{telegram_user_id}",
            )
        except Exception:
            pass

    except Exception as e:
        logger.error(f"[guide] Ошибка отправки уведомления об ошибке: {e}", exc_info=True)
