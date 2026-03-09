# src/services/automation/engine.py

"""
Движок автоматических триггеров — главная точка входа.

emit_automation_event() — вызывается из точек событий:
  - stage_transition: funnel_repo.move_client_to_stage / auto_move_client_in_crm
  - payment_success: payment_service.process_payment_success
  - tag_changed: client_crm_repo.add_client_tag / remove_client_tag / set_client_tags
  - subscription_expiring: subscription_checker / expire_old_subscriptions

Без каскада: действия триггеров НЕ вызывают другие триггеры.
"""

import logging
from typing import Dict, Any, Optional

from src.services.db import automation_trigger_repo as repo
from src.services.automation.conditions import evaluate_conditions
from src.services.automation.executor import execute_actions

logger = logging.getLogger(__name__)


def _match_event_config(trigger_config: Dict[str, Any], event_data: Dict[str, Any], event_type: str) -> bool:
    """
    Проверить, совпадает ли event_config триггера с данными события.
    """
    if event_type == 'stage_transition':
        return (
            trigger_config.get('funnel_id') == event_data.get('funnel_id')
            and trigger_config.get('stage_key') == event_data.get('stage_key')
        )

    elif event_type == 'payment_success':
        # payment_type: subscription|tokens|null (null = любой)
        cfg_type = trigger_config.get('payment_type')
        if cfg_type and cfg_type != event_data.get('payment_type'):
            return False
        # plan_id: конкретный план или null (null = любой)
        cfg_plan = trigger_config.get('plan_id')
        if cfg_plan and cfg_plan != event_data.get('plan_id'):
            return False
        return True

    elif event_type == 'tag_changed':
        return (
            trigger_config.get('tag_id') == event_data.get('tag_id')
            and trigger_config.get('action') == event_data.get('action')
        )

    elif event_type == 'subscription_expiring':
        return trigger_config.get('days_before') == event_data.get('days_before')

    return False


async def emit_automation_event(
    event_type: str,
    user_id: int,
    telegram_user_id: int,
    event_data: Dict[str, Any],
) -> None:
    """
    Главная функция движка. Вызывается как asyncio.create_task() из точек событий.

    Этапы:
    1. Получить все активные триггеры для event_type
    2. Для каждого — проверить совпадение event_config
    3. Оценить conditions
    4. Если delay > 0 — записать pending в лог
    5. Иначе — выполнить немедленно через executor
    """
    try:
        triggers = await repo.get_active_triggers_by_event(event_type)
        if not triggers:
            return

        for trigger in triggers:
            trigger_id = trigger['id']
            trigger_config = trigger.get('event_config') or {}
            conditions = trigger.get('conditions')
            actions = trigger.get('actions') or []
            delay_minutes = trigger.get('delay_minutes', 0) or 0

            # 1. Проверяем совпадение event_config
            if not _match_event_config(trigger_config, event_data, event_type):
                continue

            # 2. Проверяем дедупликацию (только для отложенных — у немедленных атомарный claim)
            event_snapshot = _build_event_snapshot(event_type, event_data)

            # 3. Оценить условия
            conditions_met = await evaluate_conditions(conditions, user_id)

            # 4. Отложенная или немедленная отправка
            if delay_minutes > 0:
                # Для отложенных — сначала проверяем, потом пишем pending
                already = await repo.has_been_triggered(trigger_id, user_id, event_snapshot)
                if already:
                    continue
                if not conditions_met:
                    await repo.log_trigger_execution(
                        trigger_id, user_id, 'skipped',
                        event_snapshot=event_snapshot,
                    )
                    continue
                await repo.log_trigger_execution(
                    trigger_id, user_id, 'pending',
                    send_at_offset_minutes=delay_minutes,
                    event_snapshot=event_snapshot,
                )
                logger.info(
                    f"Automation trigger {trigger_id} scheduled for user {user_id} "
                    f"in {delay_minutes} min (event={event_type})"
                )
            else:
                # Немедленное выполнение — атомарный claim через INSERT ON CONFLICT DO NOTHING
                if not conditions_met:
                    # Пробуем вставить skipped — если уже есть sent/pending/processing, DO NOTHING
                    await repo.log_trigger_execution(
                        trigger_id, user_id, 'skipped',
                        event_snapshot=event_snapshot,
                    )
                    continue

                log_id = await repo.try_claim_immediate_trigger(
                    trigger_id, user_id, event_snapshot
                )
                if log_id is None:
                    # Уже обрабатывается или выполнен — пропускаем
                    logger.debug(
                        f"Automation trigger {trigger_id} already claimed for user {user_id}, skipping"
                    )
                    continue

                try:
                    results = await execute_actions(actions, user_id, telegram_user_id)
                    all_success = all(r.get('success') for r in results)

                    await repo.update_trigger_log_status(
                        log_id,
                        'sent' if all_success else 'failed',
                        actions_result=results,
                        error_message=None if all_success else _collect_errors(results),
                    )

                    logger.info(
                        f"Automation trigger {trigger_id} executed for user {user_id}: "
                        f"{'OK' if all_success else 'PARTIAL FAILURE'} (event={event_type})"
                    )
                except Exception as e:
                    error_msg = str(e)[:500]
                    await repo.update_trigger_log_status(log_id, 'failed', error_message=error_msg)
                    logger.warning(
                        f"Automation trigger {trigger_id} failed for user {user_id}: {error_msg}"
                    )

    except Exception as e:
        logger.error(f"emit_automation_event error ({event_type}): {e}", exc_info=True)


async def process_pending_automation_triggers() -> int:
    """
    Обработать отложенные триггеры у которых наступило время выполнения.

    Вызывается фоновым планировщиком каждые 30 секунд.
    """
    try:
        # Вернуть в pending записи которые застряли в processing (упали при обработке)
        await repo.reset_stale_processing_triggers(minutes=5)

        due = await repo.get_pending_triggers_due(limit=100)
        if not due:
            return 0

        processed = 0
        for record in due:
            log_id = record['log_id']
            trigger_id = record['trigger_id']
            user_id = record['user_id']
            telegram_user_id = record['telegram_user_id']
            actions = record.get('actions') or []
            event_type = record.get('event_type')
            event_config = record.get('event_config') or {}
            conditions = record.get('conditions')

            # Если триггер выключен — удалить pending запись
            if not record.get('is_active', True):
                await repo.delete_trigger_log_entry(log_id)
                logger.info(
                    f"Pending trigger log_id={log_id} deleted: trigger {trigger_id} is disabled"
                )
                processed += 1
                continue

            # Re-evaluate conditions (user state may have changed)
            conditions_met = await evaluate_conditions(conditions, user_id)
            if not conditions_met:
                await repo.update_trigger_log_status(log_id, 'skipped')
                logger.info(
                    f"Pending trigger log_id={log_id} skipped: conditions no longer met for user {user_id}"
                )
                processed += 1
                continue

            # Для stage_transition: проверить что пользователь всё ещё на этапе
            if event_type == 'stage_transition':
                from src.services.db.funnel_trigger_repo import is_user_on_stage
                funnel_id = event_config.get('funnel_id')
                stage_key = event_config.get('stage_key')
                if funnel_id and stage_key:
                    still_on_stage = await is_user_on_stage(user_id, funnel_id, stage_key)
                    if not still_on_stage:
                        await repo.delete_trigger_log_entry(log_id)
                        logger.info(
                            f"Pending trigger log_id={log_id} deleted: user {user_id} "
                            f"no longer on {funnel_id}/{stage_key}"
                        )
                        processed += 1
                        continue

            try:
                results = await execute_actions(actions, user_id, telegram_user_id)
                all_success = all(r.get('success') for r in results)

                await repo.update_trigger_log_status(
                    log_id,
                    'sent' if all_success else 'failed',
                    actions_result=results,
                    error_message=None if all_success else _collect_errors(results),
                )

                logger.info(
                    f"Pending trigger log_id={log_id} executed for user {user_id}: "
                    f"{'OK' if all_success else 'PARTIAL FAILURE'}"
                )
            except Exception as e:
                error_msg = str(e)[:500]
                await repo.update_trigger_log_status(log_id, 'failed', error_message=error_msg)
                logger.warning(f"Pending trigger log_id={log_id} failed: {error_msg}")

            processed += 1

        return processed

    except Exception as e:
        logger.error(f"process_pending_automation_triggers error: {e}", exc_info=True)
        return 0


def _build_event_snapshot(event_type: str, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Построить снимок события для дедупликации."""
    if event_type == 'subscription_expiring':
        return {
            'subscription_id': event_data.get('subscription_id'),
            'days_before': event_data.get('days_before'),
        }
    if event_type == 'stage_transition':
        return {
            'funnel_id': event_data.get('funnel_id'),
            'stage_key': event_data.get('stage_key'),
        }
    return None


def _collect_errors(results: list) -> Optional[str]:
    """Собрать ошибки из результатов действий."""
    errors = [r.get('error', '') for r in results if not r.get('success') and r.get('error')]
    return '; '.join(errors) if errors else None
