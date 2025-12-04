# src/handlers/consultation/culture_callback.py

"""
Обработчик callback-запросов для выбора культуры пользователем.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.services.db.topics_repo import get_or_create_open_topic, set_topic_culture
from src.services.db.users_repo import get_or_create_user
from src.services.db.messages_repo import log_message, get_last_messages
from src.services.llm.consultation_llm import ask_consultation_llm
from src.services.db.moderation_repo import moderation_add

from src.handlers.common import CONSULTATION_STATE, CONSULTATION_CONTEXT

router = Router()


@router.callback_query(F.data.startswith("culture:"))
async def handle_culture_selection(callback: CallbackQuery) -> None:
    """
    Обработка выбора культуры пользователем.
    После выбора культуры продолжаем обработку первого вопроса.
    """
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
        await callback.message.answer(
            "Произошла ошибка при обработке запроса. Попробуйте задать вопрос снова."
        )
        return

    user_text = history[0].get("text", "")

    # Получаем категорию из контекста (если есть)
    consultation_category = CONSULTATION_CONTEXT.get(telegram_user_id, {}).get("category")

    # Показываем статус "печатает"
    status_message = await callback.message.answer("⏳ Подождите, рекомендация формируется...")

    # Вызов LLM с защитой
    try:
        reply_text: str = await ask_consultation_llm(
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            text=user_text,
            session_id=session_id,
            culture=culture,
            consultation_category=consultation_category,
        )
    except Exception as e:
        print(f"ERROR in ask_consultation_llm: {e}")
        reply_text = (
            "Сейчас не получается обработать запрос через модель. "
            "Попробуйте ещё раз чуть позже."
        )
    finally:
        # Удаляем сообщение ожидания
        try:
            await status_message.delete()
        except Exception:
            pass

    # Ответ пользователю
    await callback.message.answer(reply_text)

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

    # Очищаем состояние после обработки
    CONSULTATION_STATE.pop(telegram_user_id, None)
