# src/services/automation/conditions.py

"""
Оценка AND/OR условий для автоматических триггеров.

Структура conditions:
{
  "operator": "AND",
  "groups": [
    {
      "operator": "OR",
      "rules": [
        { "type": "has_tag", "tag_id": 5 },
        { "type": "has_tag", "tag_id": 8 }
      ]
    },
    {
      "operator": "AND",
      "rules": [
        { "type": "from_invite_link", "invite_link_id": 12 }
      ]
    }
  ]
}

Типы правил: has_tag, not_has_tag, from_invite_link, at_funnel_stage, not_at_funnel_stage
"""

import logging
from typing import Dict, Any, Optional, Set, Tuple, List

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


async def _load_user_context(user_id: int) -> Dict[str, Any]:
    """
    Загрузить контекст пользователя одним запросом (теги, инвайт, воронки).
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        # Теги
        tag_rows = await conn.fetch(
            "SELECT tag_id FROM client_tag_links WHERE user_id = $1",
            user_id,
        )
        tag_ids: Set[int] = {row['tag_id'] for row in tag_rows}

        # Инвайт-ссылки
        invite_rows = await conn.fetch(
            "SELECT invite_link_id FROM invite_link_users WHERE user_id = $1",
            user_id,
        )
        invite_link_ids: Set[int] = {row['invite_link_id'] for row in invite_rows}

        # Позиции в воронках
        funnel_rows = await conn.fetch(
            "SELECT funnel_id, stage_key FROM client_funnel_position WHERE user_id = $1",
            user_id,
        )
        funnel_positions: List[Tuple[str, str]] = [
            (row['funnel_id'], row['stage_key']) for row in funnel_rows
        ]

    return {
        'tag_ids': tag_ids,
        'invite_link_ids': invite_link_ids,
        'funnel_positions': funnel_positions,
    }


def _evaluate_rule(rule: Dict[str, Any], context: Dict[str, Any]) -> bool:
    """Оценить одно правило."""
    rule_type = rule.get('type')

    if rule_type == 'has_tag':
        return rule.get('tag_id') in context['tag_ids']

    elif rule_type == 'not_has_tag':
        return rule.get('tag_id') not in context['tag_ids']

    elif rule_type == 'from_invite_link':
        return rule.get('invite_link_id') in context['invite_link_ids']

    elif rule_type == 'at_funnel_stage':
        target = (rule.get('funnel_id'), rule.get('stage_key'))
        return target in context['funnel_positions']

    elif rule_type == 'not_at_funnel_stage':
        target = (rule.get('funnel_id'), rule.get('stage_key'))
        return target not in context['funnel_positions']

    else:
        logger.warning(f"Unknown condition rule type: {rule_type}")
        return False


def _evaluate_group(group: Dict[str, Any], context: Dict[str, Any]) -> bool:
    """Оценить группу правил (AND/OR)."""
    operator = group.get('operator', 'AND')
    rules = group.get('rules', [])

    if not rules:
        return True

    if operator == 'OR':
        return any(_evaluate_rule(rule, context) for rule in rules)
    else:  # AND
        return all(_evaluate_rule(rule, context) for rule in rules)


def _evaluate_tree(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
    """Оценить дерево AND/OR условий."""
    operator = conditions.get('operator', 'AND')
    groups = conditions.get('groups', [])

    if not groups:
        return True

    if operator == 'OR':
        return any(_evaluate_group(group, context) for group in groups)
    else:  # AND
        return all(_evaluate_group(group, context) for group in groups)


async def evaluate_conditions(
    conditions: Optional[Dict[str, Any]],
    user_id: int,
) -> bool:
    """
    Оценить условия триггера для пользователя.

    Возвращает True если условия выполняются (или null = без условий).
    """
    if conditions is None:
        return True

    try:
        context = await _load_user_context(user_id)
        return _evaluate_tree(conditions, context)
    except Exception as e:
        logger.error(f"Error evaluating conditions for user {user_id}: {e}", exc_info=True)
        return False
