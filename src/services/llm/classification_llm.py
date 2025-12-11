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

from typing import Dict, List, Tuple
import re

from src.services.llm.core_llm import create_chat_completion, create_chat_completion_with_usage, calculate_cost
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

    # Специальные термины для клубники
    if "фриго" in text or "ус" in text or "усы" in text or "усов" in text or "виктори" in text:
        candidates.add("клубника общая")

    # Специальные термины для малины
    if "корневая поросль" in text or "поросл" in text:
        candidates.add("малина общая")

    # Специальные термины для голубики
    if "вересков" in text:
        candidates.add("голубика")

    # Сорта клубники ремонтантной
    if any(s in text for s in ["альбион", "сан андреас", "монтерей"]):
        candidates.add("клубника ремонтантная")

    # Сорта клубники летней
    if any(s in text for s in ["полка", "вима занта", "хоней"]):
        candidates.add("клубника летняя")

    # Сорта малины ремонтантной
    if any(s in text for s in ["химбо топ", "полька", "джоан джей"]):
        candidates.add("малина ремонтантная")

    # Сорта малины летней
    if any(s in text for s in ["патриция", "таруса", "гусар"]):
        candidates.add("малина летняя")

    # Клубника / земляника
    if "клубник" in text or "земляник" in text:
        # ИЗМЕНЕНО: Проверяем летнюю/обычную ПЕРВОЙ (выше приоритет)
        if "летн" in text or "традицион" in text or "обычн" in text or "июньск" in text:
            candidates.add("клубника летняя")
        # Проверяем ремонтантную ВТОРОЙ
        elif "ремонтант" in text or ("нсд" in text or "nsd" in text) or "нейтральн" in text:
            # НСД = нейтрального светового дня = ремонтантная
            candidates.add("клубника ремонтантная")
        else:
            # Без уточнения - добавляем общую категорию
            candidates.add("клубника общая")

    # Малина
    if "малин" in text:
        # ИЗМЕНЕНО: Проверяем летнюю/обычную ПЕРВОЙ (выше приоритет)
        if "летн" in text or "традицион" in text or "обычн" in text:
            candidates.add("малина летняя")
        # Проверяем ремонтантную ВТОРОЙ
        elif "ремонтант" in text or ("нсд" in text or "nsd" in text):
            candidates.add("малина ремонтантная")
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

    # Ежевика (с учетом возможных опечаток)
    if "ежевик" in text or "ежив" in text or "ежов" in text:
        candidates.add("ежевика")

    # Особый случай: НСД/ремонтантная/летняя БЕЗ упоминания культуры
    has_culture_word = any(word in text for word in ["клубник", "земляник", "малин", "смородин", "голубик", "жимолост", "крыжовник", "ежевик", "ежив", "ежов"])
    if not has_culture_word:
        if any(word in text for word in ["ремонтант", "нсд", "nsd", "летн", "обычн", "традицион"]):
            # Если есть типовые слова, но нет культуры - общая информация
            return "общая информация"

    # Несколько культур → общая информация (общий совет сразу по нескольким)
    if len(candidates) > 1:
        print(f"[_keyword_fallback] multiple candidates={candidates!r} -> 'общая информация'")
        return "общая информация"

    # Одна культура
    if len(candidates) == 1:
        return next(iter(candidates))

    # Нет конкретных культур, но явно про ягоды/кустарники → общая информация
    # ВАЖНО: проверяем только если НЕ нашли культуру выше
    if len(candidates) == 0:
        if "ягод" in text or "кустарник" in text or "куст" in text:
            return "общая информация"

    # Вообще не про ягоды
    return "не определено"


async def detect_culture_name(text: str) -> Tuple[str, float, int]:
    """
    Определяет КУЛЬТУРУ по тексту вопроса с помощью LLM.

    Контракт:
        - возвращает кортеж (culture, cost_usd, tokens):
          - culture: КРАТКОЕ название культуры (в нормальном виде),
            например: "малина", "голубика", "клубника садовая";
            либо "общая информация" — если вопрос общий для нескольких культур;
            либо "не определено" — если понять, про что речь, нельзя.
          - cost_usd: стоимость LLM вызова в USD
          - tokens: общее количество токенов

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
        "  3) КРИТИЧЕСКИ ВАЖНО: Для клубники и малины различай типы:\n"
        "     - 'обычная', 'летняя', 'традиционная', 'июньская' → летняя (это ОДНО И ТО ЖЕ!)\n"
        "       Примеры: 'клубника обычная' = 'клубника летняя', 'малина обычная' = 'малина летняя'\n"
        "     - 'ремонтантная', 'НСД', 'NSD', 'нейтрального дня' → ремонтантная\n"
        "     - Если только 'ремонтантная'/'летняя'/'обычная' БЕЗ культуры → 'общая информация'\n"
        "     - Если тип НЕ указан явно → 'клубника общая' или 'малина общая'\n"
        "  4) Если вопрос даёт общие рекомендации сразу по нескольким культурам\n"
        "     или не привязан к одной — выбери: общая информация.\n"
        "  5) Если вопрос вообще не про ягодные культуры — выбери: не определено.\n"
        "  6) СОРТА:\n"
        "     - Альбион, Сан Андреас, Монтерей → клубника ремонтантная\n"
        "     - Полка, Вима Занта, Хоней → клубника летняя\n"
        "     - Виктория (устаревшее название) → клубника общая\n"
        "     - Химбо Топ, Полька, Джоан Джей → малина ремонтантная\n"
        "     - Патриция, Таруса, Гусар → малина летняя\n"
        "  7) ТЕХНИЧЕСКИЕ ТЕРМИНЫ:\n"
        "     - Фриго, усы → клубника\n"
        "     - Корневая поросль → малина\n"
        "     - Вересковые (в контексте ягод) → голубика\n"
        "  8) КРИТИЧЕСКИ ВАЖНО:\n"
        "     - 'кустики СМОРОДИНЫ' → смородина (НЕ 'общая информация'!)\n"
        "     - 'кустики ЖИМОЛОСТИ' → жимолость (НЕ 'общая информация'!)\n"
        "     - 'листья МАЛИНЫ' → малина (НЕ 'общая информация'!)\n"
        "     Если культура явно названа, игнорируй общие слова ('кустики', 'ягоды', 'растения')\n"
        "     и возвращай КОНКРЕТНУЮ культуру!\n"
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
        response = await create_chat_completion_with_usage(
            messages=messages,
            model=settings.openai_model,
            temperature=0.0,
        )

        # Рассчитываем стоимость
        cost_usd = calculate_cost(
            model=response["model"],
            prompt_tokens=response["prompt_tokens"],
            completion_tokens=response["completion_tokens"],
        )
        tokens = response["total_tokens"]

        llm_answer = response.get("content", "")
        raw = (llm_answer or "").strip()
        if not raw:
            print(f"[detect_culture_name][EMPTY] text={raw_text!r} -> raw=''")
            fallback_culture = _keyword_fallback(raw_text)
            print(
                f"[detect_culture_name][EMPTY_FALLBACK] text={raw_text!r} "
                f"-> keyword_fallback={fallback_culture!r}"
            )
            return fallback_culture, cost_usd, tokens

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
            # ВАЖНО: если keyword нашел конкретную культуру (не спец-значение), используем её
            if keyword_culture not in ("не определено", "общая информация"):
                print(
                    f"[detect_culture_name][KEYWORD_OVERRIDE] text={raw_text!r} "
                    f"llm={normalized!r} -> keyword={keyword_culture!r}"
                )
                return keyword_culture, cost_usd, tokens
            return normalized, cost_usd, tokens

        # 2. Маппинг частых вариантов к нормальным названиям
        mapping: Dict[str, str] = {
            # Клубника ремонтантная (включает НСД - нейтрального дня)
            "клубника ремонтантная": "клубника ремонтантная",
            "клубника нсд": "клубника ремонтантная",
            "клубника nsd": "клубника ремонтантная",
            "клубника нейтрального дня": "клубника ремонтантная",
            "клубника нейтрального света": "клубника ремонтантная",
            "земляника ремонтантная": "клубника ремонтантная",
            "земляника нсд": "клубника ремонтантная",
            "земляника нейтрального дня": "клубника ремонтантная",
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
            "виктория": "клубника общая",

            # Малина ремонтантная (приоритет выше)
            "малина ремонтантная": "малина ремонтантная",
            "малина нсд": "малина ремонтантная",
            "малина nsd": "малина ремонтантная",
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

            # Ежевика
            "ежевика": "ежевика",

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

        # 3. Попробуем keyword_fallback — ТОЛЬКО если маппинг не дал конкретной культуры
        # ИЗМЕНЕНО: не переопределяем culture, если она уже специфична
        if culture in ("общая информация", "не определено"):
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
            return final, cost_usd, tokens

        # 5. Если мы сюда дошли, culture либо пустая/странная, либо спец-значение.
        #    В этом случае уже делегируем keyword_fallback окончательно.
        final_fallback = _keyword_fallback(raw_text)
        print(
            f"[detect_culture_name][FINAL_FALLBACK] text={raw_text!r} "
            f"-> culture={culture!r} -> final={final_fallback!r}"
        )
        return final_fallback, cost_usd, tokens

    except Exception as e:
        print(f"[detect_culture_name][ERROR] {e} | text={raw_text!r}")
        fallback_culture = _keyword_fallback(raw_text)
        print(
            f"[detect_culture_name][ERROR_FALLBACK] text={raw_text!r} "
            f"-> keyword_fallback={fallback_culture!r}"
        )
        return fallback_culture, 0.0, 0


def _keyword_category_fallback(raw_text: str) -> str:
    """
    Определяет категорию консультации по ключевым словам.

    Returns:
        Название категории или "не определена"
    """
    if not raw_text:
        return "не определена"

    text = raw_text.lower()

    # Питание растений
    nutrition_keywords = [
        "подкорм", "питан", "удобрен", "азот", "калий", "фосфор",
        "npk", "макроэлемент", "микроэлемент", "комплексн",
        "минеральн", "органик", "компост", "навоз", "перегной",
        "подкормить", "кормить", "кормл", "внос"
    ]
    if any(kw in text for kw in nutrition_keywords):
        return "питание растений"

    # Защита растений
    protection_keywords = [
        "вредител", "болез", "тля", "паутин", "клещ", "долгоносик",
        "гриб", "пятн", "мучнист", "серая гниль", "фитофтор",
        "обработ", "опрыск", "защит", "борьб", "лечен", "инсектицид",
        "фунгицид", "препарат"
    ]
    if any(kw in text for kw in protection_keywords):
        return "защита растений"

    # Посадка и уход
    planting_keywords = [
        "посад", "пересад", "саж", "высад", "полив", "мульч",
        "обрез", "формиров", "укрыт", "зим", "уход", "агротехник",
        "схем", "расстоян", "глубин", "когда сажать", "как сажать",
        "размножен", "черенк", "делен"
    ]
    if any(kw in text for kw in planting_keywords):
        return "посадка и уход"

    # Улучшение почвы
    soil_keywords = [
        "почв", "грунт", "кислот", "ph", "известков", "раскисл",
        "структур почв", "дренаж", "песок", "торф", "глин",
        "плодородие", "улучш", "подготовк почв"
    ]
    if any(kw in text for kw in soil_keywords):
        return "улучшение почвы"

    # Подбор сорта
    variety_keywords = [
        "сорт", "какой лучше", "что выбрать", "порекоменду",
        "посовету", "для региона", "для климата", "морозостойк",
        "зимостойк", "урожайн", "вкус"
    ]
    if any(kw in text for kw in variety_keywords):
        return "подбор сорта"

    return "не определена"


async def detect_category_and_culture(text: str) -> tuple[str, str, float, int]:
    """
    Определяет КАТЕГОРИЮ консультации И КУЛЬТУРУ из текста вопроса.

    Использует единый вызов LLM для определения обоих параметров,
    с fallback на keyword-based классификацию.

    Args:
        text: Текст вопроса пользователя

    Returns:
        tuple[category, culture, cost_usd, tokens] where:
        - category: "питание растений", "посадка и уход", "защита растений",
                   "улучшение почвы", "подбор сорта", "другая тема" или "не определена"
        - culture: "клубника летняя", "малина общая", "не определено", etc.
        - cost_usd: стоимость LLM вызова в USD
        - tokens: общее количество токенов
    """
    import json

    raw_text = text or ""

    # Категории для промпта
    categories = [
        "питание растений",
        "посадка и уход",
        "защита растений",
        "улучшение почвы",
        "подбор сорта",
        "другая тема"
    ]

    # Культуры из БД
    db_cultures: List[str] = await kb_get_distinct_subcategories(limit=200)
    specials = ["общая информация", "не определено"]

    if db_cultures:
        cultures_for_prompt = [*db_cultures, *specials]
    else:
        cultures_for_prompt = specials

    categories_str = "\n".join(f"   - {cat}" for cat in categories)
    cultures_str = "\n".join(f"   - {cult}" for cult in cultures_for_prompt[:30])  # Первые 30 для экономии токенов

    system_prompt = (
        "Ты агроном-консультант и классификатор вопросов по ягодным культурам.\n"
        "Твоя задача: определить КАТЕГОРИЮ консультации И КУЛЬТУРУ из вопроса пользователя.\n\n"
        "КАТЕГОРИИ КОНСУЛЬТАЦИЙ:\n"
        f"{categories_str}\n\n"
        "КУЛЬТУРЫ (примеры):\n"
        f"{cultures_str}\n"
        "   - клубника общая / клубника летняя / клубника ремонтантная\n"
        "   - малина общая / малина летняя / малина ремонтантная\n"
        "   - голубика, ежевика, смородина, жимолость, крыжовник\n"
        "   - общая информация (если про несколько культур)\n"
        "   - не определено (если культура неясна)\n\n"
        "ПРАВИЛА КАТЕГОРИЙ:\n"
        "1. 'питание растений' - вопросы про удобрения, подкормки, питание\n"
        "2. 'посадка и уход' - посадка, пересадка, полив, обрезка, мульчирование\n"
        "3. 'защита растений' - болезни, вредители, обработки, лечение\n"
        "4. 'улучшение почвы' - pH, кислотность, структура почвы, дренаж\n"
        "5. 'подбор сорта' - какой сорт выбрать, рекомендации по сортам\n"
        "6. 'другая тема' - всё остальное\n\n"
        "ПРАВИЛА КУЛЬТУР:\n"
        "1. Для клубники и малины различай типы:\n"
        "   - 'летняя'/'обычная'/'традиционная'/'июньская' → летняя\n"
        "   - 'ремонтантная'/'НСД'/'NSD' → ремонтантная\n"
        "   - Если тип не указан → 'клубника общая' или 'малина общая'\n"
        "2. Сорта:\n"
        "   - Альбион, Сан Андреас → клубника ремонтантная\n"
        "   - Полка, Хоней → клубника летняя\n"
        "   - Химбо Топ, Полька → малина ремонтантная\n"
        "   - Патриция, Гусар → малина летняя\n"
        "3. ВАЖНО: Учитывай возможные опечатки в названиях культур:\n"
        "   - 'еживику', 'ежовика' → ежевика\n"
        "   - 'малену', 'малену' → малина\n"
        "   - 'клубнику', 'клупнику' → клубника\n"
        "   Если похоже на название культуры, исправь опечатку и верни правильное название.\n"
        "4. Если культура явно названа (даже с опечаткой) → возвращай конкретную культуру\n"
        "5. Если несколько культур → 'общая информация'\n"
        "6. Если культура неясна → 'не определено'\n\n"
        "ФОРМАТ ОТВЕТА:\n"
        "Верни ТОЛЬКО JSON в формате:\n"
        '{"category": "название категории", "culture": "название культуры"}\n\n'
        "БЕЗ комментариев, БЕЗ дополнительного текста!"
    )

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": f"Вопрос: {raw_text}",
        },
    ]

    try:
        response = await create_chat_completion_with_usage(
            messages=messages,
            model=settings.openai_model,
            temperature=0.0,
        )

        # Рассчитываем стоимость
        cost_usd = calculate_cost(
            model=response["model"],
            prompt_tokens=response["prompt_tokens"],
            completion_tokens=response["completion_tokens"],
        )
        tokens = response["total_tokens"]

        raw = (response.get("content", "") or "").strip()
        if not raw:
            print(f"[detect_category_and_culture][EMPTY] text={raw_text!r}")
            category = _keyword_category_fallback(raw_text)
            culture = _keyword_fallback(raw_text)
            print(
                f"[detect_category_and_culture][FALLBACK] "
                f"category={category!r}, culture={culture!r}"
            )
            return (category, culture, cost_usd, tokens)

        # Пытаемся распарсить JSON
        try:
            # Очищаем от markdown блоков если есть
            json_str = raw
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()

            data = json.loads(json_str)
            category_raw = data.get("category", "").strip().lower()
            culture_raw = data.get("culture", "").strip().lower()

            # Нормализуем категорию
            category_mapping = {
                "питание растений": "питание растений",
                "посадка и уход": "посадка и уход",
                "защита растений": "защита растений",
                "улучшение почвы": "улучшение почвы",
                "подбор сорта": "подбор сорта",
                "подбор сортов": "подбор сорта",
                "другая тема": "другая тема",
            }

            category = category_mapping.get(category_raw, "не определена")

            # Нормализуем культуру (используем существующую логику)
            culture = _cleanup_llm_answer(culture_raw)

            # Применяем маппинг культур (копируем из detect_culture_name)
            culture_mapping: Dict[str, str] = {
                "клубника ремонтантная": "клубника ремонтантная",
                "клубника летняя": "клубника летняя",
                "клубника обычная": "клубника летняя",
                "клубника общая": "клубника общая",
                "клубника": "клубника общая",
                "земляника": "клубника общая",
                "малина ремонтантная": "малина ремонтантная",
                "малина летняя": "малина летняя",
                "малина обычная": "малина летняя",
                "малина общая": "малина общая",
                "малина": "малина общая",
                "смородина": "смородина",
                "голубика": "голубика",
                "жимолость": "жимолость",
                "крыжовник": "крыжовник",
                "ежевика": "ежевика",
                "общая информация": "общая информация",
                "не определено": "не определено",
            }

            for key, value in culture_mapping.items():
                if key in culture:
                    culture = value
                    break

            # Проверяем keyword fallback для валидации или override
            keyword_culture = _keyword_fallback(raw_text)

            # Если culture не нашлась в маппинге или неопределена, используем keyword
            if culture in ("общая информация", "не определено", ""):
                if keyword_culture not in ("не определено", "общая информация"):
                    print(f"[detect_category_and_culture][KEYWORD_OVERRIDE_VAGUE] "
                          f"LLM={culture!r} -> keyword={keyword_culture!r}")
                    culture = keyword_culture
            # Если keyword нашел КОНКРЕТНУЮ культуру, а LLM вернул другую - предпочитаем keyword
            elif keyword_culture not in ("не определено", "общая информация", culture):
                print(f"[detect_category_and_culture][KEYWORD_CORRECTION] "
                      f"LLM={culture!r} -> keyword={keyword_culture!r} (возможно опечатка)")
                culture = keyword_culture

            print(
                f"[detect_category_and_culture][SUCCESS] text={raw_text!r} "
                f"-> category={category!r}, culture={culture!r}"
            )

            return (category, culture, cost_usd, tokens)

        except json.JSONDecodeError as je:
            print(f"[detect_category_and_culture][JSON_ERROR] {je} | raw={raw!r}")
            # Fallback на keyword detection
            category = _keyword_category_fallback(raw_text)
            culture = _keyword_fallback(raw_text)
            print(
                f"[detect_category_and_culture][KEYWORD_FALLBACK] "
                f"category={category!r}, culture={culture!r}"
            )
            return (category, culture, cost_usd, tokens)

    except Exception as e:
        print(f"[detect_category_and_culture][ERROR] {e} | text={raw_text!r}")
        category = _keyword_category_fallback(raw_text)
        culture = _keyword_fallback(raw_text)
        print(
            f"[detect_category_and_culture][ERROR_FALLBACK] "
            f"category={category!r}, culture={culture!r}"
        )
        return (category, culture, 0.0, 0)


async def compare_topics_for_change(
    old_category: str,
    old_culture: str,
    new_question: str,
    context_messages: str = ""
) -> tuple[str, float, int]:
    """
    Определяет, является ли новый вопрос сменой темы относительно текущей.

    Args:
        old_category: Текущая категория (IGNORED - category is fixed for follow-ups)
        old_culture: Текущая культура (например, "клубника летняя")
        new_question: Новый вопрос пользователя
        context_messages: Контекст предыдущих сообщений (опционально)

    Returns:
        tuple[decision, cost_usd, tokens] where:
        - decision: "same_topic" | "clear_change" | "unclear"
        - cost_usd: стоимость LLM вызова в USD
        - tokens: общее количество токенов
    """
    system_prompt = f"""Ты - классификатор вопросов в консультационном боте по ягодным культурам.

ТЕКУЩАЯ КУЛЬТУРА: {old_culture}

КРИТИЧЕСКИ ВАЖНО:
- Категория консультации ФИКСИРОВАНА и НЕ МЕНЯЕТСЯ для уточняющих вопросов
- ПОЛНОСТЬЮ ИГНОРИРУЙ любые изменения категории (питание→защита, посадка→уход и т.д.)
- Определяй смену темы ТОЛЬКО по изменению КУЛЬТУРЫ (растения)

ТВОЯ ЗАДАЧА: Определить, изменилась ли КУЛЬТУРА (растение) в новом вопросе:

1. SAME_TOPIC (та же культура) - если:
   - Вопрос про ту же культуру: {old_culture}
   - Вопрос уточняет детали или спрашивает про другой аспект
   - Культура не упомянута явно (значит продолжаем про {old_culture})
   - Используются слова "а если", "а как", "а когда", "еще хочу уточнить", "расскажи про..."
   - ПРИМЕРЫ для {old_culture}:
     * "А про вредителей расскажи" → SAME_TOPIC (культура не меняется!)
     * "А про почву что скажешь?" → SAME_TOPIC (культура не меняется!)
     * "Расскажи про уход" → SAME_TOPIC (культура не меняется!)
     * "А как с болезнями?" → SAME_TOPIC (культура не меняется!)

2. CLEAR_CHANGE (смена культуры) - ТОЛЬКО если:
   - КУЛЬТУРА явно сменилась (крыжовник → малина, клубника → смородина)
   - Вопрос начинается с "Теперь про малину", "А теперь хочу спросить про клубнику"
   - ЯВНОЕ упоминание ДРУГОЙ культуры в вопросе
   - ПРИМЕРЫ:
     * "А теперь про малину расскажи" → CLEAR_CHANGE
     * "Теперь хочу спросить про клубнику" → CLEAR_CHANGE

3. UNCLEAR (неопределенно) - если:
   - Вопрос слишком короткий или общий
   - Не можешь точно определить, меняется ли культура
   - В СЛУЧАЕ СОМНЕНИЯ - ВСЕГДА возвращай UNCLEAR

ВАЖНЫЕ ПРИМЕРЫ:
- Текущая культура: крыжовник
  * "А про вредителей" → SAME_TOPIC (только уточнение аспекта, культура та же)
  * "Расскажи про почву" → SAME_TOPIC (только уточнение аспекта, культура та же)
  * "А теперь про малину" → CLEAR_CHANGE (явная смена культуры)

ФОРМАТ ОТВЕТА: Верни ТОЛЬКО одно слово: same_topic, clear_change или unclear
БЕЗ пояснений, БЕЗ кавычек, БЕЗ точки!"""

    user_prompt = f"НОВЫЙ ВОПРОС ПОЛЬЗОВАТЕЛЯ:\n{new_question}"
    if context_messages:
        user_prompt += f"\n\nКОНТЕКСТ ПРЕДЫДУЩИХ СООБЩЕНИЙ:\n{context_messages}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = await create_chat_completion_with_usage(
            messages=messages,
            model=settings.openai_model,
            temperature=0.0,
        )

        # Рассчитываем стоимость
        cost_usd = calculate_cost(
            model=response["model"],
            prompt_tokens=response["prompt_tokens"],
            completion_tokens=response["completion_tokens"],
        )
        tokens = response["total_tokens"]

        result = (response.get("content", "") or "").strip().lower()

        # Нормализация ответа
        if "same" in result or result == "same_topic":
            decision = "same_topic"
        elif "clear" in result or result == "clear_change":
            decision = "clear_change"
        else:
            decision = "unclear"

        print(
            f"[compare_topics_for_change] "
            f"old=({old_category!r}, {old_culture!r}), "
            f"new={new_question[:50]!r}... -> {decision!r}"
        )

        return decision, cost_usd, tokens

    except Exception as e:
        print(f"[compare_topics_for_change][ERROR] {e}")
        # При ошибке возвращаем "unclear" - остаемся на той же теме
        return "unclear", 0.0, 0
