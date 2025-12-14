# src/prompts/consultation_prompts.py

"""
Оркестратор системных промптов для консультаций.

Собирает финальный промпт из:
- Базовой части (роль, scope, формат)
- Категорийной части (специфика: питание, болезни, посадка и т.п.)
- Контекста из базы знаний (RAG)
- Словаря терминологии
"""

from typing import List, Dict, Any, Tuple

from src.prompts.base_prompt import get_base_system_prompt, get_base_system_prompt_minimal
from src.prompts.category_prompts import (
    get_nutrition_category_prompt,
    get_planting_care_category_prompt,
    get_diseases_pests_category_prompt,
    get_soil_improvement_category_prompt,
    get_variety_selection_category_prompt,
)


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


def _get_fallback_prompt(culture: str) -> Tuple[str, bool]:
    """
    Возвращает fallback-промпт для вопросов с неопределённой темой/категорией.

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


def _get_category_specific_prompt(
    consultation_category: str,
    culture: str,
    default_location: str = "средняя полоса",
    default_growing_type: str = "открытый грунт"
) -> Tuple[str, bool]:
    """
    Возвращает специфичный промпт для категории консультации.

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
        print(f"[_get_category_specific_prompt] Unknown category: {consultation_category!r}, using fallback prompt")
        return _get_fallback_prompt(culture)


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
    2. Категорийный промпт (специфика: питание, болезни, посадка и т.п.)
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
    category_prompt = ""
    use_minimal_base = False  # По умолчанию используем полный базовый промпт

    if consultation_category:
        category_prompt, use_minimal_base = _get_category_specific_prompt(
            consultation_category,
            culture,
            default_location,
            default_growing_type
        )

    # 1. Базовый промпт (выбираем минимальный или полный в зависимости от категорийного промпта)
    if use_minimal_base:
        base_prompt = get_base_system_prompt_minimal(default_location, default_growing_type)
    else:
        base_prompt = get_base_system_prompt(default_location, default_growing_type)

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

    # 4. Словарь терминологии
    terminology_section = await build_terminology_section()
    if terminology_section:
        terminology_section = "\n\n" + terminology_section

    # Собираем все части вместе
    parts = [base_prompt]

    if culture_context:
        parts.append(culture_context)

    if category_prompt:
        parts.append(category_prompt)

    parts.append(kb_section)

    if terminology_section:
        parts.append(terminology_section)

    # Склеиваем и возвращаем
    full_prompt = "\n\n".join(parts)
    return full_prompt.strip()
