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


# Маппинг категорий на тексты кнопок "Детальный план"
CATEGORY_DETAILED_PLAN_BUTTONS = {
    "питание растений": "📋 Детальный план подкормок",
    "улучшение почвы": "📋 Детальный план улучшения почвы",
    "посадка и уход": "📋 Детальный план ухода",
    "защита растений": "📋 Детальный план защиты растений",
    "подбор сорта": "📋 Детальный план подбора сортов",
}


def get_followup_keyboard(category: str = "питание растений") -> ReplyKeyboardMarkup:
    """
    Клавиатура после получения ответа с динамической кнопкой детального плана.

    Args:
        category: Категория консультации для выбора текста кнопки
    """
    detailed_plan_text = CATEGORY_DETAILED_PLAN_BUTTONS.get(
        category, "📋 Детальный план"
    )
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🔄 Вопрос по новой теме"),
                KeyboardButton(text="✏️ Заменить параметры"),
            ],
            [
                KeyboardButton(text=detailed_plan_text),
                KeyboardButton(text="⬅️ Назад в меню"),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


# Alias для обратной совместимости
def get_nutrition_followup_keyboard() -> ReplyKeyboardMarkup:
    """Deprecated: используйте get_followup_keyboard(category) вместо этого."""
    return get_followup_keyboard("питание растений")


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
