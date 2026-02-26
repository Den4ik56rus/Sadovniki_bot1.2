# src/services/automation/subscription_checker.py

"""
Cron-задача для проверки "скоро истекающих" подписок (subscription_expiring).

Запускается каждый час. Для каждого активного триггера с event_type='subscription_expiring'
и days_before > 0 — находит пользователей с подписками, истекающими через days_before дней,
и генерирует automation event.

Для days_before=0 — вызывается из expire_old_subscriptions для каждого реально истёкшего юзера.
"""

import logging
from typing import List, Dict, Any

from src.services.db.pool import get_pool
from src.services.db import automation_trigger_repo as repo

logger = logging.getLogger(__name__)


async def check_subscription_expiring_triggers() -> int:
    """
    Проверить все триггеры subscription_expiring с days_before > 0.
    Для каждого найти подходящих пользователей и emit event.

    Возвращает количество обработанных событий.
    """
    triggers = await repo.get_active_triggers_by_event('subscription_expiring')
    if not triggers:
        return 0

    # Собираем уникальные days_before значения (только > 0)
    days_before_set = set()
    triggers_by_days: Dict[int, List[Dict[str, Any]]] = {}
    for trigger in triggers:
        days = (trigger.get('event_config') or {}).get('days_before', 0)
        if days and days > 0:
            days_before_set.add(days)
            triggers_by_days.setdefault(days, []).append(trigger)

    if not days_before_set:
        return 0

    total_processed = 0
    pool = get_pool()

    for days_before in days_before_set:
        # Найти пользователей с подписками, истекающими через days_before дней (±12ч окно)
        async with pool.acquire() as conn:
            users = await conn.fetch(
                """
                SELECT u.id, u.telegram_user_id, us.id as subscription_id, us.expires_at
                FROM user_subscriptions us
                JOIN users u ON u.id = us.user_id
                WHERE us.status = 'active'
                  AND us.expires_at BETWEEN NOW() + ($1 - 0.5) * INTERVAL '1 day'
                                        AND NOW() + ($1 + 0.5) * INTERVAL '1 day'
                """,
                days_before,
            )

        if not users:
            continue

        for user_row in users:
            user_id = user_row['id']
            telegram_user_id = user_row['telegram_user_id']
            subscription_id = user_row['subscription_id']

            event_data = {
                'days_before': days_before,
                'subscription_id': subscription_id,
            }

            # Для каждого триггера с таким days_before
            for trigger in triggers_by_days[days_before]:
                event_snapshot = {
                    'subscription_id': subscription_id,
                    'days_before': days_before,
                }

                # Проверяем дедупликацию
                already = await repo.has_been_triggered(
                    trigger['id'], user_id, event_snapshot
                )
                if already:
                    continue

                # Используем emit_automation_event для полной обработки
                from src.services.automation.engine import emit_automation_event
                await emit_automation_event(
                    event_type='subscription_expiring',
                    user_id=user_id,
                    telegram_user_id=telegram_user_id,
                    event_data=event_data,
                )
                total_processed += 1

    if total_processed > 0:
        logger.info(f"Subscription expiring checker: processed {total_processed} events")

    return total_processed
