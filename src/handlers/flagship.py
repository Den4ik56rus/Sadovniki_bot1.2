"""
Флагманский продукт — доступ к контенту через inline-кнопки.

Навигация:
    Профиль → 📂 Мои материалы → Продукт → Категория → Файл (PDF/видео)

Callback data:
    my_materials                           — список продуктов
    flagship_open:{product_key}            — обзор продукта
    flagship_cat:{pk}:{category_key}       — категория
    flagship_file:{pk}:{cat}:{file_type}   — отправка файла
    flagship_buy:{product_key}             — описание + кнопка оплаты
    flagship_pay:{product_key}             — создание платежа
    back_to_profile                        — назад в профиль
"""

import logging

from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)

from src.services.db.users_repo import get_or_create_user
from src.services.flagship.flagship_service import (
    load_product_config,
    get_available_products,
    has_product_access,
    get_user_products,
    send_flagship_file,
    resolve_file_path,
)

logger = logging.getLogger(__name__)

router = Router(name="flagship")

# Картинка-инструкция «Как пользоваться материалами»
_HOW_TO_USE_IMAGE = Path(__file__).resolve().parents[2] / "data" / "flagship" / "how_to_use_materials.png"

# message_id отправленного фото-инструкции по chat_id (для удаления при навигации назад)
_how_to_use_photo_msg: dict[int, int] = {}

# Эмодзи для категорий
_CATEGORY_EMOJI = {
    "nutrition": "🥗",
    "planting_care": "🌱",
    "protection": "🛡",
    "soil": "🌍",
    "varieties": "🫐",
    "pruning": "✂️",
    "season_plan": "📅",
}


# ---------------------------------------------------------------------------
# Мои материалы — список продуктов
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "my_materials")
async def handle_my_materials(callback: CallbackQuery) -> None:
    """Показывает купленные продукты и каталог."""
    user = callback.from_user
    internal_user_id = await get_or_create_user(
        telegram_user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    # Купленные продукты
    purchased = await get_user_products(internal_user_id)
    # Доступные для покупки
    available = get_available_products()

    # Проверяем тестовый доступ (ID 833...)
    purchased_keys = {p["product_key"] for p in purchased}
    for prod in available:
        if prod["product_key"] not in purchased_keys:
            if await has_product_access(internal_user_id, prod["product_key"], user.id):
                purchased.append({
                    "product_key": prod["product_key"],
                    "title": prod["title"],
                    "culture": prod.get("culture", ""),
                    "purchased_at": None,
                })
                purchased_keys.add(prod["product_key"])

    buttons = []
    text_parts = ["📂 <b>Мои материалы</b>\n"]

    if purchased:
        # Разделяем на программы и отдельные блоки
        programs = [p for p in purchased if p.get("product_type") != "single_block"]
        blocks = [p for p in purchased if p.get("product_type") == "single_block"]

        if programs:
            text_parts.append("📚 <b>Ваши программы:</b>")
            for p in programs:
                    buttons.append([InlineKeyboardButton(
                    text=p['title'],
                    callback_data=f"flagship_open:{p['product_key']}",
                )])

        if blocks:
            if programs:
                text_parts.append("")
            text_parts.append("📖 <b>Ваши тематические блоки:</b>")
            for p in blocks:
                emoji = _CATEGORY_EMOJI.get(p.get("topic_key", ""), "📖")
                buttons.append([InlineKeyboardButton(
                    text=f"{emoji} {p['title']}",
                    callback_data=f"flagship_block_open:{p['product_key']}",
                )])

    # Каталог — непокупленные
    not_purchased = [p for p in available if p["product_key"] not in purchased_keys]
    if not_purchased:
        if purchased:
            text_parts.append("")
        text_parts.append("🛒 <b>Доступные программы:</b>")
        for p in not_purchased:
            price = f"{p['price_rub']:,}".replace(",", " ")
            buttons.append([InlineKeyboardButton(
                text=f"{p['title']} — {price} ₽",
                callback_data=f"flagship_buy:{p['product_key']}",
            )])

    if not purchased and not not_purchased:
        text_parts.append("Пока нет доступных программ.")

    buttons.append([InlineKeyboardButton(
        text="◀️ Назад в профиль",
        callback_data="back_to_profile",
    )])

    # Удаляем фото-инструкцию, если она была отправлена ранее
    chat_id = callback.message.chat.id
    photo_mid = _how_to_use_photo_msg.pop(chat_id, None)
    if photo_mid:
        try:
            await callback.bot.delete_message(chat_id=chat_id, message_id=photo_mid)
        except Exception:
            pass

    await callback.message.edit_text(
        "\n".join(text_parts),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Назад в профиль
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "back_to_profile")
async def handle_back_to_profile(callback: CallbackQuery) -> None:
    """Удаляет сообщение «Мои материалы» и заново показывает профиль."""
    from src.handlers.menu import render_and_send_profile

    user = callback.from_user
    chat_id = callback.message.chat.id

    # Удаляем фото-инструкцию, если была
    photo_mid = _how_to_use_photo_msg.pop(chat_id, None)
    if photo_mid:
        try:
            await callback.bot.delete_message(chat_id=chat_id, message_id=photo_mid)
        except Exception:
            pass

    try:
        await callback.message.delete()
    except Exception:
        pass
    await render_and_send_profile(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        telegram_user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Обзор продукта — приветствие + категории
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("flagship_open:"))
async def handle_product_overview(callback: CallbackQuery) -> None:
    """Обзор купленного продукта: картинка-инструкция + категории."""
    product_key = callback.data.split(":", 1)[1]

    user = callback.from_user
    internal_user_id = await get_or_create_user(
        telegram_user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    if not await has_product_access(internal_user_id, product_key, user.id):
        await callback.answer("У вас нет доступа к этому продукту", show_alert=True)
        return

    try:
        config = load_product_config(product_key)
    except FileNotFoundError:
        await callback.answer("Продукт не найден", show_alert=True)
        return

    has_any_video = any(a.get("video") for a in config.get("articles", []))

    text = (
        f"<b>{config['title']}</b>\n\n"
        "Ваша программа включает 6 тематических блоков "
        "и сезонный план работ.\n\n"
        "Каждый блок содержит:\n"
        "• <b>Статья</b> (PDF) — теория и рекомендации\n"
        "• <b>Презентация</b> (PDF) — наглядный материал\n"
    )
    if has_any_video:
        text += "• <b>Видео</b> — практические приёмы\n"
    text += "\nВыберите раздел:"

    buttons = []
    for article in config["articles"]:
        emoji = _CATEGORY_EMOJI.get(article["key"], "📖")
        buttons.append([InlineKeyboardButton(
            text=f"{emoji} {article['title']}",
            callback_data=f"flagship_cat:{product_key}:{article['key']}",
        )])

    # Сезонный план
    if "season_plan" in config:
        sp = config["season_plan"]
        buttons.append([InlineKeyboardButton(
            text=f"📅 {sp['title']}",
            callback_data=f"flagship_cat:{product_key}:season_plan",
        )])

    buttons.append([InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="my_materials",
    )])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    chat_id = callback.message.chat.id

    # Отправляем картинку «Как пользоваться материалами» при первом открытии
    # (когда приходим из списка «Мои материалы», а не из «◀️ Назад к программе»)
    from_materials_list = callback.message.text and "Мои материалы" in callback.message.text
    if from_materials_list and _HOW_TO_USE_IMAGE.exists():
        try:
            await callback.message.delete()
        except Exception:
            pass
        try:
            photo_msg = await callback.bot.send_photo(
                chat_id=chat_id,
                photo=FSInputFile(_HOW_TO_USE_IMAGE),
            )
            _how_to_use_photo_msg[chat_id] = photo_msg.message_id
        except Exception as e:
            logger.warning(f"Failed to send how-to-use image: {e}")
        await callback.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    else:
        # Навигация назад из категории — просто edit_text
        try:
            await callback.message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        except Exception:
            # Fallback: удалить + отправить новое
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )

    await callback.answer()


# ---------------------------------------------------------------------------
# Отдельный блок (тема) — выбор формата
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("flagship_block_open:"))
async def handle_block_open(callback: CallbackQuery) -> None:
    """Показывает форматы для купленного отдельного блока (темы)."""
    block_product_key = callback.data.split(":", 1)[1]  # e.g. strawberry_summer__nutrition

    if "__" not in block_product_key:
        await callback.answer("Некорректный ключ блока", show_alert=True)
        return

    base_key, topic_key = block_product_key.split("__", 1)

    user = callback.from_user
    internal_user_id = await get_or_create_user(
        telegram_user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    if not await has_product_access(internal_user_id, block_product_key, user.id):
        await callback.answer("У вас нет доступа", show_alert=True)
        return

    try:
        config = load_product_config(base_key)
    except FileNotFoundError:
        await callback.answer("Продукт не найден", show_alert=True)
        return

    # Найти тему
    cat_data = None
    for article in config.get("articles", []):
        if article["key"] == topic_key:
            cat_data = article
            break
    if not cat_data:
        await callback.answer("Тема не найдена", show_alert=True)
        return

    title = cat_data["title"]
    has_video = bool(cat_data.get("video"))

    emoji = _CATEGORY_EMOJI.get(topic_key, "📖")
    text = (
        f"{emoji} <b>{title}</b>\n"
        f"<i>{config.get('title', base_key)}</i>\n\n"
        f"Выберите формат материала:"
    )

    buttons = []

    if cat_data.get("article_pdf"):
        buttons.append([InlineKeyboardButton(
            text="📄 Статья (PDF)",
            callback_data=f"flagship_file:{base_key}:{topic_key}:article:blk:{block_product_key}",
        )])

    if cat_data.get("presentation_pdf"):
        buttons.append([InlineKeyboardButton(
            text="📊 Презентация (PDF)",
            callback_data=f"flagship_file:{base_key}:{topic_key}:presentation:blk:{block_product_key}",
        )])

    if has_video:
        buttons.append([InlineKeyboardButton(
            text="🎬 Видео",
            callback_data=f"flagship_file:{base_key}:{topic_key}:video:blk:{block_product_key}",
        )])

    buttons.append([InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="my_materials",
    )])

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Категория — выбор формата (статья / презентация / видео)
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("flagship_cat:"))
async def handle_category(callback: CallbackQuery) -> None:
    """Показывает доступные форматы для выбранной категории."""
    parts = callback.data.split(":")
    product_key = parts[1]
    category_key = parts[2]

    user = callback.from_user
    internal_user_id = await get_or_create_user(
        telegram_user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    if not await has_product_access(internal_user_id, product_key, user.id):
        await callback.answer("У вас нет доступа", show_alert=True)
        return

    try:
        config = load_product_config(product_key)
    except FileNotFoundError:
        await callback.answer("Продукт не найден", show_alert=True)
        return

    # Найти категорию
    if category_key == "season_plan":
        cat_data = config.get("season_plan", {})
        title = cat_data.get("title", "Сезонный план работ")
        has_video = False
    else:
        cat_data = None
        for article in config["articles"]:
            if article["key"] == category_key:
                cat_data = article
                break
        if not cat_data:
            await callback.answer("Раздел не найден", show_alert=True)
            return
        title = cat_data["title"]
        has_video = bool(cat_data.get("video"))

    emoji = _CATEGORY_EMOJI.get(category_key, "📖")
    text = f"{emoji} <b>{title}</b>\n\nВыберите формат материала:"

    buttons = []

    if cat_data.get("article_pdf"):
        buttons.append([InlineKeyboardButton(
            text="📄 Статья (PDF)",
            callback_data=f"flagship_file:{product_key}:{category_key}:article",
        )])

    if cat_data.get("presentation_pdf"):
        buttons.append([InlineKeyboardButton(
            text="📊 Презентация (PDF)",
            callback_data=f"flagship_file:{product_key}:{category_key}:presentation",
        )])

    if has_video:
        buttons.append([InlineKeyboardButton(
            text="🎬 Видео",
            callback_data=f"flagship_file:{product_key}:{category_key}:video",
        )])

    buttons.append([InlineKeyboardButton(
        text="◀️ Назад к программе",
        callback_data=f"flagship_open:{product_key}",
    )])

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Отправка файла
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("flagship_file:"))
async def handle_send_file(callback: CallbackQuery) -> None:
    """Отправляет файл пользователю (PDF или видео)."""
    parts = callback.data.split(":")
    product_key = parts[1]     # base product key (strawberry_summer)
    category_key = parts[2]
    file_type_key = parts[3]   # article, presentation, video

    # Для отдельных блоков: flagship_file:{base}:{topic}:{type}:blk:{block_key}
    access_key = product_key
    if len(parts) >= 6 and parts[4] == "blk":
        access_key = parts[5]  # block_product_key (strawberry_summer__nutrition)

    user = callback.from_user
    internal_user_id = await get_or_create_user(
        telegram_user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    if not await has_product_access(internal_user_id, access_key, user.id):
        await callback.answer("У вас нет доступа", show_alert=True)
        return

    try:
        config = load_product_config(product_key)
    except FileNotFoundError:
        await callback.answer("Продукт не найден", show_alert=True)
        return

    # Найти данные категории
    if category_key == "season_plan":
        cat_data = config.get("season_plan", {})
        title = cat_data.get("title", "Сезонный план работ")
    else:
        cat_data = None
        for article in config["articles"]:
            if article["key"] == category_key:
                cat_data = article
                break
        if not cat_data:
            await callback.answer("Раздел не найден", show_alert=True)
            return
        title = cat_data["title"]

    # Определить файл
    file_map = {
        "article": ("article_pdf", "document"),
        "presentation": ("presentation_pdf", "document"),
        "video": ("video", "video"),
    }

    if file_type_key not in file_map:
        await callback.answer("Неизвестный тип файла", show_alert=True)
        return

    config_field, send_type = file_map[file_type_key]
    relative_path = cat_data.get(config_field)

    if not relative_path:
        await callback.answer("Файл недоступен", show_alert=True)
        return

    file_path = resolve_file_path(product_key, relative_path)
    content_key = f"{category_key}:{file_type_key}"

    type_labels = {
        "article": "Статья",
        "presentation": "Презентация",
        "video": "Видео",
    }
    caption = f"{title} — {type_labels.get(file_type_key, '')}"

    await callback.answer("Отправляю файл...")

    try:
        await send_flagship_file(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            product_key=product_key,
            content_key=content_key,
            file_path=file_path,
            file_type=send_type,
            caption=caption,
        )
    except FileNotFoundError:
        await callback.message.answer("Файл не найден. Обратитесь в поддержку.")
        logger.error(f"Flagship file not found: {file_path}")
    except Exception as e:
        await callback.message.answer("Ошибка при отправке файла. Попробуйте позже.")
        logger.error(f"Error sending flagship file {content_key}: {e}")


# ---------------------------------------------------------------------------
# Описание продукта для покупки (каталог)
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("flagship_buy:"))
async def handle_buy_info(callback: CallbackQuery) -> None:
    """Описание продукта + кнопка оплаты."""
    product_key = callback.data.split(":", 1)[1]

    try:
        config = load_product_config(product_key)
    except FileNotFoundError:
        await callback.answer("Продукт не найден", show_alert=True)
        return

    price = config.get("price_rub", 0)
    price_fmt = f"{price:,}".replace(",", " ")

    categories = "\n".join(
        f"  • {a['title']}" for a in config.get("articles", [])
    )

    has_any_video = any(a.get("video") for a in config.get("articles", []))

    text = (
        f"<b>{config['title']}</b>\n\n"
        f"Полная система ухода на сезон:\n"
        f"{categories}\n\n"
        f"Каждый раздел включает:\n"
        f"• Статью с рекомендациями\n"
        f"• Презентацию с наглядными схемами\n"
    )
    if has_any_video:
        text += "• Видео с практическими приёмами\n"
    text += (
        f"\n+ 📅 Сезонный план работ по месяцам\n\n"
        f"Доступ <b>бессрочный</b>.\n\n"
        f"Стоимость: <b>{price_fmt} ₽</b>"
    )

    buttons = [
        [InlineKeyboardButton(
            text=f"💳 Оплатить {price_fmt} ₽",
            callback_data=f"flagship_pay:{product_key}",
        )],
        [InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="my_materials",
        )],
    ]

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Создание платежа
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("flagship_pay:"))
async def handle_create_payment(callback: CallbackQuery) -> None:
    """Создаёт платёж YooKassa и показывает ссылку."""
    product_key = callback.data.split(":", 1)[1]

    user = callback.from_user
    internal_user_id = await get_or_create_user(
        telegram_user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    # Уже куплен?
    if await has_product_access(internal_user_id, product_key, user.id):
        await callback.answer("У вас уже есть доступ!", show_alert=True)
        return

    try:
        config = load_product_config(product_key)
    except FileNotFoundError:
        await callback.answer("Продукт не найден", show_alert=True)
        return

    from src.services.payments.payment_service import create_flagship_payment
    from decimal import Decimal

    try:
        result = await create_flagship_payment(
            user_id=internal_user_id,
            telegram_user_id=user.id,
            product_key=product_key,
            product_title=config["title"],
            price_rub=Decimal(str(config["price_rub"])),
        )
    except Exception as e:
        logger.error(f"Error creating flagship payment: {e}")
        await callback.message.answer("Ошибка создания платежа. Попробуйте позже.")
        await callback.answer()
        return

    price_fmt = f"{config['price_rub']:,}".replace(",", " ")

    buttons = [
        [InlineKeyboardButton(
            text=f"💳 Оплатить {price_fmt} ₽",
            url=result["confirmation_url"],
        )],
        [InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"flagship_buy:{product_key}",
        )],
    ]

    await callback.message.edit_text(
        f"<b>{config['title']}</b>\n\n"
        f"Нажмите кнопку ниже для перехода к оплате.\n"
        f"После оплаты доступ откроется автоматически.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()
