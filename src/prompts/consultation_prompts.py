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
)
from src.prompts.category_prompts import (
    get_nutrition_category_prompt,
    get_planting_care_category_prompt,
    get_diseases_pests_category_prompt,
    get_soil_improvement_category_prompt,
    get_variety_selection_category_prompt,
    get_prompt_group_for_culture,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Async DB Loading Functions
# ============================================================================

async def _get_base_prompt_from_db(
    default_location: str,
    default_growing_type: str,
    include_response_format: bool = True,
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

        # Подставляем переменные в defaults секцию
        section_contents = []
        for section in enabled_sections:
            slug = section.get("slug", "")
            content = section.get("content", "")

            # Пропускаем response_format если не нужен
            if slug == "response_format" and not include_response_format:
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
) -> Optional[Tuple[str, bool]]:
    """
    Загружает категорийный промпт из БД.

    Логика:
    - Если категория отключена (is_enabled=False) → возвращаем ("", False) — пустой промпт
    - Если категория не найдена в БД → возвращаем None (fallback на Python)
    - Если категория включена → возвращаем её содержимое

    Args:
        consultation_category: Категория консультации
        culture: Название культуры
        default_location: Местоположение по умолчанию
        default_growing_type: Тип выращивания по умолчанию

    Returns:
        Tuple[str, bool] (промпт, use_minimal_base) или None если БД недоступна
    """
    try:
        from src.services.db.prompt_repo import get_category_prompt, get_fallback_prompt, check_category_exists

        # Маппинг категорий на subgroup slugs
        category_to_subgroup = {
            "питание растений": "nutrition",
            "посадка и уход": "planting_care",
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
                return (content, fallback.get("use_minimal_base", False))
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
                return ("", False)
            # Категории нет в БД → fallback на Python
            return None

        content = prompt_data["content"]
        use_minimal_base = prompt_data.get("use_minimal_base", False)

        # Подставляем переменные
        content = content.replace("{culture}", culture)
        content = content.replace("{default_location}", default_location)
        content = content.replace("{default_growing_type}", default_growing_type)

        logger.info(f"[_get_category_prompt_from_db] Loaded {subgroup_slug}/{culture_group or 'main'} from DB")
        return (content, use_minimal_base)

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
            category_prompt, use_minimal_base = db_result
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
    base_prompt = await _get_base_prompt_from_db(
        default_location,
        default_growing_type,
        include_response_format=not use_minimal_base
    )

    if base_prompt is None:
        # Fallback на Python (БД недоступна или пуста)
        if use_minimal_base:
            base_prompt = get_base_system_prompt_minimal(default_location, default_growing_type)
        else:
            base_prompt = get_base_system_prompt(default_location, default_growing_type)
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
- В КАЖДОМ пункте/разделе ответа добавь пометку:
  "(По этому пункту информация из нашей библиотеки недостаточная — ответ отправлен на модерацию к агроному)"
- Соблюдай все ограничения (культуры, безопасность дозировок и т.д.)
"""

    # 4. Промт-документ (специализированные инструкции из админ-панели)
    prompt_doc_section = await get_prompt_document_section(culture, consultation_category)

    # 5. Словарь терминологии
    terminology_section = await build_terminology_section()
    if terminology_section:
        terminology_section = "\n\n" + terminology_section

    # Собираем все части вместе
    parts = [base_prompt]

    if culture_context:
        parts.append(culture_context)

    if category_prompt:
        parts.append(category_prompt)

    # Промт-документ добавляем ПЕРЕД KB, чтобы он был выше по приоритету
    if prompt_doc_section:
        parts.append(prompt_doc_section)

    parts.append(kb_section)

    if terminology_section:
        parts.append(terminology_section)

    # Склеиваем и возвращаем
    full_prompt = "\n\n".join(parts)
    return full_prompt.strip()
