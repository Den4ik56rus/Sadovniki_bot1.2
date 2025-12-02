# src/services/llm/classification_llm.py

"""
Классификация культуры (ягодного растения) с помощью LLM.

Задача detect_culture_name:
    - по тексту вопроса определить, о какой культуре идёт речь;
    - вернуть КРАТКОЕ название культуры в нормальном виде,
      например: "клубника садовая", "малина", "голубика";
    - если вопрос общий по нескольким культурам — "общая информация";
    - если культуру нельзя понять — "не определено".

ВАЖНО:
    - функция НЕ знает про тип консультации (питание/посадка и т.п.),
      возвращает только КУЛЬТУРУ;
    - тип консультации задаётся сценарием (например, "питание растений")
      и используется отдельно при формировании category_guess.
"""

from typing import Dict, List
import re

from src.services.llm.core_llm import create_chat_completion   # Асинхронный запрос к ChatGPT
from src.config import settings                                # Настройки проекта (модель и т.п.)
from src.services.db.kb_repo import kb_get_distinct_subcategories  # Живой список культур из базы знаний


def _cleanup_llm_answer(raw: str) -> str:
    """
    Жёсткая очистка ответа LLM:
        - убираем переводы строк,
        - вычищаем HTML-теги,
        - убираем markdown и кавычки,
        - берём только первую фразу до . ! ?,
        - оставляем только буквы, пробелы и дефисы,
        - схлопываем пробелы,
        - ограничиваем длину,
        - приводим к нижнему регистру.
    """
    if not raw:
        return ""

    text = raw.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"<[^>]+>", " ", text)
    text = (
        text.replace("**", " ")
        .replace("__", " ")
        .replace('"', " ")
        .replace("'", " ")
        .replace("`", " ")
        .replace("«", " ")
        .replace("»", " ")
    )

    parts = re.split(r"[\.!\?]", text, maxsplit=1)
    text = parts[0] if parts else text

    text = re.sub(r"[^a-zA-Zа-яА-ЯёЁ\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text)

    text = text.strip()
    if len(text) > 200:
        text = text[:200].strip()

    return text.lower()


def _keyword_fallback(raw_text: str) -> str:
    """
    Запасная классификация по ключевым словам в исходном вопросе.

    Логика:
        - если найдена ровно ОДНА культура — возвращаем её;
        - если найдены несколько разных культур — "общая информация";
        - если нет конкретных культур, но речь явно про ягоды/кустарники —
          "общая информация";
        - если вообще не про ягоды — "не определено".
    """
    if not raw_text:
        return "не определено"

    text = raw_text.lower()
    candidates: set[str] = set()

    # Клубника / земляника
    if "клубник" in text or "земляник" in text:
        # Проверяем тип
        if "ремонтант" in text or "нсд" in text:
            candidates.add("клубника ремонтантная")
        elif "летн" in text or "традицион" in text or "обычн" in text or "июньск" in text:
            candidates.add("клубника летняя")
        else:
            # Без уточнения - добавляем общую категорию
            candidates.add("клубника общая")

    # Малина
    if "малин" in text:
        if "ремонтант" in text or "нсд" in text:
            candidates.add("малина ремонтантная")
        elif "летн" in text or "традицион" in text or "обычн" in text:
            candidates.add("малина летняя")
        else:
            candidates.add("малина общая")

    # Смородина (единая категория)
    if "смородин" in text:
        candidates.add("смородина")

    # Голубика
    if "голубик" in text:
        candidates.add("голубика")

    # Жимолость
    if "жимолост" in text:
        candidates.add("жимолость")

    # Крыжовник
    if "крыжовник" in text:
        candidates.add("крыжовник")

    # Несколько культур → общая информация (общий совет сразу по нескольким)
    if len(candidates) > 1:
        print(f"[_keyword_fallback] multiple candidates={candidates!r} -> 'общая информация'")
        return "общая информация"

    # Одна культура
    if len(candidates) == 1:
        return next(iter(candidates))

    # Нет конкретных культур, но явно про ягоды/кустарники → общая информация
    if "ягод" in text or "кустарник" in text or "куст" in text:
        return "общая информация"

    # Вообще не про ягоды
    return "не определено"


async def detect_culture_name(text: str) -> str:
    """
    Определяет КУЛЬТУРУ по тексту вопроса с помощью LLM.

    Контракт:
        - возвращает КРАТКОЕ название культуры (в нормальном виде),
          например: "малина", "голубика", "клубника садовая";
        - либо "общая информация" — если вопрос общий для нескольких культур
          или не привязан к одной конкретной;
        - либо "не определено" — если понять, про что речь, нельзя.

    Функция НЕ трогает тип консультации (питание/посадка и т.п.).
    """
    raw_text = text or ""

    # Тянем список КУЛЬТУР из базы знаний.
    # Он используется как ПОДСКАЗКА модели, а не как жёсткий список допустимых значений.
    db_cultures: List[str] = await kb_get_distinct_subcategories(limit=200)
    specials = ["общая информация", "не определено"]

    if db_cultures:
        # Культуры из БД + служебные значения
        cultures_for_prompt = [*db_cultures, *specials]
    else:
        # Если БД ещё пустая — даём только служебные варианты
        cultures_for_prompt = specials

    categories_list_str = "\n".join(f"- {name}" for name in cultures_for_prompt)

    system_prompt = (
        "Ты агроном-консультант, но сейчас работаешь как КЛАССИФИКАТОР ягодных культур.\n"
        "Твоя задача: по тексту вопроса определить, к КАКОЙ КУЛЬТУРЕ относится вопрос.\n\n"
        "Вот список примеров допустимых ответов (ориентируйся на него и не выдумывай лишних слов):\n"
        f"{categories_list_str}\n\n"
        "ПРАВИЛА:\n"
        "  1) Верни ОДНУ короткую фразу — название культуры или 'общая информация' / 'не определено'.\n"
        "  2) Без кавычек и пояснений.\n"
        "  3) ВАЖНО: Для клубники и малины различай типы:\n"
        "     - Если упомянута 'ремонтантная', 'НСД', 'нейтрального дня' → клубника ремонтантная / малина ремонтантная\n"
        "     - Если упомянута 'летняя', 'обычная', 'традиционная', 'июньская' → клубника летняя / малина летняя\n"
        "     - Если тип НЕ указан явно → 'клубника общая' или 'малина общая'\n"
        "  4) Если вопрос даёт общие рекомендации сразу по нескольким культурам\n"
        "     или не привязан к одной — выбери: общая информация.\n"
        "  5) Если вопрос вообще не про ягодные культуры — выбери: не определено.\n"
    )

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": (
                "Текст вопроса пользователя по ягодным растениям:\n\n"
                f"{raw_text}\n\n"
                "Верни ТОЛЬКО одну строку — краткое название культуры\n"
                "или фразу: общая информация / не определено."
            ),
        },
    ]

    try:
        llm_answer = await create_chat_completion(
            messages=messages,
            model=settings.openai_model,
            temperature=0.0,
        )

        raw = (llm_answer or "").strip()
        if not raw:
            print(f"[detect_culture_name][EMPTY] text={raw_text!r} -> raw=''")
            fallback_culture = _keyword_fallback(raw_text)
            print(
                f"[detect_culture_name][EMPTY_FALLBACK] text={raw_text!r} "
                f"-> keyword_fallback={fallback_culture!r}"
            )
            return fallback_culture

        normalized = _cleanup_llm_answer(raw)

        print(
            f"[detect_culture_name][RAW] text={raw_text!r} "
            f"-> llm_raw={raw!r} -> normalized={normalized!r}"
        )

        specials_set = {"общая информация", "не определено"}

        # 1. Если модель честно вернула "общая информация" или "не определено"
        if normalized in specials_set:
            print(
                f"[detect_culture_name][DECISION_LLM_SPECIAL] culture={normalized!r} "
                f"for text={raw_text!r}"
            )
            # Пробуем улучшить через keyword_fallback:
            # если он дал КОНКРЕТНУЮ культуру — используем её.
            keyword_culture = _keyword_fallback(raw_text)
            if keyword_culture not in ("не определено", normalized):
                print(
                    f"[detect_culture_name][KEYWORD_OVERRIDE] text={raw_text!r} "
                    f"-> keyword_culture={keyword_culture!r}"
                )
                return keyword_culture
            return normalized

        # 2. Маппинг частых вариантов к нормальным названиям
        mapping: Dict[str, str] = {
            # Клубника ремонтантная (приоритет выше)
            "клубника ремонтантная": "клубника ремонтантная",
            "клубника нсд": "клубника ремонтантная",
            "земляника ремонтантная": "клубника ремонтантная",
            "земляника нсд": "клубника ремонтантная",
            "ремонтантная клубника": "клубника ремонтантная",
            "ремонтантная земляника": "клубника ремонтантная",

            # Клубника летняя
            "клубника летняя": "клубника летняя",
            "клубника обычная": "клубника летняя",
            "клубника традиционная": "клубника летняя",
            "клубника июньская": "клубника летняя",
            "земляника летняя": "клубника летняя",
            "земляника традиционная": "клубника летняя",
            "июньская клубника": "клубника летняя",

            # Клубника без уточнения (общая)
            "клубника садовая": "клубника общая",
            "земляника садовая": "клубника общая",
            "земляника": "клубника общая",
            "клубника": "клубника общая",

            # Малина ремонтантная (приоритет выше)
            "малина ремонтантная": "малина ремонтантная",
            "малина нсд": "малина ремонтантная",
            "ремонтантная малина": "малина ремонтантная",

            # Малина летняя
            "малина летняя": "малина летняя",
            "малина обычная": "малина летняя",
            "малина традиционная": "малина летняя",
            "летняя малина": "малина летняя",
            "обычная малина": "малина летняя",

            # Малина без уточнения (общая)
            "малина": "малина общая",

            # Смородина (единая)
            "смородина": "смородина",
            "смородина черная": "смородина",
            "смородина красная": "смородина",
            "смородина белая": "смородина",
            "чёрная смородина": "смородина",
            "красная смородина": "смородина",
            "белая смородина": "смородина",
            "черная смородина": "смородина",
            "черная": "смородина",
            "красная": "смородина",
            "белая": "смородина",

            # Голубика
            "голубика": "голубика",

            # Жимолость
            "жимолость": "жимолость",
            "жимолость съедобная": "жимолость",

            # Крыжовник
            "крыжовник": "крыжовник",

            # Специальные значения
            "общая информация": "общая информация",
            "не определено": "не определено",
        }

        culture = normalized
        for key, value in mapping.items():
            if key in normalized:
                culture = value
                print(
                    f"[detect_culture_name][MAP] text={raw_text!r} "
                    f"-> normalized={normalized!r} -> culture={culture!r}"
                )
                break

        # 3. Попробуем keyword_fallback — он часто надёжнее при шумных ответах
        keyword_culture = _keyword_fallback(raw_text)
        if keyword_culture not in ("не определено", "общая информация"):
            print(
                f"[detect_culture_name][KEYWORD_HELP] text={raw_text!r} "
                f"-> llm_culture={culture!r} -> keyword_culture={keyword_culture!r}"
            )
            culture = keyword_culture

        # 4. Если получилось 1–4 слова — принимаем как культуру
        words = culture.split()
        if 0 < len(words) <= 4 and culture not in specials_set:
            final = " ".join(words).strip()
            print(
                f"[detect_culture_name][ACCEPTED] text={raw_text!r} "
                f"-> culture={final!r}"
            )
            return final

        # 5. Если мы сюда дошли, culture либо пустая/странная, либо спец-значение.
        #    В этом случае уже делегируем keyword_fallback окончательно.
        final_fallback = _keyword_fallback(raw_text)
        print(
            f"[detect_culture_name][FINAL_FALLBACK] text={raw_text!r} "
            f"-> culture={culture!r} -> final={final_fallback!r}"
        )
        return final_fallback

    except Exception as e:
        print(f"[detect_culture_name][ERROR] {e} | text={raw_text!r}")
        fallback_culture = _keyword_fallback(raw_text)
        print(
            f"[detect_culture_name][ERROR_FALLBACK] text={raw_text!r} "
            f"-> keyword_fallback={fallback_culture!r}"
        )
        return fallback_culture
