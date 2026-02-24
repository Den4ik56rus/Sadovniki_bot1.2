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
    "5": "Максимальный урожай при минимуме усилий",
}

CONSULTATION_ENTRY_TEXT = (
    "<b>Наша беседа будет строиться диалогом</b>, ведь так удобнее!\n\n"
    "— <b>Вы задаете вопрос</b>, описываете проблему (одним сообщением).\n"
    "— <b>Я даю рекомендации</b> и подробно раскрываю эту тему.\n\n"
    "✅ После того, как я ответил - Вы можете задать <b>уточняющий вопрос</b> "
    "или <b>новый</b>, выбрав в меню нужную кнопку.\n\n"
    "Если вопрос касается выращивания, то для меня будет "
    "<b>важно знать в каком регионе Вы находитесь.</b>\n\n"
    "Ниже список вопросов для примера - обратите внимание, как их лучше "
    "формулировать. Что бы мы были на одной волне!\n\n"
    "<b>Для продолжения работы</b> выберите вопрос из списка👇 или "
    "<b>просто напишите свой вопрос в чат</b>😇"
)


def get_example_questions_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-кнопки с примерами вопросов для консультации."""
    buttons = []
    for key, text in EXAMPLE_QUESTIONS.items():
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"example_q:{key}")])
    buttons.append([InlineKeyboardButton(text="✅ Или напишите свой вопрос👇", callback_data="custom_question")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_followup_keyboard(category: str = "") -> InlineKeyboardMarkup:
    """Инлайн-клавиатура после получения ответа — выбор типа следующего вопроса."""
    buttons = [
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

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==== Клавиатура выбора формата для ВСЕХ простых вопросов ====

def get_simple_question_choice_keyboard(
    standard_cost: int = 1,
    extended_cost: int = 2,
) -> InlineKeyboardMarkup:
    """
    Универсальная клавиатура выбора формата ответа для ALL short_answer вопросов.

    Показывается ПЕРЕД ответом. Пользователь выбирает стандартный или расширенный.

    Args:
        standard_cost: Стоимость стандартного ответа в токенах
        extended_cost: Стоимость расширенного ответа в токенах
    """
    from src.pricing import pluralize_questions

    buttons = [
        [
            InlineKeyboardButton(
                text=f"Стандартный ответ ({pluralize_questions(standard_cost)})",
                callback_data="complexity_confirm:short",
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"⭐ Расширенный ответ ({pluralize_questions(extended_cost)})",
                callback_data="complexity_confirm:long",
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==== Клавиатура «Пополнить баланс» (при нехватке токенов) ====

def get_topup_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой перехода в меню подписок."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💳 Пополнить баланс",
            callback_data="show_payment_menu",
        )],
    ])


# ==== Клавиатура подтверждения стоимости (complexity-based) ====

def get_complexity_confirm_keyboard(
    tier: str,
    cost: int,
    phase_button_label: str = "",
) -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения стоимости для long_answer.

    Кнопки: Ответ по фазам роста / Отмена.

    Args:
        tier: Уровень сложности (long_answer, long_answer_insufficient)
        cost: Стоимость в вопросах
        phase_button_label: Персонализированная подпись для кнопки фазы
    """
    buttons = []

    # Кнопка "Ответ по фазам роста" — для long_answer
    if tier in ("long_answer",):
        plan_text = (
            f"{phase_button_label} ({cost} токена)"
            if phase_button_label
            else f"Ответ по фазам роста ({cost} токена)"
        )
        buttons.append([
            InlineKeyboardButton(
                text=plan_text,
                callback_data="complexity_confirm:long",
            ),
        ])

    # Кнопка "Пополнить баланс" — для long_answer_insufficient
    if tier == "long_answer_insufficient":
        buttons.append([
            InlineKeyboardButton(
                text="💳 Пополнить баланс",
                callback_data="show_payment_menu",
            ),
        ])

    # Кнопка "Отмена" — всегда
    buttons.append([
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="complexity_confirm:cancel",
        ),
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==== Клавиатура продолжения к следующей фазе (Тип C) ====

def get_next_phase_keyboard(next_phase_display_name: str = "") -> InlineKeyboardMarkup:
    """
    Клавиатура после фазового ответа — 3 кнопки.

    Args:
        next_phase_display_name: Не используется (для обратной совместимости)
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="✅ Задать уточняющий вопрос",
                callback_data="followup_type:clarification",
            ),
        ],
        [
            InlineKeyboardButton(
                text="✅ Задать вопрос по новой теме",
                callback_data="followup_type:new_topic",
            ),
        ],
        [
            InlineKeyboardButton(
                text="➡️ Выбрать следующую фазу роста",
                callback_data="phase_continue:select",
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_phase_select_keyboard(delivered_phases: list[str] | None = None) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора фазы роста (3 фазы).

    Args:
        delivered_phases: Уже пройденные фазы (будут помечены галочкой)
    """
    from src.pricing import PHASE_DISPLAY_NAMES, PHASE_COST

    delivered = set(delivered_phases or [])

    phases = [
        ("весна-цветение", PHASE_DISPLAY_NAMES["весна-цветение"]),
        ("цветение-плодоношение", PHASE_DISPLAY_NAMES["цветение-плодоношение"]),
        ("плодоношение-зима", PHASE_DISPLAY_NAMES["плодоношение-зима"]),
    ]

    buttons = []
    for phase_key, display_name in phases:
        if phase_key in delivered:
            label = f"✅ {display_name} (пройдена)"
            callback = f"phase_select:done:{phase_key}"
        else:
            label = f"📋 {display_name} ({PHASE_COST} вопроса)"
            callback = f"phase_select:{phase_key}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=callback)])

    buttons.append([
        InlineKeyboardButton(
            text="❌ Закрыть",
            callback_data="phase_continue:stop",
        ),
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==== Клавиатура выбора темы (multi-topic) ====

def get_topic_select_keyboard(topics: list[str]) -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора одной темы из нескольких.

    Args:
        topics: Список тем, например ["питание", "защита", "уход"]
    """
    # Красивые названия тем
    topic_display = {
        "питание": "Питание (подкормки)",
        "защита": "Защита (обработки)",
        "уход": "Уход (обрезка, полив)",
    }

    buttons = []
    for topic in topics:
        display_name = topic_display.get(topic, topic.capitalize())
        buttons.append([
            InlineKeyboardButton(
                text=display_name,
                callback_data=f"topic_select:{topic}",
            ),
        ])

    buttons.append([
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="complexity_confirm:cancel",
        ),
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Alias для обратной совместимости
def get_nutrition_followup_keyboard() -> InlineKeyboardMarkup:
    return get_followup_keyboard()
