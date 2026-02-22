# src/services/funnel_trigger_sender.py

"""
Отправка триггерных сообщений при смене этапа воронки.

Когда пользователь перемещается на этап с привязанным триггером,
ему отправляется контент из рассылки (текст, фото, опрос, кнопки).
"""

import logging
from typing import Optional

from src.services.db.funnel_trigger_repo import (
    get_active_triggers_for_stage,
    has_trigger_been_sent,
    log_trigger_sent,
)

logger = logging.getLogger(__name__)


async def execute_stage_triggers(
    user_id: int,
    telegram_user_id: int,
    funnel_id: str,
    stage_key: str,
) -> None:
    """
    Проверить и выполнить триггеры для этапа воронки.

    Вызывается после перемещения пользователя на новый этап.
    Для каждого активного триггера:
      - Проверяет, был ли уже отправлен этому пользователю
      - Если нет — отправляет сообщение и логирует
    """
    try:
        triggers = await get_active_triggers_for_stage(funnel_id, stage_key)
        if not triggers:
            return

        for trigger in triggers:
            trigger_id = trigger['id']
            broadcast_id = trigger['broadcast_id']

            # Проверяем: не отправляли ли уже
            already_sent = await has_trigger_been_sent(trigger_id, user_id)
            if already_sent:
                logger.debug(
                    f"Trigger {trigger_id} already sent to user {user_id}, skipping"
                )
                continue

            # Отправляем
            try:
                from src.services.broadcast_sender import send_to_single_user
                success = await send_to_single_user(
                    broadcast_id=broadcast_id,
                    user_id=user_id,
                    telegram_user_id=telegram_user_id,
                )

                if success:
                    await log_trigger_sent(trigger_id, user_id, 'sent')
                    logger.info(
                        f"Trigger {trigger_id} (broadcast={broadcast_id}) sent to user {user_id}"
                    )
                else:
                    await log_trigger_sent(trigger_id, user_id, 'failed', 'send returned false')

            except Exception as e:
                error_msg = str(e)[:500]
                await log_trigger_sent(trigger_id, user_id, 'failed', error_msg)
                logger.warning(
                    f"Trigger {trigger_id} failed for user {user_id}: {error_msg}"
                )

    except Exception as e:
        logger.error(f"execute_stage_triggers error: {e}", exc_info=True)
