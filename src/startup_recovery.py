# src/startup_recovery.py

"""
Логика восстановления после рестарта бота.

Запускается один раз при старте, ДО start_polling.

Задачи:
1. Найти пользователей с неотвеченными вопросами (последние 30 минут)
   и автоматически сгенерировать ответ заново (без повторного списания токенов).
2. Восстановить CONSULTATION_STATE / CONSULTATION_CONTEXT из БД
   для пользователей, которые были в середине диалога уточнений.
"""

import logging

from aiogram import Bot

from src.services.db.messages_repo import find_unanswered_user_messages, log_message
from src.services.db.user_state_repo import get_all_persisted_states, clear_user_state
from src.handlers.common import CONSULTATION_STATE, CONSULTATION_CONTEXT

logger = logging.getLogger(__name__)


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

    await _reprocess_unanswered_questions(bot)
    await _restore_states_from_db()

    logger.info("[recovery] Восстановление завершено.")


async def _reprocess_unanswered_questions(bot: Bot) -> None:
    """
    Находит вопросы без ответа (последние 30 мин) и автоматически генерирует ответ заново.
    Токены НЕ списываются повторно — это компенсация за сбой бота.
    """
    try:
        missed = await find_unanswered_user_messages(since_minutes=30)
    except Exception as e:
        logger.error(f"[recovery] Ошибка при поиске неотвеченных сообщений: {e}")
        return

    if not missed:
        logger.info("[recovery] Неотвеченных сообщений не найдено.")
        return

    logger.info(f"[recovery] Найдено {len(missed)} вопросов без ответа. Генерирую ответы...")

    for record in missed:
        tg_id = record["telegram_user_id"]
        question_text = record["text"]
        internal_user_id = record["user_id"]
        topic_id = record.get("topic_id")

        try:
            await _answer_missed_question(
                bot=bot,
                tg_id=tg_id,
                internal_user_id=internal_user_id,
                question_text=question_text,
                topic_id=topic_id,
            )
            logger.info(f"[recovery] Ответ отправлен пользователю {tg_id}")
        except Exception as e:
            logger.warning(f"[recovery] Не удалось ответить пользователю {tg_id}: {e}")
            # Fallback: хотя бы уведомляем
            try:
                await bot.send_message(
                    chat_id=tg_id,
                    text=(
                        "Бот был перезагружен во время подготовки вашего ответа.\n\n"
                        "Пожалуйста, отправьте вопрос ещё раз — мы готовы помочь! 🌿"
                    ),
                )
            except Exception:
                pass


async def _answer_missed_question(
    bot: Bot,
    tg_id: int,
    internal_user_id: int,
    question_text: str,
    topic_id: int | None,
) -> None:
    """
    Генерирует и отправляет ответ на пропущенный вопрос напрямую через bot.send_message.
    Использует упрощённый pipeline: классификация + RAG + LLM → отправка.
    Токены НЕ списываются (компенсация за сбой).
    """
    from src.services.llm.classification_llm import detect_category_and_culture
    from src.services.llm.consultation_llm import ask_consultation_llm, compose_full_question
    from src.services.db.topics_repo import get_or_create_open_topic, get_topic_culture
    from src.utils.formatting import markdown_to_telegram_html

    session_id = f"tg:{tg_id}"

    # Получаем или создаём топик
    if not topic_id:
        topic_id = await get_or_create_open_topic(user_id=internal_user_id, session_id=session_id)

    # Пробуем взять культуру из топика (уже определена ранее)
    culture = await get_topic_culture(topic_id)

    # Классифицируем категорию и культуру (если не определены)
    category, detected_culture, correction_hint, _, _ = await detect_category_and_culture(question_text)
    if not culture:
        culture = detected_culture

    # Формируем красивый вопрос для RAG
    composed_q, _, _ = await compose_full_question(question_text, [])

    # Отправляем статусное сообщение (простое, не стриминг — бот только запустился)
    status_msg = await bot.send_message(
        chat_id=tg_id,
        text="⏳ Подготавливаю ответ на ваш предыдущий вопрос...",
    )

    try:
        # Генерируем ответ через LLM (без стриминга при recovery)
        reply_text = await ask_consultation_llm(
            user_id=internal_user_id,
            telegram_user_id=tg_id,
            text=question_text,
            session_id=session_id,
            topic_id=topic_id,
            culture=culture,
            consultation_category=category,
            composed_question=composed_q,
            compose_cost_usd=0.0,
            compose_tokens=0,
            stream=False,  # Без стриминга при recovery
        )
    except Exception as e:
        logger.error(f"[recovery] LLM ошибка для user {tg_id}: {e}")
        await status_msg.delete()
        raise

    # Форматируем и отправляем ответ
    formatted = markdown_to_telegram_html(reply_text)

    # Удаляем статусное сообщение
    try:
        await status_msg.delete()
    except Exception:
        pass

    # Отправляем ответ (разбиваем если длинный)
    MAX_LEN = 4096
    if len(formatted) <= MAX_LEN:
        await bot.send_message(chat_id=tg_id, text=formatted, parse_mode="HTML")
    else:
        # Отправляем по частям
        for i in range(0, len(formatted), MAX_LEN):
            await bot.send_message(chat_id=tg_id, text=formatted[i:i + MAX_LEN], parse_mode="HTML")

    # Логируем ответ бота в БД
    await log_message(
        user_id=internal_user_id,
        direction="bot",
        text=reply_text,
        session_id=session_id,
        topic_id=topic_id,
        meta={"recovery": True},
    )


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
