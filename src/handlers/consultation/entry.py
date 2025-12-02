# src/handlers/consultation/entry.py

"""
Хендлер для обработки обычных текстовых сообщений (кроме команд).

Задачи:
    - перехватить ввод категории от админа (когда он меняет категорию кандидата)
    - для всех остальных текстов:
        * найти/создать пользователя
        * найти/создать открытую тему (topic)
        * залогировать сообщение
        * вызвать LLM (ask_consultation_llm)
        * отправить ответ
        * залогировать ответ
        * добавить пару вопрос-ответ в очередь модерации
"""

from aiogram import Router, F
from aiogram.types import Message

# Репозитории БД
from src.services.db.users_repo import get_or_create_user
from src.services.db.topics_repo import get_or_create_open_topic
from src.services.db.messages_repo import log_message
from src.services.db.moderation_repo import moderation_add

# LLM
from src.services.llm.consultation_llm import ask_consultation_llm

# Утилита для session_id
from src.handlers.common import build_session_id_from_message


router = Router()


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: Message) -> None:
    """
    Обработка всех текстовых сообщений (кроме команд).
    Консультационный сценарий для всех пользователей.
    """

    print("DEBUG: handle_text получил сообщение:", message.text)

    user = message.from_user
    session_id = build_session_id_from_message(message)

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

    # Пользователь
    user_id = await get_or_create_user(
        telegram_user_id=telegram_user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
    )

    # Тема
    topic_id = await get_or_create_open_topic(
        user_id=user_id,
        session_id=session_id,
    )

    user_text: str = message.text or ""

    # Логируем сообщение пользователя
    await log_message(
        user_id=user_id,
        direction="user",
        text=user_text,
        session_id=session_id,
        topic_id=topic_id,
    )

    # Показываем статус "печатает" и отправляем сообщение ожидания
    status_message = await message.answer("⏳ Подождите, рекомендация формируется...")

    # Вызов LLM с защитой
    try:
        reply_text: str = await ask_consultation_llm(
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            text=user_text,
            session_id=session_id,
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
    await message.answer(reply_text)

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
        await moderation_add(
            user_id=user_id,
            topic_id=topic_id,
            question=user_text,
            answer=reply_text,
            category_guess=None,
        )
    except Exception as e:
        print(f"ERROR in moderation_add: {e}")
