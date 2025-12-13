# src/handlers/admin/article_writing.py

"""
Handler для режима написания статей администратором.

Флоу:
1. Админ нажимает кнопку "Написать статью" в админском меню
2. Бот переходит в состояние waiting_article_topic
3. Админ вводит тему статьи
4. Бот генерирует статью с использованием RAG-поиска по всей базе знаний
5. Статья отправляется админу (с автоматической разбивкой если длинная)
"""

import logging
from typing import Dict

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from src.services.llm.article_llm import generate_article
from src.handlers.admin.moderation import is_admin
from src.handlers.consultation.entry import send_long_message

logger = logging.getLogger(__name__)

router = Router()

# Состояния для режима статей
# {telegram_user_id: "waiting_article_topic"}
ARTICLE_STATE: Dict[int, str] = {}


@router.callback_query(F.data == "admin_write_article")
async def handle_write_article_button(callback: CallbackQuery) -> None:
    """
    Обрабатывает нажатие кнопки "Написать статью" в админском меню.

    Устанавливает состояние ожидания темы статьи и отправляет инструкцию.
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    telegram_user_id = callback.from_user.id

    # Устанавливаем состояние ожидания темы
    ARTICLE_STATE[telegram_user_id] = "waiting_article_topic"

    print(f"[article_writing] Админ {telegram_user_id} активировал режим статей")

    await callback.message.answer(
        "📝 <b>Режим написания статьи</b>\n\n"
        "Введите тему статьи одним сообщением.\n\n"
        "<b>Примеры тем:</b>\n"
        "• Питание малины в период плодоношения\n"
        "• Защита клубники от серой гнили\n"
        "• Подготовка почвы для посадки голубики\n"
        "• Обрезка ремонтантной малины весной\n\n"
        "Бот проанализирует всю базу знаний и сгенерирует подробную структурированную статью.",
        parse_mode="HTML"
    )

    await callback.answer("✅ Режим статей активирован")


@router.message(
    F.text,
    lambda m: m.from_user is not None
    and ARTICLE_STATE.get(m.from_user.id) == "waiting_article_topic"
)
async def handle_article_topic_input(message: Message) -> None:
    """
    Обрабатывает ввод темы статьи от администратора.

    Генерирует статью и отправляет её админу.
    """
    if not is_admin(message.from_user.id):
        # Не админ, но каким-то образом попал в это состояние - сбрасываем
        ARTICLE_STATE.pop(message.from_user.id, None)
        return

    telegram_user_id = message.from_user.id
    topic = message.text.strip()

    if not topic:
        await message.answer("❌ Тема не может быть пустой. Введите тему статьи:")
        return

    # Ограничение длины темы
    if len(topic) > 500:
        await message.answer(
            "❌ Тема слишком длинная (максимум 500 символов).\n"
            "Пожалуйста, сформулируйте тему короче:"
        )
        return

    print(f"[article_writing] Админ {telegram_user_id} запросил статью: '{topic}'")

    # Показываем статус генерации
    status_msg = await message.answer(
        "⏳ <b>Генерирую статью...</b>\n\n"
        "Это может занять до 1 минуты, так как бот:\n"
        "• Анализирует всю базу знаний\n"
        "• Находит релевантные материалы\n"
        "• Создаёт структурированную статью\n\n"
        "Пожалуйста, подождите...",
        parse_mode="HTML"
    )

    try:
        # Генерация статьи
        article_text = await generate_article(
            topic=topic,
            telegram_user_id=telegram_user_id,
        )

        # Удаляем статус
        await status_msg.delete()

        print(f"[article_writing] Статья сгенерирована: {len(article_text)} символов")

        # Отправляем статью (с автоматической разбивкой если длинная)
        await send_long_message(message, article_text)

        # Информационное сообщение после отправки
        await message.answer(
            "✅ <b>Статья сгенерирована</b>\n\n"
            f"📊 Длина: {len(article_text)} символов\n"
            f"💡 Тема: {topic}\n\n"
            "Токены НЕ списаны (админский режим)",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"[article_writing] Ошибка при генерации статьи: {e}", exc_info=True)

        # Удаляем статус
        try:
            await status_msg.delete()
        except:
            pass

        await message.answer(
            "❌ <b>Ошибка при генерации статьи</b>\n\n"
            "Произошла ошибка при обработке запроса.\n"
            "Попробуйте ещё раз или измените тему.\n\n"
            f"Детали: {str(e)[:200]}",
            parse_mode="HTML"
        )

    finally:
        # Очищаем состояние
        ARTICLE_STATE.pop(telegram_user_id, None)
        print(f"[article_writing] Режим статей завершён для админа {telegram_user_id}")
