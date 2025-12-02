# src/handlers/admin/terminology.py

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from src.services.db.terminology_repo import (
    get_all_terminology,
    add_terminology,
)
import html

router = Router()


# Загружаем ADMIN_IDS из переменной окружения
def _load_admin_ids() -> set[int]:
    from src.config import settings
    if not settings.admin_ids:
        return set()

    ids = set()
    for id_str in settings.admin_ids.split(","):
        id_str = id_str.strip()
        if id_str.isdigit():
            ids.add(int(id_str))
    return ids

ADMIN_IDS = _load_admin_ids()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# user_id админа -> ожидание ввода данных для термина (term, preferred_phrase, description)
WAITING_TERM_DATA: dict[int, dict] = {}


@router.callback_query(F.data == "admin_terminology")
async def cb_admin_terminology(callback: CallbackQuery):
    """
    Показывает меню управления словарём терминов.
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return

    terms = await get_all_terminology()
    count = len(terms)

    text = f"📚 <b>Словарь терминов</b>\n\nВ словаре {count} термин(ов)"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Показать термины",
                    callback_data="admin_show_terms"
                )
            ],
            [
                InlineKeyboardButton(
                    text="➕ Добавить термин",
                    callback_data="admin_add_term"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ В админ-меню",
                    callback_data="admin_back"
                )
            ],
        ]
    )

    await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin_show_terms")
async def cb_admin_show_terms(callback: CallbackQuery):
    """
    Показывает список всех терминов.
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return

    terms = await get_all_terminology()

    if not terms:
        text = "📚 <b>Словарь терминов пуст</b>\n\nДобавь первый термин."
    else:
        lines = ["📚 <b>Список терминов</b>\n"]
        for term in terms:
            lines.append(
                f"• <b>{html.escape(term['term'])}</b> → {html.escape(term['preferred_phrase'])}"
            )
        text = "\n".join(lines)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="admin_terminology"
                )
            ],
        ]
    )

    await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin_add_term")
async def cb_admin_add_term(callback: CallbackQuery):
    """
    Начинает процесс добавления термина.
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return

    WAITING_TERM_DATA[callback.from_user.id] = {"step": "term"}

    await callback.message.answer(
        "➕ <b>Добавление нового термина</b>\n\n"
        "Шаг 1 из 2: Введи исходный термин или фразу, которую нужно заменять.\n\n"
        "Пример: навоз"
    )

    await callback.answer("Жду термин...")


@router.message(F.text, lambda m: m.from_user and m.from_user.id in WAITING_TERM_DATA)
async def handle_term_input(message: Message):
    """
    Обрабатывает ввод данных для термина.
    """
    user_id = message.from_user.id
    text = message.text.strip()

    if user_id not in WAITING_TERM_DATA:
        return

    data = WAITING_TERM_DATA[user_id]
    step = data.get("step")

    if step == "term":
        # Сохраняем термин, запрашиваем предпочитаемую фразу
        data["term"] = text
        data["step"] = "preferred_phrase"

        await message.answer(
            f"Термин: <b>{html.escape(text)}</b>\n\n"
            f"Шаг 2 из 2: Введи предпочитаемую формулировку, которую должен использовать бот.\n\n"
            f"Пример: удобрения естественного происхождения"
        )

    elif step == "preferred_phrase":
        # Сохраняем предпочитаемую фразу и добавляем в БД
        term = data["term"]
        preferred_phrase = text

        try:
            term_id = await add_terminology(
                term=term,
                preferred_phrase=preferred_phrase,
                description=f"Вместо '{term}' использовать '{preferred_phrase}'"
            )

            await message.answer(
                f"✅ <b>Термин добавлен</b>\n\n"
                f"• Исходный: <b>{html.escape(term)}</b>\n"
                f"• Заменять на: <b>{html.escape(preferred_phrase)}</b>\n"
                f"• ID: {term_id}\n\n"
                f"Теперь LLM будет использовать эту формулировку при ответах."
            )

            WAITING_TERM_DATA.pop(user_id)

        except Exception as e:
            await message.answer(
                f"❌ Ошибка при добавлении термина: {str(e)}\n\n"
                f"Попробуй ещё раз."
            )
            WAITING_TERM_DATA.pop(user_id)
