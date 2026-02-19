# src/prompts/category_prompts/_varieties_reference.py

"""
Справочник рекомендуемых сортов ягодных культур.
Данные загружаются из data/varieties_reference.json (по культурам).
"""

import json
from pathlib import Path
from typing import Optional

# Кеш загруженных данных (загружается один раз)
_varieties_data: Optional[dict] = None

# Маппинг значений culture → ключ в JSON
_CULTURE_KEY_MAP = {
    'клубника летняя': 'клубника',
    'клубника ремонтантная': 'клубника',
    'клубника общая': 'клубника',
    'клубника': 'клубника',
    'малина летняя': 'малина',
    'малина ремонтантная': 'малина',
    'малина общая': 'малина',
    'малина': 'малина',
    'смородина': 'смородина',
    'голубика': 'голубика',
    'жимолость': 'жимолость',
    'ежевика': 'ежевика',
    'крыжовник': 'крыжовник',
}

# Фильтр по типу для клубники и малины
_TYPE_FILTERS = {
    'клубника летняя': lambda t: 'ремонтантн' not in t.lower() and 'нсд' not in t.lower(),
    'клубника ремонтантная': lambda t: 'ремонтантн' in t.lower() or 'нсд' in t.lower(),
    'малина летняя': lambda t: 'ремонтантн' not in t.lower(),
    'малина ремонтантная': lambda t: 'ремонтантн' in t.lower(),
}

# Fallback для культур, которых нет в JSON
_FALLBACK_REFERENCES = {
    'крыжовник': """🟦 КРЫЖОВНИК — РЕКОМЕНДУЕМЫЕ СОРТА

Финик, Колобок, Черносливовый, Грушенька, Малахит, Инвикта

Данные по крыжовнику ограничены. ИИ может дополнить рекомендации из своей базы знаний, соблюдая требования к региону и современности сорта.""",
}

# Emoji для культур
_CULTURE_EMOJI = {
    'клубника': '🍓',
    'малина': '🍇',
    'ежевика': '🖤',
    'смородина': '⚫',
    'голубика': '🫐',
    'жимолость': '💙',
    'крыжовник': '🟢',
}


def _load_data() -> dict:
    """Загружает JSON с данными сортов (один раз, с кешированием)."""
    global _varieties_data
    if _varieties_data is None:
        json_path = Path(__file__).parent.parent.parent.parent / 'data' / 'varieties_reference.json'
        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                _varieties_data = json.load(f)
        else:
            _varieties_data = {}
    return _varieties_data


def _format_variety(variety: dict, emoji: str) -> str:
    """Форматирует один сорт в компактный текстовый блок для промпта."""
    name = variety['name']
    vtype = variety.get('type', '')
    desc = variety.get('description', '')
    pros = variety.get('pros', [])
    cons = variety.get('cons', [])

    lines = []
    type_suffix = f' ({vtype})' if vtype else ''
    lines.append(f'{emoji} {name.upper()}{type_suffix}')

    # Компактное описание — берём первые 2 предложения
    if desc:
        sentences = desc.replace('\n', ' ').split('. ')
        short_desc = '. '.join(sentences[:3]).strip()
        if not short_desc.endswith('.'):
            short_desc += '.'
        # Ограничиваем длину
        if len(short_desc) > 400:
            short_desc = short_desc[:397] + '...'
        lines.append(short_desc)

    if pros:
        lines.append('✅ Плюсы: ' + '; '.join(p.rstrip('.') for p in pros[:4]))
    if cons:
        lines.append('❌ Минусы: ' + '; '.join(c.rstrip('.') for c in cons[:4]))

    return '\n'.join(lines)


def get_varieties_instruction() -> str:
    """
    Возвращает общую инструкцию для ИИ по рекомендации сортов.
    Добавляется один раз в конец промпта (не дублируется для каждой культуры).
    """
    return """🟦 ИНСТРУКЦИЯ ДЛЯ ИИ
При рекомендации сортов:
— учитывай регион пользователя (климат, морозы, длина сезона)
— рекомендуй только современные, проверенные сорта из этого списка
— различай летние и ремонтантные сорта
— указывай сроки созревания, зимостойкость, устойчивость к болезням
— НЕ рекомендуй устаревшие, редкие и экспериментальные сорта""".strip()


def get_varieties_reference(culture: str) -> str:
    """
    Возвращает справочник сортов ТОЛЬКО для указанной культуры.

    Args:
        culture: Значение вроде "клубника летняя", "малина ремонтантная", "смородина" и т.д.

    Returns:
        Отформатированный текст справочника для вставки в промпт.
        Пустая строка для "общая информация" / "не определено".
    """
    culture_lower = culture.lower().strip()

    # Для неопределённой культуры — не загружаем справочник
    if culture_lower in ('общая информация', 'не определено', ''):
        return ''

    # Определяем ключ в JSON
    culture_key = _CULTURE_KEY_MAP.get(culture_lower)
    if not culture_key:
        return ''

    # Проверяем fallback
    data = _load_data()
    if culture_key not in data:
        return _FALLBACK_REFERENCES.get(culture_key, '')

    varieties = data[culture_key]

    # Фильтруем по типу (летний/ремонтантный) если нужно
    type_filter = _TYPE_FILTERS.get(culture_lower)
    if type_filter:
        filtered = [v for v in varieties if type_filter(v.get('type', ''))]
        # Если после фильтрации ничего не осталось — показываем все
        if filtered:
            varieties = filtered

    # Форматируем
    emoji = _CULTURE_EMOJI.get(culture_key, '🌱')
    culture_title = culture_key.upper()

    header = f'🟦 СПРАВОЧНИК РЕКОМЕНДУЕМЫХ СОРТОВ — {culture_title}'
    variety_blocks = [_format_variety(v, emoji) for v in varieties]

    return header + '\n\n' + '\n\n'.join(variety_blocks)
