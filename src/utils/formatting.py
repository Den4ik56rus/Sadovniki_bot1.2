# src/utils/formatting.py

"""
Утилиты для форматирования текста.
Конвертация Markdown → HTML для Telegram.
"""

import re
import unicodedata
from html import escape


def _get_display_width(text: str) -> int:
    """
    Вычисляет ширину строки с учётом широких символов (кириллица, CJK и т.д.).
    Для моноширинного шрифта в Telegram.
    """
    width = 0
    for char in text:
        # East Asian Width: Wide (W) и Full-width (F) занимают 2 позиции
        ea_width = unicodedata.east_asian_width(char)
        if ea_width in ('W', 'F'):
            width += 2
        else:
            width += 1
    return width


def _pad_to_width(text: str, target_width: int) -> str:
    """Дополняет строку пробелами до заданной ширины с учётом широких символов."""
    current_width = _get_display_width(text)
    padding = target_width - current_width
    return text + ' ' * max(0, padding)


def convert_markdown_table_to_cards(table_text: str) -> str:
    """
    Конвертирует markdown-таблицу в вертикальный формат (карточки).
    Оптимизировано для мобильных экранов Telegram.

    Входной формат:
    | Фаза | Удобрения | Цель |
    |------|-----------|------|
    | Весна | Азофоска | Рост |

    Выходной формат:
    ▸ Весна
    ├ Удобрения: Азофоска
    └ Цель: Рост
    """
    lines = [line.strip() for line in table_text.strip().split('\n') if line.strip()]

    if not lines:
        return table_text

    # Парсим строки в ячейки
    rows = []
    for line in lines:
        # Пропускаем строку-разделитель |---|---|
        if re.match(r'^\|[\s\-:|\s]+\|?$', line):
            continue
        # Убираем крайние |, разбиваем по |
        cells = [c.strip() for c in line.strip('|').split('|')]
        if cells:
            rows.append(cells)

    if len(rows) < 2:
        return table_text

    # Первая строка — заголовки (названия полей)
    headers = rows[0]
    data_rows = rows[1:]

    # Собираем карточки
    cards = []
    for row in data_rows:
        card_lines = []
        # Первый столбец — заголовок карточки
        title = row[0] if row else ''
        card_lines.append(f"▸ {title}")

        # Остальные столбцы — поля карточки
        for i in range(1, len(headers)):
            value = row[i] if i < len(row) else ''
            if value:  # Пропускаем пустые значения
                header = headers[i]
                # Последнее поле с └, остальные с ├
                is_last = (i == len(headers) - 1) or all(
                    (row[j] if j < len(row) else '') == ''
                    for j in range(i + 1, len(headers))
                )
                prefix = '└' if is_last else '├'
                card_lines.append(f"{prefix} {header}: {value}")

        cards.append('\n'.join(card_lines))

    return '\n\n'.join(cards)


def markdown_to_telegram_html(text: str) -> str:
    """
    Конвертирует Markdown-форматирование в HTML для Telegram.

    Поддерживаемые преобразования:
    - **bold** или __bold__ → <b>bold</b>
    - *italic* или _italic_ → <i>italic</i>
    - `code` → <code>code</code>
    - ```code block``` → <pre>code block</pre>
    - # Заголовок → <b>Заголовок</b>
    - ## Подзаголовок → <b>Подзаголовок</b>
    - - список → • список
    - * список → • список
    - | таблица | → ASCII-таблица в <pre>

    Args:
        text: Текст с Markdown-форматированием

    Returns:
        Текст с HTML-тегами для Telegram
    """
    if not text:
        return text

    # 1. Экранируем HTML-символы (кроме тех, что мы сами добавим)
    # Сначала заменяем на плейсхолдеры то, что нужно сохранить

    # Сохраняем code blocks (```) перед экранированием
    code_blocks = []
    def save_code_block(match):
        code_blocks.append(match.group(1))
        return f"__CODE_BLOCK_{len(code_blocks) - 1}__"

    text = re.sub(r'```(?:\w+)?\n?(.*?)```', save_code_block, text, flags=re.DOTALL)

    # Конвертируем markdown-таблицы в вертикальный формат (карточки)
    # Паттерн: несколько строк, начинающихся с |
    tables_converted = []

    def convert_table(match):
        table_text = match.group(0)
        cards = convert_markdown_table_to_cards(table_text)
        tables_converted.append(cards)
        return f"__TABLE_{len(tables_converted) - 1}__"

    # Ищем блоки таблиц: минимум 2 строки с | (заголовок + разделитель или данные)
    table_pattern = r'(?:^\|.+\|[ \t]*$\n?){2,}'
    text = re.sub(table_pattern, convert_table, text, flags=re.MULTILINE)

    # Сохраняем inline code (`) перед экранированием
    inline_codes = []
    def save_inline_code(match):
        inline_codes.append(match.group(1))
        return f"__INLINE_CODE_{len(inline_codes) - 1}__"

    text = re.sub(r'`([^`]+)`', save_inline_code, text)

    # Экранируем HTML-символы
    text = escape(text)

    # 2. Восстанавливаем code с HTML-тегами
    for i, code in enumerate(code_blocks):
        escaped_code = escape(code.strip())
        text = text.replace(f"__CODE_BLOCK_{i}__", f"<pre>{escaped_code}</pre>")

    for i, code in enumerate(inline_codes):
        escaped_code = escape(code)
        text = text.replace(f"__INLINE_CODE_{i}__", f"<code>{escaped_code}</code>")

    # Восстанавливаем таблицы (уже в формате карточек, нужно экранировать)
    for i, table in enumerate(tables_converted):
        escaped_table = escape(table)
        text = text.replace(f"__TABLE_{i}__", escaped_table)

    # 3. Заголовки: # Текст → <b>Текст</b>
    # Обрабатываем в начале строки
    text = re.sub(r'^#{1,6}\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)

    # 4. Bold: **text** или __text__ → <b>text</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)

    # 5. Italic: *text* или _text_ → <i>text</i>
    # Важно: не путать с маркерами списков
    # Используем lookbehind/lookahead чтобы не захватывать * в начале строки
    text = re.sub(r'(?<!\*)\*([^\*\n]+?)\*(?!\*)', r'<i>\1</i>', text)
    text = re.sub(r'(?<!_)_([^_\n]+?)_(?!_)', r'<i>\1</i>', text)

    # 6. Списки: - или * в начале строки (с возможными пробелами) → •
    # Сохраняем отступы, заменяем только маркер
    text = re.sub(r'^(\s*)[\-\*]\s+', r'\1• ', text, flags=re.MULTILINE)

    # 7. Нумерованные списки: оставляем как есть (1. 2. 3.)

    return text
