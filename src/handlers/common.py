# src/handlers/common.py

"""
Общие вспомогательные вещи для хендлеров:
    - CONSULTATION_STATE — простое состояние консультации по user_id
    - CONSULTATION_CONTEXT — доп. данные по текущей консультации (рут-вопрос, культура и т.п.)
    - build_session_id_from_message — построение session_id по сообщению
"""

from typing import Dict, Any          # Dict и Any используем для типизации словарей

from aiogram.types import Message     # Message — тип для входящих сообщений Telegram


# Простое состояние консультации:
# для каждого пользователя можно хранить, чего мы от него ждём (на каком шаге сценария он сейчас)
CONSULTATION_STATE: Dict[int, str] = {}   # Пример: {123456789: "waiting_nutrition_root"}


# Дополнительный контекст консультации:
# сюда будем складывать сам рут-вопрос, полный вопрос, культуру, user_id, topic_id и т.п.
CONSULTATION_CONTEXT: Dict[int, Dict[str, Any]] = {}  # Пример: {123456789: {"category": "nutrition", "root_question": "..."}}


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
