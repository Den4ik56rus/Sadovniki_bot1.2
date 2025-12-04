# src/keyboards/consultation/cultures.py

"""Клавиатура для выбора культуры пользователем."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_culture_selection_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора культуры.
    Используется когда культура не определена автоматически.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🍓 Клубника ремонтантная",
                    callback_data="culture:клубника ремонтантная",
                ),
                InlineKeyboardButton(
                    text="🍓 Клубника летняя",
                    callback_data="culture:клубника летняя",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🍓 Клубника (общее)",
                    callback_data="culture:клубника общая",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🫐 Малина ремонтантная",
                    callback_data="culture:малина ремонтантная",
                ),
                InlineKeyboardButton(
                    text="🫐 Малина летняя",
                    callback_data="culture:малина летняя",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🫐 Малина (общее)",
                    callback_data="culture:малина общая",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚫ Смородина",
                    callback_data="culture:смородина",
                ),
                InlineKeyboardButton(
                    text="🔵 Голубика",
                    callback_data="culture:голубика",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🟣 Жимолость",
                    callback_data="culture:жимолость",
                ),
                InlineKeyboardButton(
                    text="🟢 Крыжовник",
                    callback_data="culture:крыжовник",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚫ Ежевика",
                    callback_data="culture:ежевика",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📚 Общая информация",
                    callback_data="culture:общая информация",
                ),
            ],
        ]
    )
