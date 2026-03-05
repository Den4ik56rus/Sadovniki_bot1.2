#!/usr/bin/env python3
"""
Конвертер: article_text (Markdown) → PDF файл.

Использование:
    python scripts/md_to_pdf.py --test          # тест на захардкоженной статье
    python scripts/md_to_pdf.py --input file.md --output out.pdf --culture "Малина"
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS

SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent

CULTURE_LABELS = {
    "strawberry": "Клубника",
    "raspberry": "Малина",
    "blackberry": "Ежевика",
    "blueberry": "Голубика",
    "currant": "Смородина",
    "honeysuckle": "Жимолость",
}
VARIETY_LABELS = {
    "summer": "летняя",
    "remontant": "ремонтантная",
}
CATEGORY_LABELS = {
    "nutrition": "Питание растений",
    "planting_care": "Посадка и уход",
    "protection": "Защита растений",
    "soil": "Улучшение почвы",
    "varieties": "Подбор сорта",
    "pruning": "Обрезка",
}


def extract_toc(md_text: str) -> list[str]:
    """Извлекает ## заголовки из Markdown-текста."""
    toc = []
    for line in md_text.split('\n'):
        line = line.strip()
        if line.startswith('## ') and not line.startswith('### '):
            title = line[3:].strip()
            toc.append(title)
    return toc


def postprocess_html(html: str) -> str:
    """
    Постобработка HTML:
    - параграфы начинающиеся с Важно: / Note: / Внимание: → .callout-important
    - пустые параграфы удаляем
    """
    # Callout блоки
    html = re.sub(
        r'<p>(<strong>(?:Важно|Note|Внимание|ВАЖНО)[:\s!]*</strong>)',
        r'<p class="callout-important">\1',
        html,
    )
    return html


def md_to_html(md_text: str) -> str:
    """Конвертирует Markdown в HTML с расширениями."""
    md = markdown.Markdown(extensions=[
        'tables',
        'fenced_code',
        'nl2br',
        'sane_lists',
    ])
    html = md.convert(md_text)
    return postprocess_html(html)


def generate_pdf(
    article_text: str,
    output_path: str,
    culture_key: str = "",
    variety_key: str = "",
    category_key: str = "",
    topic: str = "",
    logo_path: str = None,
) -> str:
    """
    Генерирует PDF из текста статьи.

    Args:
        article_text: текст в Markdown
        output_path: путь для сохранения PDF
        culture_key: ключ культуры (strawberry, raspberry, ...)
        variety_key: вариант (summer, remontant, или пусто)
        category_key: категория (nutrition, planting_care, ...)
        topic: полное название темы (из БД)
        logo_path: путь к логотипу (опционально)

    Returns:
        путь к созданному PDF
    """
    culture_name = CULTURE_LABELS.get(culture_key, culture_key.capitalize())
    variety_label = VARIETY_LABELS.get(variety_key, "") if variety_key else ""
    category_label = CATEGORY_LABELS.get(category_key, category_key)

    # Автоматически подставляем лого если не указан явно
    if logo_path is None:
        default_logo = SCRIPTS_DIR / "assets" / "logo.png"
        if default_logo.exists():
            logo_path = str(default_logo)

    # Инфографика (вторая страница обложки)
    infographic_path = None
    default_infographic = SCRIPTS_DIR / "assets" / "infographic.png"
    if default_infographic.exists():
        infographic_path = str(default_infographic)

    toc = extract_toc(article_text)
    article_html = md_to_html(article_text)

    # Jinja2 шаблон
    env = Environment(loader=FileSystemLoader(str(SCRIPTS_DIR)))
    template = env.get_template("pdf_template.html")

    css_path = SCRIPTS_DIR / "pdf_styles.css"

    html_content = template.render(
        culture_name=culture_name,
        variety_label=variety_label,
        category_label=category_label,
        topic=topic or f"{category_label} — {culture_name}",
        toc=toc,
        article_html=article_html,
        css_path=str(css_path),
        logo_path=logo_path,
        infographic_path=infographic_path,
        year=datetime.now().year,
    )

    # Генерируем PDF
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    HTML(string=html_content, base_url=str(SCRIPTS_DIR)).write_pdf(
        output_path,
        stylesheets=[CSS(filename=str(css_path))],
    )

    return output_path


def main():
    parser = argparse.ArgumentParser(description='Генератор PDF из Markdown-статьи')
    parser.add_argument('--test', action='store_true', help='Тест на захардкоженной статье')
    parser.add_argument('--input', help='Входной .md файл')
    parser.add_argument('--output', help='Выходной .pdf файл')
    parser.add_argument('--culture', default='strawberry', help='Ключ культуры')
    parser.add_argument('--variety', default='', help='Вариант (summer/remontant)')
    parser.add_argument('--category', default='nutrition', help='Ключ категории')
    parser.add_argument('--topic', default='', help='Название темы')
    args = parser.parse_args()

    if args.test:
        test_text = """Ниже — системная схема питания земляники садовой на весь сезон.

## 1. Подготовка почвы

### Задача

Создать «долгоиграющий» запас питания и хорошую структуру почвы.

### Что важно по элементам

- **Азот (N)** — нужен, но на этапе подготовки не даём много.
- **Фосфор (P)** — отвечает за корневую систему.
- **Калий (K)** — критичен для ягодных культур.

**Важно:** Всегда сверяться с инструкцией к удобрению.

### Схема подготовки

На 1 м² будущей грядки:

1. Перепревший перегной / зрелый компост: **10–15 л/м²**
2. При тяжёлых почвах: **10 л песка/м²**
3. Азофоска NPK 16-16-16: **20–40 г/м²** при перекопке.

---

## 2. Ранняя весна

### Задачи питания

1. Восстановить корни после зимы.
2. Быстро нарастить здоровую листву.
3. Подготовить куст к цветению.
"""
        output = str(PROJECT_ROOT / "data" / "article_pdfs" / "test.pdf")
        path = generate_pdf(
            test_text,
            output,
            culture_key="strawberry",
            variety_key="summer",
            category_key="nutrition",
            topic="Питание растений — Клубника летняя",
        )
        print(f"✓ Тест PDF: {path}")
        return

    if args.input:
        text = Path(args.input).read_text(encoding='utf-8')
        output = args.output or args.input.replace('.md', '.pdf')
        path = generate_pdf(
            text, output,
            culture_key=args.culture,
            variety_key=args.variety,
            category_key=args.category,
            topic=args.topic,
        )
        print(f"✓ PDF создан: {path}")


if __name__ == '__main__':
    main()
