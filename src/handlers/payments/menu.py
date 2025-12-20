"""
Главное меню покупок токенов и подписок.

Обработчики:
    - /buy — открыть меню покупок
    - Кнопка "💳 Купить" из главного меню
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from src.services.db import subscription_plan_repo, token_package_repo

logger = logging.getLogger(__name__)
router = Router(name="payments_menu")


def get_payment_menu_keyboard(
    subscription_plans: list,
    token_packages: list,
) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру меню покупок.

    Args:
        subscription_plans: Список активных планов подписки
        token_packages: Список активных пакетов токенов

    Returns:
        InlineKeyboardMarkup с кнопками покупки
    """
    buttons = []

    # Заголовок разовых покупок
    if token_packages:
        buttons.append([
            InlineKeyboardButton(
                text="📦 Разовая покупка",
                callback_data="payment_menu_header_tokens"
            )
        ])

        # Пакеты токенов
        for package in token_packages:
            buttons.append([
                InlineKeyboardButton(
                    text=f"  {package['name']} — {int(package['price_rub'])}₽",
                    callback_data=f"buy_tokens_{package['id']}"
                )
            ])

    # Заголовок подписок
    if subscription_plans:
        buttons.append([
            InlineKeyboardButton(
                text="📅 Подписка",
                callback_data="payment_menu_header_subscription"
            )
        ])

        # Планы подписки
        for plan in subscription_plans:
            buttons.append([
                InlineKeyboardButton(
                    text=f"  {plan['name']} — {int(plan['price_rub'])}₽/мес",
                    callback_data=f"buy_subscription_{plan['id']}"
                )
            ])

    # Кнопка возврата
    buttons.append([
        InlineKeyboardButton(
            text="◀️ Назад в меню",
            callback_data="main_menu"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("buy"))
@router.message(F.text == "💳 Купить")
async def show_payment_menu(message: Message):
    """Показать меню покупок."""
    user_id = message.from_user.id

    try:
        # Получить активные планы и пакеты
        subscription_plans = await subscription_plan_repo.get_all_active()
        token_packages = await token_package_repo.get_all_active()

        if not subscription_plans and not token_packages:
            await message.answer(
                "⚠️ В данный момент нет доступных тарифов.\n"
                "Попробуйте позже или свяжитесь с поддержкой."
            )
            return

        # Сформировать описание
        text_parts = ["💳 Купить токены или подписку\n"]

        if token_packages:
            text_parts.append("\n📦 Разовая покупка:")
            for package in token_packages:
                text_parts.append(
                    f"  • {package['name']} — {int(package['price_rub'])}₽"
                )

        if subscription_plans:
            text_parts.append("\n📅 Подписка:")
            for plan in subscription_plans:
                tokens_info = f"({plan['tokens_included']} вопросов в месяц)" if plan.get('tokens_included') else ""
                text_parts.append(
                    f"  • {plan['name']} — {int(plan['price_rub'])}₽/мес {tokens_info}"
                )

        text_parts.append("\nВыберите подходящий вариант:")

        keyboard = get_payment_menu_keyboard(subscription_plans, token_packages)

        await message.answer(
            "\n".join(text_parts),
            reply_markup=keyboard
        )

        logger.info(f"Payment menu shown to user {user_id}")

    except Exception as e:
        logger.error(f"Error showing payment menu for user {user_id}: {e}", exc_info=True)
        await message.answer(
            "❌ Произошла ошибка при загрузке меню покупок.\n"
            "Попробуйте позже или свяжитесь с поддержкой."
        )


@router.callback_query(F.data == "show_payment_menu")
async def show_payment_menu_callback(callback: CallbackQuery):
    """Показать меню покупок (callback версия)."""
    await callback.answer()

    telegram_user_id = callback.from_user.id

    # Убедиться что пользователь существует в БД
    from src.services.db.users_repo import get_or_create_user
    user_id = await get_or_create_user(
        telegram_user_id=telegram_user_id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
    )

    try:
        # Получить активные планы и пакеты
        subscription_plans = await subscription_plan_repo.get_all_active()
        token_packages = await token_package_repo.get_all_active()

        if not subscription_plans and not token_packages:
            await callback.message.edit_text(
                "⚠️ В данный момент нет доступных тарифов.\n"
                "Попробуйте позже или свяжитесь с поддержкой."
            )
            return

        # Сформировать описание
        text_parts = ["💳 Купить токены или подписку\n"]

        if token_packages:
            text_parts.append("\n📦 Разовая покупка:")
            for package in token_packages:
                text_parts.append(
                    f"  • {package['name']} — {int(package['price_rub'])}₽"
                )

        if subscription_plans:
            text_parts.append("\n📅 Подписка:")
            for plan in subscription_plans:
                tokens_info = f"({plan['tokens_included']} вопросов в месяц)" if plan.get('tokens_included') else ""
                text_parts.append(
                    f"  • {plan['name']} — {int(plan['price_rub'])}₽/мес {tokens_info}"
                )

        text_parts.append("\nВыберите подходящий вариант:")

        keyboard = get_payment_menu_keyboard(subscription_plans, token_packages)

        await callback.message.edit_text(
            "\n".join(text_parts),
            reply_markup=keyboard
        )

        logger.info(f"Payment menu shown to user {user_id} (callback)")

    except Exception as e:
        logger.error(f"Error showing payment menu callback for user {user_id}: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ Произошла ошибка при загрузке меню покупок.\n"
            "Попробуйте позже или свяжитесь с поддержкой."
        )


@router.callback_query(F.data.in_(["payment_menu_header_tokens", "payment_menu_header_subscription"]))
async def payment_menu_headers(callback: CallbackQuery):
    """Обработка кликов по заголовкам (они не активны, просто заглушка)."""
    await callback.answer()
