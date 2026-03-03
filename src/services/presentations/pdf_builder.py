# src/services/presentations/pdf_builder.py

"""
Сборка PNG-слайдов в PDF файл.

Использует img2pdf для лёгкой сборки без потери качества.
Fallback на Pillow если img2pdf недоступен.
"""

import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


async def build_pdf(image_paths: List[str], output_path: str) -> str:
    """
    Собирает PNG-изображения в PDF.

    Args:
        image_paths: Список путей к PNG файлам (в порядке слайдов)
        output_path: Путь для сохранения PDF

    Returns:
        Путь к PDF файлу
    """
    if not image_paths:
        raise ValueError("Нет изображений для сборки PDF")

    # Проверяем что все файлы существуют
    existing = []
    for p in image_paths:
        if Path(p).exists():
            existing.append(p)
        else:
            logger.warning(f"[pdf_builder] Файл не найден, пропускаем: {p}")

    if not existing:
        raise ValueError("Ни одного изображения не найдено для PDF")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    try:
        import img2pdf
        # img2pdf — лёгкая библиотека, без перекодирования
        with open(output_path, "wb") as f:
            f.write(img2pdf.convert(existing))
        logger.info(f"[pdf_builder] PDF собран (img2pdf): {output_path}, {len(existing)} слайдов")
        return output_path
    except ImportError:
        logger.info("[pdf_builder] img2pdf недоступен, используем Pillow")

    # Fallback: Pillow
    from PIL import Image

    images = []
    for p in existing:
        img = Image.open(p).convert("RGB")
        images.append(img)

    if len(images) == 1:
        images[0].save(output_path, "PDF")
    else:
        images[0].save(output_path, "PDF", save_all=True, append_images=images[1:])

    logger.info(f"[pdf_builder] PDF собран (Pillow): {output_path}, {len(images)} слайдов")
    return output_path
