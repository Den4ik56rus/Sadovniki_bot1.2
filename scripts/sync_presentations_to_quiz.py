#!/usr/bin/env python3
"""
Синхронизация презентаций → quiz_solutions.

Копирует PDF из data/content/presentations/{culture}/{problem_key}.pdf
в data/quiz_solutions/{culture}/{problem}/solution.pdf

Запуск:
    python scripts/sync_presentations_to_quiz.py          # без перезаписи
    python scripts/sync_presentations_to_quiz.py --force   # с перезаписью
    python scripts/sync_presentations_to_quiz.py --dry-run  # только показать что будет скопировано
"""

import argparse
import os
import shutil
import sys

# Добавляем корень проекта в sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.services.quiz_solutions import _KEY_TO_PATH

PRESENTATIONS_DIR = os.path.join(ROOT, "data", "content", "presentations")
QUIZ_SOLUTIONS_DIR = os.path.join(ROOT, "data", "quiz_solutions")


def find_presentation_pdf(culture_folder: str, problem_key: str) -> str | None:
    """Ищет PDF презентации для данного problem_key."""
    candidate = os.path.join(PRESENTATIONS_DIR, culture_folder, f"{problem_key}.pdf")
    if os.path.exists(candidate):
        return candidate
    return None


def main():
    parser = argparse.ArgumentParser(description="Синхронизация презентаций в quiz_solutions")
    parser.add_argument("--force", action="store_true", help="Перезаписать существующие solution.pdf")
    parser.add_argument("--dry-run", action="store_true", help="Только показать что будет скопировано")
    args = parser.parse_args()

    if not os.path.exists(PRESENTATIONS_DIR):
        print(f"❌ Директория презентаций не найдена: {PRESENTATIONS_DIR}")
        print("   Убедитесь что презентации сгенерированы через пакетную генерацию.")
        sys.exit(1)

    copied = 0
    skipped = 0
    not_found = 0

    for problem_key, (culture_folder, problem_folder) in sorted(_KEY_TO_PATH.items()):
        src = find_presentation_pdf(culture_folder, problem_key)
        dest_dir = os.path.join(QUIZ_SOLUTIONS_DIR, culture_folder, problem_folder)
        dest = os.path.join(dest_dir, "solution.pdf")

        if src is None:
            print(f"  ⚪ {problem_key}: презентация не найдена")
            not_found += 1
            continue

        if os.path.exists(dest) and not args.force:
            print(f"  ⏭️  {problem_key}: solution.pdf уже есть (--force для перезаписи)")
            skipped += 1
            continue

        if args.dry_run:
            print(f"  🔵 {problem_key}: будет скопирован → {dest}")
            copied += 1
            continue

        os.makedirs(dest_dir, exist_ok=True)
        shutil.copy2(src, dest)
        print(f"  ✅ {problem_key}: скопирован → {dest}")
        copied += 1

    print()
    action = "будет скопировано" if args.dry_run else "скопировано"
    print(f"📊 Итого: {action} {copied}, пропущено {skipped}, не найдено {not_found}")
    print(f"   Всего ключей: {len(_KEY_TO_PATH)}")


if __name__ == "__main__":
    main()
