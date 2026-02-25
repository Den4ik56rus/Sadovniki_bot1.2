# src/handlers/payments/discount_menu.py
"""
Меню подписок с персональной скидкой из рассылки.

Вызывается только при клике по discount-кнопке рассылки.
Показывает то же меню тарифов, но с зачёркнутыми ценами и баннером скидки.
"""

import logging
from datetime import datetime, timezone

from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from src.services.db import subscription_plan_repo
from src.services.db.discount_repo import get_user_active_broadcast_discount

logger = logging.getLogger(__name__)


def _compute_time_left(expires_at: datetime) -> tuple[int, int]:
    """Возвращает (hours_left, minutes_left) до истечения скидки."""
    now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    delta = expires_at - now
    total_seconds = max(0, int(delta.total_seconds()))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return hours, minutes


async def show_discount_subscription_menu(callback: CallbackQuery, user_id: int) -> None:
    """
    Показать меню тарифов со скидкой новым сообщением (не заменяя исходное).
    Кнопка в исходном сообщении остаётся активной на всё время действия скидки.
    """
    discount = await get_user_active_broadcast_discount(user_id)

    if not discount:
        # Скидка истекла — отправляем новое сообщение
        await callback.message.answer(
            "⏰ Срок действия скидки истёк.\n\nВы можете оформить подписку по стандартным ценам:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Перейти к тарифам", callback_data="show_payment_menu")]
            ])
        )
        return

    discount_pct = discount['discount_percent']
    bonus_tokens = discount.get('bonus_tokens', 0) or 0
    bonus_mode = discount.get('bonus_tokens_mode', 'absolute')
    expires_at = discount['expires_at']
    hours_left, minutes_left = _compute_time_left(expires_at)

    plans = await subscription_plan_repo.get_all_active()

    # Баннер
    import math
    time_str = f"{hours_left}ч {minutes_left}мин" if hours_left > 0 else f"{minutes_left}мин"
    if discount_pct > 0:
        banner = (
            f"🔥 <b>Ваша персональная скидка {discount_pct}%</b>\n"
            f"Действует ещё: <b>{time_str}</b>\n\n"
        )
    else:
        banner = (
            f"🎁 <b>Ваш персональный бонус</b>\n"
            f"Действует ещё: <b>{time_str}</b>\n\n"
        )

    # Список тарифов со скидкой/бонусом
    plan_lines = []
    for plan in plans:
        original = int(plan['price_rub'])
        base_tokens = plan.get('tokens_included', 0)
        discounted = int(original * (100 - discount_pct) / 100) if discount_pct > 0 else original
        if discount_pct > 0:
            line = f"📅 <b>{plan['name']}</b>: <s>{original}₽</s> → <b>{discounted}₽</b>/мес"
        else:
            line = f"📅 <b>{plan['name']}</b>: <b>{original}₽</b>/мес"
        # Базовое кол-во токенов + бонус
        if bonus_tokens > 0:
            if bonus_mode == 'percent':
                plan_bonus = math.ceil(base_tokens * bonus_tokens / 100)
            else:
                plan_bonus = bonus_tokens
            line += f"\n   🎁 {base_tokens} токенов + {plan_bonus} бонус = <b>{base_tokens + plan_bonus} токенов</b>"
        else:
            line += f"\n   🎁 {base_tokens} токенов"
        plan_lines.append(line)

    text = banner + "\n\n".join(plan_lines) + "\n\nВыберите тариф для оформления:"

    # Кнопки — стандартные buy_subscription_{id}, скидка применится в payment_service
    buttons = []
    for plan in plans:
        original = int(plan['price_rub'])
        discounted = int(original * (100 - discount_pct) / 100) if discount_pct > 0 else original
        if discount_pct > 0:
            btn_text = f"{plan['name']} — {original}₽ → {discounted}₽"
        else:
            btn_text = f"{plan['name']} — {original}₽"
        buttons.append([InlineKeyboardButton(
            text=btn_text,
            callback_data=f"buy_subscription_{plan['id']}"
        )])

    # Отправляем новым сообщением — исходное сообщение рассылки не трогаем
    await callback.message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )
