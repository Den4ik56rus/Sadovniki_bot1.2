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


# Примеры вопросов для инлайн-кнопок при входе в консультацию
EXAMPLE_QUESTIONS = {
    "1": "Как подготовить ПОЧВУ перед посадкой?",
    "2": "Чем обработать клубнику от ДОЛГОНОСИКА?",
    "3": "Как избавиться от ДИДИМЕЛЛЫ на малине?",
    "4": "План подкормок клубники на сезон",
}

CONSULTATION_ENTRY_TEXT = (
    "Добро пожаловать в режим консультаций! Здесь вы можете получить ответы, "
    "основанные на отобранной литературе и рекомендациях лучших экспертов.\n\n"
    "Ниже — примеры вопросов, на которые вы можете получить качественный ответ "
    "по выбранной культуре. Вы также можете задать свой вопрос.\n\n"
    "Стоимость: 1-2 вопроса в зависимости от темы."
)


def get_example_questions_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-кнопки с примерами вопросов для консультации."""
    buttons = []
    for key, text in EXAMPLE_QUESTIONS.items():
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"example_q:{key}")])
    # Кнопка "Свой вопрос" внизу
    buttons.append([InlineKeyboardButton(text="✅ Или напишите свой вопрос👇", callback_data="custom_question")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_followup_keyboard(category: str = "") -> InlineKeyboardMarkup:
    """Инлайн-клавиатура после получения ответа — выбор типа следующего вопроса."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Задать уточняющий вопрос",
                    callback_data="followup_type:clarification"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✅ Задать вопрос по новой теме",
                    callback_data="followup_type:new_topic"
                ),
            ],
        ]
    )


# Alias для обратной совместимости
def get_nutrition_followup_keyboard() -> InlineKeyboardMarkup:
    return get_followup_keyboard()


