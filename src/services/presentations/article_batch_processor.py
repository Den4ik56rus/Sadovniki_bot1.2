# src/services/presentations/article_batch_processor.py

"""
Оркестратор пакетной генерации презентаций по статьям.

Для каждой культуры:
  - 6 категорий: берёт существующую статью → генерирует презентацию в режиме "article"
  - Сезонный план: читает все 6 статей → GPT извлекает план → генерирует презентацию
"""

import asyncio
import logging
import os
import shutil
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.types import FSInputFile

from src.services.db import batch_repo, presentation_repo, article_repo
from src.services.presentations.presentation_service import generate_presentation, _pdf_path
from src.services.llm.season_plan_llm import generate_season_plan
from src.data.article_categories import (
    get_category_label,
    get_culture_label_for_batch,
)
from src.api.sse_manager import sse_manager
from src.config import settings

logger = logging.getLogger(__name__)

CONTENT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data", "content", "presentations",
)


def _now():
    return datetime.now(timezone.utc)


def _get_admin_ids() -> list[int]:
    raw = settings.admin_ids or ""
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            try:
                ids.append(int(part))
            except ValueError:
                pass
    return ids


def _copy_pdf_to_content_folder(
    presentation_id: int,
    culture_key: str,
    variety_key: str | None,
    filename: str,
) -> str:
    """Копирует PDF в data/content/presentations/{culture}/{filename}.pdf"""
    src = _pdf_path(presentation_id)
    folder = culture_key + ("_" + variety_key if variety_key else "")
    dest_dir = os.path.join(CONTENT_DIR, folder)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, f"{filename}.pdf")
    shutil.copy2(src, dest)
    logger.info(f"[article_batch_processor] PDF скопирован: {dest}")
    return dest


async def run_article_presentation_batch(batch_id: int, bot: Bot) -> None:
    """Последовательно генерирует презентации по статьям."""
    batch = await batch_repo.get_batch(batch_id)
    if not batch:
        logger.error(f"[article_batch_processor] Пакет {batch_id} не найден")
        return

    admin_ids = _get_admin_ids()

    await batch_repo.update_batch_status(batch_id, "running", started_at=_now())
    await sse_manager.broadcast(
        "batch_started",
        {"batch_id": batch_id, "total_items": batch["total_items"]},
        "batch",
        batch_id,
    )

    items = batch.get("items", [])
    total = batch["total_items"]

    for i, item in enumerate(items):
        if item["status"] != "pending":
            continue

        # Проверяем отмену
        current_batch = await batch_repo.get_batch(batch_id)
        if current_batch and current_batch["status"] == "cancelled":
            logger.info(f"[article_batch_processor] Пакет {batch_id} отменён")
            break

        culture_label = get_culture_label_for_batch(
            item["culture_key"], item.get("variety_key")
        ) or item["culture_key"]
        is_season_plan = item.get("is_season_plan", False)
        category_key = item.get("category_key")

        if is_season_plan:
            title = f"Сезонный план — {culture_label}"
            category_label = "Сезонный план"
        else:
            category_label = get_category_label(category_key) or category_key
            title = f"{category_label} — {culture_label}"

        await batch_repo.update_batch_item_status(
            item["id"], "generating", started_at=_now(),
        )
        await batch_repo.update_batch_status(batch_id, current_item_index=i)
        await sse_manager.broadcast(
            "batch_item_started",
            {
                "batch_id": batch_id,
                "item_id": item["id"],
                "index": i,
                "total": total,
                "title": title,
                "culture": culture_label,
                "problem": category_label,
            },
            "batch",
            batch_id,
        )

        try:
            # Получаем source_text
            source_text = ""
            extra_cost = 0.0

            if is_season_plan:
                # Читаем все статьи культуры → генерируем план
                articles = await article_repo.get_articles_with_text_by_culture(
                    item["culture_key"], item.get("variety_key"),
                )
                if not articles:
                    raise Exception(f"Нет статей для {culture_label} — невозможно создать сезонный план")

                plan_result = await generate_season_plan(
                    culture_label=culture_label,
                    articles=articles,
                    model=batch.get("llm_model"),
                    reasoning_effort=batch.get("reasoning_effort") or "medium",
                )
                source_text = plan_result["plan_text"]
                extra_cost = plan_result["cost_usd"]
            else:
                # Берём существующую статью
                article = await article_repo.get_article_by_category_and_culture(
                    category_key, item["culture_key"], item.get("variety_key"),
                )
                if not article:
                    raise Exception(f"Статья не найдена: {category_label} × {culture_label}")
                source_text = article["article_text"]

            # Создаём презентацию
            generation_mode = "article"
            presentation_id = await presentation_repo.create_presentation(
                title=title,
                source_text=source_text,
                style_id=batch.get("style_id"),
                template_id=batch.get("template_id"),
                llm_model=batch.get("llm_model"),
                reasoning_effort=batch.get("reasoning_effort"),
                image_model=batch.get("image_model"),
                generation_mode=generation_mode,
                culture_key=item["culture_key"],
                variety_key=item.get("variety_key"),
                problem_key=item.get("problem_key"),
                custom_system_prompt=batch.get("custom_system_prompt"),
            )

            # Генерируем
            async def on_progress(data, _batch_id=batch_id, _item_id=item["id"]):
                await sse_manager.broadcast(
                    "batch_item_progress",
                    {"batch_id": _batch_id, "item_id": _item_id, **data},
                    "batch",
                    _batch_id,
                )

            await generate_presentation(presentation_id, on_progress=on_progress)

            # Проверяем результат
            pres = await presentation_repo.get_presentation_by_id(presentation_id)
            if pres and pres["status"] == "failed":
                raise Exception(pres.get("error_message") or "Генерация не удалась")

            # Копируем PDF
            filename = "season_plan" if is_season_plan else category_key
            content_path = _copy_pdf_to_content_folder(
                presentation_id,
                item["culture_key"],
                item.get("variety_key"),
                filename,
            )

            # Обновляем статус
            cost = float(pres.get("total_cost_usd") or 0) if pres else 0
            cost += extra_cost
            await batch_repo.update_batch_item_status(
                item["id"], "completed",
                presentation_id=presentation_id,
                content_pdf_path=content_path,
                finished_at=_now(),
            )
            await batch_repo.increment_batch_progress(batch_id, completed=1, cost=cost)

            # Отправляем PDF админу
            pdf_path = _pdf_path(presentation_id)
            if os.path.exists(pdf_path):
                for admin_id in admin_ids:
                    try:
                        await bot.send_document(
                            chat_id=admin_id,
                            document=FSInputFile(pdf_path),
                            caption=f"✅ {title}\n({i+1}/{total})",
                        )
                    except Exception as tg_err:
                        logger.error(f"[article_batch_processor] Не удалось отправить PDF админу {admin_id}: {tg_err}")

            await sse_manager.broadcast(
                "batch_item_completed",
                {
                    "batch_id": batch_id,
                    "item_id": item["id"],
                    "index": i,
                    "presentation_id": presentation_id,
                    "title": title,
                    "cost": cost,
                },
                "batch",
                batch_id,
            )

            logger.info(f"[article_batch_processor] Элемент {i+1}/{total} завершён: {title}")

        except Exception as e:
            logger.error(f"[article_batch_processor] Ошибка элемента {item['id']}: {e}", exc_info=True)

            await batch_repo.update_batch_item_status(
                item["id"], "failed",
                error_message=str(e)[:500],
                finished_at=_now(),
            )
            await batch_repo.increment_batch_progress(batch_id, failed=1)

            for admin_id in admin_ids:
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=f"❌ Ошибка генерации:\n<b>{title}</b>\n\n{str(e)[:300]}",
                        parse_mode="HTML",
                    )
                except Exception as tg_err:
                    logger.error(f"[article_batch_processor] Не удалось отправить ошибку админу {admin_id}: {tg_err}")

            await sse_manager.broadcast(
                "batch_item_failed",
                {
                    "batch_id": batch_id,
                    "item_id": item["id"],
                    "index": i,
                    "title": title,
                    "error": str(e)[:300],
                },
                "batch",
                batch_id,
            )

    # Завершение пакета
    final = await batch_repo.get_batch(batch_id)
    if final and final["status"] != "cancelled":
        await batch_repo.update_batch_status(batch_id, "completed", finished_at=_now())

    completed_items = final["completed_items"] if final else 0
    failed_items = final["failed_items"] if final else 0
    total_cost = float(final["total_cost_usd"]) if final else 0

    await sse_manager.broadcast(
        "batch_completed",
        {
            "batch_id": batch_id,
            "completed": completed_items,
            "failed": failed_items,
            "total": total,
            "total_cost": total_cost,
        },
        "batch",
        batch_id,
    )

    for admin_id in admin_ids:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=(
                    f"📊 <b>Пакет по статьям #{batch_id} завершён</b>\n\n"
                    f"✅ Готово: {completed_items}/{total}\n"
                    f"❌ Ошибки: {failed_items}\n"
                    f"💰 Стоимость: ${total_cost:.2f}"
                ),
                parse_mode="HTML",
            )
        except Exception as tg_err:
            logger.error(f"[article_batch_processor] Не удалось отправить итог админу {admin_id}: {tg_err}")

    logger.info(
        f"[article_batch_processor] Пакет {batch_id} завершён: "
        f"{completed_items}/{total} успешно, {failed_items} ошибок, "
        f"стоимость ${total_cost:.2f}"
    )
