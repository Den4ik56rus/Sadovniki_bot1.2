# src/keyboards/main/main_menu.py

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🧑‍🌾 Консультация"),
                KeyboardButton(text="🦠 Диагноз болезней"),
            ],
            [
                KeyboardButton(text="🌱 Мои посадки"),
                KeyboardButton(text="📅 План сезона"),
            ],
            [
                KeyboardButton(text="💎 Премиум"),
                KeyboardButton(text="👤 Мой профиль"),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )
    return keyboard
