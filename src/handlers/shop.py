"""
Магазин — постоянная точка входа в покупку продуктов.

Кнопка "🛍 Магазин" в главном меню → 3 карточки (система, блок, подписка)
→ выбор продукта → оффер с полными ценами (без скидок воронки) → оплата.

Подписка — с учётом персональной скидки пользователя.

Callback-префикс: shop_ (не конфликтует с quiz_us_ в upsell).
"""

import asyncio
import logging
import os

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    FSInputFile,
)

from src.handlers.common import (
    CONSULTATION_STATE,
    CONSULTATION_CONTEXT,
    set_consultation_state,
    clear_consultation_state,
)
from src.handlers.funnel_b_upsell import (
    UPSELL_CARD_SYSTEM,
    UPSELL_CARD_SYSTEM_ANIM,
    UPSELL_CARD_BLOCK,
    UPSELL_CARD_CONSULT,
    CONSULT_PROMO_IMAGE,
    CONSULT_TARIFFS_IMAGE,
    SEASONAL_OFFER_IMAGES,
    SEASONAL_TITLES,
    SEASONAL_FULL_PRICE,
    BLOCK_FULL_PRICE,
    TOPIC_EMOJI,
    ALL_CULTURES,
    CULTURES_WITH_VARIETY,
    get_discount,
    calc_discount,
    get_internal_user_id,
)

logger = logging.getLogger(__name__)

router = Router(name="shop")

# ---------------------------------------------------------------------------
# Цены магазина (полные, без скидок воронки)
# ---------------------------------------------------------------------------

SHOP_SEASONAL_PRICE = SEASONAL_FULL_PRICE  # 3990
SHOP_BLOCK_PRICE = BLOCK_FULL_PRICE        # 1990


# ---------------------------------------------------------------------------
# Клавиатуры (shop-специфичные, с shop_ callback prefix)
# ---------------------------------------------------------------------------

def _get_shop_cta_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"✅ Система на сезон — {SHOP_SEASONAL_PRICE} ₽",
            callback_data="shop_cta_seasonal",
        )],
        [InlineKeyboardButton(
            text=f"📂 Отдельный блок — {SHOP_BLOCK_PRICE} ₽",
            callback_data="shop_cta_block",
        )],
        [InlineKeyboardButton(
            text="💬 Подписка — от 690 ₽/мес",
            callback_data="shop_cta_consult",
        )],
    ])


def _get_shop_culture_picker(callback_prefix: str) -> InlineKeyboardMarkup:
    """Клавиатура выбора культуры с кнопкой «Назад» на shop_back_to_cta."""
    pairs = list(ALL_CULTURES)
    buttons = []
    for i in range(0, len(pairs), 2):
        row = [InlineKeyboardButton(text=pairs[i][1], callback_data=f"{callback_prefix}{pairs[i][0]}")]
        if i + 1 < len(pairs):
            row.append(InlineKeyboardButton(text=pairs[i+1][1], callback_data=f"{callback_prefix}{pairs[i+1][0]}"))
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="shop_back_to_cta")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _get_shop_variety_picker(culture_key: str, callback_prefix: str) -> InlineKeyboardMarkup:
    """Клавиатура летняя/ремонтантная с «Назад к культурам»."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="☀️ Летняя",
            callback_data=f"{callback_prefix}{culture_key}_summer",
        )],
        [InlineKeyboardButton(
            text="🔄 Ремонтантная",
            callback_data=f"{callback_prefix}{culture_key}_remontant",
        )],
        [InlineKeyboardButton(
            text="⬅️ Назад к культурам",
            callback_data=f"{callback_prefix}back_cultures",
        )],
    ])


def _shop_mark_selected(markup: InlineKeyboardMarkup, selected_data: str) -> InlineKeyboardMarkup:
    """Заменяет клавиатуру на одну кнопку с галочкой."""
    for row in markup.inline_keyboard:
        for btn in row:
            if btn.callback_data == selected_data:
                return InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=f"✅ {btn.text}", callback_data="shop_noop")]
                ])
    return markup


async def _build_shop_consult_tariff_keyboard(user_id: int | None) -> InlineKeyboardMarkup:
    """Строит клавиатуру тарифов подписки с shop_ prefix."""
    from src.services.db import subscription_plan_repo

    plans = await subscription_plan_repo.get_all_active()
    buttons = []

    for plan in plans:
        price = int(plan["price_rub"])
        discount_pct, _ = await get_discount(user_id, plan)

        if discount_pct > 0:
            discounted = calc_discount(price, discount_pct)
            text = f"{plan['name']}  {price}₽ → {discounted}₽/мес"
        else:
            text = f"{plan['name']}  {price}₽/мес"

        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"shop_consult_plan_{plan['id']}",
        )])

    buttons.append([InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data="shop_back_to_cta",
    )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ---------------------------------------------------------------------------
# Обработчик кнопки «🛍 Магазин»
# ---------------------------------------------------------------------------

async def send_shop_cards(bot, tg_id: int) -> None:
    """Отправляет 3 карточки + CTA. Вызывается из ReplyKeyboard и inline-меню."""
    logger.info(f"[shop] Пользователь {tg_id} открыл магазин")

    # Очищаем предыдущее состояние
    await clear_consultation_state(tg_id)

    # 1. Система на сезон — GIF (.mp4) с подписью «⭐ Рекомендуем для вас»
    try:
        if os.path.exists(UPSELL_CARD_SYSTEM_ANIM):
            anim = FSInputFile(UPSELL_CARD_SYSTEM_ANIM)
            await bot.send_animation(chat_id=tg_id, animation=anim, caption="⭐ Рекомендуем для вас")
        else:
            photo = FSInputFile(UPSELL_CARD_SYSTEM)
            await bot.send_photo(chat_id=tg_id, photo=photo, caption="⭐ Рекомендуем для вас")
    except Exception as e:
        logger.warning(f"[shop] Не удалось отправить карточку системы: {e}")

    await asyncio.sleep(1)

    # 2. Отдельный блок — статичная PNG
    try:
        photo = FSInputFile(UPSELL_CARD_BLOCK)
        await bot.send_photo(chat_id=tg_id, photo=photo)
    except Exception as e:
        logger.warning(f"[shop] Не удалось отправить карточку блока: {e}")

    await asyncio.sleep(1)

    # 3. Подписка — статичная PNG
    try:
        photo = FSInputFile(UPSELL_CARD_CONSULT)
        await bot.send_photo(chat_id=tg_id, photo=photo)
    except Exception as e:
        logger.warning(f"[shop] Не удалось отправить карточку подписки: {e}")

    await asyncio.sleep(0.5)

    # CTA-кнопки
    await bot.send_message(
        chat_id=tg_id,
        text="Выберите подходящий вариант:",
        reply_markup=_get_shop_cta_keyboard(),
    )

    ctx = CONSULTATION_CONTEXT.get(tg_id, {})
    await set_consultation_state(tg_id, "shop_cta", ctx)


@router.message(F.text == "🛍 Магазин")
async def handle_shop_button(message: Message) -> None:
    """Обратная совместимость — старая ReplyKeyboard кнопка «🛍 Магазин»."""
    from src.keyboards.main.main_menu import REMOVE_REPLY_KEYBOARD
    _tmp = await message.answer("⏳", reply_markup=REMOVE_REPLY_KEYBOARD)
    try:
        await _tmp.delete()
    except Exception:
        pass
    await send_shop_cards(message.bot, message.from_user.id)


# ---------------------------------------------------------------------------
# CTA: Система на сезон
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "shop_cta_seasonal")
async def handle_shop_cta_seasonal(callback: CallbackQuery) -> None:
    """CTA: Система на сезон — выбор культуры."""
    tg_id = callback.from_user.id

    await callback.message.edit_reply_markup(
        reply_markup=_shop_mark_selected(callback.message.reply_markup, callback.data)
    )
    await callback.answer()

    await callback.message.answer(
        text="Выберите культуру:",
        reply_markup=_get_shop_culture_picker("shop_culture_sys_"),
    )

    ctx = CONSULTATION_CONTEXT.get(tg_id, {})
    await set_consultation_state(tg_id, "shop_seasonal_culture", ctx)


@router.callback_query(F.data == "shop_pick_culture_sys")
async def handle_shop_pick_culture_sys(callback: CallbackQuery) -> None:
    """Показывает выбор культуры для системы (кнопка «Выбрать другую культуру»)."""
    await callback.answer()
    await callback.message.edit_text(
        text="Выберите культуру:",
        reply_markup=_get_shop_culture_picker("shop_culture_sys_"),
    )


@router.callback_query(F.data == "shop_culture_sys_back_cultures")
async def handle_shop_sys_back_cultures(callback: CallbackQuery) -> None:
    """Назад к выбору культуры (из летняя/ремонтантная)."""
    await callback.answer()
    await callback.message.edit_text(
        text="Выберите культуру:",
        reply_markup=_get_shop_culture_picker("shop_culture_sys_"),
    )


@router.callback_query(F.data.startswith("shop_culture_sys_"))
async def handle_shop_culture_sys(callback: CallbackQuery) -> None:
    """Выбор культуры для системы."""
    tg_id = callback.from_user.id
    await callback.answer()

    raw_key = callback.data.replace("shop_culture_sys_", "")

    # Если финальный product_key — показываем оффер
    if raw_key in SEASONAL_OFFER_IMAGES:
        await _show_shop_seasonal_offer(callback, tg_id, raw_key)
        return

    culture_key = raw_key

    # Клубника/малина — выбор летняя/ремонтантная
    if culture_key in CULTURES_WITH_VARIETY:
        culture_label = dict(ALL_CULTURES).get(culture_key, culture_key)
        await callback.message.edit_text(
            text=f"{culture_label} — выберите тип:",
            reply_markup=_get_shop_variety_picker(culture_key, "shop_culture_sys_"),
        )
        return

    # Без выбора сорта — оффер напрямую
    await _show_shop_seasonal_offer(callback, tg_id, culture_key)


async def _show_shop_seasonal_offer(callback: CallbackQuery, tg_id: int, product_key: str) -> None:
    """Оффер сезонной системы по полной цене."""
    ctx = CONSULTATION_CONTEXT.get(tg_id, {})
    ctx["shop_product_key"] = product_key

    internal_user_id = await get_internal_user_id(tg_id)

    # Проверить, не куплено ли
    from src.services.db.flagship_repo import check_access
    if internal_user_id and await check_access(internal_user_id, product_key):
        await callback.message.answer(
            "У вас уже есть доступ к этой программе!\n"
            "Нажмите «👤 Мой профиль» → «📂 Мои материалы», чтобы открыть."
        )
        await clear_consultation_state(tg_id)
        return

    # Картинка
    image_path = SEASONAL_OFFER_IMAGES.get(product_key)
    if image_path:
        try:
            photo = FSInputFile(image_path)
            await callback.message.answer_photo(photo=photo)
        except Exception as e:
            logger.warning(f"[shop] Не удалось отправить картинку {image_path}: {e}")

    # Оффер (полная цена, без зачёркивания)
    title = SEASONAL_TITLES.get(product_key, "Сезонная система ухода")
    offer_text = (
        f"<b>{title}</b>\n\n"
        f"📋 Календарь работ по фазам\n"
        f"📖 6 ключевых направлений ухода\n"
        f"🎥 Короткие видео ролики\n"
        f"📊 Презентации со схемами\n"
        f"📝 Подробные статьи по каждой теме\n\n"
        f"<b>{SHOP_SEASONAL_PRICE} ₽</b> — доступ бессрочный"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"💳 Оплатить {SHOP_SEASONAL_PRICE} ₽",
            callback_data="shop_pay_seasonal",
        )],
        [InlineKeyboardButton(
            text="🔄 Выбрать другую культуру",
            callback_data="shop_pick_culture_sys",
        )],
        [InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="shop_back_to_cta",
        )],
    ])

    await callback.message.answer(
        text=offer_text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )

    ctx["shop_product_key"] = product_key
    await set_consultation_state(tg_id, "shop_seasonal_offer", ctx)


@router.callback_query(F.data == "shop_pay_seasonal")
async def handle_shop_pay_seasonal(callback: CallbackQuery) -> None:
    """Создаёт платёж за сезонную систему по полной цене."""
    tg_id = callback.from_user.id
    await callback.answer()

    ctx = CONSULTATION_CONTEXT.get(tg_id, {})
    product_key = ctx.get("shop_product_key", "strawberry_summer")

    internal_user_id = await get_internal_user_id(tg_id)
    if not internal_user_id:
        await callback.message.answer("Произошла ошибка. Попробуйте позже.")
        return

    from src.services.payments.payment_service import create_flagship_payment
    from decimal import Decimal

    title = SEASONAL_TITLES.get(product_key, "Сезонная система ухода")

    try:
        result = await create_flagship_payment(
            user_id=internal_user_id,
            telegram_user_id=tg_id,
            product_key=product_key,
            product_title=title,
            price_rub=Decimal(str(SHOP_SEASONAL_PRICE)),
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"💳 Перейти к оплате — {SHOP_SEASONAL_PRICE} ₽",
                url=result["confirmation_url"],
            )],
        ])
        await callback.message.answer(
            "Нажмите кнопку ниже для перехода к оплате 👇",
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.error(f"[shop] Ошибка создания платежа за систему: {e}")
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже или напишите нам."
        )

    await clear_consultation_state(tg_id)


# ---------------------------------------------------------------------------
# CTA: Отдельный блок
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "shop_cta_block")
async def handle_shop_cta_block(callback: CallbackQuery) -> None:
    """CTA: Отдельный блок — выбор культуры."""
    tg_id = callback.from_user.id

    await callback.message.edit_reply_markup(
        reply_markup=_shop_mark_selected(callback.message.reply_markup, callback.data)
    )
    await callback.answer()

    await callback.message.answer(
        text="Выберите культуру:",
        reply_markup=_get_shop_culture_picker("shop_culture_blk_"),
    )

    ctx = CONSULTATION_CONTEXT.get(tg_id, {})
    await set_consultation_state(tg_id, "shop_block_culture", ctx)


@router.callback_query(F.data == "shop_pick_culture_blk")
async def handle_shop_pick_culture_blk(callback: CallbackQuery) -> None:
    """Кнопка «Выбрать другую культуру» для блока."""
    await callback.answer()
    await callback.message.edit_text(
        text="Выберите культуру:",
        reply_markup=_get_shop_culture_picker("shop_culture_blk_"),
    )


@router.callback_query(F.data == "shop_culture_blk_back_cultures")
async def handle_shop_blk_back_cultures(callback: CallbackQuery) -> None:
    """Назад к выбору культуры (из летняя/ремонтантная) для блока."""
    await callback.answer()
    await callback.message.edit_text(
        text="Выберите культуру:",
        reply_markup=_get_shop_culture_picker("shop_culture_blk_"),
    )


@router.callback_query(F.data.startswith("shop_culture_blk_"))
async def handle_shop_culture_blk(callback: CallbackQuery) -> None:
    """Выбор культуры для блока."""
    tg_id = callback.from_user.id
    await callback.answer()

    raw_key = callback.data.replace("shop_culture_blk_", "")

    # Финальный product_key — показываем темы
    if raw_key not in dict(ALL_CULTURES):
        await _show_shop_block_topics(callback, tg_id, raw_key)
        return

    culture_key = raw_key

    # Клубника/малина — летняя/ремонтантная
    if culture_key in CULTURES_WITH_VARIETY:
        culture_label = dict(ALL_CULTURES).get(culture_key, culture_key)
        await callback.message.edit_text(
            text=f"{culture_label} — выберите тип:",
            reply_markup=_get_shop_variety_picker(culture_key, "shop_culture_blk_"),
        )
        return

    await _show_shop_block_topics(callback, tg_id, culture_key)


async def _show_shop_block_topics(callback: CallbackQuery, tg_id: int, product_key: str) -> None:
    """Показывает 6 тем для выбранной культуры."""
    from src.services.flagship.flagship_service import load_product_config

    try:
        config = load_product_config(product_key)
    except FileNotFoundError:
        culture_labels = dict(ALL_CULTURES)
        label = SEASONAL_TITLES.get(product_key, culture_labels.get(product_key, product_key))
        await callback.message.edit_text(
            f"Вы выбрали: <b>{label}</b>\n\n"
            f"Тематические блоки для этой культуры скоро будут доступны! 🌱",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="🔄 Выбрать другую культуру",
                    callback_data="shop_pick_culture_blk",
                )],
                [InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="shop_back_to_cta",
                )],
            ]),
            parse_mode="HTML",
        )
        return

    title = config.get("title", product_key)
    articles = config.get("articles", [])

    buttons = []
    for i in range(0, len(articles), 2):
        row = []
        for article in articles[i:i+2]:
            emoji = TOPIC_EMOJI.get(article["key"], "📖")
            row.append(InlineKeyboardButton(
                text=f"{emoji} {article['title']}",
                callback_data=f"shop_blk_topic:{product_key}:{article['key']}",
            ))
        buttons.append(row)

    buttons.append([InlineKeyboardButton(
        text="🔄 Выбрать другую культуру",
        callback_data="shop_pick_culture_blk",
    )])

    await callback.message.edit_text(
        f"<b>{title}</b>\n\n"
        f"Выберите тему:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )

    ctx = CONSULTATION_CONTEXT.get(tg_id, {})
    ctx["shop_block_product_key"] = product_key
    await set_consultation_state(tg_id, "shop_block_topics", ctx)


@router.callback_query(F.data.startswith("shop_blk_topic:"))
async def handle_shop_block_topic(callback: CallbackQuery) -> None:
    """Выбрана тема — оффер с полной ценой."""
    tg_id = callback.from_user.id
    await callback.answer()

    parts = callback.data.split(":")
    product_key = parts[1]
    topic_key = parts[2]

    await _show_shop_block_offer(callback, tg_id, product_key, topic_key)


async def _show_shop_block_offer(
    callback: CallbackQuery, tg_id: int, product_key: str, topic_key: str,
) -> None:
    """Оффер для одного блока по полной цене."""
    from src.services.flagship.flagship_service import load_product_config

    try:
        config = load_product_config(product_key)
    except FileNotFoundError:
        await callback.message.answer("Продукт не найден. Попробуйте другую культуру.")
        return

    topic_title = topic_key
    topic_data = None
    for article in config.get("articles", []):
        if article["key"] == topic_key:
            topic_title = article["title"]
            topic_data = article
            break

    if not topic_data:
        await callback.message.answer("Тема не найдена.")
        return

    # Проверить, не куплено ли
    internal_user_id = await get_internal_user_id(tg_id)
    block_product_key = f"{product_key}__{topic_key}"
    if internal_user_id:
        from src.services.db.flagship_repo import check_access
        if await check_access(internal_user_id, block_product_key):
            await callback.message.edit_text(
                f"У вас уже есть доступ к теме «{topic_title}»!\n"
                f"Нажмите «👤 Мой профиль» → «📂 Мои материалы», чтобы открыть.",
                parse_mode="HTML",
            )
            await clear_consultation_state(tg_id)
            return

    emoji = TOPIC_EMOJI.get(topic_key, "📖")
    culture_title = SEASONAL_TITLES.get(product_key, config.get("title", ""))

    content_lines = []
    if topic_data.get("article_pdf"):
        content_lines.append("📝 Подробная статья с рекомендациями")
    if topic_data.get("presentation_pdf"):
        content_lines.append("📊 Презентация со схемами")
    if topic_data.get("video"):
        content_lines.append("🎥 Видео с практическими приёмами")

    content_text = "\n".join(content_lines)

    # Полная цена, без зачёркивания
    offer_text = (
        f"{emoji} <b>{topic_title}</b>\n"
        f"<i>{culture_title}</i>\n\n"
        f"{content_text}\n\n"
        f"Доступ <b>бессрочный</b>.\n\n"
        f"<b>{SHOP_BLOCK_PRICE} ₽</b>"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"💳 Оплатить {SHOP_BLOCK_PRICE} ₽",
            callback_data=f"shop_pay_block:{product_key}:{topic_key}",
        )],
        [InlineKeyboardButton(
            text="🔄 Выбрать другую тему",
            callback_data=f"shop_blk_back_topics:{product_key}",
        )],
        [InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="shop_back_to_cta",
        )],
    ])

    await callback.message.edit_text(
        text=offer_text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )

    ctx = CONSULTATION_CONTEXT.get(tg_id, {})
    ctx["shop_block_product_key"] = product_key
    ctx["shop_block_topic_key"] = topic_key
    await set_consultation_state(tg_id, "shop_block_offer", ctx)


@router.callback_query(F.data.startswith("shop_blk_back_topics:"))
async def handle_shop_back_to_topics(callback: CallbackQuery) -> None:
    """Назад к выбору темы."""
    tg_id = callback.from_user.id
    await callback.answer()

    product_key = callback.data.split(":", 1)[1]
    await _show_shop_block_topics(callback, tg_id, product_key)


@router.callback_query(F.data.startswith("shop_pay_block:"))
async def handle_shop_pay_block(callback: CallbackQuery) -> None:
    """Создаёт платёж за один блок по полной цене."""
    tg_id = callback.from_user.id
    await callback.answer()

    parts = callback.data.split(":")
    product_key = parts[1]
    topic_key = parts[2]

    internal_user_id = await get_internal_user_id(tg_id)
    if not internal_user_id:
        await callback.message.answer("Произошла ошибка. Попробуйте позже.")
        return

    from src.services.flagship.flagship_service import load_product_config

    try:
        config = load_product_config(product_key)
    except FileNotFoundError:
        await callback.message.answer("Продукт не найден.")
        return

    topic_title = topic_key
    for article in config.get("articles", []):
        if article["key"] == topic_key:
            topic_title = article["title"]
            break

    culture_title = SEASONAL_TITLES.get(product_key, config.get("title", ""))
    full_title = f"{topic_title} — {culture_title}"
    block_product_key = f"{product_key}__{topic_key}"

    from src.services.payments.payment_service import create_flagship_payment
    from decimal import Decimal

    try:
        result = await create_flagship_payment(
            user_id=internal_user_id,
            telegram_user_id=tg_id,
            product_key=block_product_key,
            product_title=full_title,
            price_rub=Decimal(str(SHOP_BLOCK_PRICE)),
            product_type="single_block",
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"💳 Перейти к оплате — {SHOP_BLOCK_PRICE} ₽",
                url=result["confirmation_url"],
            )],
        ])
        await callback.message.answer(
            "Нажмите кнопку ниже для перехода к оплате 👇",
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.error(f"[shop] Ошибка создания платежа за блок: {e}")
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже или напишите нам."
        )

    await clear_consultation_state(tg_id)


# ---------------------------------------------------------------------------
# CTA: Подписка
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "shop_cta_consult")
async def handle_shop_cta_consult(callback: CallbackQuery) -> None:
    """CTA: Подписка — промо + тарифы + кнопки."""
    tg_id = callback.from_user.id

    await callback.message.edit_reply_markup(
        reply_markup=_shop_mark_selected(callback.message.reply_markup, callback.data)
    )
    await callback.answer()

    internal_user_id = await get_internal_user_id(tg_id)

    # 1. Промо-картинка
    try:
        promo = FSInputFile(CONSULT_PROMO_IMAGE)
        await callback.message.answer_photo(photo=promo)
    except Exception as e:
        logger.warning(f"[shop] Не удалось отправить промо: {e}")

    await asyncio.sleep(1)

    # 2. Картинка тарифов
    try:
        tariffs = FSInputFile(CONSULT_TARIFFS_IMAGE)
        await callback.message.answer_photo(photo=tariffs)
    except Exception as e:
        logger.warning(f"[shop] Не удалось отправить тарифы: {e}")

    await asyncio.sleep(0.5)

    # 3. Кнопки тарифов с персональной скидкой
    keyboard = await _build_shop_consult_tariff_keyboard(internal_user_id)

    await callback.message.answer(
        text=(
            "Режим консультаций работает по системе токенов.\n"
            "Стандартный ответ — 1 токен\n"
            "Подробный ответ — 2 токена\n\n"
            "Выберите подходящий тариф — большой пакет токенов выгоднее! 👇"
        ),
        reply_markup=keyboard,
    )

    ctx = CONSULTATION_CONTEXT.get(tg_id, {})
    await set_consultation_state(tg_id, "shop_consult_tariff", ctx)


@router.callback_query(F.data.startswith("shop_consult_plan_"))
async def handle_shop_consult_plan_detail(callback: CallbackQuery) -> None:
    """Описание тарифа + кнопка оплаты."""
    tg_id = callback.from_user.id
    await callback.answer()

    plan_id = int(callback.data.replace("shop_consult_plan_", ""))

    from src.services.db import subscription_plan_repo
    plan = await subscription_plan_repo.get_by_id(plan_id)
    if not plan:
        await callback.message.answer("Тариф не найден. Попробуйте ещё раз.")
        return

    internal_user_id = await get_internal_user_id(tg_id)
    original_price = int(plan["price_rub"])
    qty = plan.get("tokens_included", 0)
    carryover = plan.get("max_carryover", 0)

    discount_pct, bonus_tokens = await get_discount(internal_user_id, plan)
    discounted_price = calc_discount(original_price, discount_pct)

    from src.pricing import pluralize_questions
    lines = [
        f"<b>📅 {plan['name']}</b>\n",
    ]

    if discount_pct > 0:
        lines.append(
            f"💰 Цена: <s>{original_price} ₽</s> → <b>{discounted_price} ₽</b>/мес "
            f"(скидка {discount_pct}%)"
        )
    else:
        lines.append(f"💰 Цена: <b>{original_price} ₽</b>/мес")

    lines.append(f"⏱ Срок: {plan['duration_days']} дней")

    if bonus_tokens > 0:
        lines.append(
            f"🎁 Лимит: {qty} + {bonus_tokens} бонус = "
            f"<b>{qty + bonus_tokens} токенов</b> в месяц"
        )
    else:
        lines.append(f"🎁 Лимит: {pluralize_questions(qty)} в месяц")

    if carryover > 0:
        lines.append(f"🔄 Перенос: до {carryover} неиспользованных на след. месяц")

    lines.append("")
    lines.append("Нажмите кнопку ниже для оплаты.")

    detail_text = "\n".join(lines)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"💳 Оплатить {discounted_price} ₽",
            callback_data=f"shop_pay_consult_{plan_id}",
        )],
        [InlineKeyboardButton(
            text="⬅️ Назад к тарифам",
            callback_data="shop_back_to_consult_tariffs",
        )],
    ])

    await callback.message.edit_text(
        text=detail_text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )

    ctx = CONSULTATION_CONTEXT.get(tg_id, {})
    ctx["shop_consult_plan_id"] = plan_id
    await set_consultation_state(tg_id, "shop_consult_detail", ctx)


@router.callback_query(F.data.startswith("shop_pay_consult_"))
async def handle_shop_pay_consult(callback: CallbackQuery) -> None:
    """Создаёт платёж за подписку."""
    tg_id = callback.from_user.id
    await callback.answer()

    plan_id = int(callback.data.replace("shop_pay_consult_", ""))

    internal_user_id = await get_internal_user_id(tg_id)
    if not internal_user_id:
        await callback.message.answer("Произошла ошибка. Попробуйте позже.")
        return

    from src.services.payments import payment_service
    from src.config import settings

    try:
        payment = await payment_service.create_subscription_payment(
            user_id=internal_user_id,
            telegram_user_id=tg_id,
            plan_id=plan_id,
            return_url=settings.YOOKASSA_RETURN_URL,
        )

        pay_amount = int(payment["amount"])
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"💳 Перейти к оплате — {pay_amount} ₽",
                url=payment["confirmation_url"],
            )],
        ])
        await callback.message.answer(
            "Нажмите кнопку ниже для перехода к оплате 👇",
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.error(f"[shop] Ошибка создания платежа за подписку: {e}")
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже или напишите нам."
        )

    await clear_consultation_state(tg_id)


@router.callback_query(F.data == "shop_back_to_consult_tariffs")
async def handle_shop_back_to_tariffs(callback: CallbackQuery) -> None:
    """Возврат к выбору тарифа."""
    tg_id = callback.from_user.id
    await callback.answer()

    internal_user_id = await get_internal_user_id(tg_id)
    keyboard = await _build_shop_consult_tariff_keyboard(internal_user_id)

    tariff_text = (
        "Режим консультаций работает по системе токенов.\n"
        "Стандартный ответ — 1 токен\n"
        "Подробный ответ — 2 токена\n\n"
        "Выберите подходящий тариф — большой пакет токенов выгоднее! 👇"
    )
    try:
        await callback.message.edit_text(
            text=tariff_text,
            reply_markup=keyboard,
        )
    except Exception:
        await callback.message.answer(
            text=tariff_text,
            reply_markup=keyboard,
        )

    ctx = CONSULTATION_CONTEXT.get(tg_id, {})
    await set_consultation_state(tg_id, "shop_consult_tariff", ctx)


# ---------------------------------------------------------------------------
# Навигация: назад к CTA
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "shop_back_to_cta")
async def handle_shop_back_to_cta(callback: CallbackQuery) -> None:
    """Возврат к выбору CTA."""
    tg_id = callback.from_user.id
    await callback.answer()

    try:
        await callback.message.edit_text(
            text="Выберите подходящий вариант:",
            reply_markup=_get_shop_cta_keyboard(),
        )
    except Exception:
        await callback.message.answer(
            text="Выберите подходящий вариант:",
            reply_markup=_get_shop_cta_keyboard(),
        )

    ctx = CONSULTATION_CONTEXT.get(tg_id, {})
    await set_consultation_state(tg_id, "shop_cta", ctx)


@router.callback_query(F.data == "shop_noop")
async def handle_shop_noop(callback: CallbackQuery) -> None:
    """Заглушка для уже выбранных кнопок."""
    await callback.answer()


# ---------------------------------------------------------------------------
# Guard: текстовые сообщения во время shop-навигации
# ---------------------------------------------------------------------------

@router.message(
    F.text,
    lambda msg: CONSULTATION_STATE.get(msg.from_user.id, "").startswith("shop_"),
)
async def handle_text_during_shop(message: Message) -> None:
    """Перехватываем текст, когда ожидаем нажатие кнопки."""
    await message.answer("Пожалуйста, выберите один из вариантов выше 👆")
