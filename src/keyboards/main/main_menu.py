# src/keyboards/main/main_menu.py

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove,
)

# Используем ReplyKeyboardRemove чтобы убрать старую ReplyKeyboard у пользователей
REMOVE_REPLY_KEYBOARD = ReplyKeyboardRemove()


def get_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧑‍🌾 Консультация", callback_data="menu_consultation")],
        [InlineKeyboardButton(text="🛍 Магазин", callback_data="menu_shop")],
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="menu_profile")],
        [InlineKeyboardButton(text="📂 Мои материалы", callback_data="menu_materials")],
    ])


def get_admin_start_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для администратора при команде /start.
    Две кнопки: переход в режим пользователя или администратора.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Режим пользователя", callback_data="admin_user_mode")],
        [InlineKeyboardButton(text="🛠 Режим администратора", callback_data="admin_admin_mode")],
    ])
