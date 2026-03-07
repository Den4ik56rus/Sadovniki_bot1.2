#!/usr/bin/env python3
"""
Генератор PDF "План основных уходовых работ" для клубники.

Использование:
    python scripts/generate_care_plan_pdf.py                     # генерация КСД
    python scripts/generate_care_plan_pdf.py --output path.pdf   # custom путь

Результат: data/article_pdfs/care_plan_ksd.pdf
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS

SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent

# Добавляем scripts/ в sys.path для импорта care_plan_data
sys.path.insert(0, str(SCRIPTS_DIR))
from care_plan_data import get_care_plan_data


def generate_care_plan_pdf(
    variety: str = "ksd",
    output_path: str = None,
) -> str:
    """Генерирует PDF плана уходовых работ."""

    data = get_care_plan_data(variety)

    # Пути к ресурсам
    css_path = SCRIPTS_DIR / "pdf_styles.css"
    extra_css_path = SCRIPTS_DIR / "care_plan_extra.css"
    logo_path = SCRIPTS_DIR / "assets" / "logo.png"
    infographic_path = SCRIPTS_DIR / "assets" / "infographic.png"

    if output_path is None:
        output_path = str(
            PROJECT_ROOT / "data" / "article_pdfs" / f"care_plan_{variety}.pdf"
        )

    # Рендерим шаблон
    env = Environment(loader=FileSystemLoader(str(SCRIPTS_DIR)))
    template = env.get_template("care_plan_template.html")

    html_content = template.render(
        title=data["title"],
        subtitle=data["subtitle"],
        intro_text=data.get("intro_text", ""),
        culture_name="Клубника",
        seasons=data["seasons"],
        css_path=str(css_path),
        extra_css_path=str(extra_css_path),
        logo_path=str(logo_path) if logo_path.exists() else None,
        infographic_path=str(infographic_path) if infographic_path.exists() else None,
        year=datetime.now().year,
    )

    # Генерируем PDF
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
    parser = argparse.ArgumentParser(
        description='Генератор PDF "План уходовых работ"'
    )
    parser.add_argument(
        "--variety", default="ksd",
        choices=["ksd", "remontant"],
        help="Тип клубники (ksd или remontant)",
    )
    parser.add_argument("--output", help="Путь для PDF")
    args = parser.parse_args()

    path = generate_care_plan_pdf(
        variety=args.variety,
        output_path=args.output,
    )
    size_kb = Path(path).stat().st_size // 1024
    print(f"✓ PDF создан: {path} ({size_kb} KB)")


if __name__ == "__main__":
    main()
