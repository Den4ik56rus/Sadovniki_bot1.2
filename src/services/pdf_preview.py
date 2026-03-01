"""
Генератор размытого превью для PDF файлов.

Берёт первую страницу PDF, рендерит в изображение,
накладывает сильный blur + оверлей "Заблокировано" с иконкой замка.
Используется для оффера в воронке — показать что контент есть,
но прочитать нельзя без оплаты.

Зависимости: Pillow, pdftoppm (poppler-utils)
"""

import asyncio
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

# Путь к шрифтам проекта
FONTS_DIR = Path(__file__).parent.parent.parent / "data" / "fonts"
BOLD_FONT = FONTS_DIR / "DejaVuSans-Bold.ttf"

# Директория для превью
PREVIEWS_DIR = Path(__file__).parent.parent.parent / "data" / "previews"


def _remove_watermark(img: Image.Image, margin: int = 15) -> Image.Image:
    """
    Удаляет watermark NotebookLM из правого нижнего угла.
    Определяет цвет фона вокруг watermark и закрашивает область.
    """
    w, h = img.size
    # Область watermark: ~350x80 пикселей в правом нижнем углу (при 150 dpi)
    wm_w = min(350, int(w * 0.13))
    wm_h = min(80, int(h * 0.06))

    # Зона закрашивания (с отступом)
    x1 = w - wm_w - margin
    y1 = h - wm_h - margin
    x2 = w
    y2 = h

    # Семплируем цвет фона — берём полоску пикселей СЛЕВА от watermark
    sample_x = max(0, x1 - 30)
    sample_region = img.crop((sample_x, y1, sample_x + 10, y2))
    pixels = list(sample_region.convert("RGB").tobytes())
    pixels = [(pixels[i], pixels[i+1], pixels[i+2]) for i in range(0, len(pixels), 3)]
    # Медианный цвет (устойчив к выбросам)
    r = sorted([p[0] for p in pixels])[len(pixels) // 2]
    g = sorted([p[1] for p in pixels])[len(pixels) // 2]
    b = sorted([p[2] for p in pixels])[len(pixels) // 2]
    bg_color = (r, g, b)

    draw = ImageDraw.Draw(img)
    draw.rectangle([(x1, y1), (x2, y2)], fill=bg_color)

    return img


def _render_pdf_page_to_image(pdf_path: str, dpi: int = 150) -> Image.Image:
    """Рендерит первую страницу PDF в PIL Image через pdftoppm."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_prefix = os.path.join(tmpdir, "page")
        subprocess.run(
            [
                "pdftoppm",
                "-png",
                "-r", str(dpi),
                "-f", "1",      # первая страница
                "-l", "1",      # только одна
                pdf_path,
                output_prefix,
            ],
            check=True,
            capture_output=True,
        )
        # pdftoppm создаёт файл вида page-1.png или page-01.png
        png_files = list(Path(tmpdir).glob("page-*.png"))
        if not png_files:
            raise FileNotFoundError(f"pdftoppm не создал изображение из {pdf_path}")
        return Image.open(png_files[0]).copy()


def _add_lock_overlay(img: Image.Image) -> Image.Image:
    """Добавляет затемнение + замок + текст 'Заблокировано' по центру."""
    # Создаём полупрозрачный тёмный оверлей
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    w, h = img.size

    # Полупрозрачная полоса по центру
    band_h = int(h * 0.25)
    band_top = (h - band_h) // 2
    draw.rectangle(
        [(0, band_top), (w, band_top + band_h)],
        fill=(30, 30, 30, 180),
    )

    # Подбираем размер шрифта
    font_size = max(28, int(w * 0.06))
    try:
        font = ImageFont.truetype(str(BOLD_FONT), font_size)
    except (OSError, IOError):
        font = ImageFont.load_default()

    text = "Контент заблокирован"

    # Центрируем текст
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # Замок слева от текста
    lock_size = int(text_h * 0.9)
    lock_gap = int(lock_size * 0.5)
    total_w = lock_size + lock_gap + text_w

    start_x = (w - total_w) // 2
    text_x = start_x + lock_size + lock_gap
    text_y = band_top + (band_h - text_h) // 2

    # Рисуем замок (дужка + корпус)
    lock_cx = start_x + lock_size // 2
    lock_cy = band_top + band_h // 2
    body_w = lock_size
    body_h = int(lock_size * 0.65)
    arc_r = int(lock_size * 0.3)
    arc_thick = max(3, int(lock_size * 0.1))

    # Корпус замка
    body_top = lock_cy - body_h // 4
    draw.rounded_rectangle(
        [(lock_cx - body_w // 2, body_top), (lock_cx + body_w // 2, body_top + body_h)],
        radius=int(body_h * 0.15),
        fill=(255, 255, 255, 220),
    )
    # Дужка замка (полукруг сверху)
    arc_box = [
        lock_cx - arc_r, body_top - arc_r * 2 + arc_thick,
        lock_cx + arc_r, body_top + arc_thick,
    ]
    draw.arc(arc_box, 0, 360, fill=(255, 255, 255, 220), width=arc_thick)
    # Замочная скважина
    hole_r = max(2, int(lock_size * 0.08))
    draw.ellipse(
        [(lock_cx - hole_r, body_top + body_h // 3 - hole_r),
         (lock_cx + hole_r, body_top + body_h // 3 + hole_r)],
        fill=(30, 30, 30, 200),
    )

    # Тень текста
    draw.text((text_x + 2, text_y + 2), text, font=font, fill=(0, 0, 0, 200))
    # Основной текст
    draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 240))

    # Подпись снизу
    sub_font_size = max(18, int(w * 0.035))
    try:
        sub_font = ImageFont.truetype(str(BOLD_FONT), sub_font_size)
    except (OSError, IOError):
        sub_font = ImageFont.load_default()

    sub_text = "Оплатите для получения полной версии"
    sub_bbox = draw.textbbox((0, 0), sub_text, font=sub_font)
    sub_w = sub_bbox[2] - sub_bbox[0]
    sub_x = (w - sub_w) // 2
    sub_y = band_top + band_h + int(h * 0.03)

    draw.text((sub_x + 1, sub_y + 1), sub_text, font=sub_font, fill=(0, 0, 0, 160))
    draw.text((sub_x, sub_y), sub_text, font=sub_font, fill=(255, 255, 255, 220))

    # Склеиваем
    result = img.convert("RGBA")
    result = Image.alpha_composite(result, overlay)
    return result.convert("RGB")


def generate_blurred_preview(
    pdf_path: str,
    output_path: Optional[str] = None,
    blur_radius: int = 20,
    dpi: int = 150,
) -> str:
    """
    Генерирует размытое превью первой страницы PDF.

    Args:
        pdf_path: Путь к исходному PDF файлу
        output_path: Куда сохранить. Если None — автоматически в data/previews/
        blur_radius: Сила размытия (20 = сильное, текст не читаем)
        dpi: Качество рендера (150 = хорошее для Telegram)

    Returns:
        Путь к сохранённому изображению превью
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF не найден: {pdf_path}")

    # Рендерим первую страницу
    img = _render_pdf_page_to_image(pdf_path, dpi=dpi)

    # Убираем watermark NotebookLM
    img = _remove_watermark(img)

    # Размываем
    img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    # Добавляем оверлей
    img = _add_lock_overlay(img)

    # Определяем путь сохранения
    if output_path is None:
        pdf_name = Path(pdf_path).stem
        output_path = str(PREVIEWS_DIR / f"preview_{pdf_name}.jpg")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Сохраняем в JPEG (меньше размер для Telegram)
    img.save(output_path, "JPEG", quality=85)
    logger.info("Превью создано: %s (%d KB)", output_path, os.path.getsize(output_path) // 1024)

    return output_path


async def generate_blurred_preview_async(
    pdf_path: str,
    output_path: Optional[str] = None,
    blur_radius: int = 20,
    dpi: int = 150,
) -> str:
    """Асинхронная обёртка — запускает генерацию в thread pool."""
    return await asyncio.to_thread(
        generate_blurred_preview, pdf_path, output_path, blur_radius, dpi
    )


def _render_pdf_all_pages(pdf_path: str, dpi: int = 200) -> list[Image.Image]:
    """Рендерит ВСЕ страницы PDF в список PIL Image."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_prefix = os.path.join(tmpdir, "page")
        subprocess.run(
            ["pdftoppm", "-png", "-r", str(dpi), pdf_path, output_prefix],
            check=True,
            capture_output=True,
        )
        png_files = sorted(Path(tmpdir).glob("page-*.png"))
        if not png_files:
            raise FileNotFoundError(f"pdftoppm не создал изображения из {pdf_path}")
        return [Image.open(f).copy() for f in png_files]


def remove_watermark_from_pdf(
    pdf_path: str,
    output_path: Optional[str] = None,
    dpi: int = 200,
) -> str:
    """
    Убирает watermark NotebookLM со всех страниц PDF.
    Рендерит каждую страницу → убирает watermark → собирает обратно в PDF.

    Args:
        pdf_path: Путь к исходному PDF
        output_path: Куда сохранить. Если None — рядом с исходным файлом с суффиксом _clean
        dpi: Качество рендера (200 = хорошее для печати)

    Returns:
        Путь к очищенному PDF
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF не найден: {pdf_path}")

    pages = _render_pdf_all_pages(pdf_path, dpi=dpi)
    logger.info("Рендер завершён: %d страниц из %s", len(pages), pdf_path)

    # Убираем watermark с каждой страницы
    cleaned = [_remove_watermark(page) for page in pages]

    # Определяем путь
    if output_path is None:
        stem = Path(pdf_path).stem
        output_path = str(Path(pdf_path).parent / f"{stem}_clean.pdf")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Собираем в PDF
    first = cleaned[0].convert("RGB")
    rest = [p.convert("RGB") for p in cleaned[1:]]
    first.save(output_path, "PDF", save_all=True, append_images=rest, resolution=dpi)

    size_kb = os.path.getsize(output_path) // 1024
    logger.info("Чистый PDF: %s (%d KB, %d стр.)", output_path, size_kb, len(cleaned))

    return output_path


# --- CLI для быстрого тестирования ---
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Использование:")
        print("  Превью:  python -m src.services.pdf_preview preview <pdf> [output.jpg]")
        print("  Очистка: python -m src.services.pdf_preview clean <pdf> [output.pdf]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "preview":
        pdf = sys.argv[2]
        out = sys.argv[3] if len(sys.argv) > 3 else None
        result = generate_blurred_preview(pdf, out)
        print(f"Превью: {result}")

    elif cmd == "clean":
        pdf = sys.argv[2]
        out = sys.argv[3] if len(sys.argv) > 3 else None
        result = remove_watermark_from_pdf(pdf, out)
        print(f"Чистый PDF: {result}")

    else:
        # Обратная совместимость: просто путь к PDF = превью
        out = sys.argv[2] if len(sys.argv) > 2 else None
        result = generate_blurred_preview(cmd, out)
        print(f"Превью: {result}")
