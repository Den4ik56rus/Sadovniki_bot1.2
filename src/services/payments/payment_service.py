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
        elif payment['payment_type'] == 'quiz_plan':
            meta = payment.get('metadata', {})
            if isinstance(meta, str):
                meta = json.loads(meta)
            product_name = f"Персональный план: {meta.get('problem_display', 'квиз')}"
        elif payment['payment_type'] == 'flagship':
            meta = payment.get('metadata', {})
            if isinstance(meta, str):
                meta = json.loads(meta)
            product_name = meta.get('product_title', 'Сезонная программа')

        event_data = {
            'payment_id': payment_id,
            'amount_rub': float(payment['amount_rub']),
            'payment_type': payment['payment_type'],
            'paid': payment['paid'],
            'product_name': product_name,
            'paid_at': payment['paid_at'].isoformat() if payment['paid_at'] else None,
        }

        await client_crm_repo.log_activity(
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

    # Бонус токенов (%) по инвайт-ссылке
    import math
    from src.services.db.invite_link_repo import get_user_active_token_bonus
    invite_token_bonus_pct = await get_user_active_token_bonus(user_id)
    invite_bonus_tokens = 0
    if invite_token_bonus_pct and invite_token_bonus_pct > 0:
        invite_bonus_tokens = math.ceil(package['tokens_amount'] * invite_token_bonus_pct / 100)

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
    if invite_bonus_tokens > 0:
        metadata["bonus_tokens"] = str(invite_bonus_tokens)

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

    # Применить скидку — берём максимальную из инвайт-ссылки и рассылки
    original_price = Decimal(str(plan["price_rub"]))
    _, invite_discount_pct = await _apply_invite_discount(user_id, original_price)

    from src.services.db.discount_repo import get_user_active_broadcast_discount
    broadcast_disc = await get_user_active_broadcast_discount(user_id)
    broadcast_discount_pct = broadcast_disc['discount_percent'] if broadcast_disc else 0
    broadcast_bonus_tokens_raw = broadcast_disc['bonus_tokens'] if broadcast_disc else 0
    broadcast_bonus_mode = broadcast_disc.get('bonus_tokens_mode', 'absolute') if broadcast_disc else 'absolute'

    # Вычисляем бонусные токены: абсолютное число или % от tokens_included тарифа
    import math
    if broadcast_bonus_mode == 'percent' and broadcast_bonus_tokens_raw and broadcast_bonus_tokens_raw > 0:
        broadcast_bonus_tokens = math.ceil(plan['tokens_included'] * broadcast_bonus_tokens_raw / 100)
    else:
        broadcast_bonus_tokens = broadcast_bonus_tokens_raw

    # Бонус токенов (%) по инвайт-ссылке
    from src.services.db.invite_link_repo import get_user_active_token_bonus
    invite_token_bonus_pct = await get_user_active_token_bonus(user_id)
    invite_bonus_tokens = 0
    if invite_token_bonus_pct and invite_token_bonus_pct > 0:
        invite_bonus_tokens = math.ceil(plan['tokens_included'] * invite_token_bonus_pct / 100)

    # Берём максимальный бонус токенов из всех источников
    final_bonus_tokens = max(broadcast_bonus_tokens or 0, invite_bonus_tokens)

    best_pct = max(invite_discount_pct or 0, broadcast_discount_pct)
    if best_pct > 0:
        discount_amount = original_price * Decimal(best_pct) / Decimal(100)
        final_price = original_price - discount_amount
        if final_price < Decimal('1.00'):
            final_price = Decimal('1.00')
        discount_percent = best_pct
    else:
        final_price = original_price
        discount_percent = None

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
    # Бонусные токены (начисляются в process_payment_success)
    if final_bonus_tokens and final_bonus_tokens > 0:
        metadata["bonus_tokens"] = str(final_bonus_tokens)

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


async def create_subscription_payment_custom(
    user_id: int,
    telegram_user_id: int,
    plan_id: int,
    custom_price: Optional[int] = None,
    bonus_tokens: Optional[int] = None,
    return_url: Optional[str] = None,
    user_email: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Создать платёж для подписки с кастомной ценой/бонусными токенами (для триггеров воронки).

    Аналог create_subscription_payment, но цена/токены переопределяются из параметров.
    Бонусные токены сохраняются в metadata и начисляются на активации.

    Args:
        custom_price: Переопределённая цена в рублях (None = цена плана)
        bonus_tokens: Доп. токены сверх плана (None = без бонуса)
    """
    plan = await subscription_plan_repo.get_by_id(plan_id)
    if not plan:
        raise ValueError(f"Subscription plan {plan_id} not found")
    if not plan["is_active"]:
        raise ValueError(f"Subscription plan {plan_id} is not active")

    original_price = Decimal(str(plan["price_rub"]))
    final_price = Decimal(str(custom_price)) if custom_price else original_price
    discount_percent = 0
    if custom_price and final_price < original_price:
        discount_percent = round((1 - float(final_price) / float(original_price)) * 100)

    idempotency_key = f"subscription_custom_{user_id}_{plan_id}_{int(datetime.now().timestamp())}"

    description_text = f"Подписка {plan['name']} ({plan['duration_days']} дней)"
    if discount_percent:
        description_text = f"{description_text} (скидка {discount_percent}%)"

    receipt_items = yookassa_client.create_receipt_items(
        description=description_text,
        amount_rub=final_price,
        quantity=1,
    )

    metadata: Dict[str, Any] = {
        "user_id": str(user_id),
        "telegram_user_id": str(telegram_user_id),
        "payment_type": "subscription",
        "plan_id": str(plan_id),
    }
    if discount_percent:
        metadata["discount_percent"] = str(discount_percent)
        metadata["original_price_rub"] = str(original_price)
    if bonus_tokens:
        metadata["bonus_tokens"] = str(bonus_tokens)

    try:
        yookassa_payment = await yookassa_client.create_payment(
            amount_rub=final_price,
            description=f"Подписка {plan['name']}",
            return_url=return_url or settings.YOOKASSA_RETURN_URL,
            user_telegram_id=telegram_user_id,
            user_email=user_email,
            receipt_items=receipt_items if settings.YOOKASSA_SEND_RECEIPT else None,
            metadata=metadata,
            idempotence_key=idempotency_key,
            save_payment_method=False,
        )

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

        await create_payment_activity_event(user_id, payment["id"])

        logger.info(
            f"Custom subscription payment created: payment_id={payment['id']}, "
            f"user={user_id}, plan={plan_id}, price={final_price}"
            f"{f', bonus_tokens={bonus_tokens}' if bonus_tokens else ''}"
        )

        return {
            "payment_id": payment["id"],
            "yookassa_payment_id": yookassa_payment["id"],
            "confirmation_url": yookassa_payment["confirmation"]["confirmation_url"],
            "amount": float(final_price),
            "original_amount": float(original_price),
            "discount_percent": discount_percent,
            "description": f"Подписка {plan['name']}",
        }

    except Exception as e:
        logger.error(f"Failed to create custom subscription payment: {e}", exc_info=True)
        await payment_repo.log_payment_error(
            user_id=user_id,
            payment_id=None,
            error_code="payment_creation_failed",
            error_message=str(e),
        )
        raise


async def create_token_payment_custom(
    user_id: int,
    telegram_user_id: int,
    package_id: int,
    custom_price: Optional[int] = None,
    return_url: Optional[str] = None,
    user_email: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Создать платёж для покупки доп. токенов с кастомной ценой (для рассылок/воронок).

    Аналог create_token_payment, но цена переопределяется из параметров.
    Не требует активной подписки (для рассылок — оплата из письма).

    Args:
        custom_price: Переопределённая цена в рублях (None = цена пакета)
    """
    from src.services.db import token_package_repo
    package = await token_package_repo.get_by_id(package_id)
    if not package:
        raise ValueError(f"Token package {package_id} not found")
    if not package["is_active"]:
        raise ValueError(f"Token package {package_id} is not active")

    original_price = Decimal(str(package["price_rub"]))
    final_price = Decimal(str(custom_price)) if custom_price else original_price
    discount_percent = 0
    if custom_price and final_price < original_price:
        discount_percent = round((1 - float(final_price) / float(original_price)) * 100)

    idempotency_key = f"tokens_custom_{user_id}_{package_id}_{int(datetime.now().timestamp())}"

    description_text = f"Токены: {package['tokens_amount']} шт."
    if discount_percent:
        description_text = f"{description_text} (скидка {discount_percent}%)"

    receipt_items = yookassa_client.create_receipt_items(
        description=description_text,
        amount_rub=final_price,
        quantity=1,
    )

    metadata: Dict[str, Any] = {
        "user_id": str(user_id),
        "telegram_user_id": str(telegram_user_id),
        "payment_type": "tokens",
        "package_id": str(package_id),
    }
    if discount_percent:
        metadata["discount_percent"] = str(discount_percent)
        metadata["original_price_rub"] = str(original_price)

    try:
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

        await create_payment_activity_event(user_id, payment["id"])

        logger.info(
            f"Custom token payment created: payment_id={payment['id']}, "
            f"user={user_id}, package={package_id}, price={final_price}"
            f"{f', discount={discount_percent}%' if discount_percent else ''}"
        )

        return {
            "payment_id": payment["id"],
            "yookassa_payment_id": yookassa_payment["id"],
            "confirmation_url": yookassa_payment["confirmation"]["confirmation_url"],
            "amount": float(final_price),
            "original_amount": float(original_price),
            "discount_percent": discount_percent,
            "tokens_amount": package["tokens_amount"],
            "description": package["name"],
        }

    except Exception as e:
        logger.error(f"Failed to create custom token payment: {e}", exc_info=True)
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


async def create_quiz_plan_payment(
    user_id: int,
    telegram_user_id: int,
    culture_display: str,
    problem_display: str,
    problem_key: str = "",
    return_url: Optional[str] = None,
    user_email: Optional[str] = None,
    price_rub: float = 99.0,
) -> Dict[str, Any]:
    """
    Создает платеж за персональный план из квиза.

    Args:
        user_id: Внутренний ID пользователя
        telegram_user_id: Telegram ID пользователя
        culture_display: Название культуры (напр. "летней клубники")
        problem_display: Название проблемы (напр. "мелкие ягоды")
        problem_key: Ключ проблемы для lookup PDF-решения
        return_url: URL для возврата
        user_email: Email для чека
        price_rub: Цена в рублях (по умолчанию 99)

    Returns:
        Словарь с данными платежа: payment_id, confirmation_url, amount
    """
    price_rub = Decimal(str(price_rub))

    idempotency_key = f"quiz_plan_{user_id}_{int(datetime.now().timestamp())}"

    description_text = f"Персональный план: {problem_display} ({culture_display})"

    receipt_items = yookassa_client.create_receipt_items(
        description=description_text,
        amount_rub=price_rub,
        quantity=1,
    )

    metadata = {
        "user_id": str(user_id),
        "telegram_user_id": str(telegram_user_id),
        "payment_type": "quiz_plan",
        "culture_display": culture_display,
        "problem_display": problem_display,
        "problem_key": problem_key,
    }

    try:
        yookassa_payment = await yookassa_client.create_payment(
            amount_rub=price_rub,
            description=description_text,
            return_url=return_url or settings.YOOKASSA_RETURN_URL,
            user_telegram_id=telegram_user_id,
            user_email=user_email,
            receipt_items=receipt_items if settings.YOOKASSA_SEND_RECEIPT else None,
            metadata=metadata,
            idempotence_key=idempotency_key,
        )

        payment = await payment_repo.create_payment(
            user_id=user_id,
            yookassa_payment_id=yookassa_payment["id"],
            idempotency_key=idempotency_key,
            payment_type="quiz_plan",
            amount_rub=float(price_rub),
            description=description_text,
            confirmation_url=yookassa_payment["confirmation"]["confirmation_url"],
            metadata=metadata,
        )

        await create_payment_activity_event(user_id, payment["id"])

        logger.info(
            f"Quiz plan payment created: payment_id={payment['id']}, "
            f"yookassa_id={yookassa_payment['id']}, user={user_id}"
        )

        return {
            "payment_id": payment["id"],
            "yookassa_payment_id": yookassa_payment["id"],
            "confirmation_url": yookassa_payment["confirmation"]["confirmation_url"],
            "amount": float(price_rub),
            "description": description_text,
        }

    except Exception as e:
        logger.error(f"Failed to create quiz plan payment: {e}", exc_info=True)
        await payment_repo.log_payment_error(
            user_id=user_id,
            payment_id=None,
            error_code="quiz_plan_payment_creation_failed",
            error_message=str(e),
        )
        raise


async def create_flagship_payment(
    user_id: int,
    telegram_user_id: int,
    product_key: str,
    product_title: str,
    price_rub: Decimal,
    return_url: Optional[str] = None,
    user_email: Optional[str] = None,
    product_type: str = "seasonal_program",
) -> Dict[str, Any]:
    """
    Создает платеж за флагманский продукт (сезонная программа или отдельный блок).

    Args:
        user_id: Внутренний ID пользователя
        telegram_user_id: Telegram ID пользователя
        product_key: Ключ продукта (strawberry_summer или strawberry_summer__nutrition)
        product_title: Название продукта
        price_rub: Цена в рублях
        return_url: URL для возврата
        user_email: Email для чека
        product_type: Тип продукта (seasonal_program или single_block)

    Returns:
        Словарь с данными платежа: payment_id, confirmation_url, amount
    """
    idempotency_key = f"flagship_{user_id}_{product_key}_{int(datetime.now().timestamp())}"

    description_text = product_title

    receipt_items = yookassa_client.create_receipt_items(
        description=description_text,
        amount_rub=price_rub,
        quantity=1,
    )

    metadata = {
        "user_id": str(user_id),
        "telegram_user_id": str(telegram_user_id),
        "payment_type": "flagship",
        "product_key": product_key,
        "product_title": product_title,
        "product_type": product_type,
    }

    try:
        yookassa_payment = await yookassa_client.create_payment(
            amount_rub=price_rub,
            description=description_text,
            return_url=return_url or settings.YOOKASSA_RETURN_URL,
            user_telegram_id=telegram_user_id,
            user_email=user_email,
            receipt_items=receipt_items if settings.YOOKASSA_SEND_RECEIPT else None,
            metadata=metadata,
            idempotence_key=idempotency_key,
        )

        payment = await payment_repo.create_payment(
            user_id=user_id,
            yookassa_payment_id=yookassa_payment["id"],
            idempotency_key=idempotency_key,
            payment_type="flagship",
            amount_rub=float(price_rub),
            description=description_text,
            confirmation_url=yookassa_payment["confirmation"]["confirmation_url"],
            metadata=metadata,
        )

        await create_payment_activity_event(user_id, payment["id"])

        logger.info(
            f"Flagship payment created: payment_id={payment['id']}, "
            f"yookassa_id={yookassa_payment['id']}, user={user_id}, product={product_key}"
        )

        return {
            "payment_id": payment["id"],
            "yookassa_payment_id": yookassa_payment["id"],
            "confirmation_url": yookassa_payment["confirmation"]["confirmation_url"],
            "amount": float(price_rub),
            "description": description_text,
        }

    except Exception as e:
        logger.error(f"Failed to create flagship payment: {e}", exc_info=True)
        await payment_repo.log_payment_error(
            user_id=user_id,
            payment_id=None,
            error_code="flagship_payment_creation_failed",
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
        elif payment["payment_type"] == "quiz_plan":
            await _process_quiz_plan_payment_success(payment, verified_payment)
        elif payment["payment_type"] == "flagship":
            await _process_flagship_payment_success(payment, verified_payment)
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

        # Emit automation event: payment_success
        try:
            import asyncio
            from src.services.automation.engine import emit_automation_event
            # Получаем telegram_user_id
            from src.services.db.pool import get_pool as _get_pool
            _pool = _get_pool()
            async with _pool.acquire() as _conn:
                _tg_row = await _conn.fetchrow(
                    "SELECT telegram_user_id FROM users WHERE id = $1",
                    payment["user_id"],
                )
            tg_uid = _tg_row['telegram_user_id'] if _tg_row else None
            if tg_uid:
                asyncio.create_task(
                    emit_automation_event(
                        'payment_success',
                        payment["user_id"],
                        tg_uid,
                        {
                            'payment_type': payment.get('payment_type'),
                            'plan_id': payment.get('subscription_plan_id'),
                            'payment_id': payment['id'],
                        }
                    )
                )
        except Exception as _e:
            logger.warning(f"Failed to emit payment automation event: {_e}")

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

    # Читаем bonus_tokens из metadata (бонус % по инвайт-ссылке)
    metadata = payment.get("metadata", {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}
    bonus_tokens = int(metadata.get("bonus_tokens", 0)) if metadata.get("bonus_tokens") else 0

    total_tokens = package["tokens_amount"] + bonus_tokens

    # Начислить купленные токены + бонус
    new_balance = await add_purchased_tokens(
        user_id=payment["user_id"],
        amount=total_tokens,
        operation_type="payment_yookassa",
        description=f"Оплата пакета: {package['name']}{f' (+{bonus_tokens} бонус)' if bonus_tokens else ''} (платеж {payment['yookassa_payment_id']})",
    )

    bonus_info = f" (base={package['tokens_amount']} + bonus={bonus_tokens})" if bonus_tokens else ""
    logger.info(
        f"Tokens credited: user={payment['user_id']}, "
        f"amount={total_tokens}{bonus_info}, new_balance={new_balance}"
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

    # Читаем bonus_tokens из metadata (устанавливается create_subscription_payment_custom)
    metadata = payment.get("metadata", {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}
    bonus_tokens = int(metadata.get("bonus_tokens", 0)) if metadata.get("bonus_tokens") else 0

    await activate_subscription(
        user_id=payment["user_id"],
        plan_id=payment["subscription_plan_id"],
        payment_id=payment["id"],
        payment_method_id=payment_method_id,
        bonus_tokens=bonus_tokens if bonus_tokens else None,
    )

    # CRM: подписка → 'bought_product' + добавляем в Buyers
    try:
        from src.services.db.funnel_repo import auto_move_client_in_crm, add_client_to_funnel
        await auto_move_client_in_crm(payment["user_id"], 'bought_product')
        await add_client_to_funnel(payment["user_id"], 'buyers', 'active')
    except Exception as e:
        logger.warning(f"[subscription] CRM/Buyers move failed: {e}")


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


async def _process_quiz_plan_payment_success(
    payment: Dict[str, Any],
    yookassa_payment: Dict[str, Any],
) -> None:
    """Обрабатывает успешный платеж за персональный план из квиза — запускает генерацию."""
    metadata = payment.get("metadata", {})
    if isinstance(metadata, str):
        metadata = json.loads(metadata)

    # Отменяем воронку дожима (follow-up) если была запущена
    try:
        from src.services.db.tripwire_followup_repo import cancel_all_pending
        cancelled = await cancel_all_pending(payment["user_id"])
        if cancelled:
            logger.info(f"[quiz_plan] Cancelled {cancelled} follow-ups for user {payment['user_id']}")
    except Exception as e:
        logger.error(f"[quiz_plan] Error cancelling follow-ups: {e}")

    # Уведомляем пользователя и запускаем генерацию в фоне
    asyncio.create_task(
        _generate_quiz_plan_after_payment(payment, metadata)
    )


async def _process_flagship_payment_success(
    payment: Dict[str, Any],
    yookassa_payment: Dict[str, Any],
) -> None:
    """Обрабатывает успешный платеж за флагманский продукт — выдаёт доступ."""
    metadata = payment.get("metadata", {})
    if isinstance(metadata, str):
        metadata = json.loads(metadata)

    product_key = metadata.get("product_key", "")
    product_title = metadata.get("product_title", "Сезонная программа")
    product_type = metadata.get("product_type", "seasonal_program")
    telegram_user_id = int(metadata.get("telegram_user_id", 0))

    # Выдать доступ
    from src.services.db import flagship_repo
    await flagship_repo.grant_access(
        user_id=payment["user_id"],
        product_key=product_key,
        payment_id=payment["id"],
        product_type=product_type,
    )

    # Уведомить пользователя
    if telegram_user_id:
        try:
            from src.main import bot
            await bot.send_message(
                chat_id=telegram_user_id,
                text=(
                    f"✅ Оплата подтверждена!\n\n"
                    f"<b>{product_title}</b> — доступ открыт.\n\n"
                    f"Нажмите «👤 Мой профиль» → «📂 Мои материалы», "
                    f"чтобы открыть программу."
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"[flagship] Ошибка отправки уведомления: {e}")

    # CRM: покупка flagship → 'bought_product'
    try:
        from src.services.db.funnel_repo import auto_move_client_in_crm
        await auto_move_client_in_crm(payment["user_id"], 'bought_product')
    except Exception as e:
        logger.warning(f"[flagship] CRM auto-move to bought_product failed: {e}")

    logger.info(
        f"[flagship] Access granted: user={payment['user_id']}, "
        f"product={product_key}, payment={payment['id']}"
    )


async def _deliver_quiz_pdf_solution(
    bot,
    payment: Dict[str, Any],
    telegram_user_id: int,
    solution: Dict[str, Any],
) -> None:
    """Отправляет готовое PDF-решение пользователю после оплаты."""
    from aiogram.types import FSInputFile
    from src.services.db.messages_repo import log_message

    session_id = f"tg:{telegram_user_id}"

    # 1. Подтверждение оплаты
    confirm_text = "Оплата подтверждена! Отправляю Ваш персональный план..."
    await bot.send_message(chat_id=telegram_user_id, text=confirm_text)
    try:
        await log_message(user_id=payment["user_id"], direction="bot", text=confirm_text, session_id=session_id)
    except Exception:
        pass

    # 2. Отправляем PDF (с retry — файлы 25-30 MB, таймаут вероятен)
    import asyncio as _asyncio
    caption = solution["delivery_caption"]
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            document = FSInputFile(solution["pdf_path"], filename=f"{solution['title']}.pdf")
            await bot.send_document(
                chat_id=telegram_user_id,
                document=document,
                caption=caption,
                request_timeout=120,
            )
            break
        except Exception as e:
            logger.warning(
                f"[quiz_plan] send_document attempt {attempt}/{max_attempts} failed: {e}"
            )
            if attempt == max_attempts:
                await bot.send_message(
                    chat_id=telegram_user_id,
                    text="К сожалению, не удалось отправить файл. "
                         "Пожалуйста, напишите нам — мы отправим его вручную.",
                )
                raise
            await _asyncio.sleep(3 * attempt)
    try:
        await log_message(user_id=payment["user_id"], direction="bot", text=f"[PDF] {caption}", session_id=session_id)
    except Exception:
        pass

    # 3. Переводим в состояние консультации для follow-up вопросов
    from src.handlers.common import set_consultation_state
    await set_consultation_state(telegram_user_id, "waiting_consultation_question")

    logger.info(
        f"[quiz_plan] PDF-решение доставлено: problem_key={solution['problem_key']}, "
        f"user_id={payment['user_id']}"
    )


async def _generate_quiz_plan_after_payment(
    payment: Dict[str, Any],
    metadata: Dict[str, Any],
) -> None:
    """Фоновая задача: доставка PDF-решения или генерация LLM-плана после оплаты."""
    try:
        from src.bot import get_bot
        from src.services.quiz_solutions import get_quiz_solution

        pool = get_pool()
        async with pool.acquire() as conn:
            telegram_user_id = await conn.fetchval(
                "SELECT telegram_user_id FROM users WHERE id = $1",
                payment["user_id"],
            )

        if not telegram_user_id:
            logger.error(f"[quiz_plan] Telegram user not found for user_id={payment['user_id']}")
            return

        bot = get_bot()

        # Проверяем наличие готового PDF-решения
        problem_key = metadata.get("problem_key", "")
        solution = get_quiz_solution(problem_key) if problem_key else None

        if solution:
            # === PDF-решение ===
            await _deliver_quiz_pdf_solution(bot, payment, telegram_user_id, solution)
        else:
            # === LLM-генерация (старый путь) ===
            from src.handlers.funnel_b import _generate_auto_consultation

            text = (
                "Оплата подтверждена! Готовлю Ваш персональный план...\n\n"
                "Это займёт около минуты."
            )
            msg = await bot.send_message(chat_id=telegram_user_id, text=text)

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

            class _TgUser:
                def __init__(self, uid, uname=None, fname=None, lname=None):
                    self.id = uid
                    self.username = uname
                    self.first_name = fname
                    self.last_name = lname

            async with pool.acquire() as conn:
                user_row = await conn.fetchrow(
                    "SELECT telegram_user_id, username, first_name, last_name FROM users WHERE id = $1",
                    payment["user_id"],
                )

            tg_user = _TgUser(
                uid=telegram_user_id,
                uname=user_row["username"] if user_row else None,
                fname=user_row["first_name"] if user_row else None,
                lname=user_row["last_name"] if user_row else None,
            )

            await _generate_auto_consultation(msg, tg_user, payment["user_id"])

        # CRM: оплата quiz plan → 'bought_plan'
        try:
            from src.services.db.funnel_repo import auto_move_client_in_crm
            await auto_move_client_in_crm(payment["user_id"], 'bought_plan')
        except Exception as e:
            logger.error(f"[quiz_plan] CRM auto-move to bought_plan failed: {e}")

        # Запускаем upsell-воронку через 90 секунд
        try:
            from src.handlers.funnel_b_upsell import schedule_upsell_trigger
            await schedule_upsell_trigger(bot, telegram_user_id, payment["user_id"])
        except Exception as e:
            logger.error(f"[quiz_plan] Ошибка запуска upsell: {e}")

    except Exception as e:
        logger.error(f"[quiz_plan] Ошибка после оплаты quiz_plan: {e}", exc_info=True)
