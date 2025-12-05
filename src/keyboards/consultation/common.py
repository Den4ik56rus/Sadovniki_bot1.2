# src/keyboards/consultation/common.py

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

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


# Клавиатура после получения ответа в консультации
def get_nutrition_followup_keyboard() -> ReplyKeyboardMarkup:
    """
    Обычное меню с кнопками после получения ответа на вопрос консультации.
    Используется для всех типов консультаций.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🔄 Вопрос по новой теме"),
                KeyboardButton(text="✏️ Заменить параметры"),
            ],
            [
                KeyboardButton(text="📋 Детальный план подкормок"),
                KeyboardButton(text="⬅️ Назад в меню"),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def get_more_questions_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура с кнопкой для получения дополнительных 3 уточняющих вопросов.
    Показывается когда счётчик достигает 0.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Получить еще 3 уточняющих вопроса",
                    callback_data="get_more_followup_questions",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Новая тема консультации",
                    callback_data="new_consultation_topic",
                )
            ],
        ]
    )
