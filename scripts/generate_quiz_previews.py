#!/usr/bin/env python3
"""Генерация превью (размытый первый слайд + замок) для всех quiz solutions."""

import sys
import os
from pathlib import Path

# Добавляем корень проекта в sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.services.pdf_preview import generate_blurred_preview


def main():
    quiz_dir = PROJECT_ROOT / "data" / "quiz_solutions"
    if not quiz_dir.exists():
        print(f"Папка не найдена: {quiz_dir}")
        return

    generated = 0
    skipped = 0
    errors = []

    for solution_pdf in sorted(quiz_dir.rglob("solution.pdf")):
        preview_path = solution_pdf.parent / "preview.jpg"

        if preview_path.exists():
            skipped += 1
            print(f"  SKIP  {solution_pdf.parent.relative_to(quiz_dir)} (уже есть)")
            continue

        try:
            generate_blurred_preview(str(solution_pdf), str(preview_path))
            generated += 1
            size_kb = preview_path.stat().st_size // 1024
            print(f"  OK    {solution_pdf.parent.relative_to(quiz_dir)} ({size_kb} KB)")
        except Exception as e:
            errors.append((solution_pdf, e))
            print(f"  ERR   {solution_pdf.parent.relative_to(quiz_dir)}: {e}")

    print(f"\nИтого: {generated} создано, {skipped} пропущено, {len(errors)} ошибок")


if __name__ == "__main__":
    main()
