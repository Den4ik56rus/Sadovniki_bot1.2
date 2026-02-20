# src/handlers/common.py

"""
Общие вспомогательные вещи для хендлеров:
    - CONSULTATION_STATE — простое состояние консультации по user_id
    - CONSULTATION_CONTEXT — доп. данные по текущей консультации (рут-вопрос, культура и т.п.)
    - build_session_id_from_message — построение session_id по сообщению
    - set_consultation_state — установить состояние + сохранить в БД
    - clear_consultation_state — очистить состояние + удалить из БД
"""

import logging
from typing import Any, Dict, Optional

from aiogram.types import Message     # Message — тип для входящих сообщений Telegram

logger = logging.getLogger(__name__)

# Простое состояние консультации:
# для каждого пользователя можно хранить, чего мы от него ждём (на каком шаге сценария он сейчас)
CONSULTATION_STATE: Dict[int, str] = {}   # Пример: {123456789: "waiting_nutrition_root"}


# Дополнительный контекст консультации:
# сюда будем складывать сам рут-вопрос, полный вопрос, культуру, user_id, topic_id и т.п.
CONSULTATION_CONTEXT: Dict[int, Dict[str, Any]] = {}  # Пример: {123456789: {"category": "nutrition", "root_question": "..."}}

# Сохранённые сообщения пользователя, написанные вместо нажатия кнопки.
# Используется для автоподгрузки текста после нажатия кнопки выбора типа вопроса.
PENDING_USER_MESSAGES: Dict[int, Message] = {}  # Пример: {123456789: <Message object>}


async def set_consultation_state(
    telegram_user_id: int,
    state: str,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Устанавливает CONSULTATION_STATE и опционально CONSULTATION_CONTEXT,
    одновременно сохраняя в БД для восстановления после рестарта.
    """
    CONSULTATION_STATE[telegram_user_id] = state
    if context is not None:
        CONSULTATION_CONTEXT[telegram_user_id] = context
    try:
        from src.services.db.user_state_repo import save_user_state
        ctx = CONSULTATION_CONTEXT.get(telegram_user_id, {})
        await save_user_state(telegram_user_id, state, ctx)
    except Exception as e:
        logger.warning(f"[state] Не удалось сохранить состояние для {telegram_user_id}: {e}")


async def clear_consultation_state(telegram_user_id: int) -> None:
    """
    Очищает CONSULTATION_STATE и CONSULTATION_CONTEXT,
    одновременно удаляя запись из БД.
    """
    CONSULTATION_STATE.pop(telegram_user_id, None)
    CONSULTATION_CONTEXT.pop(telegram_user_id, None)
    try:
        from src.services.db.user_state_repo import clear_user_state
        await clear_user_state(telegram_user_id)
    except Exception as e:
        logger.warning(f"[state] Не удалось очистить состояние для {telegram_user_id}: {e}")


def build_session_id_from_message(message: Message) -> str:
    """
    Строим session_id на основе Telegram user id.
    Формат: "tg:<user_id>" или "tg:unknown".
    """
    # Если по какой-то причине в сообщении нет информации о пользователе — возвращаем "tg:unknown"
    if message.from_user is None:
        return "tg:unknown"

    # Иначе берём id пользователя и формируем строку вида "tg:123456789"
    return f"tg:{message.from_user.id}"
