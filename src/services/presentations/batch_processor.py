# src/services/presentations/batch_processor.py

"""
Оркестратор пакетной генерации презентаций.

Последовательно генерирует презентации для выбранных проблем,
отправляя каждую готовую PDF админу в Telegram и уведомляя об ошибках.
"""

import asyncio
import logging
import os
import shutil
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.types import FSInputFile

from src.services.db import batch_repo, presentation_repo
from src.services.presentations.presentation_service import generate_presentation, _pdf_path
from src.data.funnel_b_problems import get_culture_label, get_problem_label
from src.api.sse_manager import sse_manager
from src.config import settings

logger = logging.getLogger(__name__)

# Директория для отсортированных PDF по культурам
CONTENT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data", "content", "presentations",
)


def _now():
    return datetime.now(timezone.utc)


def _get_admin_ids() -> list[int]:
    """Получить список admin Telegram IDs."""
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
    problem_key: str,
) -> str:
    """Копирует PDF в data/content/presentations/{culture}/{problem}.pdf"""
    src = _pdf_path(presentation_id)
    folder = culture_key + ("_" + variety_key if variety_key else "")
    dest_dir = os.path.join(CONTENT_DIR, folder)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, f"{problem_key}.pdf")
    shutil.copy2(src, dest)
    logger.info(f"[batch_processor] PDF скопирован: {dest}")
    return dest


async def run_batch(batch_id: int, bot: Bot) -> None:
    """Последовательно генерирует все презентации в пакете."""
    batch = await batch_repo.get_batch(batch_id)
    if not batch:
        logger.error(f"[batch_processor] Пакет {batch_id} не найден")
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

        # Проверяем, не отменён ли пакет
        current_batch = await batch_repo.get_batch(batch_id)
        if current_batch and current_batch["status"] == "cancelled":
            logger.info(f"[batch_processor] Пакет {batch_id} отменён, прерываем")
            break

        culture_label = get_culture_label(item["culture_key"], item.get("variety_key"))
        problem_label = get_problem_label(item["problem_key"])
        title = f"{culture_label} — {problem_label}"

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
                "problem": problem_label,
            },
            "batch",
            batch_id,
        )

        try:
            # 1. Создать презентацию (draft)
            presentation_id = await presentation_repo.create_presentation(
                title=title,
                source_text="",
                style_id=batch.get("style_id"),
                template_id=batch.get("template_id"),
                llm_model=batch.get("llm_model"),
                reasoning_effort=batch.get("reasoning_effort"),
                image_model=batch.get("image_model"),
                generation_mode="problem",
                culture_key=item["culture_key"],
                variety_key=item.get("variety_key"),
                problem_key=item["problem_key"],
                custom_system_prompt=batch.get("custom_system_prompt"),
            )

            # 2. Генерировать (переиспользуем существующий сервис)
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

            # 3. Копировать PDF
            content_path = _copy_pdf_to_content_folder(
                presentation_id,
                item["culture_key"],
                item.get("variety_key"),
                item["problem_key"],
            )

            # 4. Обновить статус
            cost = float(pres.get("total_cost_usd") or 0) if pres else 0
            await batch_repo.update_batch_item_status(
                item["id"], "completed",
                presentation_id=presentation_id,
                content_pdf_path=content_path,
                finished_at=_now(),
            )
            await batch_repo.increment_batch_progress(batch_id, completed=1, cost=cost)

            # 5. Отправить PDF админу в Telegram
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
                        logger.error(f"[batch_processor] Не удалось отправить PDF админу {admin_id}: {tg_err}")

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

            logger.info(f"[batch_processor] Элемент {i+1}/{total} завершён: {title}")

        except Exception as e:
            logger.error(f"[batch_processor] Ошибка элемента {item['id']}: {e}", exc_info=True)

            await batch_repo.update_batch_item_status(
                item["id"], "failed",
                error_message=str(e)[:500],
                finished_at=_now(),
            )
            await batch_repo.increment_batch_progress(batch_id, failed=1)

            # Уведомить админа об ошибке
            for admin_id in admin_ids:
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=f"❌ Ошибка генерации:\n<b>{title}</b>\n\n{str(e)[:300]}",
                        parse_mode="HTML",
                    )
                except Exception as tg_err:
                    logger.error(f"[batch_processor] Не удалось отправить ошибку админу {admin_id}: {tg_err}")

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

    # Итоговое уведомление
    for admin_id in admin_ids:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=(
                    f"📊 <b>Пакет #{batch_id} завершён</b>\n\n"
                    f"✅ Готово: {completed_items}/{total}\n"
                    f"❌ Ошибки: {failed_items}\n"
                    f"💰 Стоимость: ${total_cost:.2f}"
                ),
                parse_mode="HTML",
            )
        except Exception as tg_err:
            logger.error(f"[batch_processor] Не удалось отправить итог админу {admin_id}: {tg_err}")

    logger.info(
        f"[batch_processor] Пакет {batch_id} завершён: "
        f"{completed_items}/{total} успешно, {failed_items} ошибок, "
        f"стоимость ${total_cost:.2f}"
    )


async def resume_running_batches(bot: Bot) -> int:
    """
    Возобновляет незавершённые пакеты после рестарта сервера.
    Вызывается из startup_recovery.
    """
    running = await batch_repo.get_batches_by_status("running")
    if not running:
        return 0

    for batch in running:
        logger.info(f"[batch_processor] Возобновляю пакет {batch['id']} после рестарта")
        # Сбрасываем generating items обратно в pending
        from src.services.db.pool import get_pool
        pool = get_pool()
        await pool.execute(
            """
            UPDATE presentation_batch_items
            SET status = 'pending', started_at = NULL
            WHERE batch_id = $1 AND status = 'generating'
            """,
            batch["id"],
        )
        asyncio.create_task(run_batch(batch["id"], bot))

    logger.info(f"[batch_processor] Возобновлено {len(running)} пакетов")
    return len(running)
