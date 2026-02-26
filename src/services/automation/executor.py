# src/services/automation/executor.py

"""
Выполнение действий автоматических триггеров.

Типы действий:
  - send_broadcast: отправить рассылку
  - move_to_stage: переместить по воронке
  - add_tag / remove_tag: управление тегами
  - set_custom_field: установить кастомное поле
  - send_payment_offer: отправить платёжный оффер
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


async def execute_actions(
    actions: List[Dict[str, Any]],
    user_id: int,
    telegram_user_id: int,
) -> List[Dict[str, Any]]:
    """
    Последовательно выполнить список действий триггера.

    Возвращает массив результатов:
    [{"type": "send_broadcast", "success": True}, ...]
    """
    results: List[Dict[str, Any]] = []

    for action in actions:
        action_type = action.get('type')
        try:
            if action_type == 'send_broadcast':
                result = await _action_send_broadcast(action, user_id, telegram_user_id)
            elif action_type == 'move_to_stage':
                result = await _action_move_to_stage(action, user_id, telegram_user_id)
            elif action_type == 'add_tag':
                result = await _action_add_tag(action, user_id)
            elif action_type == 'remove_tag':
                result = await _action_remove_tag(action, user_id)
            elif action_type == 'set_custom_field':
                result = await _action_set_custom_field(action, user_id)
            elif action_type == 'send_payment_offer':
                result = await _action_send_payment_offer(action, user_id, telegram_user_id)
            else:
                result = {'type': action_type, 'success': False, 'error': f'Unknown action type: {action_type}'}

            results.append(result)

        except Exception as e:
            error_msg = str(e)[:500]
            results.append({'type': action_type, 'success': False, 'error': error_msg})
            logger.warning(f"Action {action_type} failed for user {user_id}: {error_msg}")

    return results


async def _action_send_broadcast(
    action: Dict[str, Any],
    user_id: int,
    telegram_user_id: int,
) -> Dict[str, Any]:
    """Отправить рассылку одному пользователю."""
    from src.services.broadcast_sender import send_to_single_user

    broadcast_id = action.get('broadcast_id')
    if not broadcast_id:
        return {'type': 'send_broadcast', 'success': False, 'error': 'broadcast_id not set'}

    success = await send_to_single_user(
        broadcast_id=broadcast_id,
        user_id=user_id,
        telegram_user_id=telegram_user_id,
    )
    return {'type': 'send_broadcast', 'success': success, 'broadcast_id': broadcast_id}


async def _action_move_to_stage(
    action: Dict[str, Any],
    user_id: int,
    telegram_user_id: int,
) -> Dict[str, Any]:
    """
    Переместить пользователя на этап воронки.

    Использует _from_automation=True чтобы не запускать каскадные триггеры.
    """
    from src.services.db.funnel_repo import move_client_to_stage

    funnel_id = action.get('funnel_id')
    stage_key = action.get('stage_key')
    if not funnel_id or not stage_key:
        return {'type': 'move_to_stage', 'success': False, 'error': 'funnel_id/stage_key not set'}

    success = await move_client_to_stage(
        user_id=user_id,
        telegram_user_id=telegram_user_id,
        funnel_id=funnel_id,
        new_stage_key=stage_key,
        _from_automation=True,
    )
    return {'type': 'move_to_stage', 'success': success, 'funnel_id': funnel_id, 'stage_key': stage_key}


async def _action_add_tag(action: Dict[str, Any], user_id: int) -> Dict[str, Any]:
    """Добавить тег пользователю."""
    from src.services.db.client_crm_repo import add_client_tag

    tag_id = action.get('tag_id')
    if not tag_id:
        return {'type': 'add_tag', 'success': False, 'error': 'tag_id not set'}

    success = await add_client_tag(user_id, tag_id, _from_automation=True)
    return {'type': 'add_tag', 'success': success, 'tag_id': tag_id}


async def _action_remove_tag(action: Dict[str, Any], user_id: int) -> Dict[str, Any]:
    """Удалить тег у пользователя."""
    from src.services.db.client_crm_repo import remove_client_tag

    tag_id = action.get('tag_id')
    if not tag_id:
        return {'type': 'remove_tag', 'success': False, 'error': 'tag_id not set'}

    success = await remove_client_tag(user_id, tag_id, _from_automation=True)
    return {'type': 'remove_tag', 'success': success, 'tag_id': tag_id}


async def _action_set_custom_field(action: Dict[str, Any], user_id: int) -> Dict[str, Any]:
    """Установить кастомное поле пользователю."""
    from src.services.db.client_crm_repo import set_client_field_value

    field_id = action.get('field_id')
    value = action.get('value')
    if not field_id:
        return {'type': 'set_custom_field', 'success': False, 'error': 'field_id not set'}

    success = await set_client_field_value(user_id, field_id, value)
    return {'type': 'set_custom_field', 'success': success, 'field_id': field_id}


async def _action_send_payment_offer(
    action: Dict[str, Any],
    user_id: int,
    telegram_user_id: int,
) -> Dict[str, Any]:
    """Отправить платёжный оффер."""
    from src.services.funnel_trigger_sender import send_payment_offer

    payment_config = {
        'plan_id': action.get('plan_id'),
        'custom_price': action.get('custom_price'),
        'bonus_tokens': action.get('bonus_tokens'),
    }

    success = await send_payment_offer(
        telegram_user_id=telegram_user_id,
        user_id=user_id,
        payment_config=payment_config,
    )
    return {'type': 'send_payment_offer', 'success': success, 'plan_id': action.get('plan_id')}
