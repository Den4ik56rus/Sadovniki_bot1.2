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
pip install weasyprint markdown jinja2
# На macOS: brew install pango
# На Ubuntu: apt install libpango-1.0-0 libpangoft2-1.0-0 libcairo2
```

На macOS обязательно использовать `DYLD_LIBRARY_PATH=/opt/homebrew/lib` при запуске.

### Тест одного PDF

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/lib python scripts/md_to_pdf.py --test
# → data/article_pdfs/test.pdf
```

### Батч-генерация всех PDF

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/lib python scripts/generate_article_pdfs.py
# → data/article_pdfs/{culture}_{variety}/{category}.pdf
```

### Обновить конкретную культуру

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/lib python scripts/generate_article_pdfs.py --culture raspberry --force
```

### Dry-run (список без генерации)

```bash
python scripts/generate_article_pdfs.py --dry-run
```

## Расположение файлов

- Шаблон: `scripts/pdf_template.html`
- Стили: `scripts/pdf_styles.css`
- Шрифты: `scripts/fonts/*.ttf` (Cormorant Garamond + Source Sans 3)
- Логотип: `scripts/assets/logo.png` (добавить когда будет готов)
- Выходные PDF: `data/article_pdfs/{culture_key}_{variety_key}/{category_key}.pdf`
- Конвертер: `scripts/md_to_pdf.py`
- Батч: `scripts/generate_article_pdfs.py`

## БД

Таблица `admin_articles`, поля: `culture_key, variety_key, category_key, article_text, topic`.

## Сервер (Ubuntu)

```bash
apt install libpango-1.0-0 libpangoft2-1.0-0 libcairo2
pip install weasyprint markdown jinja2
python scripts/generate_article_pdfs.py
```

На сервере `DYLD_LIBRARY_PATH` не нужен (Linux находит библиотеки автоматически).
