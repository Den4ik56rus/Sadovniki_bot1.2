# src/data/funnel_b_problems.py

"""
Общий модуль проблем Funnel B.

Используется в:
- src/handlers/funnel_b.py — клавиатуры Telegram
- src/api/handlers/presentations.py — API для админ-панели
"""

from typing import Optional


# ---------------------------------------------------------------------------
# Культуры
# ---------------------------------------------------------------------------

CULTURES = [
    {
        "key": "strawberry",
        "label": "Клубника",
        "has_varieties": True,
        "varieties": [
            {"key": "summer", "label": "Летняя"},
            {"key": "remontant", "label": "Ремонтантная"},
        ],
    },
    {
        "key": "raspberry",
        "label": "Малина",
        "has_varieties": True,
        "varieties": [
            {"key": "summer", "label": "Летняя"},
            {"key": "remontant", "label": "Ремонтантная"},
        ],
    },
    {
        "key": "currant",
        "label": "Смородина",
        "has_varieties": False,
        "varieties": [],
    },
    {
        "key": "honeysuckle",
        "label": "Жимолость",
        "has_varieties": False,
        "varieties": [],
    },
    {
        "key": "blackberry",
        "label": "Ежевика",
        "has_varieties": False,
        "varieties": [],
    },
    {
        "key": "blueberry",
        "label": "Голубика",
        "has_varieties": False,
        "varieties": [],
    },
]


# ---------------------------------------------------------------------------
# Проблемы по культурам
# ---------------------------------------------------------------------------

STRAWBERRY_PROBLEMS = {
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

RASPBERRY_PROBLEMS = {
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

CURRANT_PROBLEMS = [
    {"key": "cur_yellow_leaves", "label": "Кусты желтеют", "hint": "хлороз, дефицит питания, грибные заболевания"},
    {"key": "cur_drying", "label": "Кусты засыхают", "hint": "стеклянница, корневые гнили, засуха"},
    {"key": "cur_glasswing", "label": "Как побороть стеклянницу", "hint": "обрезка поражённых побегов, инсектициды"},
    {"key": "cur_pruning", "label": "Правила обрезки", "hint": None},
    {"key": "cur_planting", "label": "Как и на каком расстоянии сажать", "hint": None},
    {"key": "cur_soil_prep", "label": "Подготовка почвы перед посадкой", "hint": None},
]

HONEYSUCKLE_PROBLEMS = [
    {"key": "hon_bad_taste", "label": "Не вкусная ягода", "hint": "сорт, полив, питание"},
    {"key": "hon_low_yield", "label": "Мало ягод", "hint": "опыление, возраст куста, подкормка"},
    {"key": "hon_brown_leaves", "label": "Листья становятся бурого цвета", "hint": "грибные болезни, ожог"},
    {"key": "hon_no_berries", "label": "Нет ягод на взрослых кустах", "hint": "отсутствие опылителя, обрезка"},
    {"key": "hon_pruning", "label": "Правила обрезки", "hint": None},
    {"key": "hon_planting", "label": "Как и на каком расстоянии сажать", "hint": None},
    {"key": "hon_soil_prep", "label": "Подготовка почвы перед посадкой", "hint": None},
]

BLACKBERRY_PROBLEMS = [
    {"key": "blk_pruning", "label": "Правила обрезки", "hint": None},
    {"key": "blk_shelter", "label": "Правила укрытия", "hint": "укрытие на зиму, материалы"},
    {"key": "blk_planting", "label": "Как и на каком расстоянии сажать", "hint": None},
    {"key": "blk_soil_prep", "label": "Подготовка почвы перед посадкой", "hint": None},
]

BLUEBERRY_PROBLEMS = [
    {"key": "blu_yellow_leaves", "label": "Желтеют листья", "hint": "хлороз, pH почвы, дефицит железа"},
    {"key": "blu_no_fruit", "label": "Не плодоносит", "hint": "кислотность, опыление, возраст"},
    {"key": "blu_soil_prep", "label": "Подготовка грунта", "hint": "кислый торф, хвойный опад"},
    {"key": "blu_planting", "label": "Правила посадки", "hint": None},
]


# ---------------------------------------------------------------------------
# Проблемы по ключу культуры (для API)
# ---------------------------------------------------------------------------

_PROBLEMS_BY_CULTURE = {
    "strawberry": STRAWBERRY_PROBLEMS,
    "raspberry": RASPBERRY_PROBLEMS,
    "currant": {"_default": CURRANT_PROBLEMS},
    "honeysuckle": {"_default": HONEYSUCKLE_PROBLEMS},
    "blackberry": {"_default": BLACKBERRY_PROBLEMS},
    "blueberry": {"_default": BLUEBERRY_PROBLEMS},
}

# Плоский lookup: problem_key → {key, label, hint, culture_key, variety_key}
_ALL_PROBLEMS_MAP: dict[str, dict] = {}

for _culture_key, _culture_data in _PROBLEMS_BY_CULTURE.items():
    for _var_key, _prob_list in _culture_data.items():
        for _p in _prob_list:
            _ALL_PROBLEMS_MAP[_p["key"]] = {
                **_p,
                "culture_key": _culture_key,
                "variety_key": _var_key if _var_key != "_default" else None,
            }

# Маппинг culture_key → русское название для RAG
_CULTURE_KEY_TO_RUSSIAN = {
    "strawberry": "клубника",
    "raspberry": "малина",
    "currant": "смородина",
    "honeysuckle": "жимолость",
    "blackberry": "ежевика",
    "blueberry": "голубика",
}


# ---------------------------------------------------------------------------
# Публичные функции
# ---------------------------------------------------------------------------

def get_problem_label(problem_key: str) -> str:
    """Возвращает русское название проблемы по ключу."""
    p = _ALL_PROBLEMS_MAP.get(problem_key)
    return p["label"] if p else problem_key


def get_culture_label(culture_key: str, variety_key: Optional[str] = None) -> str:
    """Возвращает русское название культуры (с сортом если есть)."""
    for c in CULTURES:
        if c["key"] == culture_key:
            label = c["label"]
            if variety_key:
                for v in c["varieties"]:
                    if v["key"] == variety_key:
                        label += f" {v['label'].lower()}"
                        break
            return label
    return culture_key


def get_culture_russian(culture_key: str) -> str:
    """Возвращает русское название культуры для RAG фильтрации."""
    return _CULTURE_KEY_TO_RUSSIAN.get(culture_key, "")


def get_all_structured() -> list:
    """Возвращает полную структуру культур + проблем для API."""
    result = []
    for culture in CULTURES:
        entry = {
            "key": culture["key"],
            "label": culture["label"],
            "has_varieties": culture["has_varieties"],
            "varieties": culture["varieties"],
            "problems": _PROBLEMS_BY_CULTURE.get(culture["key"], {}),
        }
        result.append(entry)
    return result
