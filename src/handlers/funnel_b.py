"""
Воронка Тип Б — онбординг-квиз для A/B теста.

Сценарий:
    1. Приветственное сообщение
    2. Квиз 1: выбор культуры (InlineKeyboard)
    3. Квиз 2: выбор региона (InlineKeyboard, с возможностью ввести свой)
    4. Квиз 3: выбор проблемы (InlineKeyboard)
    5. Оффер + CTA (оплата или бесплатная консультация)

Ответы сохраняются в таблицу user_quiz_answers.
"""

import asyncio
import logging
from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.enums import ChatAction

from src.handlers.common import (
    CONSULTATION_STATE,
    CONSULTATION_CONTEXT,
    set_consultation_state,
    clear_consultation_state,
)

logger = logging.getLogger(__name__)

router = Router(name="funnel_b")

# ---------------------------------------------------------------------------
# Тексты сообщений
# ---------------------------------------------------------------------------

WELCOME_TEXT = (
    "Ок, начинаем диагностику.\n"
    "На старте сезона чаще всего теряют 20–40% урожая из-за пары ошибок.\n"
    "Это займёт меньше минуты"
)

QUIZ_CULTURE_TEXT = "Какая культура у Вас преобладает?"

QUIZ_VARIETY_TEXT = "Какой сорт у Вас?"

QUIZ_REGION_TEXT = "Отлично. В каком регионе выращиваете?"

QUIZ_REGION_CUSTOM_TEXT = "Напишите свой регион:"

QUIZ_CULTURE_CUSTOM_TEXT = "Напишите свою культуру:"

QUIZ_PROBLEM_TEXT = "Что сейчас больше всего волнует?"

# ---------------------------------------------------------------------------
# Персонализированные тексты оффера (культура × проблема)
# ---------------------------------------------------------------------------

# Названия культур в родительном падеже для текстов оффера
_CULTURE_GENITIVE = {
    "strawberry": "клубники",
    "raspberry": "малины",
    "blueberry": "голубики",
    "currant": "смородины",
    "honeysuckle": "жимолости",
    "blackberry": "ежевики",
    "other": "ягод",
}

# Лейблы общих проблем для текста оффера
_PROBLEM_LABELS = {
    "small_berries": "мелкие ягоды",
    "diseases": "болезни",
    "low_yield": "мало урожая",
    "increase_yield": "увеличение урожая",
    "check_care": "проверка ухода",
}

# Названия культур в творительном падеже (для "ухаживают за ...")
_CULTURE_INSTRUMENTAL = {
    "strawberry": "клубникой",
    "raspberry": "малиной",
    "blueberry": "голубикой",
    "currant": "смородиной",
    "honeysuckle": "жимолостью",
    "blackberry": "ежевикой",
    "other": "ягодами",
}


def _get_offer_text(culture_key: str, problem_key: str) -> str:
    """Генерирует текст оффера — проблема из опроса + предложение плана."""
    culture_gen = _CULTURE_GENITIVE.get(culture_key, "ягод")
    problem_label = _PROBLEM_LABELS.get(problem_key, "неправильный уход")
    return (
        f"По Вашему региону дачники теряют до 25–40% урожая {culture_gen} "
        f"в связи с проблемой: <b>{problem_label}</b>.\n\n"
        f"Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
    )

OFFER_TEXT_2 = (
    "Обычно такой план стоит 490 ₽.\n"
    "Сегодня - 99 ₽."
)

# ---------------------------------------------------------------------------
# Клавиатуры
# ---------------------------------------------------------------------------

def get_culture_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора культуры: 2+2+2+1."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🍓 Клубника", callback_data="quiz_culture_strawberry"),
            InlineKeyboardButton(text="🍇 Малина", callback_data="quiz_culture_raspberry"),
        ],
        [
            InlineKeyboardButton(text="🫐 Голубика", callback_data="quiz_culture_blueberry"),
            InlineKeyboardButton(text="🌿 Смородина", callback_data="quiz_culture_currant"),
        ],
        [
            InlineKeyboardButton(text="🌸 Жимолость", callback_data="quiz_culture_honeysuckle"),
            InlineKeyboardButton(text="🫒 Ежевика", callback_data="quiz_culture_blackberry"),
        ],
        [
            InlineKeyboardButton(text="👉 Другая культура", callback_data="quiz_culture_other"),
        ],
    ])


def get_variety_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора сорта: летняя / ремонтантная."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="☀️ Летняя", callback_data="quiz_variety_summer"),
            InlineKeyboardButton(text="🔄 Ремонтантная", callback_data="quiz_variety_remontant"),
        ],
    ])


def get_region_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора региона: 2+2."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Средняя полоса", callback_data="quiz_region_central"),
            InlineKeyboardButton(text="Юг", callback_data="quiz_region_south"),
        ],
        [
            InlineKeyboardButton(text="Север", callback_data="quiz_region_north"),
            InlineKeyboardButton(text="Указать свой", callback_data="quiz_region_custom"),
        ],
    ])


def get_problem_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора проблемы: по 1 кнопке в ряд (общая для всех культур)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Мелкие ягоды", callback_data="quiz_problem_small_berries")],
        [InlineKeyboardButton(text="Болезни", callback_data="quiz_problem_diseases")],
        [InlineKeyboardButton(text="Мало урожая", callback_data="quiz_problem_low_yield")],
        [InlineKeyboardButton(text="Хочу увеличить урожай", callback_data="quiz_problem_increase_yield")],
        [InlineKeyboardButton(text="Просто проверить уход", callback_data="quiz_problem_check_care")],
    ])


# ---------------------------------------------------------------------------
# Культуро-специфичные проблемы: клубника
# ---------------------------------------------------------------------------

_STRAWBERRY_PROBLEMS = {
    "summer": [
        {"key": "straw_s_low_yield", "label": "Мало ягод или они мелкие", "hint": "старые кусты, питание в фазу цветение-плодоношение и осень"},
        {"key": "straw_s_yellow_leaves", "label": "Желтые листья", "hint": "Хлороз, щелочная почва/вода, особенность некоторых сортов"},
        {"key": "straw_s_leaf_spots", "label": "Пятна на листьях", "hint": "весенняя медью и обработки во второй половине лета, в период распространения заболеваний"},
        {"key": "straw_s_pests", "label": "Вредители портят лист", "hint": "обеспечить профилактику весной до цветения от листогрызущих и клещей"},
        {"key": "straw_s_planting", "label": "Как и на каком расстоянии сажать", "hint": None},
        {"key": "straw_s_soil_prep", "label": "Подготовка почвы перед посадкой", "hint": None},
    ],
    "remontant": [
        {"key": "straw_r_leaf_spots", "label": "Пятна на листьях", "hint": "весенняя медью и обработки во второй половине лета, в период распространения заболеваний между волнами"},
        {"key": "straw_r_rot", "label": "Ягода гниет", "hint": "Сырость, влага, обработки биофунгицидами на стадии формирования ягоды"},
        {"key": "straw_r_yellow_leaves", "label": "Желтые листья", "hint": "Хлороз в основном, щелочная почва/вода, особенность некоторых сортов"},
        {"key": "straw_r_dieback", "label": "Выпады во второй половине лета", "hint": "Корневые гнили, почвенные фунгицид"},
        {"key": "straw_r_planting", "label": "Как и на каком расстоянии сажать", "hint": None},
        {"key": "straw_r_soil_prep", "label": "Подготовка почвы перед посадкой", "hint": None},
    ],
}

# Быстрый lookup по ключу проблемы
_STRAWBERRY_PROBLEM_MAP: dict[str, dict] = {}
for _variety, _problems in _STRAWBERRY_PROBLEMS.items():
    for _p in _problems:
        _STRAWBERRY_PROBLEM_MAP[_p["key"]] = _p


# ---------------------------------------------------------------------------
# Культуро-специфичные проблемы: малина
# ---------------------------------------------------------------------------

_RASPBERRY_PROBLEMS = {
    "summer": [
        {"key": "rasp_s_diseases", "label": "Болезни малины", "hint": None},
        {"key": "rasp_s_pruning", "label": "Особенности обрезки", "hint": None},
        {"key": "rasp_s_larvae", "label": "Личинки в ягоде", "hint": "инсектицид в период цветения/завязи"},
        {"key": "rasp_s_white_berry", "label": "Белая ягода", "hint": "солнцепек или мучнистая роса"},
        {"key": "rasp_s_small_berry", "label": "Очень мелкая ягода", "hint": "Вырождение, старая посадка"},
        {"key": "rasp_s_stem_spots", "label": "Пятна на стеблях", "hint": "дидимела, обработка фунгицидами"},
        {"key": "rasp_s_planting", "label": "Как и на каком расстоянии сажать", "hint": None},
        {"key": "rasp_s_soil_prep", "label": "Подготовка почвы перед посадкой", "hint": None},
    ],
    "remontant": [
        {"key": "rasp_r_diseases", "label": "Болезни малины", "hint": None},
        {"key": "rasp_r_pruning", "label": "Особенности обрезки", "hint": None},
        {"key": "rasp_r_larvae", "label": "Личинки в ягоде", "hint": "инсектицид в период цветения/завязи"},
        {"key": "rasp_r_small_berry", "label": "Очень мелкая ягода", "hint": "Вырождение, старая посадка"},
        {"key": "rasp_r_white_berry", "label": "Белая ягода", "hint": "солнцепек или мучнистая роса"},
        {"key": "rasp_r_stem_spots", "label": "Пятна на стеблях", "hint": "дидимела, обработка фунгицидами"},
        {"key": "rasp_r_planting", "label": "Как и на каком расстоянии сажать", "hint": None},
        {"key": "rasp_r_soil_prep", "label": "Подготовка почвы перед посадкой", "hint": None},
    ],
}

# Быстрый lookup по ключу проблемы малины
_RASPBERRY_PROBLEM_MAP: dict[str, dict] = {}
for _variety, _problems in _RASPBERRY_PROBLEMS.items():
    for _p in _problems:
        _RASPBERRY_PROBLEM_MAP[_p["key"]] = _p


# ---------------------------------------------------------------------------
# Культуро-специфичные проблемы: смородина
# ---------------------------------------------------------------------------

_CURRANT_PROBLEMS = [
    {"key": "cur_yellow_leaves", "label": "Кусты желтеют", "hint": "хлороз, дефицит питания, грибные заболевания"},
    {"key": "cur_drying", "label": "Кусты засыхают", "hint": "стеклянница, корневые гнили, засуха"},
    {"key": "cur_glasswing", "label": "Как побороть стеклянницу", "hint": "обрезка поражённых побегов, инсектициды"},
    {"key": "cur_pruning", "label": "Правила обрезки", "hint": None},
    {"key": "cur_planting", "label": "Как и на каком расстоянии сажать", "hint": None},
    {"key": "cur_soil_prep", "label": "Подготовка почвы перед посадкой", "hint": None},
]

_CURRANT_PROBLEM_MAP: dict[str, dict] = {p["key"]: p for p in _CURRANT_PROBLEMS}


# ---------------------------------------------------------------------------
# Культуро-специфичные проблемы: жимолость
# ---------------------------------------------------------------------------

_HONEYSUCKLE_PROBLEMS = [
    {"key": "hon_bad_taste", "label": "Не вкусная ягода", "hint": "сорт, полив, питание"},
    {"key": "hon_low_yield", "label": "Мало ягод", "hint": "опыление, возраст куста, подкормка"},
    {"key": "hon_brown_leaves", "label": "Листья становятся бурого цвета", "hint": "грибные болезни, ожог"},
    {"key": "hon_no_berries", "label": "Нет ягод на взрослых кустах", "hint": "отсутствие опылителя, обрезка"},
    {"key": "hon_pruning", "label": "Правила обрезки", "hint": None},
    {"key": "hon_planting", "label": "Как и на каком расстоянии сажать", "hint": None},
    {"key": "hon_soil_prep", "label": "Подготовка почвы перед посадкой", "hint": None},
]

_HONEYSUCKLE_PROBLEM_MAP: dict[str, dict] = {p["key"]: p for p in _HONEYSUCKLE_PROBLEMS}


# ---------------------------------------------------------------------------
# Культуро-специфичные проблемы: ежевика
# ---------------------------------------------------------------------------

_BLACKBERRY_PROBLEMS = [
    {"key": "blk_pruning", "label": "Правила обрезки", "hint": None},
    {"key": "blk_shelter", "label": "Правила укрытия", "hint": "укрытие на зиму, материалы"},
    {"key": "blk_planting", "label": "Как и на каком расстоянии сажать", "hint": None},
    {"key": "blk_soil_prep", "label": "Подготовка почвы перед посадкой", "hint": None},
]

_BLACKBERRY_PROBLEM_MAP: dict[str, dict] = {p["key"]: p for p in _BLACKBERRY_PROBLEMS}


# ---------------------------------------------------------------------------
# Культуро-специфичные проблемы: голубика
# ---------------------------------------------------------------------------

_BLUEBERRY_PROBLEMS = [
    {"key": "blu_yellow_leaves", "label": "Желтеют листья", "hint": "хлороз, pH почвы, дефицит железа"},
    {"key": "blu_no_fruit", "label": "Не плодоносит", "hint": "кислотность, опыление, возраст"},
    {"key": "blu_soil_prep", "label": "Подготовка грунта", "hint": "кислый торф, хвойный опад"},
    {"key": "blu_planting", "label": "Правила посадки", "hint": None},
]

_BLUEBERRY_PROBLEM_MAP: dict[str, dict] = {p["key"]: p for p in _BLUEBERRY_PROBLEMS}


def _build_problem_keyboard(problems: list[dict]) -> InlineKeyboardMarkup:
    """Строит клавиатуру из списка проблем (по 1 кнопке в ряд)."""
    rows = [
        [InlineKeyboardButton(text=p["label"], callback_data=f"quiz_problem_{p['key']}")]
        for p in problems
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# Маппинг культур без сортов → их список проблем
_CULTURE_PROBLEMS = {
    "currant": _CURRANT_PROBLEMS,
    "honeysuckle": _HONEYSUCKLE_PROBLEMS,
    "blackberry": _BLACKBERRY_PROBLEMS,
    "blueberry": _BLUEBERRY_PROBLEMS,
}


def get_problem_keyboard_for_context(ctx: dict) -> InlineKeyboardMarkup:
    """Выбирает клавиатуру проблем в зависимости от культуры и сорта."""
    culture_key = ctx.get("quiz_culture_key")
    variety_key = ctx.get("quiz_variety_key")

    if culture_key == "strawberry" and variety_key in ("summer", "remontant"):
        return _build_problem_keyboard(_STRAWBERRY_PROBLEMS[variety_key])

    if culture_key == "raspberry" and variety_key in ("summer", "remontant"):
        return _build_problem_keyboard(_RASPBERRY_PROBLEMS[variety_key])

    # Культуры без сортов (смородина, жимолость, ежевика, голубика)
    if culture_key in _CULTURE_PROBLEMS:
        return _build_problem_keyboard(_CULTURE_PROBLEMS[culture_key])

    return get_problem_keyboard()


def _get_strawberry_offer_text(problem_key: str, variety_key: str) -> str:
    """Генерирует текст оффера для клубники — индивидуальный текст для каждой проблемы."""
    problem = _STRAWBERRY_PROBLEM_MAP.get(problem_key)
    if not problem:
        return _get_offer_text("strawberry", problem_key)

    variety_label = "летней" if variety_key == "summer" else "ремонтантной"

    # Индивидуальные тексты для каждого типа проблемы
    offer_texts = {
        # --- Летняя клубника ---
        "straw_s_low_yield": (
            f"Ежегодно дачники теряют до 25–40% объёма урожая {variety_label} клубники.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "straw_s_yellow_leaves": (
            f"В Вашем регионе из-за желтеющих листьев дачники теряют до 25–40% урожая {variety_label} клубники.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "straw_s_leaf_spots": (
            f"В Вашем регионе из-за пятен на листьях дачники теряют до 25–40% урожая {variety_label} клубники.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "straw_s_pests": (
            f"В Вашем регионе из-за вредителей дачники теряют до 25–40% урожая {variety_label} клубники.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "straw_s_planting": (
            f"Не зная правильной технологии посадки {variety_label} клубники, дачники теряют до 25–40% урожая.\n\n"
            "Я могу составить для Вас персональный план и решить эту проблему раз и навсегда!"
        ),
        "straw_s_soil_prep": (
            f"Не зная правильной технологии подготовки почвы перед посадкой {variety_label} клубники, дачники теряют до 25–40% урожая.\n\n"
            "Я могу составить для Вас персональный план и решить эту проблему раз и навсегда!"
        ),
        # --- Ремонтантная клубника ---
        "straw_r_leaf_spots": (
            f"В Вашем регионе из-за пятен на листьях дачники теряют до 25–40% урожая {variety_label} клубники.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "straw_r_rot": (
            f"В Вашем регионе из-за гниения ягод дачники теряют до 25–40% урожая {variety_label} клубники.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "straw_r_yellow_leaves": (
            f"В Вашем регионе из-за желтеющих листьев дачники теряют до 25–40% урожая {variety_label} клубники.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "straw_r_dieback": (
            f"В Вашем регионе из-за выпадов во второй половине лета дачники теряют до 25–40% урожая {variety_label} клубники.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "straw_r_planting": (
            f"Не зная правильной технологии посадки {variety_label} клубники, дачники теряют до 25–40% урожая.\n\n"
            "Я могу составить для Вас персональный план и решить эту проблему раз и навсегда!"
        ),
        "straw_r_soil_prep": (
            f"Не зная правильной технологии подготовки почвы перед посадкой {variety_label} клубники, дачники теряют до 25–40% урожая.\n\n"
            "Я могу составить для Вас персональный план и решить эту проблему раз и навсегда!"
        ),
    }

    text = offer_texts.get(problem_key)
    if text:
        return text

    # Fallback на общий шаблон
    return _get_offer_text("strawberry", problem_key)


def _get_raspberry_offer_text(problem_key: str, variety_key: str) -> str:
    """Генерирует текст оффера для малины — индивидуальный текст для каждой проблемы."""
    problem = _RASPBERRY_PROBLEM_MAP.get(problem_key)
    if not problem:
        return _get_offer_text("raspberry", problem_key)

    variety_label = "летней" if variety_key == "summer" else "ремонтантной"

    offer_texts = {
        # --- Летняя малина ---
        "rasp_s_diseases": (
            f"В Вашем регионе из-за болезней дачники теряют до 25–40% урожая {variety_label} малины.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "rasp_s_pruning": (
            f"Не зная правильной технологии обрезки {variety_label} малины, дачники теряют до 25–40% урожая.\n\n"
            "Я могу составить для Вас персональный план и решить эту проблему раз и навсегда!"
        ),
        "rasp_s_larvae": (
            f"В Вашем регионе из-за личинок в ягоде дачники теряют до 25–40% урожая {variety_label} малины.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "rasp_s_white_berry": (
            f"В Вашем регионе из-за побеления ягод дачники теряют до 25–40% урожая {variety_label} малины.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "rasp_s_small_berry": (
            f"Ежегодно дачники теряют до 25–40% объёма урожая {variety_label} малины.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "rasp_s_stem_spots": (
            f"В Вашем регионе из-за пятен на стеблях дачники теряют до 25–40% урожая {variety_label} малины.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "rasp_s_planting": (
            f"Не зная правильной технологии посадки {variety_label} малины, дачники теряют до 25–40% урожая.\n\n"
            "Я могу составить для Вас персональный план и решить эту проблему раз и навсегда!"
        ),
        "rasp_s_soil_prep": (
            f"Не зная правильной технологии подготовки почвы перед посадкой {variety_label} малины, дачники теряют до 25–40% урожая.\n\n"
            "Я могу составить для Вас персональный план и решить эту проблему раз и навсегда!"
        ),
        # --- Ремонтантная малина ---
        "rasp_r_diseases": (
            f"В Вашем регионе из-за болезней дачники теряют до 25–40% урожая {variety_label} малины.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "rasp_r_pruning": (
            f"Не зная правильной технологии обрезки {variety_label} малины, дачники теряют до 25–40% урожая.\n\n"
            "Я могу составить для Вас персональный план и решить эту проблему раз и навсегда!"
        ),
        "rasp_r_larvae": (
            f"В Вашем регионе из-за личинок в ягоде дачники теряют до 25–40% урожая {variety_label} малины.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "rasp_r_small_berry": (
            f"Ежегодно дачники теряют до 25–40% объёма урожая {variety_label} малины.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "rasp_r_white_berry": (
            f"В Вашем регионе из-за побеления ягод дачники теряют до 25–40% урожая {variety_label} малины.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "rasp_r_stem_spots": (
            f"В Вашем регионе из-за пятен на стеблях дачники теряют до 25–40% урожая {variety_label} малины.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "rasp_r_planting": (
            f"Не зная правильной технологии посадки {variety_label} малины, дачники теряют до 25–40% урожая.\n\n"
            "Я могу составить для Вас персональный план и решить эту проблему раз и навсегда!"
        ),
        "rasp_r_soil_prep": (
            f"Не зная правильной технологии подготовки почвы перед посадкой {variety_label} малины, дачники теряют до 25–40% урожая.\n\n"
            "Я могу составить для Вас персональный план и решить эту проблему раз и навсегда!"
        ),
    }

    text = offer_texts.get(problem_key)
    if text:
        return text

    return _get_offer_text("raspberry", problem_key)


def _get_currant_offer_text(problem_key: str) -> str:
    """Генерирует текст оффера для смородины — индивидуальный текст для каждой проблемы."""
    offer_texts = {
        "cur_yellow_leaves": (
            "В Вашем регионе из-за пожелтения кустов дачники теряют до 25–40% урожая смородины.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "cur_drying": (
            "В Вашем регионе из-за засыхания кустов дачники теряют до 25–40% урожая смородины.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "cur_glasswing": (
            "В Вашем регионе из-за стеклянницы дачники теряют до 25–40% урожая смородины.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "cur_pruning": (
            "Не зная правильной технологии обрезки смородины, дачники теряют до 25–40% урожая.\n\n"
            "Я могу составить для Вас персональный план и решить эту проблему раз и навсегда!"
        ),
        "cur_planting": (
            "Не зная правильной технологии посадки смородины, дачники теряют до 25–40% урожая.\n\n"
            "Я могу составить для Вас персональный план и решить эту проблему раз и навсегда!"
        ),
        "cur_soil_prep": (
            "Не зная правильной технологии подготовки почвы перед посадкой смородины, дачники теряют до 25–40% урожая.\n\n"
            "Я могу составить для Вас персональный план и решить эту проблему раз и навсегда!"
        ),
    }
    return offer_texts.get(problem_key, _get_offer_text("currant", problem_key))


def _get_honeysuckle_offer_text(problem_key: str) -> str:
    """Генерирует текст оффера для жимолости — индивидуальный текст для каждой проблемы."""
    offer_texts = {
        "hon_bad_taste": (
            "В Вашем регионе многие дачники жалуются на невкусную ягоду жимолости и теряют до 25–40% урожая.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "hon_low_yield": (
            "Ежегодно дачники теряют до 25–40% объёма урожая жимолости.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "hon_brown_leaves": (
            "В Вашем регионе из-за побурения листьев дачники теряют до 25–40% урожая жимолости.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "hon_no_berries": (
            "В Вашем регионе из-за отсутствия плодоношения дачники теряют до 25–40% урожая жимолости.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "hon_pruning": (
            "Не зная правильной технологии обрезки жимолости, дачники теряют до 25–40% урожая.\n\n"
            "Я могу составить для Вас персональный план и решить эту проблему раз и навсегда!"
        ),
        "hon_planting": (
            "Не зная правильной технологии посадки жимолости, дачники теряют до 25–40% урожая.\n\n"
            "Я могу составить для Вас персональный план и решить эту проблему раз и навсегда!"
        ),
        "hon_soil_prep": (
            "Не зная правильной технологии подготовки почвы перед посадкой жимолости, дачники теряют до 25–40% урожая.\n\n"
            "Я могу составить для Вас персональный план и решить эту проблему раз и навсегда!"
        ),
    }
    return offer_texts.get(problem_key, _get_offer_text("honeysuckle", problem_key))


def _get_blackberry_offer_text(problem_key: str) -> str:
    """Генерирует текст оффера для ежевики — индивидуальный текст для каждой проблемы."""
    offer_texts = {
        "blk_pruning": (
            "Не зная правильной технологии обрезки ежевики, дачники теряют до 25–40% урожая.\n\n"
            "Я могу составить для Вас персональный план и решить эту проблему раз и навсегда!"
        ),
        "blk_shelter": (
            "Не зная правильной технологии укрытия ежевики, дачники теряют до 25–40% урожая.\n\n"
            "Я могу составить для Вас персональный план и решить эту проблему раз и навсегда!"
        ),
        "blk_planting": (
            "Не зная правильной технологии посадки ежевики, дачники теряют до 25–40% урожая.\n\n"
            "Я могу составить для Вас персональный план и решить эту проблему раз и навсегда!"
        ),
        "blk_soil_prep": (
            "Не зная правильной технологии подготовки почвы перед посадкой ежевики, дачники теряют до 25–40% урожая.\n\n"
            "Я могу составить для Вас персональный план и решить эту проблему раз и навсегда!"
        ),
    }
    return offer_texts.get(problem_key, _get_offer_text("blackberry", problem_key))


def _get_blueberry_offer_text(problem_key: str) -> str:
    """Генерирует текст оффера для голубики — индивидуальный текст для каждой проблемы."""
    offer_texts = {
        "blu_yellow_leaves": (
            "В Вашем регионе из-за пожелтения листьев дачники теряют до 25–40% урожая голубики.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "blu_no_fruit": (
            "В Вашем регионе из-за отсутствия плодоношения дачники теряют до 25–40% урожая голубики.\n\n"
            "Я могу составить для Вас персональный план решения этой проблемы прямо сейчас!"
        ),
        "blu_soil_prep": (
            "Не зная правильной технологии подготовки грунта для голубики, дачники теряют до 25–40% урожая.\n\n"
            "Я могу составить для Вас персональный план и решить эту проблему раз и навсегда!"
        ),
        "blu_planting": (
            "Не зная правильной технологии посадки голубики, дачники теряют до 25–40% урожая.\n\n"
            "Я могу составить для Вас персональный план и решить эту проблему раз и навсегда!"
        ),
    }
    return offer_texts.get(problem_key, _get_offer_text("blueberry", problem_key))


def get_offer_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура финального оффера: 2 кнопки по 1 в ряд."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Получить персональную схему", callback_data="quiz_cta_payment")],
        [InlineKeyboardButton(text="Получить бесплатную консультацию", callback_data="quiz_cta_consultation")],
    ])


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


async def _log_quiz_msg(user_id: int, direction: str, text: str) -> None:
    """Логирует сообщение quiz в таблицу messages для отображения в CRM."""
    from src.services.db.messages_repo import log_message
    try:
        await log_message(
            user_id=user_id,
            direction=direction,
            text=text,
            session_id=f"quiz:{user_id}",
            topic_id=None,
        )
    except Exception as e:
        logger.debug(f"[funnel_b] Ошибка логирования quiz msg: {e}")


async def _quiz_already_done(user_id: int) -> bool:
    """Проверяет, прошёл ли пользователь квиз (есть запись в user_quiz_answers)."""
    from src.services.db.pool import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM user_quiz_answers WHERE user_id = $1",
            user_id,
        )
    return row is not None


async def _save_quiz_answer(user_id: int, field: str, value: str) -> None:
    """Сохраняет или обновляет один ответ квиза для пользователя."""
    from src.services.db.pool import get_pool
    pool = get_pool()
    # Используем параметризованный запрос с явным списком полей для защиты от инъекций.
    # field всегда одно из: culture, region, problem — задаётся только внутри модуля.
    allowed_fields = {"culture", "region", "problem"}
    if field not in allowed_fields:
        logger.error(f"[funnel_b] Недопустимое поле квиза: {field}")
        return
    async with pool.acquire() as conn:
        if field == "culture":
            await conn.execute(
                """
                INSERT INTO user_quiz_answers (user_id, culture)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET culture = EXCLUDED.culture, updated_at = NOW()
                """,
                user_id, value,
            )
        elif field == "region":
            await conn.execute(
                """
                INSERT INTO user_quiz_answers (user_id, region)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET region = EXCLUDED.region, updated_at = NOW()
                """,
                user_id, value,
            )
        elif field == "problem":
            await conn.execute(
                """
                INSERT INTO user_quiz_answers (user_id, problem)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET problem = EXCLUDED.problem, updated_at = NOW()
                """,
                user_id, value,
            )


async def _save_quiz_problem_key(user_id: int, problem_key: str) -> None:
    """Сохраняет ключ проблемы в user_quiz_answers для будущей авто-консультации."""
    from src.services.db.pool import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE user_quiz_answers SET problem_key = $2 WHERE user_id = $1",
            user_id, problem_key,
        )


async def _generate_auto_consultation(message: Message, tg_user, internal_user_id: int) -> None:
    """Генерирует автоматический ответ ИИ на основе данных quiz."""
    from src.services.db.pool import get_pool
    from src.services.db.topics_repo import get_or_create_open_topic
    from src.services.db.messages_repo import log_message
    from src.services.llm.consultation_llm import ask_consultation_llm
    from src.handlers.consultation.entry import send_long_message, finalize_streaming_message
    from src.utils.status_manager import StatusMessageManager

    # Достаём данные quiz из БД
    pool = get_pool()
    async with pool.acquire() as conn:
        quiz = await conn.fetchrow(
            "SELECT culture, region, problem, problem_key FROM user_quiz_answers WHERE user_id = $1",
            internal_user_id,
        )

    if not quiz:
        logger.error(f"[funnel_b] Нет данных quiz для user {internal_user_id}")
        await set_consultation_state(tg_user.id, "waiting_consultation_question")
        await message.answer("Задайте свой вопрос:")
        return

    culture = quiz["culture"] or "клубника"
    region = quiz["region"] or "средняя полоса"
    problem = quiz["problem"] or "уход за клубникой"
    problem_key = quiz["problem_key"]

    # Системная инструкция: пользователь прошёл quiz, ответ должен быть чётким и по делу
    quiz_focus = (
        "\n\n## ФОКУС ОТВЕТА (quiz автоконсультация)\n"
        "Пользователь прошёл диагностический опрос и оплатил персональный план. "
        "Твой ответ должен быть чётким, конкретным и практичным — "
        "строго по заданной проблеме. Не добавляй лишнюю теорию, "
        "давай готовый к применению план действий."
    )

    # Формируем авто-вопрос
    auto_question = (
        f"Помоги с проблемой: {problem}. "
        f"Культура: {culture}. Регион: {region}. "
        f"Дай подробный план действий."
    )

    session_id = f"tg:{tg_user.id}"
    topic_id = await get_or_create_open_topic(internal_user_id, session_id, force_new=True)

    # Показываем прогресс-бар
    status_mgr = StatusMessageManager(message)
    await status_mgr.start()

    try:
        reply_text = await ask_consultation_llm(
            user_id=internal_user_id,
            telegram_user_id=tg_user.id,
            text=auto_question,
            session_id=session_id,
            topic_id=topic_id,
            consultation_category=None,
            culture=culture,
            default_location=region,
            skip_rag=False,
            quiz_focus_instructions=quiz_focus,
            status_updater=status_mgr.update,
            stream=True,
            streaming_transition=status_mgr.start_streaming,
        )
    except Exception as e:
        logger.error(f"[funnel_b] Ошибка генерации авто-консультации для {internal_user_id}: {e}")
        await status_mgr.complete()
        await set_consultation_state(tg_user.id, "waiting_consultation_question")
        await message.answer("Произошла ошибка. Задайте свой вопрос:")
        return

    streaming_msg = status_mgr.get_streaming_message()
    await status_mgr.complete()

    # Финализируем стриминг — отправляем полный отформатированный текст
    await finalize_streaming_message(streaming_msg, message, reply_text)

    # Логируем вопрос и ответ
    try:
        await log_message(
            user_id=internal_user_id,
            direction="user",
            text=auto_question,
            session_id=session_id,
            topic_id=topic_id,
        )
        await log_message(
            user_id=internal_user_id,
            direction="bot",
            text=reply_text,
            session_id=session_id,
            topic_id=topic_id,
        )
    except Exception as e:
        logger.error(f"[funnel_b] Ошибка логирования для {internal_user_id}: {e}")

    # Переводим в режим ожидания нового вопроса (пользователь может сразу писать)
    await set_consultation_state(tg_user.id, "waiting_consultation_question")


def _mark_selected(markup: InlineKeyboardMarkup, selected_data: str) -> InlineKeyboardMarkup:
    """Заменяет клавиатуру на одну кнопку с галочкой — выбранный вариант."""
    for row in markup.inline_keyboard:
        for btn in row:
            if btn.callback_data == selected_data:
                return InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=f"✅ {btn.text}", callback_data="noop")]
                ])
    return markup


@router.callback_query(F.data == "noop")
async def handle_noop(callback: CallbackQuery) -> None:
    """Заглушка для уже выбранных кнопок."""
    await callback.answer()


async def _get_internal_user_id(telegram_user_id: int, tg_user) -> int:
    """Возвращает внутренний user_id по telegram_user_id."""
    from src.services.db.users_repo import get_or_create_user
    return await get_or_create_user(
        telegram_user_id=telegram_user_id,
        username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
    )


# ---------------------------------------------------------------------------
# Точка входа воронки Б
# ---------------------------------------------------------------------------

async def start_funnel_b(message: Message, user_id: int) -> None:
    """
    Точка входа для новых пользователей с вариантом воронки Б.
    Вызывается из menu.py cmd_start() при is_new_user == True и active_variant == 'B'.

    user_id — внутренний ID пользователя (из таблицы users).
    """
    logger.info(f"[funnel_b] User {user_id} entered funnel B")

    telegram_user_id = message.from_user.id

    # Сообщение 1: приветствие
    await message.answer(WELCOME_TEXT)
    await _log_quiz_msg(user_id, "bot", WELCOME_TEXT)

    # Пауза с индикатором "печатает..." для естественности
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    await asyncio.sleep(3)

    # Сообщение 2: первый шаг квиза
    await message.answer(QUIZ_CULTURE_TEXT, reply_markup=get_culture_keyboard())
    await _log_quiz_msg(user_id, "bot", QUIZ_CULTURE_TEXT)

    await set_consultation_state(telegram_user_id, "quiz_awaiting_culture")


# ---------------------------------------------------------------------------
# Обработчики квиза — культура
# ---------------------------------------------------------------------------

_CULTURE_LABELS = {
    "strawberry": "🍓 Клубника",
    "raspberry": "🍇 Малина",
    "blueberry": "🫐 Голубика",
    "currant": "🌿 Смородина",
    "honeysuckle": "🌸 Жимолость",
    "blackberry": "🫒 Ежевика",
    "other": "Другая культура",
}


@router.callback_query(F.data.startswith("quiz_culture_"))
async def handle_quiz_culture(callback: CallbackQuery) -> None:
    """Обработка выбора культуры."""
    await callback.answer()

    tg_user = callback.from_user
    internal_user_id = await _get_internal_user_id(tg_user.id, tg_user)

    culture_key = callback.data.replace("quiz_culture_", "")
    culture_label = _CULTURE_LABELS.get(culture_key, culture_key)

    # Ставим галочку на выбранную кнопку
    await callback.message.edit_reply_markup(
        reply_markup=_mark_selected(get_culture_keyboard(), callback.data)
    )

    try:
        await _save_quiz_answer(internal_user_id, "culture", culture_label)
    except Exception as e:
        logger.error(f"[funnel_b] Ошибка сохранения культуры для {internal_user_id}: {e}")

    await _log_quiz_msg(internal_user_id, "user", f"Культура: {culture_label}")

    # Сохраняем culture_key в контекст для персонализации оффера
    CONSULTATION_CONTEXT[tg_user.id] = {"quiz_culture_key": culture_key}

    if culture_key == "other":
        # Просим пользователя ввести культуру текстом
        await set_consultation_state(tg_user.id, "quiz_awaiting_culture_text")
        await callback.message.answer(QUIZ_CULTURE_CUSTOM_TEXT)
        await _log_quiz_msg(internal_user_id, "bot", QUIZ_CULTURE_CUSTOM_TEXT)
    elif culture_key in ("strawberry", "raspberry"):
        # Для клубники и малины — доп. вопрос про сорт
        await set_consultation_state(tg_user.id, "quiz_awaiting_variety")
        await callback.message.answer(QUIZ_VARIETY_TEXT, reply_markup=get_variety_keyboard())
        await _log_quiz_msg(internal_user_id, "bot", QUIZ_VARIETY_TEXT)
    else:
        await set_consultation_state(tg_user.id, "quiz_awaiting_region")
        await callback.message.answer(QUIZ_REGION_TEXT, reply_markup=get_region_keyboard())
        await _log_quiz_msg(internal_user_id, "bot", QUIZ_REGION_TEXT)


# ---------------------------------------------------------------------------
# Обработчики квиза — сорт (летняя / ремонтантная)
# ---------------------------------------------------------------------------

_VARIETY_LABELS = {
    "summer": "Летняя",
    "remontant": "Ремонтантная",
}


@router.callback_query(F.data.startswith("quiz_variety_"))
async def handle_quiz_variety(callback: CallbackQuery) -> None:
    """Обработка выбора сорта (летняя/ремонтантная) для клубники и малины."""
    await callback.answer()

    tg_user = callback.from_user
    internal_user_id = await _get_internal_user_id(tg_user.id, tg_user)

    variety_key = callback.data.replace("quiz_variety_", "")
    variety_label = _VARIETY_LABELS.get(variety_key, variety_key)

    # Ставим галочку на выбранную кнопку
    await callback.message.edit_reply_markup(
        reply_markup=_mark_selected(get_variety_keyboard(), callback.data)
    )

    # Дописываем сорт к культуре в БД (например "🍓 Клубника (Ремонтантная)")
    ctx = CONSULTATION_CONTEXT.get(tg_user.id, {})
    ctx["quiz_variety_key"] = variety_key
    CONSULTATION_CONTEXT[tg_user.id] = ctx
    culture_key = ctx.get("quiz_culture_key", "other")
    culture_label = _CULTURE_LABELS.get(culture_key, culture_key)
    full_culture_label = f"{culture_label} ({variety_label})"

    try:
        await _save_quiz_answer(internal_user_id, "culture", full_culture_label)
    except Exception as e:
        logger.error(f"[funnel_b] Ошибка сохранения сорта для {internal_user_id}: {e}")

    await _log_quiz_msg(internal_user_id, "user", f"Сорт: {variety_label}")

    await set_consultation_state(tg_user.id, "quiz_awaiting_region")
    await callback.message.answer(QUIZ_REGION_TEXT, reply_markup=get_region_keyboard())
    await _log_quiz_msg(internal_user_id, "bot", QUIZ_REGION_TEXT)


# ---------------------------------------------------------------------------
# Обработчики квиза — регион
# ---------------------------------------------------------------------------

_REGION_LABELS = {
    "central": "Средняя полоса",
    "south": "Юг",
    "north": "Север",
}


@router.callback_query(F.data.startswith("quiz_region_"))
async def handle_quiz_region(callback: CallbackQuery) -> None:
    """Обработка выбора региона."""
    await callback.answer()

    tg_user = callback.from_user
    region_key = callback.data.replace("quiz_region_", "")

    # Ставим галочку на выбранную кнопку
    await callback.message.edit_reply_markup(
        reply_markup=_mark_selected(get_region_keyboard(), callback.data)
    )

    if region_key == "custom":
        # Просим пользователя ввести регион текстом
        await set_consultation_state(tg_user.id, "quiz_awaiting_region_text")
        await callback.message.answer(QUIZ_REGION_CUSTOM_TEXT)
        return

    internal_user_id = await _get_internal_user_id(tg_user.id, tg_user)
    region_label = _REGION_LABELS.get(region_key, region_key)

    try:
        await _save_quiz_answer(internal_user_id, "region", region_label)
    except Exception as e:
        logger.error(f"[funnel_b] Ошибка сохранения региона для {internal_user_id}: {e}")

    # Сохраняем регион в контексте для офера
    if tg_user.id not in CONSULTATION_CONTEXT:
        CONSULTATION_CONTEXT[tg_user.id] = {}
    CONSULTATION_CONTEXT[tg_user.id]["quiz_region_label"] = region_label

    await _log_quiz_msg(internal_user_id, "user", f"Регион: {region_label}")

    await set_consultation_state(tg_user.id, "quiz_awaiting_problem")
    ctx = CONSULTATION_CONTEXT.get(tg_user.id, {})
    await callback.message.answer(QUIZ_PROBLEM_TEXT, reply_markup=get_problem_keyboard_for_context(ctx))
    await _log_quiz_msg(internal_user_id, "bot", QUIZ_PROBLEM_TEXT)


@router.message(F.text)
async def handle_quiz_text_input(message: Message) -> None:
    """
    Обработка текстового ввода в квизе (культура / регион).
    Срабатывает в состояниях quiz_awaiting_culture_text и quiz_awaiting_region_text.
    """
    if message.from_user is None:
        return

    tg_user = message.from_user
    state = CONSULTATION_STATE.get(tg_user.id)

    if state == "quiz_awaiting_culture_text":
        internal_user_id = await _get_internal_user_id(tg_user.id, tg_user)
        culture_text = message.text.strip()

        try:
            await _save_quiz_answer(internal_user_id, "culture", culture_text)
        except Exception as e:
            logger.error(f"[funnel_b] Ошибка сохранения культуры (текст) для {internal_user_id}: {e}")

        await _log_quiz_msg(internal_user_id, "user", f"Культура: {culture_text}")

        # Переходим к выбору региона (без вопроса про сорт)
        await set_consultation_state(tg_user.id, "quiz_awaiting_region")
        await message.answer(QUIZ_REGION_TEXT, reply_markup=get_region_keyboard())
        await _log_quiz_msg(internal_user_id, "bot", QUIZ_REGION_TEXT)

    elif state == "quiz_awaiting_region_text":
        internal_user_id = await _get_internal_user_id(tg_user.id, tg_user)
        region_text = message.text.strip()

        try:
            await _save_quiz_answer(internal_user_id, "region", region_text)
        except Exception as e:
            logger.error(f"[funnel_b] Ошибка сохранения региона (текст) для {internal_user_id}: {e}")

        # Сохраняем регион в контексте для офера
        if tg_user.id not in CONSULTATION_CONTEXT:
            CONSULTATION_CONTEXT[tg_user.id] = {}
        CONSULTATION_CONTEXT[tg_user.id]["quiz_region_label"] = region_text

        await _log_quiz_msg(internal_user_id, "user", f"Регион: {region_text}")

        await set_consultation_state(tg_user.id, "quiz_awaiting_problem")
        ctx = CONSULTATION_CONTEXT.get(tg_user.id, {})
        await message.answer(QUIZ_PROBLEM_TEXT, reply_markup=get_problem_keyboard_for_context(ctx))
        await _log_quiz_msg(internal_user_id, "bot", QUIZ_PROBLEM_TEXT)

    else:
        return  # Не наш шаг — пропускаем


# ---------------------------------------------------------------------------
# Обработчики квиза — проблема
# ---------------------------------------------------------------------------

_PROBLEM_LABELS = {
    "small_berries": "Мелкие ягоды",
    "diseases": "Болезни",
    "low_yield": "Мало урожая",
    "increase_yield": "Хочу увеличить урожай",
    "check_care": "Просто проверить уход",
}


@router.callback_query(F.data.startswith("quiz_problem_"))
async def handle_quiz_problem(callback: CallbackQuery) -> None:
    """Обработка выбора проблемы — последний шаг квиза, показываем оффер."""
    await callback.answer()

    tg_user = callback.from_user
    internal_user_id = await _get_internal_user_id(tg_user.id, tg_user)

    problem_key = callback.data.replace("quiz_problem_", "")

    # Резолв label: ищем по всем культурам, потом общие
    _all_problem_maps = (
        _STRAWBERRY_PROBLEM_MAP, _RASPBERRY_PROBLEM_MAP,
        _CURRANT_PROBLEM_MAP, _HONEYSUCKLE_PROBLEM_MAP,
        _BLACKBERRY_PROBLEM_MAP, _BLUEBERRY_PROBLEM_MAP,
    )
    problem_label = None
    for pmap in _all_problem_maps:
        if problem_key in pmap:
            problem_label = pmap[problem_key]["label"]
            break
    if not problem_label:
        problem_label = _PROBLEM_LABELS.get(problem_key, problem_key)

    # Достаём контекст для правильной клавиатуры и оффера
    ctx = CONSULTATION_CONTEXT.get(tg_user.id, {})
    culture_key = ctx.get("quiz_culture_key", "other")
    variety_key = ctx.get("quiz_variety_key")

    # Ставим галочку на выбранную кнопку (с правильной клавиатурой)
    current_keyboard = get_problem_keyboard_for_context(ctx)
    await callback.message.edit_reply_markup(
        reply_markup=_mark_selected(current_keyboard, callback.data)
    )

    try:
        await _save_quiz_answer(internal_user_id, "problem", problem_label)
        await _save_quiz_problem_key(internal_user_id, problem_key)
    except Exception as e:
        logger.error(f"[funnel_b] Ошибка сохранения проблемы для {internal_user_id}: {e}")

    await _log_quiz_msg(internal_user_id, "user", f"Проблема: {problem_label}")

    # Пробуем загрузить текст офера из файла offer.txt
    from src.services.quiz_solutions import get_offer_text as get_file_offer
    region = ctx.get("quiz_region_label", "")
    intro_text = get_file_offer(problem_key, region)

    if not intro_text:
        # Fallback на захардкоженные тексты
        _culture_offer_fn = {
            "currant": lambda pk, _: _get_currant_offer_text(pk),
            "honeysuckle": lambda pk, _: _get_honeysuckle_offer_text(pk),
            "blackberry": lambda pk, _: _get_blackberry_offer_text(pk),
            "blueberry": lambda pk, _: _get_blueberry_offer_text(pk),
        }
        if culture_key == "strawberry" and variety_key in ("summer", "remontant") and problem_key in _STRAWBERRY_PROBLEM_MAP:
            intro_text = _get_strawberry_offer_text(problem_key, variety_key)
        elif culture_key == "raspberry" and variety_key in ("summer", "remontant") and problem_key in _RASPBERRY_PROBLEM_MAP:
            intro_text = _get_raspberry_offer_text(problem_key, variety_key)
        elif culture_key in _culture_offer_fn:
            intro_text = _culture_offer_fn[culture_key](problem_key, variety_key)
        else:
            intro_text = _get_offer_text(culture_key, problem_key)

    await callback.message.answer(intro_text)
    await _log_quiz_msg(internal_user_id, "bot", intro_text)

    # Превью PDF-решения (если есть готовый PDF для этой проблемы)
    from src.services.quiz_solutions import get_quiz_solution
    solution = get_quiz_solution(problem_key)
    if solution and solution.get("preview_path"):
        from aiogram.types import FSInputFile
        preview_photo = FSInputFile(solution["preview_path"])
        preview_caption = f"🔒 {solution['preview_caption']}\n\n{solution['teaser']}"
        await callback.message.answer_photo(photo=preview_photo, caption=preview_caption)
        await _log_quiz_msg(internal_user_id, "bot", f"[Превью PDF: {solution['title']}]")

    # Квиз пройден — очищаем состояние
    await clear_consultation_state(tg_user.id)

    # Показываем оффер с кнопками
    await callback.message.answer(OFFER_TEXT_2, reply_markup=get_offer_keyboard())
    await _log_quiz_msg(internal_user_id, "bot", OFFER_TEXT_2)


# ---------------------------------------------------------------------------
# Обработчики CTA-кнопок оффера
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "quiz_cta_payment")
async def handle_quiz_cta_payment(callback: CallbackQuery) -> None:
    """CTA «Получить персональную схему» → показ описания + кнопка оплаты через ЮКассу."""
    await callback.answer()

    tg_user = callback.from_user
    internal_user_id = await _get_internal_user_id(tg_user.id, tg_user)

    # Отслеживаем этап в CRM-воронке (колонка "УЗНАЛ ЦЕНУ")
    try:
        from src.services.db.client_funnel_repo import update_client_status
        await update_client_status(internal_user_id, "paid")
    except Exception as e:
        logger.error(f"[funnel_b] Ошибка перемещения в воронке для {internal_user_id}: {e}")

    await _log_quiz_msg(internal_user_id, "user", "🔥 Получить персональную схему")

    # Достаём данные квиза из БД для описания платежа
    from src.services.db.pool import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        quiz = await conn.fetchrow(
            "SELECT culture, problem, problem_key FROM user_quiz_answers WHERE user_id = $1",
            internal_user_id,
        )

    culture_display = quiz["culture"] if quiz and quiz["culture"] else "ягодных культур"
    problem_display = quiz["problem"] if quiz and quiz["problem"] else "уход"
    problem_key = quiz["problem_key"] if quiz and quiz["problem_key"] else ""

    # Создаём платёж в ЮКассе
    try:
        from src.services.payments.payment_service import create_quiz_plan_payment
        result = await create_quiz_plan_payment(
            user_id=internal_user_id,
            telegram_user_id=tg_user.id,
            culture_display=culture_display,
            problem_display=problem_display,
            problem_key=problem_key,
        )

        confirmation_url = result["confirmation_url"]

        # Сообщение с описанием продукта + кнопка оплаты
        payment_text = (
            f"Персональный план по проблеме «{problem_display}» "
            f"для {culture_display}\n\n"
            f"<s>490 ₽</s> → <b>99 ₽</b>"
        )

        payment_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Оплатить 99 ₽", url=confirmation_url)],
        ])

        await callback.message.answer(payment_text, reply_markup=payment_keyboard)
        await _log_quiz_msg(internal_user_id, "bot", payment_text)

    except Exception as e:
        logger.error(f"[funnel_b] Ошибка создания платежа для {internal_user_id}: {e}")
        # Fallback: если платёж не создался — генерируем бесплатно
        await callback.message.answer(
            "Произошла ошибка при создании платежа. Генерирую план бесплатно..."
        )
        try:
            from src.services.db.topics_repo import close_open_topics
            await close_open_topics(internal_user_id)
        except Exception:
            pass
        await _generate_auto_consultation(callback.message, tg_user, internal_user_id)


@router.callback_query(F.data == "quiz_cta_consultation")
async def handle_quiz_cta_consultation(callback: CallbackQuery) -> None:
    """CTA «Получить бесплатную консультацию» → запускает consultation flow."""
    await callback.answer()

    tg_user = callback.from_user
    if tg_user is None:
        return

    internal_user_id = await _get_internal_user_id(tg_user.id, tg_user)

    await _log_quiz_msg(internal_user_id, "user", "Получить бесплатную консультацию")

    # Закрываем все открытые топики
    try:
        from src.services.db.topics_repo import close_open_topics
        await close_open_topics(internal_user_id)
    except Exception as e:
        logger.error(f"[funnel_b] Ошибка закрытия топиков для {internal_user_id}: {e}")

    # Переводим в состояние ожидания вопроса консультации
    await set_consultation_state(tg_user.id, "waiting_consultation_question")

    # Показываем стандартное вступление консультации
    from src.keyboards.consultation.common import CONSULTATION_ENTRY_TEXT, get_example_questions_keyboard
    kb = get_example_questions_keyboard()
    await callback.message.answer(CONSULTATION_ENTRY_TEXT, reply_markup=kb)
