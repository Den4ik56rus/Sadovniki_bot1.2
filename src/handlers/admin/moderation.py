# src/handlers/admin/moderation.py

from typing import List, Dict, Tuple
import math
import html
from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from src.services.db.moderation_repo import (
    moderation_get_next_pending,
    moderation_get_by_id,
    moderation_update_status,
    moderation_set_category,
    moderation_count_pending,   # <<< добавили
)

from src.services.db.kb_repo import (
    kb_get_distinct_categories,
    kb_insert,
)

from src.services.llm.embeddings_llm import get_text_embedding
from src.keyboards.admin.menu import (
    admin_main_menu_kb,
    admin_queue_summary_kb,
    admin_queue_empty_kb,
    admin_candidate_kb,
    admin_category_menu_kb,
    admin_category_suggestions_kb,
)


router = Router()

# Только эти user_id считаются администраторами
ADMIN_IDS = {
    833371989,
}

# Маппинг человекочитаемых типов консультаций → коды, которые храним в БД.
# ЛЕВАЯ часть — то, что админ пишет / видит,
# ПРАВАЯ часть — аккуратный код, который кладём в knowledge_base.consultation_topic.
CONSULTATION_TOPIC_MAP: Dict[str, str] = {
    "питание растений": "nutrition",
    "питание": "nutrition",
    "удобрения": "nutrition",

    "посадка и уход": "planting",
    "посадка": "planting",
    "уход": "planting",

    "улучшение почвы": "soil",
    "почва": "soil",

    "защита растений": "protection",
    "защита": "protection",

    "подбор сорта/места": "variety",
    "подбор сорта": "variety",
    "подбор места": "variety",

    "другая тема": "other",
    "прочее": "other",
}


# user_id админа -> id кандидата, для которого ждём текст категории
WAITING_CATEGORY: Dict[int, int] = {}

# токен выбора -> (id кандидата, категория)
PENDING_CATEGORY_CHOICES: Dict[str, Tuple[int, str]] = {}


# ===============================
#        ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ===============================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _cosine_sim(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _map_topic_name_to_code(raw_topic: str) -> str:
    """
    Преобразует человекочитаемое название типа консультации
    (например: 'питание растений') в код ('nutrition').

    Если не нашли — возвращаем 'unknown', чтобы не ломать схему.
    """
    if not raw_topic:
        return "unknown"

    key = raw_topic.strip().lower()
    return CONSULTATION_TOPIC_MAP.get(key, "unknown")


async def _send_next_pending(message: Message):
    """
    Показать первого кандидата из очереди модерации.
    Общая логика для /kb_pending и admin-меню.
    """
    item = await moderation_get_next_pending()

    if not item:
        await message.answer("Очередь модерации пуста ✅")
        return

    category_guess = item["category_guess"]
    category_guess_safe = html.escape(category_guess) if category_guess else None

    question_safe = html.escape(item["question"] or "")
    answer_safe = html.escape(item["answer"] or "")

    lines = [
        f"<b>Кандидат #{item['id']}</b>",
        "",
    ]

    if category_guess_safe:
        lines.append(f"<b>Категория (тип / культура):</b> {category_guess_safe}")
    else:
        lines.append("<b>Категория:</b> не определена ❗")

    lines += [
        "",
        "<b>Полный вопрос (root + уточнения):</b>",
        question_safe,
        "",
        "<b>Ответ бота:</b>",
        answer_safe,
    ]

    text = "\n".join(lines)

    keyboard = admin_candidate_kb(item_id=item["id"])

    await message.answer(text, reply_markup=keyboard)


# ===============================
#    /admin и /админ — МЕНЮ АДМИНА
# ===============================

@router.message(Command("admin", "админ"))
async def cmd_admin(message: Message):
    """
    Главное меню администратора.
    Доступно по командам /admin и /админ.
    """
    if not is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администратору.")
        return

    await message.answer("Меню администратора:", reply_markup=admin_main_menu_kb())


@router.callback_query(F.data == "admin_close_menu")
async def cb_admin_close_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return

    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data == "admin_back")
async def cb_admin_back(callback: CallbackQuery):
    """
    Кнопка '⬅️ В админ-меню' из разных мест.
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return

    await cmd_admin(callback.message)
    await callback.answer()


# ===============================
#       ОЧЕРЕДЬ МОДЕРАЦИИ (/admin)
# ===============================

@router.callback_query(F.data == "admin_queue")
async def cb_admin_queue(callback: CallbackQuery):
    """
    Кнопка '🧾 Очередь модерации' в админ-меню.

    Требования:
    - писать: "В очереди на проверку N вопросов"
    - писать: "Очередь с <дата>"
    - без текста "Нажми/Нажмите Начать..."
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return

    # Берём самого старого кандидата
    item = await moderation_get_next_pending()

    if not item:
        await callback.message.answer(
            "Очередь модерации пуста ✅",
            reply_markup=admin_queue_empty_kb(),
        )
        await callback.answer()
        return

    # Считаем реальное количество pending
    pending_count = await moderation_count_pending()
    count_line = f"Вопросов в очереди на проверку: <b>{pending_count}</b>"

    created_at = item.get("created_at")
    if isinstance(created_at, datetime):
        if created_at.tzinfo is not None:
            dt = created_at.astimezone(created_at.tzinfo)
        else:
            dt = created_at.replace(tzinfo=timezone.utc)

        date_str = dt.date().strftime("%d.%m.%Y")
        age_line = f"Очередь с <b>{date_str}</b>."
    else:
        age_line = "Очередь: дата создания не определена."

    text = "\n".join(
        [
            "🧾 <b>Очередь модерации</b>",
            "",
            count_line,
            age_line,
        ]
    )

    await callback.message.answer(
        text,
        reply_markup=admin_queue_summary_kb(),  # кнопки 'Начать' / 'Закрыть'
    )
    await callback.answer()


@router.callback_query(F.data == "admin_queue_start")
async def cb_admin_queue_start(callback: CallbackQuery):
    """
    Кнопка '▶️ Начать' — открывает первого кандидата из очереди.
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return

    await _send_next_pending(callback.message)
    await callback.answer()


# ===============================
#        /kb_pending (старый вход)
# ===============================

@router.message(Command("kb_pending"))
async def cmd_kb_pending(message: Message):
    """
    Старый вход в модерацию — напрямую.
    Оставлен для удобства, использует ту же общую логику.
    """
    if not is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администратору.")
        return

    await _send_next_pending(message)


# ===============================
#      ПОДМЕНЮ КАТЕГОРИИ (ОДНА КНОПКА)
# ===============================

@router.callback_query(F.data.startswith("kb_category_menu:"))
async def cb_kb_category_menu(callback: CallbackQuery):
    """
    Открывает подменю управления категорией:
      - добавить новую
      - выбрать из существующих
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("Только администратор может это делать.", show_alert=True)
        return

    _, raw_id = callback.data.split(":")
    item_id = int(raw_id)

    await callback.message.answer(
        f"Управление категорией для кандидата #{item_id}:\n"
        f"• можно добавить новую категорию,\n"
        f"• или выбрать одну из уже существующих.",
        reply_markup=admin_category_menu_kb(item_id=item_id),
    )

    await callback.answer()


# ===============================
#      ВВОД КАТЕГОРИИ ВРУЧНУЮ
# ===============================

@router.callback_query(F.data.startswith("kb_setcat_text:"))
async def cb_kb_set_category_text(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Только администратор может это делать.", show_alert=True)
        return

    _, raw_id = callback.data.split(":")
    item_id = int(raw_id)

    WAITING_CATEGORY[callback.from_user.id] = item_id

    # Без угловых скобок, чтобы не ломать HTML-разметку
    await callback.message.answer(
        f"Напиши категорию для кандидата #{item_id} одним сообщением.\n\n"
        f"Примеры:\n"
        f"  • малина\n"
        f"  • клубника садовая\n"
        f"  • питание растений / малина\n"
        f"  • защита растений / клубника садовая\n"
        f"  • подбор сорта/места / голубика\n\n"
        f"Формат: тип консультации / культура\n"
        f"Например: питание растений / голубика"
    )

    await callback.answer("Жду категорию…")



# ===============================
#    ВЫБОР КАТЕГОРИИ ИЗ СУЩЕСТВУЮЩИХ
# ===============================

@router.callback_query(F.data.startswith("kb_choosecat:"))
async def cb_kb_choose_category(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Только администратор может это делать.", show_alert=True)
        return

    _, raw_id = callback.data.split(":")
    item_id = int(raw_id)

    item = await moderation_get_by_id(item_id)
    if not item:
        await callback.answer("Кандидат не найден.", show_alert=True)
        return

    categories = await kb_get_distinct_categories(limit=50)
    if not categories:
        await callback.answer("Пока нет существующих категорий. Создай новую.", show_alert=True)
        return

    question = item["question"]

    try:
        q_emb = await get_text_embedding(question)
    except Exception:
        await callback.answer("Не удалось посчитать похожесть. Введи категорию вручную.", show_alert=True)
        return

    scored: list[tuple[str, float]] = []

    for cat in categories:
        try:
            cat_emb = await get_text_embedding(cat)
        except Exception:
            continue
        sim = _cosine_sim(q_emb, cat_emb)
        scored.append((cat, sim))

    if not scored:
        await callback.answer("Не удалось подобрать категории. Введи свою.", show_alert=True)
        return

    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:9]

    PENDING_CATEGORY_CHOICES.clear()
    choices_for_kb: list[tuple[str, str]] = []

    for idx, (cat, sim) in enumerate(top):
        token = f"{item_id}_{idx}"
        PENDING_CATEGORY_CHOICES[token] = (item_id, cat)
        choices_for_kb.append((token, cat))

    keyboard = admin_category_suggestions_kb(item_id=item_id, choices=choices_for_kb)

    await callback.message.answer(
        f"Выбери подходящую категорию для кандидата #{item_id}:",
        reply_markup=keyboard,
    )

    await callback.answer()


@router.callback_query(F.data.startswith("kb_pickcat:"))
async def cb_kb_pick_category(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Только администратор может это делать.", show_alert=True)
        return

    _, token = callback.data.split(":")

    if token not in PENDING_CATEGORY_CHOICES:
        await callback.answer("Эта категория больше недоступна. Попробуй ещё раз.", show_alert=True)
        return

    item_id, category = PENDING_CATEGORY_CHOICES.pop(token)

    await moderation_set_category(item_id=item_id, category=category)

    await callback.message.answer(
        f"Категория <b>{html.escape(category)}</b> установлена для кандидата #{item_id}.\n"
        f"Теперь можно открыть /admin или /админ → Очередь → Начать и добавить его в базу."
    )

    await callback.answer("Категория выбрана ✅")


# ===============================
#       ИЗМЕНЕНИЕ ОТВЕТА (STUB)
# ===============================

@router.callback_query(F.data.startswith("kb_edit_answer:"))
async def cb_kb_edit_answer(callback: CallbackQuery):
    """
    Заглушка под будущую логику редактирования ответа через LLM.
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("Только администратор может это делать.", show_alert=True)
        return

    _, raw_id = callback.data.split(":")
    item_id = int(raw_id)

    await callback.message.answer(
        f"Изменение ответа для кандидата #{item_id} пока не реализовано.\n"
        f"На следующем шаге добавим логику через нейросеть: "
        f"'улучшить ответ' → [согласен/в базу] или [переделать]."
    )

    await callback.answer("Функция в разработке.")


# ===============================
#          ДОБАВИТЬ В БАЗУ
# ===============================

@router.callback_query(F.data.startswith("kb_approve:"))
async def cb_kb_approve(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Только администратор может это делать.", show_alert=True)
        return

    _, raw_id = callback.data.split(":")
    item_id = int(raw_id)

    item = await moderation_get_by_id(item_id)
    if not item:
        await callback.answer("Запись не найдена (возможно, уже обработана).", show_alert=True)
        return

    raw_cat = item["category_guess"]

    # По умолчанию:
    #   - consultation_topic = 'unknown'
    #   - category           = 'общая информация' (общий совет, не по конкретной культуре)
    #   - subcategory        = None (можно использовать для доп. уточнений в будущем)
    consultation_topic = "unknown"
    category = "общая информация"
    subcategory = None

    if raw_cat:
        # Форматы, которые ожидаем:
        #   1) "питание растений / малина"
        #   2) "малина" (только культура, без типа консультации)
        text = raw_cat.strip()

        if " / " in text:
            # "тип консультации / культура"
            raw_topic, raw_plant = text.split(" / ", 1)
            consultation_topic = _map_topic_name_to_code(raw_topic)
            category = raw_plant.strip() or "общая информация"
        else:
            # Без разделителя — считаем, что это просто культура.
            # Тип консультации остаётся 'unknown' (или можно будет добрать по topic_id позже).
            category = text or "общая информация"

    question = item["question"]   # ПОЛНЫЙ ВОПРОС (root + уточнения)
    answer = item["answer"]

    # Эмбеддинги считаем по ВОПРОСУ
    embedding = await get_text_embedding(question)

    kb_id = await kb_insert(
        category=category,                  # Культура (растение)
        subcategory=subcategory,            # Доп. уточнение (пока не используем)
        consultation_topic=consultation_topic,  # Тип консультации (nutrition/planting/...)
        question=question,
        answer=answer,
        embedding=embedding,
        source_type="admin_qa",
    )

    await moderation_update_status(
        item_id=item_id,
        status="approved",
        admin_id=callback.from_user.id,
        kb_id=kb_id,
    )

    category_safe = html.escape(category)
    subcategory_safe = html.escape(subcategory) if subcategory else None
    question_safe = html.escape(question)
    answer_safe = html.escape(answer)

    cat_line = (
        f"<b>Категория:</b> {category_safe}"
        if not subcategory_safe
        else f"<b>Категория:</b> {category_safe} / {subcategory_safe}"
    )

    topic_line = f"<b>Тип консультации:</b> {html.escape(consultation_topic)}"

    new_text = (
        f"<b>Кандидат #{item_id}</b> добавлен в базу знаний.\n\n"
        f"{cat_line}\n"
        f"{topic_line}\n"
        f"<b>KB ID:</b> {kb_id}\n\n"
        f"<b>Вопрос:</b>\n{question_safe}\n\n"
        f"<b>Ответ:</b>\n{answer_safe}"
    )

    await callback.message.edit_text(new_text)
    await callback.answer("Добавлено в KB!")


# ===============================
#              ОТКЛОНИТЬ
# ===============================

@router.callback_query(F.data.startswith("kb_reject:"))
async def cb_kb_reject(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Только администратор может это делать.", show_alert=True)
        return

    _, raw_id = callback.data.split(":")
    item_id = int(raw_id)

    await moderation_update_status(
        item_id=item_id,
        status="rejected",
        admin_id=callback.from_user.id,
    )

    await callback.message.edit_text(
        f"<b>Кандидат #{item_id}</b> отклонён."
    )

    await callback.answer("Отклонено.")
