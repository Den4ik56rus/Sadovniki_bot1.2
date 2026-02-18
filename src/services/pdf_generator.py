# src/services/pdf_generator.py

"""
Генерация PDF-книг из гайдов (Готовое решение).

Принимает секции из generate_full_guide() и рендерит PDF-книгу
через fpdf2 (чистый Python, без внешних зависимостей).

Шрифт: DejaVuSans (data/fonts/) — полная поддержка кириллицы.
"""

import asyncio
import os
import re
import logging
import time
from datetime import date
from pathlib import Path
from typing import Dict, Any, List

from fpdf import FPDF

logger = logging.getLogger(__name__)

# Пути
BASE_DIR = Path(__file__).parent.parent.parent
FONTS_DIR = BASE_DIR / "data" / "fonts"
GUIDES_DIR = BASE_DIR / "data" / "guides"

# Страницы без header/footer: титульная (1) и оглавление (2)
_SKIP_HEADER_PAGES = {1, 2}


# ─── PDF-класс с колонтитулами ───

class GuidePDF(FPDF):
    """PDF с кастомными header/footer для книжного формата гайдов."""

    def __init__(self, culture: str):
        super().__init__()
        self.culture = culture
        self._setup_fonts()
        self.set_auto_page_break(auto=True, margin=20)

    def _setup_fonts(self):
        self.add_font("DejaVu", style="", fname=str(FONTS_DIR / "DejaVuSans.ttf"))
        self.add_font("DejaVu", style="B", fname=str(FONTS_DIR / "DejaVuSans-Bold.ttf"))
        self.add_font("DejaVu", style="I", fname=str(FONTS_DIR / "DejaVuSans-Oblique.ttf"))
        self.add_font("DejaVu", style="BI", fname=str(FONTS_DIR / "DejaVuSans-BoldOblique.ttf"))

    def header(self):
        if self.page in _SKIP_HEADER_PAGES:
            return
        self.set_font("DejaVu", "I", 8)
        self.set_text_color(140, 140, 140)
        title = f"Уход за {self.culture} \u2014 руководство на сезон"
        self.cell(0, 8, title, align="C", markdown=False)
        self.ln(2)
        y_line = self.get_y()
        self.set_draw_color(210, 210, 210)
        self.line(self.l_margin, y_line, self.w - self.r_margin, y_line)
        self.ln(4)
        self.set_text_color(0, 0, 0)

    def footer(self):
        if self.page in _SKIP_HEADER_PAGES:
            return
        self.set_y(-15)
        self.set_font("DejaVu", "I", 8)
        self.set_text_color(140, 140, 140)
        self.cell(0, 10, f"\u2014 {self.page_no()} \u2014", align="C", markdown=False)


# ─── Рендер титульной страницы ───

def _render_title_page(pdf: GuidePDF, culture: str):
    pdf.add_page()

    # Декоративная линия сверху
    pdf.set_draw_color(74, 124, 89)  # #4A7C59
    pdf.set_line_width(0.8)
    pdf.line(30, 40, pdf.w - 30, 40)

    pdf.ln(55)

    # Название культуры
    pdf.set_font("DejaVu", "B", 26)
    pdf.set_text_color(40, 40, 40)
    pdf.multi_cell(0, 13, f"Уход за {culture}", align="C")
    pdf.ln(4)

    # Подзаголовок
    pdf.set_font("DejaVu", "", 15)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(0, 9, "Полное руководство на сезон", align="C")
    pdf.ln(6)

    # Темы
    pdf.set_font("DejaVu", "I", 11)
    pdf.set_text_color(110, 110, 110)
    pdf.multi_cell(0, 7, "Питание  \u00b7  Защита  \u00b7  Подготовка почвы  \u00b7  Уходные работы", align="C")

    # Декоративная линия
    pdf.ln(8)
    pdf.set_draw_color(74, 124, 89)
    pdf.line(60, pdf.get_y(), pdf.w - 60, pdf.get_y())

    # Брендинг внизу
    pdf.set_y(-55)
    pdf.set_font("DejaVu", "", 10)
    pdf.set_text_color(130, 130, 130)
    pdf.cell(0, 7, f"Сгенерировано: {date.today().strftime('%d.%m.%Y')}", align="C",
             new_x="LMARGIN", new_y="NEXT", markdown=False)
    pdf.cell(0, 7, "Садовники \u2014 бот для профессиональных консультаций", align="C",
             markdown=False)

    pdf.set_text_color(0, 0, 0)


# ─── Рендер оглавления (вручную, без insert_toc_placeholder) ───

def _render_toc_page(pdf: GuidePDF, toc_entries: List[Dict[str, Any]]):
    """Рендерит страницу оглавления из заранее собранных данных."""
    pdf.add_page()  # Страница 2

    pdf.set_font("DejaVu", "B", 16)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(0, 12, "Содержание", new_x="LMARGIN", new_y="NEXT", markdown=False)
    pdf.ln(4)

    pdf.set_draw_color(210, 210, 210)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(8)

    for entry in toc_entries:
        pdf.set_font("DejaVu", "", 11)
        pdf.set_text_color(50, 50, 50)

        link = pdf.add_link(page=entry["page"])
        label = f"{entry['title']}  \u00b7\u00b7\u00b7  {entry['page']}"
        pdf.cell(0, 9, label, link=link, new_x="LMARGIN", new_y="NEXT", markdown=False)

    pdf.set_text_color(0, 0, 0)


# ─── Конвертер Markdown → HTML ───

def _inline_format(text: str) -> str:
    """Конвертирует **bold** и *italic* в HTML-теги."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    return text


def _is_special_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    return (
        s.startswith("#")
        or s.startswith("|")
        or s.startswith("- ")
        or bool(re.match(r"^\d+\.\s", s))
    )


def _strip_markdown_inline(text: str) -> str:
    """Убирает markdown inline-форматирование (**bold**, *italic*) и экранирует HTML."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    return text


def _parse_table(table_lines: List[str]) -> str:
    """Конвертирует markdown-таблицу в HTML <table>.

    fpdf2 не поддерживает вложенные теги (<b>, <i>) внутри <td>/<th>,
    поэтому inline-форматирование удаляется, оставляя только текст.
    """
    data_lines = [
        l for l in table_lines if not re.match(r"^\|[\s\-:|]+\|$", l)
    ]
    if not data_lines:
        return ""

    rows = []
    for line in data_lines:
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows.append(cells)

    if not rows:
        return ""

    n_cols = len(rows[0])
    col_width = int(100 / n_cols) if n_cols else 100

    html = '<table border="1" width="100%"><thead><tr>'
    for cell in rows[0]:
        html += f'<th width="{col_width}%">{_strip_markdown_inline(cell)}</th>'
    html += "</tr></thead><tbody>"

    for row in rows[1:]:
        html += "<tr>"
        for cell in row:
            html += f"<td>{_strip_markdown_inline(cell)}</td>"
        html += "</tr>"

    html += "</tbody></table><br>"
    return html


def _strip_first_heading(md_text: str, section_title: str) -> str:
    """Убирает первый заголовок из markdown, если он дублирует название секции."""
    lines = md_text.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            heading_text = re.sub(r"^#+\s*", "", stripped).strip()
            if (heading_text.lower() in section_title.lower()
                    or section_title.lower() in heading_text.lower()
                    or heading_text.split(":")[0].strip().lower() == section_title.split(":")[0].strip().lower()):
                lines[i] = ""
        break
    return "\n".join(lines)


def _markdown_to_html(md_text: str) -> str:
    """
    Конвертирует markdown-текст секции в HTML для fpdf2 write_html().

    Не использует <h1>-<h4> HTML-теги — вместо них стилизованные
    параграфы с <font size> + <b>.
    """
    lines = md_text.split("\n")
    html_parts: List[str] = []
    i = 0
    total = len(lines)

    while i < total:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Заголовки → стилизованные параграфы (без <h*>)
        if stripped.startswith("#### "):
            text = _inline_format(stripped[5:])
            html_parts.append(f'<p><font size="11"><b>{text}</b></font></p>')
            i += 1
            continue
        if stripped.startswith("### "):
            text = _inline_format(stripped[4:])
            html_parts.append(f'<p><font size="12"><b>{text}</b></font></p>')
            i += 1
            continue
        if stripped.startswith("## "):
            text = _inline_format(stripped[3:])
            html_parts.append(f'<br><p><font size="14"><b>{text}</b></font></p>')
            i += 1
            continue
        if stripped.startswith("# "):
            text = _inline_format(stripped[2:])
            html_parts.append(f'<br><p><font size="14"><b>{text}</b></font></p>')
            i += 1
            continue

        # Таблица
        if stripped.startswith("|"):
            table_lines = []
            while i < total and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            html_parts.append(_parse_table(table_lines))
            continue

        # Чек-бокс: - [ ] или - [x]
        if stripped.startswith("- [ ]") or stripped.startswith("- [x]") or stripped.startswith("- [X]"):
            items = []
            while i < total and (
                lines[i].strip().startswith("- [ ]")
                or lines[i].strip().startswith("- [x]")
                or lines[i].strip().startswith("- [X]")
            ):
                item = lines[i].strip()
                checked = item.startswith("- [x]") or item.startswith("- [X]")
                text = item[5:].strip()
                marker = "\u2611" if checked else "\u2610"
                items.append(f"<li>{marker} {_inline_format(text)}</li>")
                i += 1
            html_parts.append(f"<ul>{''.join(items)}</ul>")
            continue

        # Маркированный список
        if stripped.startswith("- ") and not stripped.startswith("- ["):
            items = []
            while i < total and lines[i].strip().startswith("- ") and not lines[i].strip().startswith("- ["):
                text = lines[i].strip()[2:]
                items.append(f"<li>{_inline_format(text)}</li>")
                i += 1
            html_parts.append(f"<ul>{''.join(items)}</ul>")
            continue

        # Нумерованный список
        if re.match(r"^\d+\.\s", stripped):
            items = []
            while i < total and re.match(r"^\d+\.\s", lines[i].strip()):
                text = re.sub(r"^\d+\.\s+", "", lines[i].strip())
                items.append(f"<li>{_inline_format(text)}</li>")
                i += 1
            html_parts.append(f"<ol>{''.join(items)}</ol>")
            continue

        # Обычный параграф
        para_lines = []
        while i < total and lines[i].strip() and not _is_special_line(lines[i]):
            para_lines.append(lines[i].strip())
            i += 1
        if para_lines:
            html_parts.append(f"<p>{_inline_format(' '.join(para_lines))}</p>")

    return "\n".join(html_parts)


# ─── Рендер секции ───

def _render_section(pdf: GuidePDF, title: str, content: str):
    """Рендерит одну секцию гайда с новой страницы."""
    pdf.add_page()

    # Заголовок секции
    pdf.set_font("DejaVu", "B", 18)
    pdf.set_text_color(40, 40, 40)
    pdf.multi_cell(0, 11, title)
    pdf.ln(2)

    # Декоративная линия
    pdf.set_draw_color(74, 124, 89)
    pdf.set_line_width(0.5)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + 40, pdf.get_y())
    pdf.ln(6)

    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.2)
    pdf.set_text_color(0, 0, 0)

    # Убираем первый заголовок markdown если дублирует title
    content = _strip_first_heading(content, title)

    # Конвертируем markdown → HTML и рендерим
    html_content = _markdown_to_html(content)
    pdf.set_font("DejaVu", "", 10)
    pdf.write_html(html_content)


# ─── Синхронная генерация PDF ───

def _generate_guide_pdf_sync(
    sections: Dict[str, Any],
    culture: str,
    culture_display: str,
) -> str:
    """Синхронная генерация PDF (вызывается из asyncio.to_thread)."""
    GUIDES_DIR.mkdir(parents=True, exist_ok=True)

    from src.services.llm.guide_generation_llm import GUIDE_SECTIONS, INTRO_SECTION
    def _section_order(k):
        if k == "intro":
            return INTRO_SECTION.get("order", 0)
        return GUIDE_SECTIONS.get(k, {}).get("order", 99)
    ordered_keys = sorted(sections.keys(), key=_section_order)

    # Собираем данные для ToC: рендерим секции и запоминаем номера страниц
    # Для ToC нужно знать на какой странице начинается каждая секция.
    # Подход: сначала рендерим title (стр.1), ToC placeholder (стр.2),
    # затем секции (стр.3+). Номера страниц секций известны только после рендера.
    # Поэтому генерируем PDF в 2 прохода:
    # 1) Рендерим всё без ToC чтобы узнать номера страниц
    # 2) Рендерим финальный PDF с заполненным ToC

    # --- Проход 1: пробный рендер для сбора номеров страниц ---
    probe = GuidePDF(culture=culture_display)
    probe.add_page()  # title = page 1
    probe.add_page()  # toc = page 2

    toc_entries = []
    for key in ordered_keys:
        section = sections[key]
        content = section.get("content", "")
        if content:
            title = section.get("title", key)
            probe.add_page()
            page_num = probe.page
            toc_entries.append({"title": title, "page": page_num})
            # Рендерим контент чтобы узнать сколько страниц он занимает
            probe.set_font("DejaVu", "B", 18)
            probe.multi_cell(0, 11, title)
            probe.ln(8)
            content_clean = _strip_first_heading(content, title)
            html_content = _markdown_to_html(content_clean)
            probe.set_font("DejaVu", "", 10)
            probe.write_html(html_content)

    # --- Проход 2: финальный рендер с ToC ---
    pdf = GuidePDF(culture=culture_display)

    # 1. Титульная страница
    _render_title_page(pdf, culture_display)

    # 2. Оглавление
    _render_toc_page(pdf, toc_entries)

    # 3. Секции
    for key in ordered_keys:
        section = sections[key]
        content = section.get("content", "")
        if content:
            title = section.get("title", key)
            _render_section(pdf, title, content)

    # 4. Сохранить
    safe_name = re.sub(r"[^\w\s-]", "", culture_display).strip().replace(" ", "_")
    filename = f"guide_{safe_name}_{int(time.time())}.pdf"
    output_path = str(GUIDES_DIR / filename)

    pdf.output(output_path)

    file_size = os.path.getsize(output_path)
    logger.info(
        f"[pdf_gen] PDF сгенерирован: {output_path}, "
        f"размер={file_size / 1024:.1f} KB, страниц={pdf.pages_count}"
    )
    return output_path


# ─── Асинхронная обёртка (основная точка входа) ───

async def generate_guide_pdf(
    sections: Dict[str, Any],
    culture: str,
    culture_display: str,
) -> str:
    """
    Генерирует PDF-книгу из секций гайда.

    Args:
        sections: Dict из generate_full_guide() — {key: {"title": str, "content": str}}
        culture: Ключ культуры (machine-readable)
        culture_display: Отображаемое название культуры

    Returns:
        Абсолютный путь к сгенерированному PDF.
    """
    return await asyncio.to_thread(
        _generate_guide_pdf_sync, sections, culture, culture_display
    )
