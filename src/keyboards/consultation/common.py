# src/keyboards/consultation/common.py

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

CONSULTATION_MENU_INLINE_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Питание растений",
                callback_data="consult_category:nutrition",
            ),
            InlineKeyboardButton(
                text="Подбор сорта/места",
                callback_data="consult_category:sort_place",
            ),
        ],
        [
            InlineKeyboardButton(
                text="Защита растений",
                callback_data="consult_category:protection",
            ),
            InlineKeyboardButton(
                text="Посадка и уход",
                callback_data="consult_category:plant_care",
                
            ),
        ],
        [
            InlineKeyboardButton(
                text="Улучшение почвы",
                callback_data="consult_category:soil",
                
            ),
            InlineKeyboardButton(
                text="Другая тема",
                callback_data="consult_category:other",
            ),
        ],
        [
            InlineKeyboardButton(
                text="❌ Закрыть",
                callback_data="consult_close",
            )
        ],
    ]
)
