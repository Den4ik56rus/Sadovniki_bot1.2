# src/services/quiz_solutions.py

"""
Lookup готовых PDF-решений для квиза воронки Б.

Структура хранения:
    data/quiz_solutions/{culture}/{problem}/
        solution.pdf      — полный PDF
        preview.jpg|png   — картинка-превью (заблокированная)
        config.json       — метаданные (опционально)
    data/quiz_solutions/{culture}/preview/
        — превью по культуре (общее)
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
SOLUTIONS_DIR = BASE_DIR / "data" / "quiz_solutions"

_DEFAULT_CONFIG = {
    "title": "Персональный план решения",
    "teaser": "Подробный план действий с конкретными препаратами, дозировками и сроками.",
    "preview_caption": "Вот что вы получите после оплаты:",
    "delivery_caption": "Ваш персональный план готов!",
}

# Маппинг problem_key → (culture_folder, problem_folder)
_KEY_TO_PATH: Dict[str, tuple] = {
    # Клубника летняя
    "straw_s_low_yield": ("strawberry_summer", "low_yield"),
    "straw_s_yellow_leaves": ("strawberry_summer", "yellow_leaves"),
    "straw_s_leaf_spots": ("strawberry_summer", "leaf_spots"),
    "straw_s_pests": ("strawberry_summer", "pests"),
    "straw_s_planting": ("strawberry_summer", "planting"),
    "straw_s_soil_prep": ("strawberry_summer", "soil_prep"),
    # Клубника ремонтантная
    "straw_r_leaf_spots": ("strawberry_remontant", "leaf_spots"),
    "straw_r_rot": ("strawberry_remontant", "rot"),
    "straw_r_yellow_leaves": ("strawberry_remontant", "yellow_leaves"),
    "straw_r_dieback": ("strawberry_remontant", "dieback"),
    "straw_r_planting": ("strawberry_remontant", "planting"),
    "straw_r_soil_prep": ("strawberry_remontant", "soil_prep"),
    # Малина летняя
    "rasp_s_diseases": ("raspberry_summer", "diseases"),
    "rasp_s_pruning": ("raspberry_summer", "pruning"),
    "rasp_s_larvae": ("raspberry_summer", "larvae"),
    "rasp_s_white_berry": ("raspberry_summer", "white_berry"),
    "rasp_s_small_berry": ("raspberry_summer", "small_berry"),
    "rasp_s_stem_spots": ("raspberry_summer", "stem_spots"),
    "rasp_s_planting": ("raspberry_summer", "planting"),
    "rasp_s_soil_prep": ("raspberry_summer", "soil_prep"),
    # Малина ремонтантная
    "rasp_r_diseases": ("raspberry_remontant", "diseases"),
    "rasp_r_pruning": ("raspberry_remontant", "pruning"),
    "rasp_r_larvae": ("raspberry_remontant", "larvae"),
    "rasp_r_small_berry": ("raspberry_remontant", "small_berry"),
    "rasp_r_white_berry": ("raspberry_remontant", "white_berry"),
    "rasp_r_stem_spots": ("raspberry_remontant", "stem_spots"),
    "rasp_r_planting": ("raspberry_remontant", "planting"),
    "rasp_r_soil_prep": ("raspberry_remontant", "soil_prep"),
    # Смородина
    "cur_yellow_leaves": ("currant", "yellow_leaves"),
    "cur_drying": ("currant", "drying"),
    "cur_glasswing": ("currant", "glasswing"),
    "cur_pruning": ("currant", "pruning"),
    "cur_planting": ("currant", "planting"),
    "cur_soil_prep": ("currant", "soil_prep"),
    # Жимолость
    "hon_bad_taste": ("honeysuckle", "bad_taste"),
    "hon_low_yield": ("honeysuckle", "low_yield"),
    "hon_brown_leaves": ("honeysuckle", "brown_leaves"),
    "hon_no_berries": ("honeysuckle", "no_berries"),
    "hon_pruning": ("honeysuckle", "pruning"),
    "hon_planting": ("honeysuckle", "planting"),
    "hon_soil_prep": ("honeysuckle", "soil_prep"),
    # Ежевика
    "blk_pruning": ("blackberry", "pruning"),
    "blk_shelter": ("blackberry", "shelter"),
    "blk_planting": ("blackberry", "planting"),
    "blk_soil_prep": ("blackberry", "soil_prep"),
    # Голубика
    "blu_yellow_leaves": ("blueberry", "yellow_leaves"),
    "blu_no_fruit": ("blueberry", "no_fruit"),
    "blu_soil_prep": ("blueberry", "soil_prep"),
    "blu_planting": ("blueberry", "planting"),
}


def _resolve_path(problem_key: str) -> Optional[Path]:
    """Преобразует problem_key в путь к папке решения."""
    mapping = _KEY_TO_PATH.get(problem_key)
    if mapping:
        return SOLUTIONS_DIR / mapping[0] / mapping[1]
    # Fallback: попробовать как прямую папку (обратная совместимость)
    direct = SOLUTIONS_DIR / problem_key
    if direct.exists():
        return direct
    return None


def _find_pdf(directory: Path) -> Optional[Path]:
    """Ищет PDF в папке: сначала solution.pdf, потом любой *.pdf."""
    preferred = directory / "solution.pdf"
    if preferred.exists():
        return preferred
    pdfs = list(directory.glob("*.pdf"))
    return pdfs[0] if pdfs else None


def get_quiz_solution(problem_key: str) -> Optional[Dict[str, Any]]:
    """Проверяет наличие готового PDF-решения для problem_key.

    Returns:
        dict с путями и метаданными, или None если решения нет.
    """
    solution_dir = _resolve_path(problem_key)

    pdf_path: Optional[Path] = None
    if solution_dir is not None:
        pdf_path = _find_pdf(solution_dir)

    if pdf_path is None:
        return None

    # Загрузить config (опционален)
    config: Dict[str, Any] = dict(_DEFAULT_CONFIG)
    config_path = solution_dir / "config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            config.update(user_config)
        except Exception as e:
            logger.warning(f"[quiz_solutions] Ошибка чтения config для {problem_key}: {e}")

    # Найти превью (jpg/png) — сначала в папке проблемы, потом в preview/ культуры
    preview_path: Optional[str] = None
    for ext in ("jpg", "jpeg", "png"):
        candidate = solution_dir / f"preview.{ext}"
        if candidate.exists():
            preview_path = str(candidate)
            break

    if preview_path is None and solution_dir.parent:
        culture_preview = solution_dir.parent / "preview"
        for ext in ("jpg", "jpeg", "png"):
            candidate = culture_preview / f"preview.{ext}"
            if candidate.exists():
                preview_path = str(candidate)
                break

    return {
        "problem_key": problem_key,
        "pdf_path": str(pdf_path),
        "preview_path": preview_path,
        "title": config["title"],
        "teaser": config["teaser"],
        "preview_caption": config["preview_caption"],
        "delivery_caption": config["delivery_caption"],
    }


# Маппинг problem_key → русское название культуры + проблемы для заголовка офера
_OFFER_HEADERS: Dict[str, tuple] = {
    # Клубника летняя
    "straw_s_low_yield": ("Клубника летняя", "мало ягод или они мелкие"),
    "straw_s_yellow_leaves": ("Клубника летняя", "жёлтые листья"),
    "straw_s_leaf_spots": ("Клубника летняя", "пятна на листьях"),
    "straw_s_pests": ("Клубника летняя", "вредители портят лист"),
    "straw_s_planting": ("Клубника летняя", "посадка"),
    "straw_s_soil_prep": ("Клубника летняя", "подготовка почвы"),
    # Клубника ремонтантная
    "straw_r_leaf_spots": ("Клубника ремонтантная", "пятна на листьях"),
    "straw_r_rot": ("Клубника ремонтантная", "ягода гниёт"),
    "straw_r_yellow_leaves": ("Клубника ремонтантная", "жёлтые листья"),
    "straw_r_dieback": ("Клубника ремонтантная", "выпады во второй половине лета"),
    "straw_r_planting": ("Клубника ремонтантная", "посадка"),
    "straw_r_soil_prep": ("Клубника ремонтантная", "подготовка почвы"),
    # Малина летняя
    "rasp_s_diseases": ("Малина летняя", "болезни"),
    "rasp_s_pruning": ("Малина летняя", "обрезка"),
    "rasp_s_larvae": ("Малина летняя", "личинки в ягоде"),
    "rasp_s_white_berry": ("Малина летняя", "белая ягода"),
    "rasp_s_small_berry": ("Малина летняя", "мелкая ягода"),
    "rasp_s_stem_spots": ("Малина летняя", "пятна на стеблях"),
    "rasp_s_planting": ("Малина летняя", "посадка"),
    "rasp_s_soil_prep": ("Малина летняя", "подготовка почвы"),
    # Малина ремонтантная
    "rasp_r_diseases": ("Малина ремонтантная", "болезни"),
    "rasp_r_pruning": ("Малина ремонтантная", "обрезка"),
    "rasp_r_larvae": ("Малина ремонтантная", "личинки в ягоде"),
    "rasp_r_small_berry": ("Малина ремонтантная", "мелкая ягода"),
    "rasp_r_white_berry": ("Малина ремонтантная", "белая ягода"),
    "rasp_r_stem_spots": ("Малина ремонтантная", "пятна на стеблях"),
    "rasp_r_planting": ("Малина ремонтантная", "посадка"),
    "rasp_r_soil_prep": ("Малина ремонтантная", "подготовка почвы"),
    # Смородина
    "cur_yellow_leaves": ("Смородина", "кусты желтеют"),
    "cur_drying": ("Смородина", "кусты засыхают"),
    "cur_glasswing": ("Смородина", "стеклянница"),
    "cur_pruning": ("Смородина", "обрезка"),
    "cur_planting": ("Смородина", "посадка"),
    "cur_soil_prep": ("Смородина", "подготовка почвы"),
    # Жимолость
    "hon_bad_taste": ("Жимолость", "невкусная ягода"),
    "hon_low_yield": ("Жимолость", "мало ягод"),
    "hon_brown_leaves": ("Жимолость", "бурые листья"),
    "hon_no_berries": ("Жимолость", "нет ягод на взрослых кустах"),
    "hon_pruning": ("Жимолость", "обрезка"),
    "hon_planting": ("Жимолость", "посадка"),
    "hon_soil_prep": ("Жимолость", "подготовка почвы"),
    # Ежевика
    "blk_pruning": ("Ежевика", "обрезка"),
    "blk_shelter": ("Ежевика", "укрытие"),
    "blk_planting": ("Ежевика", "посадка"),
    "blk_soil_prep": ("Ежевика", "подготовка почвы"),
    # Голубика
    "blu_yellow_leaves": ("Голубика", "желтеют листья"),
    "blu_no_fruit": ("Голубика", "не плодоносит"),
    "blu_soil_prep": ("Голубика", "подготовка грунта"),
    "blu_planting": ("Голубика", "посадка"),
}


def get_offer_text(problem_key: str, region: str = "") -> Optional[str]:
    """Загружает текст офера из offer.txt и подставляет заголовок.

    Returns:
        Готовый текст офера или None если offer.txt не найден.
    """
    solution_dir = _resolve_path(problem_key)
    if solution_dir is None:
        return None

    offer_path = solution_dir / "offer.txt"
    if not offer_path.exists():
        return None

    try:
        body = offer_path.read_text(encoding="utf-8").strip()
    except Exception as e:
        logger.warning(f"[quiz_solutions] Ошибка чтения offer.txt для {problem_key}: {e}")
        return None

    header_info = _OFFER_HEADERS.get(problem_key)
    if header_info:
        culture_name, problem_name = header_info
        region_text = region if region else "ваш регион"
        header = f"<b>{culture_name}</b>, {region_text}, проблема — <b>{problem_name}</b>.\n\n"
    else:
        header = ""

    return header + body
