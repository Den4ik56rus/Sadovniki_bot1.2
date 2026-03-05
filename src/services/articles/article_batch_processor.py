# src/services/articles/article_batch_processor.py

"""
Оркестратор пакетной генерации статей.

Последовательно генерирует статьи для выбранных комбинаций категория × культура,
уведомляя админа в Telegram и обновляя прогресс через SSE.
"""

import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot

from src.services.db import article_batch_repo
from src.services.llm.article_llm import generate_article
from src.data.article_categories import get_category_consultation, get_culture_russian_for_batch
from src.api.sse_manager import sse_manager
from src.config import settings

logger = logging.getLogger(__name__)


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


async def run_article_batch(batch_id: int, bot: Bot) -> None:
    """Последовательно генерирует все статьи в пакете."""
    batch = await article_batch_repo.get_batch(batch_id)
    if not batch:
        logger.error(f"[article_batch_processor] Пакет {batch_id} не найден")
        return

    admin_ids = _get_admin_ids()

    await article_batch_repo.update_batch_status(batch_id, "running", started_at=_now())
    await sse_manager.broadcast(
        "article_batch_started",
        {"batch_id": batch_id, "total_items": batch["total_items"]},
        "article_batch",
        batch_id,
    )

    items = batch.get("items", [])
    total = batch["total_items"]

    for i, item in enumerate(items):
        if item["status"] != "pending":
            continue

        # Проверяем, не отменён ли пакет
        current_batch = await article_batch_repo.get_batch(batch_id)
        if current_batch and current_batch["status"] == "cancelled":
            logger.info(f"[article_batch_processor] Пакет {batch_id} отменён, прерываем")
            break

        topic = item["topic"]
        culture_label = item["culture_label"]
        category_label = item["category_label"]

        await article_batch_repo.update_batch_item_status(
            item["id"], "generating", started_at=_now(),
        )
        await article_batch_repo.update_batch_status(batch_id, current_item_index=i)
        await sse_manager.broadcast(
            "article_batch_item_started",
            {
                "batch_id": batch_id,
                "item_id": item["id"],
                "index": i,
                "total": total,
                "topic": topic,
                "culture": culture_label,
                "category": category_label,
            },
            "article_batch",
            batch_id,
        )

        try:
            # Получаем consultation_category и culture для RAG
            consultation_category = get_category_consultation(item["category_key"])
            culture_russian = get_culture_russian_for_batch(
                item["culture_key"], item.get("variety_key")
            )

            # Генерируем статью
            article_text, article_id = await generate_article(
                topic=topic,
                telegram_user_id=0,  # webapp admin
                category=consultation_category,
                culture=culture_russian,
                use_scripts=True,
                use_problem_solving=False,
                skip_rag=False,
                model_override=batch.get("llm_model"),
                reasoning_effort_override=batch.get("reasoning_effort"),
                culture_key=item["culture_key"],
                variety_key=item.get("variety_key"),
                category_key=item["category_key"],
                batch_id=batch_id,
            )

            # Получаем стоимость из БД
            from src.services.db.article_repo import get_article_by_id
            article = await get_article_by_id(article_id)
            cost = float(article.get("cost_usd") or 0) if article else 0

            # Обновляем статус
            await article_batch_repo.update_batch_item_status(
                item["id"], "completed",
                article_id=article_id,
                finished_at=_now(),
            )
            await article_batch_repo.increment_batch_progress(batch_id, completed=1, cost=cost)

            await sse_manager.broadcast(
                "article_batch_item_completed",
                {
                    "batch_id": batch_id,
                    "item_id": item["id"],
                    "index": i,
                    "article_id": article_id,
                    "topic": topic,
                    "cost": cost,
                    "article_length": len(article_text),
                },
                "article_batch",
                batch_id,
            )

            logger.info(
                f"[article_batch_processor] Элемент {i+1}/{total} завершён: {topic} "
                f"(article_id={article_id}, {len(article_text)} симв.)"
            )

        except Exception as e:
            logger.error(f"[article_batch_processor] Ошибка элемента {item['id']}: {e}", exc_info=True)

            await article_batch_repo.update_batch_item_status(
                item["id"], "failed",
                error_message=str(e)[:500],
                finished_at=_now(),
            )
            await article_batch_repo.increment_batch_progress(batch_id, failed=1)

            # Уведомить админа об ошибке
            for admin_id in admin_ids:
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=f"❌ Ошибка генерации статьи:\n<b>{topic}</b>\n\n{str(e)[:300]}",
                        parse_mode="HTML",
                    )
                except Exception as tg_err:
                    logger.error(f"[article_batch_processor] Не удалось отправить ошибку админу {admin_id}: {tg_err}")

            await sse_manager.broadcast(
                "article_batch_item_failed",
                {
                    "batch_id": batch_id,
                    "item_id": item["id"],
                    "index": i,
                    "topic": topic,
                    "error": str(e)[:300],
                },
                "article_batch",
                batch_id,
            )

    # Завершение пакета
    final = await article_batch_repo.get_batch(batch_id)
    if final and final["status"] != "cancelled":
        await article_batch_repo.update_batch_status(batch_id, "completed", finished_at=_now())

    completed_items = final["completed_items"] if final else 0
    failed_items = final["failed_items"] if final else 0
    total_cost = float(final["total_cost_usd"]) if final else 0

    await sse_manager.broadcast(
        "article_batch_completed",
        {
            "batch_id": batch_id,
            "completed": completed_items,
            "failed": failed_items,
            "total": total,
            "total_cost": total_cost,
        },
        "article_batch",
        batch_id,
    )

    # Итоговое уведомление
    for admin_id in admin_ids:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=(
                    f"📊 <b>Пакет статей #{batch_id} завершён</b>\n\n"
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


async def resume_running_article_batches(bot: Bot) -> int:
    """
    Возобновляет незавершённые пакеты статей после рестарта.
    Вызывается из startup_recovery.
    """
    running = await article_batch_repo.get_batches_by_status("running")
    if not running:
        return 0

    for batch in running:
        logger.info(f"[article_batch_processor] Возобновляю пакет {batch['id']} после рестарта")
        from src.services.db.pool import get_pool
        pool = get_pool()
        await pool.execute(
            """
            UPDATE article_batch_items
            SET status = 'pending', started_at = NULL
            WHERE batch_id = $1 AND status = 'generating'
            """,
            batch["id"],
        )
        asyncio.create_task(run_article_batch(batch["id"], bot))

    logger.info(f"[article_batch_processor] Возобновлено {len(running)} пакетов статей")
    return len(running)
