# src/startup_recovery.py

"""
Логика восстановления после рестарта бота.

Запускается один раз при старте, ДО start_polling.

Задачи:
1. Найти пользователей с неотвеченными вопросами (последние 30 минут)
   и отправить им уведомление с просьбой повторить вопрос.
2. Восстановить CONSULTATION_STATE / CONSULTATION_CONTEXT из БД
   для пользователей, которые были в середине диалога уточнений.
"""

import logging

from aiogram import Bot

from src.services.db.messages_repo import find_unanswered_user_messages
from src.services.db.user_state_repo import get_all_persisted_states, clear_user_state
from src.handlers.common import CONSULTATION_STATE, CONSULTATION_CONTEXT

logger = logging.getLogger(__name__)


MISSED_MESSAGE_NOTIFICATION = (
    "Извините, бот был перезагружен и не смог ответить на ваш последний вопрос.\n\n"
    "Пожалуйста, отправьте ваш вопрос ещё раз — мы готовы помочь! 🌿"
)

# Состояния ожидания текстового ввода — восстанавливаем контекст в память
RECOVERABLE_STATES = {
    "waiting_clarification_answer",
    "waiting_variety_clarification",
    "waiting_consultation_question",
    "waiting_followup",
    "waiting_example_details",
}

# Состояния ожидания нажатия кнопки — кнопки устарели после рестарта, очищаем
STALE_BUTTON_STATES = {
    "waiting_complexity_confirm",
    "waiting_topic_select",
    "waiting_phase_continue",
    "waiting_phase_select",
}


async def run_startup_recovery(bot: Bot) -> None:
    """
    Основная функция восстановления. Вызывается из main.py
    после init_db_pool() и set_main_menu_commands(), но ДО dp.start_polling().
    """
    logger.info("[recovery] Запускаю восстановление после рестарта...")

    await _notify_unanswered_users(bot)
    await _restore_states_from_db()

    logger.info("[recovery] Восстановление завершено.")


async def _notify_unanswered_users(bot: Bot) -> None:
    """
    Ищет пользователей с неотвеченными вопросами за последние 30 минут
    и отправляет им уведомление.
    """
    try:
        missed = await find_unanswered_user_messages(since_minutes=30)
    except Exception as e:
        logger.error(f"[recovery] Ошибка при поиске неотвеченных сообщений: {e}")
        return

    if not missed:
        logger.info("[recovery] Неотвеченных сообщений не найдено.")
        return

    logger.info(f"[recovery] Найдено {len(missed)} пользователей с неотвеченными вопросами.")

    for record in missed:
        tg_id = record["telegram_user_id"]
        try:
            await bot.send_message(chat_id=tg_id, text=MISSED_MESSAGE_NOTIFICATION)
            logger.info(f"[recovery] Уведомление отправлено пользователю {tg_id}")
        except Exception as e:
            # Пользователь мог заблокировать бота — это нормально
            logger.warning(f"[recovery] Не удалось уведомить пользователя {tg_id}: {e}")


async def _restore_states_from_db() -> None:
    """
    Восстанавливает CONSULTATION_STATE и CONSULTATION_CONTEXT из таблицы user_bot_state.

    - RECOVERABLE_STATES: ожидание текста от пользователя → восстанавливаем
    - STALE_BUTTON_STATES: ожидание кнопки → кнопки устарели, очищаем из БД
    """
    try:
        persisted = await get_all_persisted_states()
    except Exception as e:
        logger.error(f"[recovery] Ошибка при загрузке сохранённых состояний: {e}")
        return

    restored_count = 0
    cleared_count = 0

    for entry in persisted:
        tg_id = entry["telegram_user_id"]
        state_key = entry["state_key"]
        context = entry["context"]

        if state_key in RECOVERABLE_STATES:
            CONSULTATION_STATE[tg_id] = state_key
            if context:
                CONSULTATION_CONTEXT[tg_id] = context
            restored_count += 1
            logger.debug(f"[recovery] Восстановлено state={state_key} для user {tg_id}")
        else:
            # Состояние кнопки или неизвестное — устарело, очищаем
            try:
                await clear_user_state(tg_id)
            except Exception as e:
                logger.warning(f"[recovery] Не удалось очистить устаревшее состояние для {tg_id}: {e}")
            cleared_count += 1

    logger.info(
        f"[recovery] Состояния: восстановлено={restored_count}, устаревших очищено={cleared_count}"
    )
