# src/keyboards/main/main_menu.py

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🧑‍🌾 Консультация"),
            ],
            [
                KeyboardButton(text="🛍 Магазин"),
            ],
            [
                KeyboardButton(text="👤 Мой профиль"),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )
    return keyboard


def get_admin_start_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура для администратора при команде /start.
    Две кнопки: переход в режим пользователя или администратора.
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="👤 Режим пользователя"),
            ],
            [
                KeyboardButton(text="🛠 Режим администратора"),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )
    return keyboard
