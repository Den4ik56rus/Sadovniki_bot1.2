# src/handlers/consultation/culture_callback.py

"""
Обработчик callback-запросов для выбора культуры пользователем.
"""

import asyncio

from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.shutdown import shutdown_coordinator
from src.services.db.topics_repo import get_or_create_open_topic, set_topic_culture
from src.services.db.users_repo import get_or_create_user
from src.services.db.messages_repo import log_message, get_last_messages
from src.services.llm.consultation_llm import ask_consultation_llm, compose_full_question
from src.services.db.moderation_repo import moderation_add

from src.handlers.common import CONSULTATION_STATE, CONSULTATION_CONTEXT, set_consultation_state, clear_consultation_state
from src.handlers.consultation.entry import finalize_streaming_message, _log_bot_msg, _log_user_callback
from src.utils.status_manager import StatusMessageManager
from src.services.db.tokens_repo import add_tokens
from src.pricing import COST_NEW_TOPIC, get_consultation_cost

router = Router()


@router.callback_query(F.data.startswith("culture:"))
async def handle_culture_selection(callback: CallbackQuery) -> None:
    """
    Обработка выбора культуры пользователем.
    После выбора культуры продолжаем обработку первого вопроса.
    """
    # Graceful shutdown: регистрируем задачу
    current_task = asyncio.current_task()
    if current_task:
        shutdown_coordinator.register_task(current_task)

    if not callback.data or not callback.message:
        return

    # Извлекаем культуру из callback_data
    culture = callback.data.split("culture:", 1)[1]

    user = callback.from_user
    if user is not None:
        telegram_user_id = user.id
        username = user.username
        first_name = user.first_name
        last_name = user.last_name
    else:
        telegram_user_id = 0
        username = None
        first_name = None
        last_name = None

    # Получаем или создаём пользователя
    user_id = await get_or_create_user(
        telegram_user_id=telegram_user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
    )

    # Строим session_id из callback
    session_id = f"tg_{telegram_user_id}_{callback.message.chat.id}"

    # Получаем тему
    topic_id = await get_or_create_open_topic(
        user_id=user_id,
        session_id=session_id,
    )

    # Сохраняем выбранную культуру
    await set_topic_culture(topic_id, culture)

    # Привязываем ВСЕ промежуточные сообщения к топику
    _q_msg_id = CONSULTATION_CONTEXT.get(telegram_user_id, {}).get("question_msg_id")
    if _q_msg_id:
        try:
            from src.services.db.messages_repo import attach_pending_messages_to_topic
            await attach_pending_messages_to_topic(user_id, topic_id, since_msg_id=_q_msg_id)
        except Exception:
            pass

    # Логируем нажатие кнопки пользователем
    await _log_user_callback(f"[Кнопка] Культура: {culture}", callback=callback, topic_id=topic_id)

    print(f"[CULTURE] Пользователь выбрал культуру: {culture}")

    # Удаляем сообщение с клавиатурой
    try:
        await callback.message.delete()
    except Exception:
        pass

    # Подтверждаем выбор
    await callback.answer(f"Выбрана культура: {culture}")

    # Получаем последнее сообщение пользователя (его первый вопрос)
    history = await get_last_messages(user_id=user_id, limit=1)

    if not history:
        err_text = "Произошла ошибка при обработке запроса. Попробуйте задать вопрос снова."
        await callback.message.answer(err_text)
        await _log_bot_msg(err_text, user_id=user_id, session_id=session_id, topic_id=topic_id)
        return

    user_text = history[0].get("text", "")

    # Получаем категорию из контекста (если есть)
    consultation_category = CONSULTATION_CONTEXT.get(telegram_user_id, {}).get("category")

    # Показываем статус с динамическими обновлениями
    status_mgr = StatusMessageManager(callback)
    await status_mgr.start()

    # Формируем красивый вопрос для RAG (даже без уточнений)
    composed_q, compose_cost, compose_tokens = await compose_full_question(user_text, [])

    # Вызов LLM с защитой
    try:
        reply_text: str = await ask_consultation_llm(
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            text=user_text,
            session_id=session_id,
            topic_id=topic_id,
            culture=culture,
            consultation_category=consultation_category,
            composed_question=composed_q,  # Красиво сформированный вопрос
            compose_cost_usd=compose_cost,  # Стоимость формирования вопроса
            compose_tokens=compose_tokens,  # Токены формирования вопроса
            status_updater=status_mgr.update,
            stream=True,
            streaming_transition=status_mgr.start_streaming,
        )
    except Exception as e:
        print(f"[culture_callback] ERROR in ask_consultation_llm: {e}, returning questions to user {user_id}")
        await status_mgr.complete()
        refund_cost = get_consultation_cost(consultation_category) if consultation_category else COST_NEW_TOPIC
        await add_tokens(user_id, refund_cost, "refund", "Возврат: ошибка модели")
        err_text = (
            "Произошла ошибка при обработке запроса. "
            "Вопросы возвращены на ваш баланс. Попробуйте ещё раз."
        )
        await callback.message.answer(err_text)
        await _log_bot_msg(err_text, user_id=user_id, session_id=session_id, topic_id=topic_id)
        await clear_consultation_state(telegram_user_id)
        return

    # Забираем стриминг-сообщение ДО complete() чтобы переиспользовать
    streaming_msg = status_mgr.get_streaming_message()
    await status_mgr.complete()

    # Ответ пользователю (edit стриминг-сообщения или новое)
    await finalize_streaming_message(streaming_msg, callback.message, reply_text)

    # Логируем ответ бота
    await log_message(
        user_id=user_id,
        direction="bot",
        text=reply_text,
        session_id=session_id,
        topic_id=topic_id,
    )

    # Кандидат в базу знаний (очередь модерации)
    try:
        category_guess = f"{consultation_category} / {culture}" if consultation_category else None

        await moderation_add(
            user_id=user_id,
            topic_id=topic_id,
            question=user_text,
            answer=reply_text,
            category_guess=category_guess,
        )
    except Exception as e:
        print(f"ERROR in moderation_add: {e}")

    # Переводим в режим ожидания follow-up
    await set_consultation_state(telegram_user_id, "waiting_followup")
