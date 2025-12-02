# src/keyboards/admin/menu.py

from typing import List, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def admin_main_menu_kb() -> InlineKeyboardMarkup:
    """
    Главное меню администратора (/admin, /админ).
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🧾 Очередь модерации",
                    callback_data="admin_queue",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📚 Словарь терминов",
                    callback_data="admin_terminology",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Закрыть меню",
                    callback_data="admin_close_menu",
                )
            ],
        ]
    )


def admin_queue_summary_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура для краткой сводки по очереди:
    [Начать] [Закрыть]
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="▶️ Начать",
                    callback_data="admin_queue_start",
                ),
                InlineKeyboardButton(
                    text="❌ Закрыть",
                    callback_data="admin_close_menu",
                ),
            ]
        ]
    )


def admin_queue_empty_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура, когда очередь пуста.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ В админ-меню",
                    callback_data="admin_back",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Закрыть",
                    callback_data="admin_close_menu",
                )
            ],
        ]
    )


def admin_candidate_kb(item_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура под конкретным кандидатом.

    1 ряд: одна кнопка "Категория" → внутри уже выбор:
           добавить новую / выбрать из существующих.
    2 ряд: изменить ответ / в базу
    3 ряд: отклонить
    4 ряд: назад в админ-меню
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏷 Категория",
                    callback_data=f"kb_category_menu:{item_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Изменить ответ",
                    callback_data=f"kb_edit_answer:{item_id}",
                ),
                InlineKeyboardButton(
                    text="✅ В базу",
                    callback_data=f"kb_approve:{item_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"kb_reject:{item_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ В админ-меню",
                    callback_data="admin_back",
                ),
            ],
        ]
    )


def admin_category_menu_kb(item_id: int) -> InlineKeyboardMarkup:
    """
    Подменю управления категорией для кандидата:
    - добавить новую
    - выбрать из существующих
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Добавить новую категорию",
                    callback_data=f"kb_setcat_text:{item_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📚 Выбрать из существующих",
                    callback_data=f"kb_choosecat:{item_id}",
                ),
            ],
        ]
    )


def admin_category_suggestions_kb(
    item_id: int,
    choices: List[Tuple[str, str]],
) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора существующей категории.

    choices: список (token, category_name)
    """
    rows: List[List[InlineKeyboardButton]] = []

    for token, cat in choices:
        rows.append(
            [
                InlineKeyboardButton(
                    text=cat,
                    callback_data=f"kb_pickcat:{token}",
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="📝 Создать свою категорию",
                callback_data=f"kb_setcat_text:{item_id}",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)
