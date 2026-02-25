# src/services/reminder_scheduler.py

"""
Расчёт времени отправки напоминалок после завершения родительской рассылки.

Вызывается из execute_broadcast() когда родительская рассылка завершена.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.services.db.broadcast_repo import (
    get_broadcast,
    get_reminders_for_broadcast,
    update_reminder_status,
)

logger = logging.getLogger(__name__)


def _find_discount_button(broadcast: dict) -> Optional[dict]:
    """Найти первую discount-кнопку в рассылке."""
    buttons = broadcast.get('inline_buttons')
    if not buttons:
        return None
    if isinstance(buttons, str):
        buttons = json.loads(buttons)
    for btn in buttons:
        if btn.get('type') == 'discount':
            return btn
    return None


async def compute_reminder_schedules(parent_broadcast_id: int) -> None:
    """
    Рассчитать абсолютное время отправки для всех напоминалок родительской рассылки.

    Логика:
    - after_send: completed_at + offset_hours
    - before_discount_end: completed_at + discount_duration_hours - offset_hours
    - Если время уже прошло → skipped
    """
    parent = await get_broadcast(parent_broadcast_id)
    if not parent:
        return

    completed_at_str = parent.get('completed_at')
    if not completed_at_str:
        logger.warning(f"Parent broadcast {parent_broadcast_id} has no completed_at, cannot schedule reminders")
        return

    # Парсим completed_at (может быть строкой из _row_to_dict)
    if isinstance(completed_at_str, str):
        completed_at = datetime.fromisoformat(completed_at_str)
    else:
        completed_at = completed_at_str

    if completed_at.tzinfo is None:
        completed_at = completed_at.replace(tzinfo=timezone.utc)

    reminders = await get_reminders_for_broadcast(parent_broadcast_id)
    if not reminders:
        return

    discount_btn = _find_discount_button(parent)
    now = datetime.now(timezone.utc)

    for reminder in reminders:
        # Пропустить уже обработанные
        if reminder.get('reminder_status') not in ('pending', None):
            continue

        trigger_type = reminder.get('reminder_trigger_type', 'after_send')
        offset_hours = float(reminder.get('reminder_offset_hours', 2))

        if trigger_type == 'after_send':
            scheduled = completed_at + timedelta(hours=offset_hours)

        elif trigger_type == 'before_discount_end':
            if not discount_btn:
                logger.info(
                    f"Reminder {reminder['id']}: trigger_type=before_discount_end but parent has no discount button, skipping"
                )
                await update_reminder_status(reminder['id'], 'skipped')
                continue

            discount_hours = float(discount_btn.get('discount_duration_hours', 24))
            discount_end = completed_at + timedelta(hours=discount_hours)
            scheduled = discount_end - timedelta(hours=offset_hours)
        else:
            logger.warning(f"Reminder {reminder['id']}: unknown trigger_type '{trigger_type}', skipping")
            await update_reminder_status(reminder['id'], 'skipped')
            continue

        # Не планируем в прошлом
        if scheduled <= now:
            logger.info(
                f"Reminder {reminder['id']}: scheduled time {scheduled} is in the past, skipping"
            )
            await update_reminder_status(reminder['id'], 'skipped')
            continue

        await update_reminder_status(reminder['id'], 'scheduled', scheduled_at=scheduled)
        logger.info(
            f"Reminder {reminder['id']} for broadcast {parent_broadcast_id}: "
            f"scheduled at {scheduled.isoformat()} ({trigger_type}, offset={offset_hours}h)"
        )
