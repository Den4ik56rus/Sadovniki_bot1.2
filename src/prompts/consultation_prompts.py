# src/prompts/consultation_prompts.py

"""
Оркестратор системных промптов для консультаций.

Собирает финальный промпт из:
- Базовой части (роль, scope, формат) — загружается из БД или fallback на Python
- Категорийной части (специфика: питание, болезни, посадка и т.п.) — загружается из БД или fallback на Python
- Промт-документа (если есть для культуры + категории)
- Контекста из базы знаний (RAG)
- Словаря терминологии
"""

import logging
from typing import List, Dict, Any, Tuple, Optional

from src.prompts.base_prompt import (
    get_base_system_prompt,
    get_base_system_prompt_minimal,
    build_base_prompt_from_sections,
    _section_role,
    _section_scope,
    _section_defaults,
    _section_culture_rules_with_context,
    _section_culture_rules_undefined,
    _section_kb_usage,
    _section_response_format,
    _section_work_context,
    _section_answer_logic,
    _section_tone,
    _section_safety,
)
from src.prompts.category_prompts import (
    get_nutrition_category_prompt,
    get_planting_care_category_prompt,
    get_pruning_category_prompt,
    get_diseases_pests_category_prompt,
    get_soil_improvement_category_prompt,
    get_variety_selection_category_prompt,
    get_prompt_group_for_culture,
    get_fertilizers_reference,
    get_pesticides_reference,
)
from src.prompts.category_prompts._fertilizers_reference import (
    get_varieties_reference,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Async DB Loading Functions
# ============================================================================

async def _get_base_prompt_from_db(
    default_location: str,
    default_growing_type: str,
    include_response_format: bool = True,
    culture_is_known: bool = True,
) -> Optional[str]:
    """
    Загружает базовый промпт из БД.

    Логика:
    - Загружаем ВСЕ секции (включая отключённые) чтобы знать что БД доступна
    - В итоговый промпт включаем только is_enabled=True секции
    - Если БД недоступна → None (fallback на Python)
    - Если БД доступна но все секции отключены → пустая строка (НЕ fallback)

    Args:
        default_location: Местоположение по умолчанию
        default_growing_type: Тип выращивания по умолчанию
        include_response_format: Включать ли секцию формата ответа

    Returns:
        Собранный базовый промпт, пустая строка если всё отключено, или None если БД недоступна
    """
    try:
        from src.services.db.prompt_repo import get_base_sections

        # Загружаем ВСЕ секции чтобы проверить что БД работает
        all_sections = await get_base_sections(is_enabled_only=False)
        if not all_sections:
            # БД пуста или недоступна — fallback на Python
            logger.debug("[_get_base_prompt_from_db] No sections in DB, using Python fallback")
            return None

        # Теперь загружаем только включённые
        enabled_sections = await get_base_sections(is_enabled_only=True)

        # Построим словарь для быстрого доступа к секциям по slug
        sections_by_slug = {s.get("slug", ""): s.get("content", "") for s in enabled_sections}

        section_contents = []
        for section in enabled_sections:
            slug = section.get("slug", "")
            content = section.get("content", "")

            # Пропускаем response_format если не нужен
            if slug == "response_format" and not include_response_format:
                continue

            # Условная логика для culture_rules
            if slug == "culture_rules":
                # Если есть новые варианты — используем их вместо старого culture_rules
                if culture_is_known and "culture_rules_known" in sections_by_slug:
                    content = sections_by_slug["culture_rules_known"]
                elif not culture_is_known and "culture_rules_undefined" in sections_by_slug:
                    content = sections_by_slug["culture_rules_undefined"]
                # Если новых нет — используем старый culture_rules как есть
            elif slug in ("culture_rules_known", "culture_rules_undefined"):
                # Пропускаем — уже обработаны через culture_rules
                continue

            # Подставляем переменные в defaults
            if slug == "defaults":
                content = content.replace("{default_location}", default_location)
                content = content.replace("{default_growing_type}", default_growing_type)

            section_contents.append(content)

        # Возвращаем результат (может быть пустым если всё отключено)
        result = "\n\n".join(section_contents)
        logger.info(f"[_get_base_prompt_from_db] Loaded {len(enabled_sections)} enabled sections from DB (total: {len(all_sections)})")
        return result  # Может быть "" если всё отключено — это ОК

    except Exception as e:
        logger.warning(f"[_get_base_prompt_from_db] Error loading from DB: {e}")
        return None


async def _get_category_prompt_from_db(
    consultation_category: str,
    culture: str,
    default_location: str,
    default_growing_type: str,
) -> Optional[Tuple[str, bool, Optional[int]]]:
    """
    Загружает категорийный промпт из БД.

    Логика:
    - Если категория отключена (is_enabled=False) → возвращаем ("", False, None) — пустой промпт
    - Если категория не найдена в БД → возвращаем None (fallback на Python)
    - Если категория включена → возвращаем её содержимое

    Args:
        consultation_category: Категория консультации
        culture: Название культуры
        default_location: Местоположение по умолчанию
        default_growing_type: Тип выращивания по умолчанию

    Returns:
        Tuple[str, bool, Optional[int]] (промпт, use_minimal_base, prompt_id) или None если БД недоступна
    """
    try:
        from src.services.db.prompt_repo import get_category_prompt, get_fallback_prompt, check_category_exists

        # Маппинг категорий на subgroup slugs
        category_to_subgroup = {
            "питание растений": "nutrition",
            "посадка и уход": "planting_care",
            "обрезка": "pruning",
            "защита растений": "diseases_pests",
            "болезни и вредители": "diseases_pests",
            "улучшение почвы": "soil_improvement",
            "подбор сортов": "variety_selection",
            "подбор сорта": "variety_selection",
        }

        normalized_category = consultation_category.lower().strip()
        subgroup_slug = category_to_subgroup.get(normalized_category)

        if not subgroup_slug:
            # Неизвестная категория — пробуем fallback
            fallback = await get_fallback_prompt()
            if fallback and fallback.get("content"):
                content = fallback["content"].replace("{culture}", culture)
                return (content, fallback.get("use_minimal_base", False), None)
            return None

        # Для питания нужно определить группу культуры
        culture_group = None
        if subgroup_slug == "nutrition":
            group_key = get_prompt_group_for_culture("питание растений", culture)
            # Маппинг group_key на slug в БД
            group_to_slug = {
                "group_strawberry": "strawberry",
                "group_raspberry": "raspberry",
                "group_b_berries": "b_berries",
            }
            culture_group = group_to_slug.get(group_key, "default")

        # Загружаем из БД (функция уже проверяет is_enabled=TRUE)
        prompt_data = await get_category_prompt(subgroup_slug, culture_group)

        if not prompt_data or not prompt_data.get("content"):
            # Проверяем существует ли категория в БД (даже если отключена)
            exists = await check_category_exists(subgroup_slug, culture_group)
            if exists:
                # Категория есть но отключена → возвращаем пустой промпт
                logger.info(f"[_get_category_prompt_from_db] Category {subgroup_slug}/{culture_group or 'main'} is disabled in DB")
                return ("", False, None)
            # Категории нет в БД → fallback на Python
            return None

        content = prompt_data["content"]
        use_minimal_base = prompt_data.get("use_minimal_base", False)
        prompt_id = prompt_data.get("id")

        # Подставляем переменные
        content = content.replace("{culture}", culture)
        content = content.replace("{default_location}", default_location)
        content = content.replace("{default_growing_type}", default_growing_type)

        logger.info(f"[_get_category_prompt_from_db] Loaded {subgroup_slug}/{culture_group or 'main'} from DB")
        return (content, use_minimal_base, prompt_id)

    except Exception as e:
        logger.warning(f"[_get_category_prompt_from_db] Error loading from DB: {e}")
        return None


def build_kb_context_snippet(snippets: List[Dict[str, Any]], qa_found: bool) -> str:
    """
    Формирует текстовый блок с фрагментами из базы знаний для вставки в системный промт.

    НОВОЕ ПОВЕДЕНИЕ:
        - Если qa_found=True → показываем ТОЛЬКО уровень 1 (Q&A)
        - Если qa_found=False → показываем уровни 2 и 3 (документы)

    Обрабатывает три уровня приоритета:
    - УРОВЕНЬ 1: Q&A пары из knowledge_base (высший приоритет)
    - УРОВЕНЬ 2: Приоритетные документы (средний приоритет)
    - УРОВЕНЬ 3: Общие документы (низкий приоритет)
    """
    # Если подходящих фрагментов нет — возвращаем пустую строку
    if not snippets:
        return ""

    # Группируем фрагменты по уровням приоритета
    level1 = [s for s in snippets if s.get("priority_level") == 1]
    level2 = [s for s in snippets if s.get("priority_level") == 2]
    level3 = [s for s in snippets if s.get("priority_level") == 3]

    lines: List[str] = []

    # Логирование полных фрагментов для отладки
    print(f"\n[KB_CONTEXT] Формируем контекст из {len(snippets)} фрагментов (qa_found={qa_found})")

    # УРОВЕНЬ 1: Q&A пары (если найдены)
    if level1:
        lines.append("📌 УРОВЕНЬ 1 - ПРОВЕРЕННЫЕ Q&A ОТВЕТЫ (ВЫСШИЙ ПРИОРИТЕТ):")
        lines.append("")
        lines.append("ИНСТРУКЦИЯ:")
        lines.append("Эти ответы прошли проверку экспертом. Используй их ДОСЛОВНО, адаптируя под контекст вопроса пользователя.")
        lines.append("Если найдено несколько Q&A — объедини их в один логичный ответ.")
        lines.append("")

        for i, snip in enumerate(level1, start=1):
            text = snip.get("content") or snip.get("answer", "")
            lines.append(f"{i}) {text}")
            lines.append("")  # Пустая строка между Q&A
            print(f"[KB_CONTEXT][УРОВЕНЬ 1][#{i}] Q&A загружен ({len(text)} символов)")

        # КРИТИЧНО: если найдены Q&A, возвращаем ТОЛЬКО их
        result = "\n".join(lines)
        print(f"[KB_CONTEXT] Итоговый контекст (ТОЛЬКО Q&A): {len(result)} символов\n")
        return result

    # УРОВНИ 2 и 3: Документы (только если Q&A не найдены)
    if level2:
        lines.append("📘 УРОВЕНЬ 2 - ПРИОРИТЕТНЫЕ ДОКУМЕНТЫ:")
        # TODO: Временно отключено — раскомментировать когда нужно включить универсальность
        # lines.append("")
        # lines.append("⚠️ ВАЖНО: Эти документы содержат УНИВЕРСАЛЬНЫЕ агрономические принципы.")
        # lines.append("Даже если в тексте упоминается конкретная культура (например, 'клубника'),")
        # lines.append("АДАПТИРУЙ информацию для культуры из текущей консультации.")
        # lines.append("Принципы питания, защиты и ухода применимы ко всем ягодным культурам с учётом их особенностей.")
        # lines.append("")
        for i, snip in enumerate(level2, start=1):
            text = snip.get("content", "")
            lines.append(f"  {i}) {text}")
            print(f"[KB_CONTEXT][УРОВЕНЬ 2][#{i}] Документ загружен ({len(text)} символов)")
        lines.append("")  # Пустая строка между уровнями

    if level3:
        lines.append("📗 УРОВЕНЬ 3 - ОБЩАЯ БАЗА ЗНАНИЙ:")
        for i, snip in enumerate(level3, start=1):
            text = snip.get("content", "")
            lines.append(f"  {i}) {text}")
            print(f"[KB_CONTEXT][УРОВЕНЬ 3][#{i}] Документ загружен ({len(text)} символов)")

    if lines:
        lines.append("")
        lines.append("ИНСТРУКЦИЯ:")
        lines.append("Синтезируй ответ из приоритетных документов (УРОВЕНЬ 2) и общей базы (УРОВЕНЬ 3).")
        lines.append("При конфликте информации отдавай приоритет УРОВНЮ 2.")

    # Склеиваем все строки
    result = "\n".join(lines)
    print(f"[KB_CONTEXT] Итоговый контекст (документы): {len(result)} символов\n")
    return result


async def build_terminology_section() -> str:
    """
    Формирует секцию со словарём терминологии из БД.
    """
    from src.services.db.terminology_repo import get_all_terminology

    try:
        terms = await get_all_terminology()
        if not terms:
            return ""

        lines = ["Словарь терминов (используй эти формулировки):"]
        for term in terms:
            lines.append(f"- Вместо '{term['term']}' используй '{term['preferred_phrase']}'")

        return "\n".join(lines) + "\n"
    except Exception as e:
        print(f"[build_terminology_section] Error: {e}")
        return ""


async def get_prompt_document_section(culture: str, consultation_category: str) -> str:
    """
    Получает текст промт-документа для консультации.

    Порядок поиска:
    1. Новая система промптов (таблица prompts, группа prompt_docs)
    2. Fallback на старую систему (таблица prompt_documents)

    Args:
        culture: Культура (например, "клубника общая", "малина ремонтантная")
        consultation_category: Категория консультации (например, "защита растений")

    Returns:
        Отформатированная секция с промт-документом или пустая строка
    """
    if not culture or not consultation_category:
        return ""

    # Пропускаем неопределённые культуры
    if culture.lower() in ("не определено", "общая информация"):
        return ""

    content = None

    # 1. Пробуем новую систему промптов
    try:
        from src.services.db.prompt_repo import get_prompt_document_content, check_prompt_doc_exists

        content = await get_prompt_document_content(culture, consultation_category)

        if content:
            logger.info(f"[prompt_doc] Loaded from prompts table for {culture} / {consultation_category} ({len(content)} chars)")
        elif await check_prompt_doc_exists(culture, consultation_category):
            # Документ есть но отключён — НЕ делаем fallback
            logger.info(f"[prompt_doc] Document exists but disabled for {culture} / {consultation_category}")
            return ""

    except Exception as e:
        logger.warning(f"[get_prompt_document_section] Error loading from prompts: {e}")

    # 2. Fallback на старую систему (prompt_documents)
    if not content:
        try:
            from src.services.db.prompt_document_repo import get_prompt_document_content_for_consultation

            content = await get_prompt_document_content_for_consultation(culture, consultation_category)

            if content:
                logger.info(f"[prompt_doc] Loaded from prompt_documents (fallback) for {culture} / {consultation_category} ({len(content)} chars)")

        except Exception as e:
            logger.error(f"[get_prompt_document_section] Error loading from prompt_documents: {e}")

    # Форматируем результат
    if content:
        return f"""

📋 СПЕЦИАЛИЗИРОВАННЫЕ ИНСТРУКЦИИ ПО ТЕМЕ:

{content}

---
"""
    return ""


async def _load_reference_section(consultation_category: str) -> str:
    """
    Загружает справочник (удобрения/СЗР/сорта) для вставки как отдельную секцию.

    Справочник загружается из БД, fallback на Python.
    Используется ТОЛЬКО когда категорийный промпт загружен из БД
    (в Python-версии справочник уже встроен через f-string).
    """
    CATEGORY_REFERENCES = {
        "питание растений": ("fertilizers", get_fertilizers_reference),
        "защита растений": ("pesticides", get_pesticides_reference),
        "болезни и вредители": ("pesticides", get_pesticides_reference),
        "подбор сортов": ("varieties", get_varieties_reference),
        "подбор сорта": ("varieties", get_varieties_reference),
    }

    normalized = consultation_category.lower().strip()
    ref_info = CATEGORY_REFERENCES.get(normalized)
    if not ref_info:
        return ""

    ref_slug, ref_python_func = ref_info
    ref_content = None

    # Пробуем из БД
    try:
        from src.services.db.prompt_repo import get_reference_content
        db_result = await get_reference_content(ref_slug)
        if db_result:
            ref_content = db_result["content"]
    except Exception as e:
        logger.warning(f"[_load_reference_section] DB error: {e}")

    # Fallback на Python
    if not ref_content:
        ref_content = ref_python_func()

    if ref_content:
        return f"""
📙 СПРАВОЧНИК (дополнительные рекомендации по препаратам/удобрениям/сортам):

ИНСТРУКЦИЯ: Используй справочник как ДОПОЛНЕНИЕ к промт-документу выше.
Сначала бери рекомендации из промт-документа, потом дополняй из справочника.

{ref_content.strip()}
"""
    return ""


def _get_fallback_prompt_python(culture: str) -> Tuple[str, bool]:
    """
    Возвращает fallback-промпт для вопросов с неопределённой темой/категорией.
    Python-версия (используется как fallback если БД недоступна).

    Используется когда тема вопроса не соответствует ни одной из основных категорий.
    """
    prompt = f"""
🟦 **УНИВЕРСАЛЬНЫЙ ШАБЛОН ДЛЯ ОТВЕТОВ НА ИНЫЕ ТЕМЫ**

Текущая культура: {culture}

Если тема вопроса не соответствует стандартным категориям (питание, защита, посадка, подбор сортов, улучшение почвы) —
формируй ответ следуя этой логике, опираясь на доступную информацию.

🟦 1. Проблема
Кратко объяснить:
— что происходит;
— почему это может быть проблемой для культуры;
— какие базовые причины чаще всего приводят к такой ситуации
(учитывать особенности растения: клубника, малина, кустарники, голубика и т.д.).

🟦 2. Возможные причины
Коротким списком:
— ошибки полива (слишком много/мало);
— особенности почвы (плотная, пересушенная, pH, дренаж);
— ошибки посадки (глубина, расстояние, загущение);
— ошибки обрезки (не то время, не тот принцип);
— погодные факторы (жара, мороз, ветер, переувлажнение);
— естественные особенности культуры или сорта.

🟦 3. Пути решения (подробно)
Дать понятный, практический план:
— что проверить
— что исправить в поливе
— что поправить в посадке или структуре почвы
— какие действия сделать в обрезке (если речь о кустарнике/малине)
— что изменить в условиях роста (мульча, вентиляция, освещение)

ИИ должен описывать действия кратко, безопасно и применимо к культуре.

🟦 Дополнительные указания:
— Отвечай простым, понятным языком
— Учитывай специфику культуры в ответе
— Если нужны препараты или удобрения — используй информацию из базы знаний
— При неясности причины — предложи несколько вариантов и способы диагностики
""".strip()

    return (prompt, False)  # False = использовать полный базовый промпт


def _get_category_specific_prompt_python(
    consultation_category: str,
    culture: str,
    default_location: str = "средняя полоса",
    default_growing_type: str = "открытый грунт"
) -> Tuple[str, bool]:
    """
    Возвращает специфичный промпт для категории консультации.
    Python-версия (используется как fallback если БД недоступна).

    Args:
        consultation_category: Тип консультации (например, "питание растений")
        culture: Название культуры (например, "малина", "голубика")
        default_location: Местоположение по умолчанию
        default_growing_type: Тип выращивания по умолчанию

    Returns:
        Tuple[str, bool]:
            - str: Строка с инструкциями для конкретной категории или пустая строка
            - bool: use_minimal_base (True = использовать минимальный базовый промпт)
    """
    # Маппинг категорий на функции промптов
    category_map = {
        "питание растений": get_nutrition_category_prompt,
        "посадка и уход": get_planting_care_category_prompt,
        "обрезка": get_pruning_category_prompt,
        "защита растений": get_diseases_pests_category_prompt,
        "болезни и вредители": get_diseases_pests_category_prompt,  # алиас
        "улучшение почвы": get_soil_improvement_category_prompt,
        "подбор сортов": get_variety_selection_category_prompt,
        "подбор сорта": get_variety_selection_category_prompt,  # алиас
    }

    # Нормализуем название категории (lowercase, trim)
    normalized_category = consultation_category.lower().strip()

    # Ищем соответствующую функцию
    prompt_func = category_map.get(normalized_category)

    if prompt_func:
        # Вызываем функцию и получаем кортеж (prompt, use_minimal_base)
        return prompt_func(culture, default_location, default_growing_type)
    else:
        # Если категория не найдена - используем fallback-промпт
        logger.debug(f"[_get_category_specific_prompt_python] Unknown category: {consultation_category!r}, using fallback")
        return _get_fallback_prompt_python(culture)


async def build_consultation_system_prompt(
    culture: str,                     # Культура (например, 'малина', 'голубика', 'не определено')
    kb_snippets: List[Dict[str, Any]], # Список фрагментов базы знаний
    qa_found: bool,                   # НОВОЕ: флаг найденных Q&A на уровне 1
    consultation_category: str = "",   # Тип консультации (например, "питание растений")
    default_location: str = "средняя полоса",        # Местоположение по умолчанию
    default_growing_type: str = "открытый грунт"     # Тип выращивания по умолчанию
) -> str:
    """
    Формирует полный системный промпт для LLM-консультации по ягодным культурам.

    Собирает промпт из четырёх частей:
    1. Базовый промпт (роль, scope, формат работы) - МИНИМАЛЬНЫЙ или ПОЛНЫЙ в зависимости от категорийного промпта
       - Сначала пробуем загрузить из БД
       - Fallback на Python-файлы если БД недоступна
    2. Категорийный промпт (специфика: питание, болезни, посадка и т.п.)
       - Сначала пробуем загрузить из БД
       - Fallback на Python-файлы если БД недоступна
    3. Контекст из базы знаний (RAG с приоритетами)
    4. Словарь терминологии

    НОВОЕ:
        - qa_found: флаг наличия Q&A на уровне 1
        - Если qa_found=True → инструкция "используй Q&A дословно"
        - Если qa_found=False → инструкция "синтезируй из документов"
        - use_minimal_base: категорийный промпт указывает, нужен ли минимальный базовый промпт

    Args:
        culture: Название культуры
        kb_snippets: Фрагменты из базы знаний для RAG
        qa_found: Флаг найденных Q&A (True если найдены на уровне 1)
        consultation_category: Тип консультации
        default_location: Местоположение по умолчанию
        default_growing_type: Тип выращивания по умолчанию

    Returns:
        Полный системный промпт для отправки в LLM
    """
    # 1.5. Добавляем информацию о культуре в начало промпта
    culture_context = ""
    if culture and culture not in ("не определено", "общая информация"):
        culture_context = f"\n\n🌱 КОНТЕКСТ КОНСУЛЬТАЦИИ:\nТы консультируешь по культуре: {culture.upper()}\nВСЕ твои ответы должны быть в контексте {culture}.\n"

    # 2. Категорийный промпт (специфика категории) + флаг use_minimal_base
    # Сначала пробуем загрузить из БД, затем fallback на Python
    category_prompt = ""
    use_minimal_base = False  # По умолчанию используем полный базовый промпт
    db_result = None  # Для проверки источника (БД vs Python) при загрузке справочников

    if consultation_category:
        # Пробуем загрузить из БД
        db_result = await _get_category_prompt_from_db(
            consultation_category,
            culture,
            default_location,
            default_growing_type
        )

        if db_result is not None:
            # Загружено из БД (может быть пустой строкой если категория отключена)
            category_prompt, use_minimal_base, _prompt_id = db_result
            if category_prompt == "":
                logger.info(f"[build_consultation_system_prompt] Category prompt disabled in DB")
            else:
                logger.debug(f"[build_consultation_system_prompt] Category prompt loaded from DB")
        else:
            # Fallback на Python (БД недоступна)
            category_prompt, use_minimal_base = _get_category_specific_prompt_python(
                consultation_category,
                culture,
                default_location,
                default_growing_type
            )
            logger.debug(f"[build_consultation_system_prompt] Category prompt loaded from Python fallback")

    # 1. Базовый промпт (выбираем минимальный или полный в зависимости от категорийного промпта)
    # Сначала пробуем загрузить из БД, затем fallback на Python
    # Определяем, известна ли культура для выбора правильной секции промпта
    culture_is_known = culture not in ("не определено", "общая информация")

    base_prompt = await _get_base_prompt_from_db(
        default_location,
        default_growing_type,
        include_response_format=not use_minimal_base,
        culture_is_known=culture_is_known,
    )

    if base_prompt is None:
        # Fallback на Python (БД недоступна или пуста)
        # Передаём culture_is_known для выбора правильной секции культуры
        if use_minimal_base:
            base_prompt = get_base_system_prompt_minimal(
                default_location,
                default_growing_type,
                culture_is_known=culture_is_known
            )
        else:
            base_prompt = get_base_system_prompt(
                default_location,
                default_growing_type,
                culture_is_known=culture_is_known
            )
        logger.debug(f"[build_consultation_system_prompt] Base prompt loaded from Python fallback")
    else:
        # Загружено из БД (может быть пустой строкой если всё отключено)
        if base_prompt == "":
            logger.info(f"[build_consultation_system_prompt] All base sections disabled in DB")
        else:
            logger.debug(f"[build_consultation_system_prompt] Base prompt loaded from DB")

    # 3. Контекст из базы знаний (НОВОЕ: передаем qa_found)
    kb_text_block = build_kb_context_snippet(kb_snippets, qa_found)

    if kb_text_block:
        kb_section = f"\n\nВот информация из базы знаний:\n\n{kb_text_block}\n"
    else:
        kb_section = """

📭 ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ НЕ НАЙДЕНА

ИНСТРУКЦИЯ:
- Отвечай на основе своих агрономических знаний, следуя стандартной структуре ответа
- Используй информацию из промт-документа и справочников, если они доступны
- Соблюдай все ограничения (культуры, безопасность дозировок и т.д.)
"""

    # 4. Промт-документ (специализированные инструкции из админ-панели)
    prompt_doc_section = await get_prompt_document_section(culture, consultation_category)

    # 5. Справочники (удобрения, СЗР, сорта) — ОТДЕЛЬНАЯ секция
    # Загружаем ТОЛЬКО когда категорийный промпт из БД (в Python-версии справочник уже встроен)
    reference_section = ""
    if consultation_category and db_result is not None and category_prompt:
        reference_section = await _load_reference_section(consultation_category)

    # 6. Словарь терминологии
    terminology_section = await build_terminology_section()
    if terminology_section:
        terminology_section = "\n\n" + terminology_section

    # Собираем все части вместе
    # Порядок: база → культура → категория → промт-документ → справочник → RAG → терминология
    parts = [base_prompt]

    if culture_context:
        parts.append(culture_context)

    if category_prompt:
        parts.append(category_prompt)

    # Промт-документ — ОСНОВНОЙ источник информации
    if prompt_doc_section:
        parts.append(prompt_doc_section)

    # Справочник — ДОПОЛНЯЕТ промт-документ конкретными препаратами/удобрениями/сортами
    if reference_section:
        parts.append(reference_section)

    parts.append(kb_section)

    if terminology_section:
        parts.append(terminology_section)

    # Склеиваем и возвращаем
    full_prompt = "\n\n".join(parts)
    return full_prompt.strip()


# ============================================================================
# Фазовые инструкции для LLM (Тип B / Тип C)
# ============================================================================

def build_short_answer_instruction() -> str:
    """
    Строит инструкцию для краткого ответа (Тип A / пользователь выбрал 'Краткий ответ').

    Добавляется к системному промпту когда ответ должен быть кратким.
    """
    return """

ИНСТРУКЦИЯ ПО ФОРМАТУ ОТВЕТА — КРАТКИЙ:
Пользователь запросил КРАТКИЙ ответ. Строго следуй правилам:
1. Ответ должен быть КРАТКИМ и КОНКРЕТНЫМ — максимум 3-5 пунктов.
2. Без длинных вступлений и предисловий.
3. НЕ расписывай план на сезон или фазу — дай точечную рекомендацию.
4. Если вопрос подразумевает несколько действий — перечисли ключевые, без деталей.
5. Объём ответа: 150-300 слов максимум.
6. Формат: короткие абзацы или нумерованный список."""


def build_phase_instruction(
    phase_key: str,
    phase_topic: str,
    is_last_phase: bool = False,
) -> str:
    """
    Строит дополнительную инструкцию для LLM при фазовом ответе.

    Добавляется к системному промпту когда ответ ограничен одной фазой.

    Args:
        phase_key: Ключ фазы (весна-цветение, цветение-плодоношение, плодоношение-зима)
        phase_topic: Тема ответа (питание, защита, уход)
        is_last_phase: Последняя ли это фаза (не предлагать следующую)
    """
    from src.pricing import get_phase_display_name
    phase_display = get_phase_display_name(phase_key)

    instruction = f"""

ФАЗОВЫЕ ИНСТРУКЦИИ:
Ты отвечаешь ТОЛЬКО на фазу развития растений: {phase_display}.
Тема ответа: {phase_topic}.

ОБЯЗАТЕЛЬНЫЙ ФОРМАТ ОТВЕТА:
1. НАЧНИ ответ с фразы: "Для того чтобы рекомендация была максимально точной и подробной, я распишу {phase_topic} для фазы развития растений — {phase_display}."
2. Далее — подробный план работ, подкормок или обработок ТОЛЬКО для этой фазы.
3. НЕ давай информацию о других фазах сезона. НЕ забегай вперёд.
4. Один ответ = одна тема ({phase_topic}). НЕ смешивай темы."""

    if not is_last_phase:
        instruction += """
5. ЗАВЕРШИ ответ фразой: "Если хотите, я дам рекомендации для следующей фазы роста."
   Эта фраза ОБЯЗАТЕЛЬНА в конце ответа."""
    else:
        instruction += """
5. Это ПОСЛЕДНЯЯ фаза сезона. НЕ предлагай продолжение."""

    return instruction


def build_phase_instruction_auto(
    phase_topic: str,
) -> str:
    """
    Строит инструкцию для фазового ответа, когда ИИ САМ выбирает фазу.

    Используется для Тип B (single phase) и расширенных phase_eligible ответов,
    когда классификатор не определяет конкретную фазу.

    Args:
        phase_topic: Тема ответа (питание, защита, уход)
    """
    return f"""

ФАЗОВЫЕ ИНСТРУКЦИИ:
Ты должен ответить по фазам роста растения. Тема: {phase_topic}.

ВЫБОР ФАЗЫ:
Определи, какая фаза роста наиболее актуальна и полезна для ответа на вопрос пользователя.
Возможные фазы:
- ранняя весна — начало цветения (март-май)
- цветение — окончание плодоношения (июнь-август)
- конец плодоношения — уход в зиму (сентябрь-февраль)

Начни ответ с той фазы, которая НАИБОЛЕЕ РЕЛЕВАНТНА вопросу.

ОБЯЗАТЕЛЬНЫЙ ФОРМАТ ОТВЕТА:
1. НАЧНИ ответ с фразы, указывающей выбранную фазу: "Для того чтобы рекомендация была максимально точной и подробной, я распишу {phase_topic} для фазы развития растений — [НАЗВАНИЕ ФАЗЫ]."
2. Далее — подробный план работ ТОЛЬКО для этой фазы.
3. НЕ давай информацию о других фазах сезона. НЕ забегай вперёд.
4. Один ответ = одна тема ({phase_topic}). НЕ смешивай темы.
5. ЗАВЕРШИ ответ фразой: "Если хотите, я дам рекомендации для следующей фазы роста."
   Эта фраза ОБЯЗАТЕЛЬНА в конце ответа."""


def build_extended_answer_instruction() -> str:
    """
    Строит инструкцию для расширенного ответа БЕЗ привязки к фазам.

    Используется когда пользователь выбрал 'Расширенный ответ' для вопроса,
    который НЕ зависит от фаз роста (phase_eligible=False).
    """
    return """

ИНСТРУКЦИЯ ПО ФОРМАТУ ОТВЕТА — РАСШИРЕННЫЙ:
Пользователь запросил РАСШИРЕННЫЙ ответ. Строго следуй правилам:
1. Дай ПОДРОБНЫЙ и РАЗВЁРНУТЫЙ ответ с пояснениями и обоснованиями.
2. Включи практические рекомендации с конкретными дозировками и сроками.
3. Объясни ПОЧЕМУ так, а не иначе — агрономическое обоснование.
4. Если уместно — приведи альтернативные варианты с их плюсами и минусами.
5. Объём ответа: 400-800 слов.
6. Структурируй ответ с подзаголовками и нумерованными списками.
7. Включи важные нюансы и предостережения."""


# ============================================================================
# Prompt Preview (для админ-панели)
# ============================================================================

# Маппинг slug → русская метка
BASE_SECTION_LABELS = {
    "role": "Роль",
    "scope": "Ограничения",
    "defaults": "Стандартные параметры",
    "culture_rules": "Правила работы с культурой",
    "culture_rules_known": "Правила (культура известна)",
    "culture_rules_undefined": "Правила (культура не определена)",
    "kb_usage": "Работа с базой знаний",
    "response_format": "Формат ответа",
    "work_context": "Контекст работ (до/после)",
    "answer_logic": "Логика формирования ответа",
    "tone": "Стиль ответа",
    "safety": "Правила безопасности",
}

# Python-функции для базовых секций (порядок как в build_base_prompt)
BASE_SECTION_FUNCTIONS = [
    ("role", _section_role),
    ("scope", _section_scope),
    # defaults и culture_rules обрабатываются отдельно (параметризованы)
    ("kb_usage", _section_kb_usage),
    ("response_format", _section_response_format),
    ("work_context", _section_work_context),
    ("tone", _section_tone),
    ("safety", _section_safety),
]


async def _get_base_sections_for_preview(
    default_location: str,
    default_growing_type: str,
    include_response_format: bool,
    culture_is_known: bool,
) -> list:
    """
    Загружает базовые секции для превью — каждую отдельно с метаданными.
    Пробует DB, fallback на Python.
    """
    sections = []

    # Пробуем загрузить из DB
    try:
        from src.services.db.prompt_repo import get_base_sections

        all_db_sections = await get_base_sections(is_enabled_only=False)
        if all_db_sections:
            # Проверяем наличие новых вариантов culture_rules
            has_split_culture_rules = any(
                s.get("slug") in ("culture_rules_known", "culture_rules_undefined")
                for s in all_db_sections
            )

            for s in all_db_sections:
                slug = s.get("slug", "")
                content = s.get("content", "")
                is_enabled = s.get("is_enabled", True)
                prompt_id = s.get("id")

                # Пропускаем response_format если use_minimal_base
                if slug == "response_format" and not include_response_format:
                    sections.append({
                        "id": f"base_{slug}",
                        "label": f"Базовая — {BASE_SECTION_LABELS.get(slug, slug)}",
                        "source": "base",
                        "color": "#3B82F6",
                        "content": content,
                        "is_from_db": True,
                        "is_enabled": False,
                        "skipped_reason": "Пропущено (use_minimal_base=True)",
                        "prompt_id": prompt_id,
                    })
                    continue

                # Скрываем старый culture_rules если есть новые варианты
                if slug == "culture_rules" and has_split_culture_rules:
                    continue

                # Условная логика для culture_rules_known/undefined
                if slug == "culture_rules_known":
                    is_active = culture_is_known
                    sections.append({
                        "id": f"base_{slug}",
                        "label": f"Базовая — {BASE_SECTION_LABELS.get(slug, slug)}",
                        "source": "base",
                        "color": "#3B82F6",
                        "content": content,
                        "is_from_db": True,
                        "is_enabled": is_enabled and is_active,
                        "prompt_id": prompt_id,
                        **({"skipped_reason": "Пропущено (культура не определена)"} if not is_active else {}),
                    })
                    continue

                if slug == "culture_rules_undefined":
                    is_active = not culture_is_known
                    sections.append({
                        "id": f"base_{slug}",
                        "label": f"Базовая — {BASE_SECTION_LABELS.get(slug, slug)}",
                        "source": "base",
                        "color": "#3B82F6",
                        "content": content,
                        "is_from_db": True,
                        "is_enabled": is_enabled and is_active,
                        "prompt_id": prompt_id,
                        **({"skipped_reason": "Пропущено (культура известна)"} if not is_active else {}),
                    })
                    continue

                # Подстановка переменных
                if slug == "defaults":
                    content = content.replace("{default_location}", default_location)
                    content = content.replace("{default_growing_type}", default_growing_type)

                sections.append({
                    "id": f"base_{slug}",
                    "label": f"Базовая — {BASE_SECTION_LABELS.get(slug, slug)}",
                    "source": "base",
                    "color": "#3B82F6",
                    "content": content,
                    "is_from_db": True,
                    "is_enabled": is_enabled,
                    "prompt_id": prompt_id,
                })

            return sections
    except Exception as e:
        logger.warning(f"[_get_base_sections_for_preview] DB error: {e}")

    # Fallback на Python
    python_sections = [
        ("role", _section_role()),
        ("scope", _section_scope()),
        ("defaults", _section_defaults(default_location, default_growing_type)),
        ("culture_rules",
         _section_culture_rules_with_context() if culture_is_known else _section_culture_rules_undefined()),
        ("kb_usage", _section_kb_usage()),
    ]
    if include_response_format:
        python_sections.append(("response_format", _section_response_format()))
    else:
        python_sections.append(("response_format", _section_response_format()))
        # Пометим как пропущенную
        sections_temp_skip = "response_format"

    python_sections.append(("work_context", _section_work_context()))
    python_sections.append(("answer_logic", _section_answer_logic()))
    python_sections.append(("tone", _section_tone()))
    python_sections.append(("safety", _section_safety()))

    for slug, content in python_sections:
        is_skipped = (slug == "response_format" and not include_response_format)
        sections.append({
            "id": f"base_{slug}",
            "label": f"Базовая — {BASE_SECTION_LABELS.get(slug, slug)}",
            "source": "base",
            "color": "#3B82F6",
            "content": content,
            "is_from_db": False,
            "is_enabled": not is_skipped,
            "prompt_id": None,
            **({"skipped_reason": "Пропущено (use_minimal_base=True)"} if is_skipped else {}),
        })

    return sections


async def build_prompt_preview(
    culture: str,
    consultation_category: str = "",
    default_location: str = "средняя полоса",
    default_growing_type: str = "открытый грунт",
) -> dict:
    """
    Собирает превью промпта — аннотированный список секций для визуализации в админ-панели.
    Повторяет логику build_consultation_system_prompt, но возвращает структуру вместо строки.
    """
    sections = []

    # --- 1. Категорийный промпт (определяем use_minimal_base) ---
    category_prompt = ""
    use_minimal_base = False
    category_source = "python"
    category_prompt_id = None
    culture_group = None

    if consultation_category:
        # Определяем culture_group для питания
        if consultation_category.lower().strip() == "питание растений":
            culture_group = get_prompt_group_for_culture("питание растений", culture)

        db_result = await _get_category_prompt_from_db(
            consultation_category, culture, default_location, default_growing_type
        )
        if db_result is not None:
            category_prompt, use_minimal_base, category_prompt_id = db_result
            category_source = "db"
        else:
            category_prompt, use_minimal_base = _get_category_specific_prompt_python(
                consultation_category, culture, default_location, default_growing_type
            )
            category_source = "python"
            category_prompt_id = None

    # --- 2. Базовые секции ---
    culture_is_known = culture not in ("не определено", "общая информация")
    base_sections = await _get_base_sections_for_preview(
        default_location, default_growing_type,
        include_response_format=not use_minimal_base,
        culture_is_known=culture_is_known,
    )
    base_source = "db" if (base_sections and base_sections[0].get("is_from_db")) else "python"
    sections.extend(base_sections)

    # --- 3. Контекст культуры ---
    if culture and culture not in ("не определено", "общая информация"):
        culture_context = f"🌱 КОНТЕКСТ КОНСУЛЬТАЦИИ:\nТы консультируешь по культуре: {culture.upper()}\nВСЕ твои ответы должны быть в контексте {culture}."
        sections.append({
            "id": "culture_context",
            "label": "Контекст культуры",
            "source": "culture",
            "color": "#22C55E",
            "content": culture_context,
            "is_from_db": False,
            "is_enabled": True,
            "prompt_id": None,
        })

    # --- 4. Категорийный промпт ---
    if consultation_category:
        group_label = ""
        if culture_group:
            group_names = {
                "group_strawberry": "Клубника",
                "group_raspberry": "Малина/Ежевика",
                "group_b_berries": "Кустарники (Группа Б)",
            }
            group_label = f" ({group_names.get(culture_group, culture_group)})"

        cat_display = consultation_category.capitalize()
        sections.append({
            "id": "category_prompt",
            "label": f"Категорийный — {cat_display}{group_label}",
            "source": "category",
            "color": "#8B5CF6",
            "content": category_prompt if category_prompt else "(Категорийный промпт отключён или пуст)",
            "is_from_db": category_source == "db",
            "is_enabled": bool(category_prompt),
            "prompt_id": category_prompt_id,
        })

    # --- 5. Промт-документ (ПЕРЕД справочником — он имеет высший приоритет) ---
    # Используем версию с ID для редактирования
    prompt_doc_data = None
    try:
        from src.services.db.prompt_repo import get_prompt_document_content_with_ids
        prompt_doc_data = await get_prompt_document_content_with_ids(culture, consultation_category)
    except Exception as e:
        logger.warning(f"[build_prompt_preview] prompt_doc_with_ids error: {e}")

    # Fallback на обычную функцию если новая не сработала
    if prompt_doc_data is None:
        prompt_doc_section = await get_prompt_document_section(culture, consultation_category)
        if prompt_doc_section:
            sections.append({
                "id": "prompt_document",
                "label": "Промт-документ",
                "source": "prompt_doc",
                "color": "#F59E0B",
                "content": prompt_doc_section.strip(),
                "is_from_db": True,
                "is_enabled": True,
                "prompt_id": None,
            })
        else:
            sections.append({
                "id": "prompt_document",
                "label": "Промт-документ",
                "source": "prompt_doc",
                "color": "#F59E0B",
                "content": None,
                "is_from_db": True,
                "is_enabled": False,
                "skipped_reason": "Не найден для данной комбинации культуры и категории",
                "prompt_id": None,
            })
    else:
        prompt_ids = prompt_doc_data["prompt_ids"]
        sections.append({
            "id": "prompt_document",
            "label": "Промт-документ",
            "source": "prompt_doc",
            "color": "#F59E0B",
            "content": prompt_doc_data["content"].strip(),
            "is_from_db": True,
            "is_enabled": True,
            "prompt_id": prompt_ids[0] if len(prompt_ids) == 1 else None,
            "prompt_ids": prompt_ids if len(prompt_ids) > 1 else None,
        })

    # --- 6. Справочники (удобрения, СЗР, сорта) — ДОПОЛНЯЮТ промт-документ ---
    # Маппинг категория → (slug в БД, python fallback, метка)
    CATEGORY_REFERENCES = {
        "питание растений": [("fertilizers", get_fertilizers_reference, "Справочник удобрений")],
        "защита растений": [("pesticides", get_pesticides_reference, "Справочник СЗР")],
        "подбор сортов": [("varieties", get_varieties_reference, "Справочник сортов")],
        "подбор сорта": [("varieties", get_varieties_reference, "Справочник сортов")],
    }

    ref_list = CATEGORY_REFERENCES.get(consultation_category.lower().strip(), [])
    for ref_slug, ref_python_func, ref_label in ref_list:
        # Если категорийный промпт из Python — справочник уже встроен через f-string
        if category_source == "python":
            sections.append({
                "id": f"reference_{ref_slug}",
                "label": ref_label,
                "source": "reference",
                "color": "#F97316",
                "content": "(Встроен в категорийный промпт выше)",
                "is_from_db": False,
                "is_enabled": True,
                "is_embedded": True,
                "prompt_id": None,
            })
            continue

        # Для DB-источника — загружаем справочник отдельно
        ref_content = None
        ref_from_db = False
        ref_prompt_id = None

        # Пробуем из БД
        try:
            from src.services.db.prompt_repo import get_reference_content
            db_result = await get_reference_content(ref_slug)
            if db_result:
                ref_content = db_result["content"]
                ref_prompt_id = db_result["id"]
                ref_from_db = True
        except Exception as e:
            logger.warning(f"[build_prompt_preview] DB reference error: {e}")

        # Fallback на Python
        if not ref_content:
            ref_content = ref_python_func()
            ref_from_db = False
            ref_prompt_id = None

        if ref_content:
            sections.append({
                "id": f"reference_{ref_slug}",
                "label": ref_label,
                "source": "reference",
                "color": "#F97316",
                "content": ref_content.strip(),
                "is_from_db": ref_from_db,
                "is_enabled": True,
                "prompt_id": ref_prompt_id,
            })

    # --- 7. RAG-плейсхолдер ---
    sections.append({
        "id": "kb_placeholder",
        "label": "База знаний (RAG)",
        "source": "rag",
        "color": "#EF4444",
        "content": None,
        "is_placeholder": True,
        "is_enabled": True,
        "prompt_id": None,
        "placeholder_text": (
            "[ Сюда вставляются результаты RAG-поиска ]\n\n"
            "УРОВЕНЬ 1: Q&A пары (высший приоритет — используются дословно)\n"
            "УРОВЕНЬ 2: Приоритетные документы (универсальные принципы)\n"
            "УРОВЕНЬ 3: Общие документы (синтез информации)\n\n"
            "Если Q&A найдены — показываются ТОЛЬКО они.\n"
            "Если нет — показываются Уровни 2 и 3."
        ),
    })

    # --- 8. Терминология ---
    terminology_section = await build_terminology_section()
    if terminology_section:
        sections.append({
            "id": "terminology",
            "label": "Словарь терминологии",
            "source": "terminology",
            "color": "#14B8A6",
            "content": terminology_section.strip(),
            "is_from_db": True,
            "is_enabled": True,
            "prompt_id": None,  # Из таблицы terminology, не prompts
        })

    # Метаданные
    total_chars = sum(
        len(s.get("content") or s.get("placeholder_text") or "")
        for s in sections
    )

    return {
        "sections": sections,
        "metadata": {
            "category": consultation_category,
            "culture": culture,
            "culture_group": culture_group,
            "use_minimal_base": use_minimal_base,
            "base_source": base_source,
            "category_source": category_source,
            "total_chars": total_chars,
        },
    }
