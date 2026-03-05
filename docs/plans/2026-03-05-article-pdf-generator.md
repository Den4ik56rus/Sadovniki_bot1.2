# Article PDF Generator Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Создать систему генерации профессиональных PDF-документов по статьям культур — флагманский платный продукт, красивый природный стиль.

**Architecture:** WeasyPrint (HTML/CSS → PDF) + Jinja2-шаблон + Python-скрипты. Один PDF на статью (culture_key + category_key + variety_key). Батч-скрипт забирает все статьи из БД и генерирует ~48 PDF-файлов в `data/article_pdfs/`.

**Tech Stack:** WeasyPrint, Jinja2, markdown (python lib), asyncpg, PostgreSQL

---

## Контекст БД

- Таблица `admin_articles` (БД `garden_bot`, пользователь `bot_user`)
- Ключевые поля: `id, topic, article_text, culture_key, variety_key, category_key`
- 48 статей с заполненными culture_key: 6 культур × 6 категорий, малина и клубника с variety_key (summer/remontant)
- Статьи в Markdown-разметке: `## h2`, `### h3`, `**bold**`, `-` списки, `1.` нумерованные, `---` разделители

## Структура PDF

- **Обложка** (стр 1): тёмно-зелёный фон, название культуры, категория, лого, декор SVG
- **Оглавление** (стр 2): список `##` заголовков из статьи
- **Контент** (стр 3..N): колонтитулы, форматированный Markdown

## Цвета (из design system)

```
--green: #4A7C59
--berry: #C75B5B
--cream: #FDFBF7
--dark-green: #1A3A2A
--text: #2C2C2C
```

## Названия культур и категорий (RU)

```python
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
```

---

## Task 1: Установить зависимости

**Files:**
- Modify: `requirements.txt`

**Step 1: Добавить weasyprint и markdown в requirements.txt**

```
weasyprint>=60.0
markdown>=3.6
```

Note: `jinja2` уже есть (используется в admin-webapp), `asyncpg` уже есть.

**Step 2: Установить локально**

```bash
pip install weasyprint markdown
```

На macOS если нет Pango:
```bash
brew install pango
```

**Step 3: Проверить установку**

```bash
python3 -c "import weasyprint; import markdown; print('OK')"
```

Expected: `OK`

**Step 4: Commit**

```bash
git add requirements.txt
git commit -m "feat: add weasyprint + markdown for PDF generation"
```

---

## Task 2: Скачать шрифты офлайн

**Files:**
- Create dir: `scripts/fonts/`
- Create: `scripts/fonts/CormorantGaramond-Regular.woff2`
- Create: `scripts/fonts/CormorantGaramond-Bold.woff2`
- Create: `scripts/fonts/CormorantGaramond-Italic.woff2`
- Create: `scripts/fonts/SourceSans3-Regular.woff2`
- Create: `scripts/fonts/SourceSans3-Bold.woff2`

**Step 1: Скачать Cormorant Garamond**

```bash
mkdir -p scripts/fonts
cd scripts/fonts

# Cormorant Garamond от Google Fonts
curl -L "https://fonts.gstatic.com/s/cormorantgaramond/v21/co3YmX5slCNuHLi8bLeY9MK7whWMhyjQAllvuQ.woff2" -o CormorantGaramond-Regular.woff2
curl -L "https://fonts.gstatic.com/s/cormorantgaramond/v21/co3bmX5slCNuHLi8bLeY9MK7whWMhyjYpHtKky8.woff2" -o CormorantGaramond-Bold.woff2
curl -L "https://fonts.gstatic.com/s/cormorantgaramond/v21/co3ZmX5slCNuHLi8bLeY9MK7whWMhyjQlnphJqA.woff2" -o CormorantGaramond-Italic.woff2
```

**Step 2: Скачать Source Sans 3**

```bash
curl -L "https://fonts.gstatic.com/s/sourcesans3/v15/nwpBtKy2OAdR1K-IwhWudF-R3woAa8opPOrG97lwqDlJ9C4Hn9gP.woff2" -o SourceSans3-Regular.woff2
curl -L "https://fonts.gstatic.com/s/sourcesans3/v15/nwpBtKy2OAdR1K-IwhWudF-R3woAa8opPOrG97lwqDlJ9C4Hn9gP.woff2" -o SourceSans3-Bold.woff2
```

Note: Если curl-ссылки устарели — просто открыть https://fonts.google.com/specimen/Cormorant+Garamond в браузере → Download family → распаковать .woff2 файлы в `scripts/fonts/`. То же для Source Sans 3.

**Step 3: Проверить что файлы есть**

```bash
ls -la scripts/fonts/*.woff2
```

Expected: 5 файлов размером > 50KB каждый

**Step 4: Добавить в .gitignore или закоммитить**

Шрифты бинарные — лучше закоммитить (небольшие, нужны на сервере):

```bash
cd ..  # обратно в корень проекта
git add scripts/fonts/
git commit -m "feat: add offline fonts for PDF generation"
```

---

## Task 3: Создать CSS шаблон

**Files:**
- Create: `scripts/pdf_styles.css`

**Step 1: Создать файл `scripts/pdf_styles.css`**

```css
/* ═══════════════════════════════════════
   PDF STYLES — Садовники (WeasyPrint)
   Природный/органический стиль
   ═══════════════════════════════════════ */

/* Шрифты */
@font-face {
    font-family: 'CormorantGaramond';
    src: url('fonts/CormorantGaramond-Regular.woff2') format('woff2');
    font-weight: 400;
    font-style: normal;
}
@font-face {
    font-family: 'CormorantGaramond';
    src: url('fonts/CormorantGaramond-Bold.woff2') format('woff2');
    font-weight: 700;
    font-style: normal;
}
@font-face {
    font-family: 'CormorantGaramond';
    src: url('fonts/CormorantGaramond-Italic.woff2') format('woff2');
    font-weight: 400;
    font-style: italic;
}
@font-face {
    font-family: 'SourceSans3';
    src: url('fonts/SourceSans3-Regular.woff2') format('woff2');
    font-weight: 400;
}
@font-face {
    font-family: 'SourceSans3';
    src: url('fonts/SourceSans3-Bold.woff2') format('woff2');
    font-weight: 700;
}

/* Страница по умолчанию */
@page {
    size: A4;
    margin: 20mm 18mm 22mm 18mm;

    @top-right {
        content: string(culture-name);
        font-family: 'SourceSans3', sans-serif;
        font-size: 8pt;
        color: #4A7C59;
        letter-spacing: 0.05em;
    }

    @bottom-center {
        content: counter(page);
        font-family: 'SourceSans3', sans-serif;
        font-size: 8pt;
        color: #999;
    }

    border-top: 2px solid #4A7C59;
}

/* Обложка — без колонтитулов */
@page cover {
    margin: 0;
    border-top: none;

    @top-right { content: none; }
    @bottom-center { content: none; }
}

/* Оглавление */
@page toc {
    margin: 20mm 18mm 22mm 18mm;
    border-top: 2px solid #4A7C59;

    @top-right { content: none; }
    @bottom-center {
        content: counter(page);
        font-family: 'SourceSans3', sans-serif;
        font-size: 8pt;
        color: #999;
    }
}

/* ═══════════════════ БАЗОВЫЕ СТИЛИ ═══════════════════ */

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: 'SourceSans3', 'Source Sans Pro', sans-serif;
    font-size: 10.5pt;
    line-height: 1.65;
    color: #2C2C2C;
    background: #FDFBF7;
}

/* Скрытый элемент для string() в колонтитуле */
#culture-name-string {
    string-set: culture-name content();
    position: absolute;
    visibility: hidden;
    height: 0;
}

/* ═══════════════════ ОБЛОЖКА ═══════════════════ */

.cover-page {
    page: cover;
    page-break-after: always;
    width: 210mm;
    height: 297mm;
    background: #1A3A2A;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
}

.cover-ornament {
    position: absolute;
    top: 0;
    right: 0;
    opacity: 0.12;
    width: 280px;
}

.cover-ornament-bottom {
    position: absolute;
    bottom: 0;
    left: 0;
    opacity: 0.08;
    width: 220px;
    transform: rotate(180deg);
}

.cover-brand {
    position: absolute;
    top: 30px;
    left: 40px;
    color: rgba(255,255,255,0.5);
    font-family: 'SourceSans3', sans-serif;
    font-size: 9pt;
    letter-spacing: 0.15em;
    text-transform: uppercase;
}

.cover-content {
    text-align: center;
    padding: 0 50px;
    z-index: 1;
}

.cover-category {
    font-family: 'SourceSans3', sans-serif;
    font-size: 9pt;
    color: #4A7C59;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    margin-bottom: 16px;
}

.cover-culture {
    font-family: 'CormorantGaramond', Georgia, serif;
    font-size: 56pt;
    font-weight: 700;
    color: #FDFBF7;
    line-height: 1.1;
    margin-bottom: 20px;
}

.cover-subtitle {
    font-family: 'CormorantGaramond', Georgia, serif;
    font-size: 20pt;
    font-style: italic;
    color: rgba(253, 251, 247, 0.7);
    line-height: 1.3;
}

.cover-divider {
    width: 60px;
    height: 2px;
    background: #4A7C59;
    margin: 24px auto;
}

.cover-footer {
    position: absolute;
    bottom: 40px;
    left: 0;
    right: 0;
    text-align: center;
}

.cover-logo-area {
    color: rgba(255,255,255,0.4);
    font-family: 'SourceSans3', sans-serif;
    font-size: 8pt;
    letter-spacing: 0.1em;
}

.cover-year {
    color: rgba(255,255,255,0.25);
    font-size: 8pt;
    margin-top: 6px;
}

/* ═══════════════════ ОГЛАВЛЕНИЕ ═══════════════════ */

.toc-page {
    page: toc;
    page-break-after: always;
    padding: 0;
}

.toc-header {
    font-family: 'CormorantGaramond', Georgia, serif;
    font-size: 28pt;
    font-weight: 700;
    color: #1A3A2A;
    margin-bottom: 24px;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(74,124,89,0.3);
}

.toc-item {
    display: flex;
    align-items: baseline;
    padding: 7px 0;
    border-bottom: 1px dotted rgba(74,124,89,0.2);
}

.toc-number {
    font-family: 'CormorantGaramond', Georgia, serif;
    font-size: 13pt;
    font-weight: 700;
    color: #4A7C59;
    min-width: 28px;
}

.toc-title {
    font-family: 'SourceSans3', sans-serif;
    font-size: 10pt;
    color: #2C2C2C;
    flex: 1;
}

.toc-dots {
    flex: 1;
    border-bottom: 1px dotted #ccc;
    margin: 0 8px;
    height: 1em;
    max-width: 80px;
}

/* ═══════════════════ КОНТЕНТ ═══════════════════ */

.content-page {
    /* колонтитулы через @page */
}

/* H2 — основные разделы */
h2 {
    font-family: 'CormorantGaramond', Georgia, serif;
    font-size: 20pt;
    font-weight: 700;
    color: #FDFBF7;
    background: #1A3A2A;
    padding: 10px 16px;
    margin: 24px -18mm 16px -18mm;
    page-break-after: avoid;
}

/* H3 — подразделы */
h3 {
    font-family: 'CormorantGaramond', Georgia, serif;
    font-size: 15pt;
    font-weight: 400;
    font-style: italic;
    color: #1A3A2A;
    margin: 20px 0 10px;
    padding-left: 12px;
    border-left: 3px solid #4A7C59;
    page-break-after: avoid;
}

/* H4 */
h4 {
    font-family: 'SourceSans3', sans-serif;
    font-size: 11pt;
    font-weight: 700;
    color: #4A7C59;
    margin: 16px 0 8px;
    page-break-after: avoid;
}

/* Параграф */
p {
    margin-bottom: 10px;
    text-align: justify;
    hyphens: auto;
    -webkit-hyphens: auto;
}

/* Списки */
ul {
    margin: 8px 0 12px 0;
    padding-left: 0;
    list-style: none;
}

ul li {
    padding: 3px 0 3px 20px;
    position: relative;
    margin-bottom: 2px;
}

ul li::before {
    content: "●";
    color: #4A7C59;
    font-size: 7pt;
    position: absolute;
    left: 4px;
    top: 6px;
}

ol {
    margin: 8px 0 12px 0;
    padding-left: 0;
    list-style: none;
    counter-reset: ol-counter;
}

ol li {
    padding: 3px 0 3px 28px;
    position: relative;
    counter-increment: ol-counter;
    margin-bottom: 2px;
}

ol li::before {
    content: counter(ol-counter) ".";
    color: #4A7C59;
    font-weight: 700;
    font-family: 'CormorantGaramond', Georgia, serif;
    font-size: 12pt;
    position: absolute;
    left: 0;
    top: 2px;
}

/* Вложенные списки */
ul ul, ol ul, ul ol, ol ol {
    margin: 4px 0 4px 0;
}

/* Жирный */
strong {
    font-weight: 700;
    color: #1A3A2A;
}

/* Курсив */
em {
    font-style: italic;
    color: #555;
}

/* Горизонтальный разделитель */
hr {
    border: none;
    border-top: 1px solid rgba(74,124,89,0.3);
    margin: 20px 0;
    position: relative;
}

/* Блоки "Важно" — параграфы начинающиеся с Важно: или Note: */
.callout-important {
    background: rgba(199, 91, 91, 0.08);
    border-left: 4px solid #C75B5B;
    padding: 10px 14px;
    margin: 12px 0;
    border-radius: 0 4px 4px 0;
}

.callout-important strong {
    color: #C75B5B;
}

/* Инлайн-код */
code {
    font-family: monospace;
    background: rgba(74,124,89,0.1);
    color: #1A3A2A;
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 9pt;
}

/* Таблицы */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 9.5pt;
}

th {
    background: #4A7C59;
    color: white;
    padding: 7px 10px;
    text-align: left;
    font-family: 'SourceSans3', sans-serif;
    font-weight: 700;
}

td {
    padding: 6px 10px;
    border-bottom: 1px solid rgba(74,124,89,0.2);
}

tr:nth-child(even) td {
    background: rgba(74,124,89,0.05);
}

/* Разрыв страницы перед h2 (кроме первого) */
h2 + * { page-break-before: avoid; }
```

**Step 2: Commit**

```bash
git add scripts/pdf_styles.css
git commit -m "feat: add PDF CSS template for article documents"
```

---

## Task 4: Создать HTML шаблон

**Files:**
- Create: `scripts/pdf_template.html`

**Step 1: Создать файл `scripts/pdf_template.html`**

```html
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<link rel="stylesheet" href="{{ css_path }}">
</head>
<body>

<!-- Строка для колонтитула -->
<div id="culture-name-string">{{ culture_name }}{% if variety_label %} {{ variety_label }}{% endif %}</div>

<!-- ═══════════════ ОБЛОЖКА ═══════════════ -->
<div class="cover-page">

  <div class="cover-brand">Садовники</div>

  <!-- Декоративный SVG орнамент (листья и ягоды) -->
  <svg class="cover-ornament" viewBox="0 0 300 400" xmlns="http://www.w3.org/2000/svg" fill="none">
    <path d="M150 20 C180 60 220 80 260 70 C240 110 200 130 160 120 C190 150 210 190 200 230 C170 210 150 180 140 150 C130 180 110 210 80 230 C70 190 90 150 120 120 C80 130 40 110 20 70 C60 80 100 60 130 20 Z" fill="#4A7C59" opacity="0.6"/>
    <circle cx="150" cy="160" r="25" fill="#C75B5B" opacity="0.5"/>
    <circle cx="120" cy="185" r="18" fill="#C75B5B" opacity="0.4"/>
    <circle cx="178" cy="178" r="20" fill="#C75B5B" opacity="0.45"/>
    <path d="M80 250 C100 230 130 225 150 240 C130 255 105 260 80 250 Z" fill="#4A7C59" opacity="0.5"/>
    <path d="M220 250 C200 230 170 225 150 240 C170 255 195 260 220 250 Z" fill="#4A7C59" opacity="0.4"/>
    <path d="M60 300 C90 280 120 290 130 310 C105 320 75 315 60 300 Z" fill="#4A7C59" opacity="0.35"/>
    <path d="M240 300 C210 280 180 290 170 310 C195 320 225 315 240 300 Z" fill="#4A7C59" opacity="0.3"/>
    <line x1="150" y1="20" x2="150" y2="340" stroke="#4A7C59" stroke-width="1.5" opacity="0.3"/>
    <line x1="150" y1="120" x2="80" y2="230" stroke="#4A7C59" stroke-width="1" opacity="0.2"/>
    <line x1="150" y1="120" x2="220" y2="230" stroke="#4A7C59" stroke-width="1" opacity="0.2"/>
  </svg>

  <svg class="cover-ornament-bottom" viewBox="0 0 300 400" xmlns="http://www.w3.org/2000/svg" fill="none">
    <path d="M150 20 C180 60 220 80 260 70 C240 110 200 130 160 120 C190 150 210 190 200 230 C170 210 150 180 140 150 C130 180 110 210 80 230 C70 190 90 150 120 120 C80 130 40 110 20 70 C60 80 100 60 130 20 Z" fill="#4A7C59"/>
    <circle cx="150" cy="160" r="25" fill="#C75B5B"/>
    <circle cx="120" cy="185" r="18" fill="#C75B5B"/>
    <circle cx="178" cy="178" r="20" fill="#C75B5B"/>
  </svg>

  <div class="cover-content">
    <div class="cover-category">{{ category_label }}</div>
    <div class="cover-culture">{{ culture_name }}{% if variety_label %}<br><span style="font-size:32pt;font-weight:400">{{ variety_label }}</span>{% endif %}</div>
    <div class="cover-divider"></div>
    <div class="cover-subtitle">{{ topic }}</div>
  </div>

  <div class="cover-footer">
    {% if logo_path %}
    <img src="{{ logo_path }}" style="height:32px;margin-bottom:8px;opacity:0.7">
    {% endif %}
    <div class="cover-logo-area">Садовники — профессиональные советы</div>
    <div class="cover-year">{{ year }}</div>
  </div>

</div>

<!-- ═══════════════ ОГЛАВЛЕНИЕ ═══════════════ -->
<div class="toc-page">
  <div class="toc-header">Содержание</div>
  {% for item in toc %}
  <div class="toc-item">
    <span class="toc-number">{{ loop.index }}.</span>
    <span class="toc-title">{{ item }}</span>
  </div>
  {% endfor %}
</div>

<!-- ═══════════════ КОНТЕНТ ═══════════════ -->
<div class="content-page">
{{ article_html }}
</div>

</body>
</html>
```

**Step 2: Commit**

```bash
git add scripts/pdf_template.html
git commit -m "feat: add PDF HTML template with cover and TOC"
```

---

## Task 5: Написать конвертер md_to_pdf.py

**Files:**
- Create: `scripts/md_to_pdf.py`

**Step 1: Создать файл `scripts/md_to_pdf.py`**

```python
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
```

**Step 2: Проверить что создаётся тестовый PDF**

```bash
python scripts/md_to_pdf.py --test
```

Expected: `✓ Тест PDF: data/article_pdfs/test.pdf`

Открыть файл и проверить визуально.

**Step 3: Commit**

```bash
git add scripts/md_to_pdf.py
git commit -m "feat: add md_to_pdf.py converter with WeasyPrint"
```

---

## Task 6: Написать батч-генератор

**Files:**
- Create: `scripts/generate_article_pdfs.py`

**Step 1: Создать файл `scripts/generate_article_pdfs.py`**

```python
#!/usr/bin/env python3
"""
Батч-генерация всех PDF из таблицы admin_articles.

Использование:
    python scripts/generate_article_pdfs.py
    python scripts/generate_article_pdfs.py --dry-run     # только список без генерации
    python scripts/generate_article_pdfs.py --culture strawberry  # одна культура

Требует доступа к БД (bot_user@garden_bot через localhost:5432).
"""

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import asyncpg

# Импортируем конвертер из соседнего скрипта
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from md_to_pdf import generate_pdf


DB_DSN = "postgresql://bot_user:bot_password@localhost:5432/garden_bot"

OUTPUT_DIR = PROJECT_ROOT / "data" / "article_pdfs"


async def get_articles(pool: asyncpg.Pool, culture_filter: str = None) -> list[dict]:
    """Получает все статьи с заполненными ключами."""
    query = """
        SELECT id, topic, article_text, culture_key, variety_key, category_key
        FROM admin_articles
        WHERE culture_key IS NOT NULL AND culture_key != ''
    """
    params = []
    if culture_filter:
        query += " AND culture_key = $1"
        params.append(culture_filter)

    query += " ORDER BY culture_key, variety_key, category_key"

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    return [dict(r) for r in rows]


def get_output_path(culture_key: str, variety_key: str, category_key: str) -> Path:
    """Формирует путь для PDF файла."""
    if variety_key:
        folder = OUTPUT_DIR / f"{culture_key}_{variety_key}"
    else:
        folder = OUTPUT_DIR / culture_key
    return folder / f"{category_key}.pdf"


async def main():
    parser = argparse.ArgumentParser(description='Батч-генерация PDF статей')
    parser.add_argument('--dry-run', action='store_true', help='Список без генерации')
    parser.add_argument('--culture', help='Фильтр по культуре')
    parser.add_argument('--force', action='store_true', help='Перегенерировать существующие')
    parser.add_argument('--dsn', default=DB_DSN, help='DSN строка подключения к БД')
    args = parser.parse_args()

    print(f"Подключение к БД: {args.dsn.split('@')[1]}...")
    pool = await asyncpg.create_pool(args.dsn)

    articles = await get_articles(pool, culture_filter=args.culture)
    print(f"Найдено статей: {len(articles)}")

    if args.dry_run:
        for a in articles:
            path = get_output_path(a['culture_key'], a['variety_key'] or '', a['category_key'])
            exists = "✓" if path.exists() else "○"
            print(f"  {exists} {a['topic']} → {path.relative_to(PROJECT_ROOT)}")
        await pool.close()
        return

    generated = 0
    skipped = 0
    errors = []

    for a in articles:
        path = get_output_path(a['culture_key'], a['variety_key'] or '', a['category_key'])

        if path.exists() and not args.force:
            skipped += 1
            print(f"  SKIP  {a['topic']}")
            continue

        try:
            generate_pdf(
                article_text=a['article_text'],
                output_path=str(path),
                culture_key=a['culture_key'] or '',
                variety_key=a['variety_key'] or '',
                category_key=a['category_key'] or '',
                topic=a['topic'],
            )
            size_kb = path.stat().st_size // 1024
            generated += 1
            print(f"  OK    {a['topic']} ({size_kb} KB)")
        except Exception as e:
            errors.append((a['topic'], e))
            print(f"  ERR   {a['topic']}: {e}")

    await pool.close()

    print(f"\n{'='*50}")
    print(f"Готово: {generated} создано, {skipped} пропущено, {len(errors)} ошибок")
    if errors:
        print("\nОшибки:")
        for topic, err in errors:
            print(f"  {topic}: {err}")


if __name__ == '__main__':
    asyncio.run(main())
```

**Step 2: Тест dry-run (нужен доступ к БД)**

На сервере (или с проброшенным портом 5432):
```bash
python scripts/generate_article_pdfs.py --dry-run
```

Expected: список из 48 статей со статусом ○ (не созданы)

**Step 3: Генерация одной культуры для проверки**

```bash
python scripts/generate_article_pdfs.py --culture strawberry
```

Expected: создаются файлы `data/article_pdfs/strawberry_summer/*.pdf` и `data/article_pdfs/strawberry_remontant/*.pdf`

**Step 4: Commit**

```bash
git add scripts/generate_article_pdfs.py
git commit -m "feat: add batch PDF generator for all article cultures"
```

---

## Task 7: Добавить логотип (когда будет готов)

**Files:**
- Create: `scripts/assets/logo.png` (или `.svg`)
- Modify: `scripts/generate_article_pdfs.py` (добавить путь к лого)

**Step 1: Поместить файл логотипа**

```bash
mkdir -p scripts/assets
# Скопировать logo.png в scripts/assets/logo.png
```

**Step 2: Обновить вызов generate_pdf в батч-скрипте**

В `scripts/generate_article_pdfs.py`, в вызове `generate_pdf(...)` добавить:

```python
logo_path=str(PROJECT_ROOT / "scripts" / "assets" / "logo.png"),
```

**Step 3: Проверить что лого отображается на обложке**

```bash
python scripts/md_to_pdf.py --test
```

Открыть PDF и проверить обложку.

**Step 4: Commit**

```bash
git add scripts/assets/logo.png scripts/generate_article_pdfs.py
git commit -m "feat: add logo to PDF cover page"
```

---

## Task 8: Задокументировать

**Files:**
- Create: `docs/features/ARTICLE_PDFS.md`

**Step 1: Создать документацию**

```markdown
# Article PDFs — Генерация PDF-продуктов по культурам

## Обзор

Флагманский платный продукт: профессиональные PDF-руководства по культурам.
Один PDF = одна культура + категория статьи (~25-35 страниц).
Пользователи получают PDF после оплаты через бота.

## Структура PDF

1. **Обложка** — тёмно-зелёный фон, название культуры, категория, лого
2. **Оглавление** — автоматически из ## заголовков статьи
3. **Контент** — форматированный Markdown с колонтитулами

## Генерация

### Предварительно

```bash
pip install weasyprint markdown
# На macOS: brew install pango
# На Ubuntu: apt install libpango-1.0-0 libpangoft2-1.0-0
```

### Тест одного PDF

```bash
python scripts/md_to_pdf.py --test
# → data/article_pdfs/test.pdf
```

### Батч-генерация всех PDF

```bash
python scripts/generate_article_pdfs.py
# → data/article_pdfs/{culture}_{variety}/{category}.pdf
```

### Обновить конкретную культуру

```bash
python scripts/generate_article_pdfs.py --culture raspberry --force
```

## Расположение файлов

- Шаблон: `scripts/pdf_template.html`
- Стили: `scripts/pdf_styles.css`
- Шрифты: `scripts/fonts/*.woff2`
- Логотип: `scripts/assets/logo.png`
- Выходные PDF: `data/article_pdfs/{culture_key}_{variety_key}/{category_key}.pdf`
- Конвертер: `scripts/md_to_pdf.py`
- Батч: `scripts/generate_article_pdfs.py`

## БД

Таблица `admin_articles`, поля: `culture_key, variety_key, category_key, article_text, topic`.
```

**Step 2: Commit**

```bash
git add docs/features/ARTICLE_PDFS.md
git commit -m "docs: add ARTICLE_PDFS.md documentation"
```

---

## Верификация

1. `python scripts/md_to_pdf.py --test` → `data/article_pdfs/test.pdf` создан, открывается
2. Визуально проверить: обложка тёмно-зелёная, оглавление есть, заголовки h2 с фоном, списки с зелёными маркерами
3. `python scripts/generate_article_pdfs.py --dry-run` → список 48 статей
4. `python scripts/generate_article_pdfs.py --culture strawberry` → 12 PDF создаются
5. Проверить размеры файлов: ожидаемо 500KB–3MB каждый

## Примечания

- **DSN для БД на сервере:** `postgresql://bot_user:bot_password@localhost:5432/garden_bot` — запускать на самом сервере или с SSH-туннелем
- **WeasyPrint на сервере (Ubuntu):** `apt install libpango-1.0-0 libpangoft2-1.0-0 libcairo2`
- **Шрифты** должны быть в `scripts/fonts/` — WeasyPrint на сервере не имеет доступа к Google Fonts
