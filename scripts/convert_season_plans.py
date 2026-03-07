#!/usr/bin/env python3
"""
Конвертация markdown-текстов сезонных планов в структурированные данные
и генерация PDF через care_plan шаблон.

Использует GPT-5.1 для парсинга markdown → JSON (shopping_list + care_steps).

Использование:
    python scripts/convert_season_plans.py                    # все культуры
    python scripts/convert_season_plans.py --culture raspberry_summer  # одна
    python scripts/convert_season_plans.py --dry-run          # только конвертация без PDF
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from openai import OpenAI

SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

ARTICLE_PDFS_DIR = PROJECT_ROOT / "data" / "article_pdfs"
FLAGSHIP_DIR = PROJECT_ROOT / "data" / "flagship"

CULTURES = {
    "blackberry": {"culture": "blackberry", "variety": "", "label": "Ежевика", "subtitle": ""},
    "blueberry": {"culture": "blueberry", "variety": "", "label": "Голубика", "subtitle": ""},
    "currant": {"culture": "currant", "variety": "", "label": "Смородина", "subtitle": ""},
    "honeysuckle": {"culture": "honeysuckle", "variety": "", "label": "Жимолость", "subtitle": ""},
    "raspberry_remontant": {"culture": "raspberry", "variety": "remontant", "label": "Малина ремонтантная", "subtitle": ""},
    "raspberry_summer": {"culture": "raspberry", "variety": "summer", "label": "Малина летняя", "subtitle": ""},
    "strawberry_remontant": {"culture": "strawberry", "variety": "remontant", "label": "Клубника ремонтантная", "subtitle": "Земляника ремонтантная (НСД) — нейтрального светового дня"},
    "strawberry_summer": {"culture": "strawberry", "variety": "summer", "label": "Клубника летняя", "subtitle": "Земляника садовая (КСД) — короткого светового дня"},
}

SYSTEM_PROMPT = """Ты — агроном-эксперт. Твоя задача — преобразовать текст плана уходовых работ из markdown в строго структурированный JSON.

Формат выхода — JSON объект с полями:
{
  "title": "План основных уходовых работ",
  "subtitle": "<название культуры и тип>",
  "intro_text": "<2-3 абзаца вводного текста о культуре, разделённые \\n\\n>",
  "seasons": [
    {
      "number": 1,
      "title": "Ранняя весна",
      "period": "до распускания почек",
      "intro": "<1-2 предложения — суть этого периода>",
      "shopping_list": [
        {"name": "Название препарата/материала", "type": "Тип (Удобрение/Органика/Фунгицид/Инсектицид/Мульча и т.п.)", "dosage": "дозировка"},
        {"group": "Название группы", "choose": "один на выбор", "options": [
          {"name": "Вариант 1", "dosage": "доза"},
          {"name": "Вариант 2", "dosage": "доза"}
        ]}
      ],
      "care_steps": [
        {"task": "Короткое название задачи (2-4 слова)", "action": "Что делать (1-2 предложения)", "details": "Детали/примечания"}
      ],
      "note": "<Примечание, если есть важная оговорка для этого сезона. null если нет>",
      "subsections": null
    }
  ]
}

ПРАВИЛА:
1. shopping_list — извлеки ВСЕ конкретные препараты, удобрения, материалы с дозировками, упомянутые в тексте для этого сезона. Если есть альтернативы (или/или), используй формат group+options.
2. care_steps — разбей все действия на конкретные шаги. task — очень короткое название (Обрезка, Подкормка, Полив, Обработка от клеща и т.п.). action — что именно делать. details — дозировки, сроки, примечания.
3. Если в тексте есть подразделы (например **Существующий малинник** и **Закладка нового участка**), используй subsections вместо care_steps:
   "subsections": [
     {"title": "Существующий малинник", "intro": null, "shopping_list": [...], "care_steps": [...]}
   ]
   При этом shopping_list и care_steps основного сезона должны быть null.
4. intro_text — напиши 2-3 информативных абзаца о культуре и её особенностях ухода. Не копируй из текста — обобщи.
5. period — краткое описание периода в скобках из заголовка.
6. Не теряй ни одного препарата, дозировки или действия из исходного текста!
7. Верни ТОЛЬКО валидный JSON, без markdown-обёрток."""


def convert_markdown_to_structure(markdown_text: str, culture_info: dict) -> dict:
    """Конвертирует markdown через GPT-5.1 в структуру care_plan_data."""

    user_prompt = f"""Конвертируй следующий план уходовых работ для культуры "{culture_info['label']}" в структурированный JSON.

Subtitle для обложки: "{culture_info.get('subtitle') or culture_info['label']}"

Исходный текст:

{markdown_text}"""

    response = client.chat.completions.create(
        model="gpt-5.1",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    result = json.loads(response.choices[0].message.content)

    # Статистика
    usage = response.usage
    cost = (usage.prompt_tokens * 2.0 + usage.completion_tokens * 8.0) / 1_000_000
    print(f"  Tokens: {usage.prompt_tokens} in + {usage.completion_tokens} out = ${cost:.4f}")

    return result


def generate_care_plan_pdf_from_data(data: dict, output_path: str, culture_name: str) -> str:
    """Генерирует PDF из структурированных данных через care_plan шаблон."""
    from jinja2 import Environment, FileSystemLoader
    from weasyprint import HTML, CSS

    css_path = SCRIPTS_DIR / "pdf_styles.css"
    extra_css_path = SCRIPTS_DIR / "care_plan_extra.css"
    logo_path = SCRIPTS_DIR / "assets" / "logo.png"
    infographic_path = SCRIPTS_DIR / "assets" / "infographic.png"

    env = Environment(loader=FileSystemLoader(str(SCRIPTS_DIR)))
    template = env.get_template("care_plan_template.html")

    # Подготовка данных для шаблона
    seasons = data.get("seasons", [])
    for s in seasons:
        if s.get("subsections") is None:
            s["subsections"] = None
        if s.get("note") is None:
            s["note"] = None
        if s.get("shopping_list") is None:
            s["shopping_list"] = []
        if s.get("care_steps") is None:
            s["care_steps"] = []

    html_content = template.render(
        title=data.get("title", "План основных уходовых работ"),
        subtitle=data.get("subtitle", culture_name),
        intro_text=data.get("intro_text", ""),
        culture_name=culture_name,
        seasons=seasons,
        css_path=str(css_path),
        extra_css_path=str(extra_css_path),
        logo_path=str(logo_path) if logo_path.exists() else None,
        infographic_path=str(infographic_path) if infographic_path.exists() else None,
        year=datetime.now().year,
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    stylesheets = [CSS(filename=str(css_path))]
    if extra_css_path.exists():
        stylesheets.append(CSS(filename=str(extra_css_path)))

    HTML(string=html_content, base_url=str(SCRIPTS_DIR)).write_pdf(
        output_path,
        stylesheets=stylesheets,
    )

    return output_path


def main():
    parser = argparse.ArgumentParser(description="Конвертация сезонных планов → PDF")
    parser.add_argument("--culture", help="Одна культура (например raspberry_summer)")
    parser.add_argument("--dry-run", action="store_true", help="Только конвертация, без PDF")
    parser.add_argument("--save-json", action="store_true", help="Сохранить промежуточный JSON")
    args = parser.parse_args()

    cultures_to_process = {}
    if args.culture:
        if args.culture not in CULTURES:
            print(f"Неизвестная культура: {args.culture}")
            print(f"Доступные: {', '.join(CULTURES.keys())}")
            sys.exit(1)
        cultures_to_process[args.culture] = CULTURES[args.culture]
    else:
        cultures_to_process = CULTURES

    total_cost = 0.0
    results = []

    for folder, info in cultures_to_process.items():
        txt_path = ARTICLE_PDFS_DIR / folder / "season_plan.txt"
        if not txt_path.exists():
            print(f"SKIP {folder}: нет season_plan.txt")
            continue

        print(f"\n{'='*60}")
        print(f"Обработка: {info['label']} ({folder})")
        print(f"{'='*60}")

        markdown_text = txt_path.read_text(encoding="utf-8")
        print(f"  Текст: {len(markdown_text)} символов")

        # Конвертация через LLM
        print(f"  Конвертация через GPT-5.1...")
        data = convert_markdown_to_structure(markdown_text, info)

        seasons_count = len(data.get("seasons", []))
        print(f"  Результат: {seasons_count} сезонов")

        # Сохранить JSON если нужно
        if args.save_json:
            json_path = ARTICLE_PDFS_DIR / folder / "season_plan_structure.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"  JSON: {json_path}")

        if args.dry_run:
            for s in data.get("seasons", []):
                shop = len(s.get("shopping_list") or [])
                steps = len(s.get("care_steps") or [])
                subs = len(s.get("subsections") or [])
                print(f"    {s['number']}. {s['title']}: {shop} покупок, {steps} шагов, {subs} подсекций")
            continue

        # Генерация PDF
        print(f"  Генерация PDF...")
        out_path = FLAGSHIP_DIR / folder / "articles" / "season_plan.pdf"
        generate_care_plan_pdf_from_data(data, str(out_path), info["label"])
        size_kb = out_path.stat().st_size // 1024
        print(f"  OK: {out_path.relative_to(PROJECT_ROOT)} ({size_kb} KB)")
        results.append((folder, out_path, size_kb))

    print(f"\n{'='*60}")
    print(f"Готово!")
    if results:
        print(f"\nСозданные PDF:")
        for folder, path, size in results:
            print(f"  {folder}: {size} KB")


if __name__ == "__main__":
    main()
