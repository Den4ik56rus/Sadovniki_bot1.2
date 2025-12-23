# src/services/documents/boundary_detector.py

"""
Детектор границ списков и структурных элементов в тексте.

Используется для защиты списков от разрыва при semantic chunking.
Если документ был обработан через docx_parser, границы списков уже известны.
Этот модуль нужен для plain text (TXT, PDF) без структурной разметки.
"""

import re
from typing import List, Dict, Tuple, Optional


def detect_list_boundaries(text: str) -> List[Dict]:
    """
    Находит границы списков в plain text.

    Поддерживаемые форматы списков:
    - Нумерованные: 1., 2., 3. или 1), 2), 3)
    - Маркированные: -, *, •, ●
    - Буквенные: а., б., в. или a), b), c)
    - Римские: i., ii., iii. или I., II., III.

    Параметры:
        text: Текст для анализа

    Возвращает:
        Список словарей:
        [
            {"start": 100, "end": 300, "type": "numbered"},
            {"start": 500, "end": 650, "type": "bulleted"}
        ]
    """
    lines = text.split("\n")
    lists = []

    in_list = False
    list_start = 0
    list_type = None
    current_position = 0

    for i, line in enumerate(lines):
        line_stripped = line.strip()
        line_length = len(line) + 1  # +1 для \n

        if not line_stripped:
            # Пустая строка может означать конец списка
            if in_list:
                lists.append({
                    "start": list_start,
                    "end": current_position,
                    "type": list_type,
                })
                in_list = False
            current_position += line_length
            continue

        is_list_item, item_type = _is_list_item(line_stripped)

        if is_list_item:
            if not in_list:
                # Начало нового списка
                in_list = True
                list_start = current_position
                list_type = item_type
            elif item_type != list_type:
                # Смена типа списка — закрываем старый, открываем новый
                lists.append({
                    "start": list_start,
                    "end": current_position,
                    "type": list_type,
                })
                list_start = current_position
                list_type = item_type
        else:
            # Обычный текст
            if in_list:
                # Проверяем, не является ли это продолжением элемента списка
                if not _is_list_continuation(line, lines, i):
                    lists.append({
                        "start": list_start,
                        "end": current_position,
                        "type": list_type,
                    })
                    in_list = False

        current_position += line_length

    # Закрываем открытый список в конце
    if in_list:
        lists.append({
            "start": list_start,
            "end": current_position,
            "type": list_type,
        })

    return lists


def _is_list_item(line: str) -> Tuple[bool, Optional[str]]:
    """
    Определяет, является ли строка элементом списка.

    Возвращает:
        (is_list: bool, list_type: str | None)
    """
    patterns = {
        "numbered": [
            r'^\d+[\.\)]\s+\S',           # 1. текст или 1) текст
            r'^\d+\.\d+[\.\)]\s+\S',      # 1.1. текст
        ],
        "bulleted": [
            r'^[-•●○◦▪★☆►]\s+\S',         # - текст, • текст
            r'^\*\s+\S',                   # * текст
        ],
        "lettered_ru": [
            r'^[а-яё][\.\)]\s+\S',         # а. текст или а) текст
        ],
        "lettered_en": [
            r'^[a-z][\.\)]\s+\S',          # a. текст или a) текст
        ],
        "roman": [
            r'^[ivxlcdmIVXLCDM]+[\.\)]\s+\S',  # i. текст или I. текст
        ],
    }

    for list_type, type_patterns in patterns.items():
        for pattern in type_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                return True, list_type

    return False, None


def _is_list_continuation(line: str, lines: List[str], index: int) -> bool:
    """
    Проверяет, является ли строка продолжением предыдущего элемента списка.

    Например:
    1. Первый пункт начинается здесь
       и продолжается на следующей строке

    Признаки продолжения:
    - Начинается с пробелов (отступ)
    - Предыдущая строка была элементом списка
    """
    if index == 0:
        return False

    # Проверяем отступ
    if line.startswith("   ") or line.startswith("\t"):
        prev_line = lines[index - 1].strip()
        is_prev_list, _ = _is_list_item(prev_line)
        return is_prev_list

    return False


def adjust_breakpoints_for_lists(
    breakpoints: List[int],
    text: str,
    list_boundaries: List[Dict],
) -> List[int]:
    """
    Корректирует точки разрыва, убирая те, что попадают внутрь списков.

    Параметры:
        breakpoints: Индексы точек разрыва (позиции символов в тексте)
        text: Исходный текст
        list_boundaries: Границы списков из detect_list_boundaries()

    Возвращает:
        Скорректированный список breakpoints
    """
    if not list_boundaries:
        return breakpoints

    adjusted = []

    for bp in breakpoints:
        inside_list = any(
            lb["start"] <= bp < lb["end"]
            for lb in list_boundaries
        )

        if not inside_list:
            adjusted.append(bp)

    return adjusted


def adjust_sentence_breakpoints_for_lists(
    breakpoints: List[int],
    sentences: List[str],
    list_boundaries: List[Dict],
) -> List[int]:
    """
    Корректирует точки разрыва между предложениями.

    Параметры:
        breakpoints: Индексы предложений (не символов!), после которых нужен разрыв
        sentences: Список предложений
        list_boundaries: Границы списков (позиции символов)

    Возвращает:
        Скорректированный список индексов предложений
    """
    if not list_boundaries:
        return breakpoints

    # Вычисляем позицию каждого предложения в тексте
    sentence_positions = []
    current_pos = 0
    for sentence in sentences:
        sentence_positions.append({
            "start": current_pos,
            "end": current_pos + len(sentence),
        })
        current_pos += len(sentence) + 1  # +1 для пробела/разделителя

    adjusted = []

    for bp in breakpoints:
        if bp >= len(sentence_positions):
            continue

        sentence_end = sentence_positions[bp]["end"]

        # Проверяем, не внутри ли списка
        inside_list = any(
            lb["start"] <= sentence_end < lb["end"]
            for lb in list_boundaries
        )

        if not inside_list:
            adjusted.append(bp)

    return adjusted


def find_safe_breakpoint_after_list(
    position: int,
    list_boundaries: List[Dict],
) -> int:
    """
    Находит безопасную точку разрыва после списка.

    Если position находится внутри списка, возвращает позицию
    сразу после конца этого списка.
    """
    for lb in list_boundaries:
        if lb["start"] <= position < lb["end"]:
            return lb["end"]

    return position


def merge_adjacent_lists(
    list_boundaries: List[Dict],
    max_gap: int = 50,
) -> List[Dict]:
    """
    Объединяет близкие списки одного типа.

    Параметры:
        list_boundaries: Список границ
        max_gap: Максимальный промежуток между списками для объединения

    Возвращает:
        Объединённый список границ
    """
    if not list_boundaries:
        return []

    # Сортируем по позиции
    sorted_lists = sorted(list_boundaries, key=lambda x: x["start"])
    merged = [sorted_lists[0].copy()]

    for current in sorted_lists[1:]:
        last = merged[-1]

        # Объединяем если:
        # 1. Тот же тип списка
        # 2. Расстояние между ними небольшое
        if (current["type"] == last["type"] and
                current["start"] - last["end"] <= max_gap):
            last["end"] = current["end"]
        else:
            merged.append(current.copy())

    return merged


def detect_headings(text: str) -> List[Dict]:
    """
    Находит заголовки в тексте.

    Признаки заголовка:
    - Короткая строка (< 100 символов)
    - Заканчивается без точки (или с двоеточием)
    - CAPS или начинается с заглавной
    - Нумерованный заголовок: "1. Название", "Глава 1."

    Параметры:
        text: Текст для анализа

    Возвращает:
        Список словарей:
        [
            {"text": "Заголовок", "start": 0, "end": 50, "type": "numbered"},
        ]
    """
    lines = text.split("\n")
    headings = []
    current_position = 0

    # Паттерны заголовков
    heading_patterns = [
        (r'^\d+\.\s+[А-ЯA-Z][^.!?]{0,80}$', 'numbered'),           # 1. Название раздела
        (r'^\d+\.\d+\.?\s+[А-ЯA-Z][^.!?]{0,80}$', 'numbered'),     # 1.1 Подраздел
        (r'^Глава\s+\d+[.:]\s*.{0,80}$', 'chapter'),               # Глава 1: Название
        (r'^Раздел\s+\d+[.:]\s*.{0,80}$', 'section'),              # Раздел 2. Название
        (r'^[А-ЯA-Z][А-ЯA-Z\s\-]{3,80}$', 'caps'),                 # ЗАГОЛОВОК В CAPS
        (r'^[А-ЯA-Z][а-яёА-ЯЁ\s\-]{3,60}:?\s*$', 'title'),         # Заголовок без точки
        (r'^[А-ЯA-Z][а-яё]+\s+[а-яё]+\s*$', 'short_title'),        # Короткий заголовок
    ]

    for i, line in enumerate(lines):
        line_stripped = line.strip()
        line_length = len(line) + 1  # +1 для \n

        if not line_stripped:
            current_position += line_length
            continue

        # Проверяем на совпадение с паттернами заголовков
        for pattern, heading_type in heading_patterns:
            if re.match(pattern, line_stripped, re.IGNORECASE):
                # Дополнительные проверки
                # 1. Не слишком длинная строка
                if len(line_stripped) > 100:
                    continue

                # 2. Следующая строка должна быть непустой (это контент)
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    # Если следующая строка пустая или тоже заголовок — пропускаем
                    if not next_line:
                        continue

                headings.append({
                    "text": line_stripped,
                    "start": current_position,
                    "end": current_position + len(line_stripped),
                    "type": heading_type,
                })
                break

        current_position += line_length

    return headings


def get_heading_sentence_indices(
    headings: List[Dict],
    sentences: List[str],
) -> List[int]:
    """
    Находит индексы предложений, которые являются заголовками.

    Используется для защиты границы между заголовком и следующим предложением.

    Параметры:
        headings: Список заголовков из detect_headings()
        sentences: Список предложений

    Возвращает:
        Список индексов предложений-заголовков
    """
    heading_indices = []
    heading_texts = {h["text"].strip().lower() for h in headings}

    for i, sentence in enumerate(sentences):
        # Проверяем совпадение текста предложения с заголовком
        sentence_clean = sentence.strip().lower()

        # Точное совпадение
        if sentence_clean in heading_texts:
            heading_indices.append(i)
            continue

        # Частичное совпадение (заголовок может быть частью предложения)
        for heading_text in heading_texts:
            if heading_text in sentence_clean and len(heading_text) > 10:
                heading_indices.append(i)
                break

    return heading_indices
