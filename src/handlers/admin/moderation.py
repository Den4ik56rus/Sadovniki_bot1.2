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
    moderation_count_pending,
    moderation_update_answer,
)

from src.services.db.kb_repo import (
    kb_get_distinct_categories,
    kb_insert,
)

from src.services.llm.embeddings_llm import get_text_embedding
from src.services.llm.core_llm import create_chat_completion
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

# Валидные категории культур
VALID_CULTURE_CATEGORIES: List[str] = [
    "клубника общая",
    "клубника летняя",
    "клубника ремонтантная",
    "малина общая",
    "малина летняя",
    "малина ремонтантная",
    "смородина",
    "голубика",
    "жимолость",
    "крыжовник",
    "ежевика",
    "общая информация",
]


# user_id админа -> id кандидата, для которого ждём текст категории
WAITING_CATEGORY: Dict[int, int] = {}

# токен выбора -> (id кандидата, категория)
PENDING_CATEGORY_CHOICES: Dict[str, Tuple[int, str]] = {}

# user_id админа -> (id кандидата, вопрос, старый ответ) - для редактирования ответа
WAITING_EDIT_INSTRUCTIONS: Dict[int, Tuple[int, str, str]] = {}

# user_id админа -> (id кандидата, новый ответ) - для подтверждения изменений
PENDING_EDIT_APPROVAL: Dict[int, Tuple[int, str]] = {}


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


def _normalize_culture_category(raw_category: str) -> str:
    """
    Нормализует название культуры к валидному формату.

    Примеры:
        "малина" -> "малина общая"
        "клубника" -> "клубника общая"
        "малина ремонтантная" -> "малина ремонтантная" (без изменений)
    """
    text = raw_category.strip().lower()

    # Если категория уже валидная - вернуть как есть
    for valid_cat in VALID_CULTURE_CATEGORIES:
        if text == valid_cat.lower():
            return valid_cat

    # Нормализация неполных названий
    if text == "малина":
        return "малина общая"
    elif text == "клубника" or text == "земляника":
        return "клубника общая"
    elif text == "смородина":
        return "смородина"
    elif text == "голубика":
        return "голубика"
    elif text == "жимолость":
        return "жимолость"
    elif text == "крыжовник":
        return "крыжовник"
    elif text == "ежевика":
        return "ежевика"

    # Если не распознано - вернуть "общая информация"
    return "общая информация"


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
#   ОБРАБОТЧИКИ ТЕКСТОВЫХ СООБЩЕНИЙ
# ===============================

def is_admin_in_input_state(message: Message) -> bool:
    """
    Проверяет, находится ли админ в процессе ввода данных
    (категория или инструкции по редактированию).
    """
    if not message.from_user:
        return False
    user_id = message.from_user.id
    return (user_id in WAITING_CATEGORY or user_id in WAITING_EDIT_INSTRUCTIONS)


@router.message(F.text, lambda m: is_admin_in_input_state(m))
async def handle_admin_text_input(message: Message):
    """
    Обработчик текстовых сообщений от админа.

    Обрабатывает:
    1. Ввод категории для кандидата
    2. Ввод инструкций по редактированию ответа

    Срабатывает ТОЛЬКО когда админ находится в процессе ввода данных.
    """
    user_id = message.from_user.id
    text = message.text.strip()

    # Проверяем, ожидаем ли категорию
    if user_id in WAITING_CATEGORY:
        item_id = WAITING_CATEGORY.pop(user_id)

        normalized_category = _normalize_culture_category(text)
        await moderation_set_category(item_id=item_id, category=normalized_category)

        await message.answer(
            f"Категория <b>{html.escape(normalized_category)}</b> установлена для кандидата #{item_id}.\n"
            f"Теперь можно открыть /admin или /админ → Очередь → Начать и добавить его в базу."
        )
        return

    # Проверяем, ожидаем ли инструкции по редактированию
    if user_id in WAITING_EDIT_INSTRUCTIONS:
        item_id, question, original_answer = WAITING_EDIT_INSTRUCTIONS.pop(user_id)

        # Отправляем уведомление о начале генерации
        processing_msg = await message.answer("⏳ Генерирую улучшенный ответ...")

        try:
            # Генерируем улучшенный ответ
            improved_answer = await _generate_improved_answer(
                question=question,
                original_answer=original_answer,
                edit_instructions=text,
            )

            # DEBUG: проверяем, что получили
            print(f"[DEBUG] Улучшенный ответ получен, длина: {len(improved_answer)} символов")
            print(f"[DEBUG] Первые 100 символов: {improved_answer[:100]}")

            # Удаляем сообщение о процессе
            await processing_msg.delete()

            # Сохраняем для подтверждения
            PENDING_EDIT_APPROVAL[user_id] = (item_id, improved_answer)

            # Получаем полную информацию о кандидате для показа
            item = await moderation_get_by_id(item_id)
            category_guess = item["category_guess"]
            category_guess_safe = html.escape(category_guess) if category_guess else "не определена"

            # Формируем полное сообщение в стандартном формате модерации
            lines = [
                f"<b>Кандидат #{item_id}</b>",
                "",
                f"<b>Категория (тип / культура):</b> {category_guess_safe}",
                "",
                "<b>Полный вопрос (root + уточнения):</b>",
                html.escape(question),
                "",
                "<b>Ответ бота:</b>",
                html.escape(improved_answer),
            ]

            full_text = "\n".join(lines)

            # Клавиатура для подтверждения
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✅ Принять",
                            callback_data=f"kb_edit_accept:{item_id}",
                        ),
                        InlineKeyboardButton(
                            text="🔄 Переделать",
                            callback_data=f"kb_edit_retry:{item_id}",
                        ),
                    ],
                ]
            )

            # Проверяем длину сообщения (лимит Telegram - 4096 символов)
            if len(full_text) > 4000:
                # Разбиваем на две части: сначала текст, потом кнопки
                await message.answer(full_text)
                await message.answer(
                    "👆 Выше показан новый вариант ответа.\n\n"
                    "<b>Принять изменения или переделать?</b>",
                    reply_markup=keyboard
                )
            else:
                # Отправляем всё одним сообщением
                await message.answer(full_text, reply_markup=keyboard)

        except Exception as e:
            await processing_msg.delete()
            await message.answer(
                f"❌ Ошибка при генерации ответа: {str(e)}\n\n"
                f"Попробуй ещё раз или используй другие инструкции."
            )
            # Возвращаем состояние обратно
            WAITING_EDIT_INSTRUCTIONS[user_id] = (item_id, question, original_answer)

        return


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

    # Нормализовать категорию перед сохранением
    normalized_category = _normalize_culture_category(category)

    await moderation_set_category(item_id=item_id, category=normalized_category)

    await callback.message.answer(
        f"Категория <b>{html.escape(normalized_category)}</b> установлена для кандидата #{item_id}.\n"
        f"Теперь можно открыть /admin или /админ → Очередь → Начать и добавить его в базу."
    )

    await callback.answer("Категория выбрана ✅")


# ===============================
#       ИЗМЕНЕНИЕ ОТВЕТА
# ===============================

async def _generate_improved_answer(
    question: str,
    original_answer: str,
    edit_instructions: str,
) -> str:
    """
    Генерирует улучшенный ответ на основе инструкций модератора.
    """
    system_prompt = (
        "Ты редактор текстов для базы знаний агрономического бота по ягодным культурам.\n\n"
        "КРИТИЧЕСКИ ВАЖНО:\n"
        "- Ты НЕ консультант. Ты технический редактор текстов.\n"
        "- Твоя ЕДИНСТВЕННАЯ задача — выполнить инструкции модератора ТОЧНО.\n"
        "- Если модератор просит заменить ответ на конкретный текст — используй ИМЕННО этот текст.\n"
        "- Если модератор просит сократить до одного слова — сократи до одного слова.\n"
        "- НИКОГДА не отказывайся редактировать текст.\n"
        "- НИКОГДА не пиши отказы типа 'я могу помочь только с...', 'это не моя тема' и т.п.\n"
        "- НЕ копируй вопрос пользователя в свой ответ.\n"
        "- НЕ копируй инструкции модератора в свой ответ.\n"
        "- НЕ добавляй ничего от себя — только то, что просит модератор.\n"
        "- Верни ТОЛЬКО отредактированный текст ответа бота.\n\n"
        "Базовые требования (если модератор не просит иное):\n"
        "- Экспертный тон агронома-консультанта\n"
        "- Конкретика и структурированность\n"
        "- Без общих фраз типа 'если у вас есть вопросы...'\n"
        "- Сохрани важную информацию из оригинала\n"
        "- Примени изменения из инструкций модератора ТОЧНО как указано"
    )

    user_message = (
        f"ВОПРОС ПОЛЬЗОВАТЕЛЯ (для контекста, НЕ копируй его):\n{question}\n\n"
        f"ТЕКУЩИЙ ОТВЕТ БОТА (отредактируй этот текст):\n{original_answer}\n\n"
        f"ИНСТРУКЦИИ МОДЕРАТОРА (выполни их ТОЧНО):\n{edit_instructions}\n\n"
        f"———\n"
        f"Верни ТОЛЬКО результат редактирования согласно инструкциям модератора. "
        f"Без вопроса, без инструкций, без комментариев — только отредактированный ответ."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    improved = await create_chat_completion(messages=messages, temperature=0.3)
    return improved.strip()


@router.callback_query(F.data.startswith("kb_edit_answer:"))
async def cb_kb_edit_answer(callback: CallbackQuery):
    """
    Начало процесса редактирования ответа через LLM.
    Запрашивает у модератора инструкции по изменению.
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("Только администратор может это делать.", show_alert=True)
        return

    _, raw_id = callback.data.split(":")
    item_id = int(raw_id)

    item = await moderation_get_by_id(item_id)
    if not item:
        await callback.answer("Кандидат не найден.", show_alert=True)
        return

    question = item["question"]
    answer = item["answer"]

    # Сохраняем состояние ожидания инструкций
    WAITING_EDIT_INSTRUCTIONS[callback.from_user.id] = (item_id, question, answer)

    await callback.message.answer(
        f"✏️ <b>Редактирование ответа для кандидата #{item_id}</b>\n\n"
        f"Опиши, какие изменения нужно внести в ответ.\n\n"
        f"Примеры:\n"
        f"• Добавь информацию про дозировку удобрений\n"
        f"• Убери общие фразы, сделай более конкретным\n"
        f"• Добавь предостережение про сроки обработки\n"
        f"• Сделай структуру более чёткой с нумерацией шагов\n\n"
        f"Напиши свои инструкции одним сообщением:"
    )

    await callback.answer("Жду инструкции по изменению...")


@router.callback_query(F.data.startswith("kb_edit_accept:"))
async def cb_kb_edit_accept(callback: CallbackQuery):
    """
    Модератор принял новую версию ответа.
    После сохранения сразу показывает кандидата для модерации.
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("Только администратор может это делать.", show_alert=True)
        return

    _, raw_id = callback.data.split(":")
    item_id = int(raw_id)

    if callback.from_user.id not in PENDING_EDIT_APPROVAL:
        await callback.answer("Сессия редактирования истекла.", show_alert=True)
        return

    stored_id, new_answer = PENDING_EDIT_APPROVAL.pop(callback.from_user.id)

    if stored_id != item_id:
        await callback.answer("Несоответствие ID кандидата.", show_alert=True)
        return

    # Обновляем ответ в moderation_queue
    await moderation_update_answer(item_id=item_id, new_answer=new_answer)

    # Получаем обновлённого кандидата
    item = await moderation_get_by_id(item_id)
    if not item:
        await callback.message.edit_text(
            f"✅ <b>Ответ обновлён, но кандидат #{item_id} не найден</b>"
        )
        await callback.answer("Ошибка при загрузке кандидата")
        return

    # Формируем сообщение как в стандартной модерации
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
    keyboard = admin_candidate_kb(item_id=item['id'])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer("Изменения сохранены! ✅")


@router.callback_query(F.data.startswith("kb_edit_retry:"))
async def cb_kb_edit_retry(callback: CallbackQuery):
    """
    Модератор хочет переделать ответ заново.
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("Только администратор может это делать.", show_alert=True)
        return

    _, raw_id = callback.data.split(":")
    item_id = int(raw_id)

    if callback.from_user.id not in PENDING_EDIT_APPROVAL:
        await callback.answer("Сессия редактирования истекла.", show_alert=True)
        return

    stored_id, _ = PENDING_EDIT_APPROVAL[callback.from_user.id]

    if stored_id != item_id:
        await callback.answer("Несоответствие ID кандидата.", show_alert=True)
        return

    # Получаем оригинальные данные
    item = await moderation_get_by_id(item_id)
    if not item:
        await callback.answer("Кандидат не найден.", show_alert=True)
        return

    question = item["question"]
    answer = item["answer"]

    # Возвращаем в режим ввода инструкций
    WAITING_EDIT_INSTRUCTIONS[callback.from_user.id] = (item_id, question, answer)
    PENDING_EDIT_APPROVAL.pop(callback.from_user.id)

    await callback.message.answer(
        f"🔄 <b>Переделываем ответ для кандидата #{item_id}</b>\n\n"
        f"Опиши новые инструкции по изменению ответа:"
    )

    await callback.answer("Жду новые инструкции...")


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
    #   - category    = тип консультации (в kb_insert это первый параметр)
    #   - subcategory = культура (в kb_insert это второй параметр)
    category = "unknown"           # Тип консультации по умолчанию
    subcategory = "общая информация"  # Культура по умолчанию

    if raw_cat:
        # Форматы, которые ожидаем:
        #   1) "питание растений / малина" → category="питание растений", subcategory="малина"
        #   2) "малина" (только культура) → category="unknown", subcategory="малина"
        text = raw_cat.strip()

        if " / " in text:
            # "тип консультации / культура"
            raw_topic, raw_plant = text.split(" / ", 1)
            category = raw_topic.strip()        # Тип консультации
            subcategory = _normalize_culture_category(raw_plant)  # Культура
        else:
            # Без разделителя — считаем, что это просто культура
            category = "unknown"
            subcategory = _normalize_culture_category(text)

    question = item["question"]   # ПОЛНЫЙ ВОПРОС (root + уточнения)
    answer = item["answer"]

    # Эмбеддинги считаем по ВОПРОСУ
    embedding = await get_text_embedding(question)

    kb_id = await kb_insert(
        category=category,          # Тип консультации (или "unknown")
        subcategory=subcategory,    # Культура (растение)
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

    # Формируем строку с категорией (тип консультации / культура)
    if subcategory_safe:
        full_category = f"{category_safe} / {subcategory_safe}"
    else:
        full_category = category_safe

    new_text = (
        f"<b>Кандидат #{item_id}</b> добавлен в базу знаний.\n\n"
        f"<b>Категория (тип / культура):</b> {full_category}\n"
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
