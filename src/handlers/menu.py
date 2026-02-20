# src/handlers/menu.py

# Импортируем Router и F (фильтры) из aiogram
from aiogram import Router, F                  # Router — для группировки хендлеров, F — для фильтрации апдейтов
# Импортируем фильтр для команды /start
from aiogram.filters import CommandStart       # CommandStart — срабатывает на /start
# Импортируем типы сообщений и callback-запросов
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo  # Message — входящее сообщение, CallbackQuery — нажатие инлайн-кнопки

# Импортируем конфиг для WebApp URL
from src.config import settings

# Импортируем функции работы с БД: пользователи, темы, логи сообщений
from src.services.db.users_repo import get_or_create_user, count_all_users, user_exists
from src.services.db.topics_repo import get_or_create_open_topic     # Создание/поиск "открытой" темы (диалога)
from src.services.db.messages_repo import log_message                # Логирование сообщений в таблицу messages
from src.services.db.moderation_repo import moderation_count_pending # Подсчёт вопросов на модерации

# Импортируем глобальное состояние консультации и утилиту для сборки session_id
from src.handlers.common import CONSULTATION_STATE, CONSULTATION_CONTEXT, build_session_id_from_message

# Импортируем функцию, создающую клавиатуру главного меню
from src.keyboards.main.main_menu import get_main_keyboard, get_admin_start_keyboard

# Импортируем инлайн-меню консультаций (6 тем + кнопка "Закрыть")
from src.keyboards.consultation.common import CONSULTATION_MENU_INLINE_KB, CONSULTATION_ENTRY_TEXT, EXAMPLE_QUESTIONS, get_example_questions_keyboard
from src.handlers.consultation.entry import _log_bot_msg, _log_user_callback, serialize_keyboard, run_consultation_pipeline

# Импортируем список админов
from src.handlers.admin import ADMIN_IDS

# Создаём роутер для этого модуля
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """
    Обработчик команды /start.

    1) Регистрирует (или находит) пользователя в БД.
    2) Обрабатывает start-параметр для отслеживания источника трафика.
    3) Находит или создаёт открытую тему (topic).
    4) Логирует /start и приветственный текст.
    5) Показывает клавиатуру главного меню (для админа - специальную).
    6) Сбрасывает состояние консультации для этого пользователя.

    Поддерживает deep links: https://t.me/BOT?start=site → источник "Сайт"
    """
    session_id = build_session_id_from_message(message)

    # Извлекаем start-параметр для отслеживания источника
    # Формат: "/start site" → start_param = "site"
    start_param = None
    if message.text and len(message.text) > 7:  # "/start X" минимум 8 символов
        start_param = message.text[7:].strip()

    user = message.from_user
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

    # Проверяем, новый ли это пользователь (до создания)
    is_new_user = not await user_exists(telegram_user_id)

    # Определяем инвайт-ссылку из start_param (campaign tracking)
    invite_link_code = None
    if start_param and start_param.startswith("inv_"):
        invite_link_code = start_param[4:]
        start_param = None  # Не обрабатывать как обычный source

    # Определяем реферальный код из start_param
    referral_code = None
    if start_param and start_param.startswith("ref_"):
        referral_code = start_param[4:]
        start_param = None  # Не обрабатывать как обычный source

    user_id = await get_or_create_user(
        telegram_user_id=telegram_user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
    )

    # Скачиваем/обновляем аватар пользователя из Telegram
    from src.services.avatars import download_user_avatar
    from src.services.db.users_repo import update_user_avatar
    avatar_filename = await download_user_avatar(message.bot, telegram_user_id)
    if avatar_filename:
        await update_user_avatar(user_id, avatar_filename)

    # Обработка реферальной ссылки (только для новых пользователей)
    if is_new_user and referral_code:
        from src.services.db.referral_repo import (
            get_user_id_by_referral_code, create_referral, grant_referral_bonuses
        )
        referrer_id = await get_user_id_by_referral_code(referral_code)
        if referrer_id and referrer_id != user_id:
            await create_referral(referrer_id, user_id)
            referrer_bonus, _ = await grant_referral_bonuses(referrer_id, user_id)
            # Источник трафика — реферал
            from src.services.db.client_funnel_repo import set_initial_source
            await set_initial_source(user_id, "Реферал")

            # Уведомляем реферера о начислении бонуса
            if referrer_bonus > 0:
                try:
                    from src.services.db.pool import get_pool as _get_pool
                    _pool = _get_pool()
                    async with _pool.acquire() as _conn:
                        referrer_tg_id = await _conn.fetchval(
                            "SELECT telegram_user_id FROM users WHERE id = $1",
                            referrer_id,
                        )
                    if referrer_tg_id:
                        from src.pricing import pluralize_questions
                        notify_text = (
                            f"🎉 Спасибо, что цените и делитесь нашим сервисом!\n\n"
                            f"По вашей ссылке зарегистрировался новый пользователь. "
                            f"В благодарность мы начислили вам <b>{pluralize_questions(referrer_bonus)}</b>."
                        )
                        await message.bot.send_message(
                            chat_id=referrer_tg_id,
                            text=notify_text,
                            parse_mode="HTML",
                        )
                except Exception as e:
                    logger.warning(f"Не удалось уведомить реферера {referrer_id}: {e}")

    # Обработка инвайт-ссылки (campaign tracking)
    if invite_link_code:
        from src.services.db.invite_link_repo import (
            get_invite_link_by_code, track_user_invite_link
        )
        inv_link = await get_invite_link_by_code(invite_link_code)
        if inv_link:
            was_new = await track_user_invite_link(inv_link['id'], user_id)
            from src.services.db.client_funnel_repo import set_initial_source
            await set_initial_source(user_id, f"Кампания: {inv_link['name']}")

            # Начислить бонусные токены (только при первой привязке)
            if was_new and inv_link.get('bonus_tokens', 0) > 0:
                from src.services.db.tokens_repo import add_tokens
                await add_tokens(
                    user_id=user_id,
                    amount=inv_link['bonus_tokens'],
                    operation_type='invite_bonus',
                    description=f"Бонус по кампании: {inv_link['name']}",
                )

    # Устанавливаем источник трафика если был start-параметр (не реферал)
    if start_param:
        # Маппинг кодов в человекочитаемые названия
        source_map = {
            "site": "Сайт",
            # Можно добавить другие источники позже:
            # "instagram": "Instagram",
            # "vk": "ВКонтакте",
            # "youtube": "YouTube",
        }
        source_name = source_map.get(start_param.lower(), start_param)

        from src.services.db.client_funnel_repo import set_initial_source
        await set_initial_source(user_id, source_name)

    # При команде /start закрываем все старые топики и создаём новый
    from src.services.db.topics_repo import close_open_topics
    await close_open_topics(user_id)

    topic_id = await get_or_create_open_topic(
        user_id=user_id,
        session_id=session_id,
    )

    user_text = message.text or "/start"

    await log_message(
        user_id=user_id,
        direction="user",
        text=user_text,
        session_id=session_id,
        topic_id=topic_id,
    )

    # Проверяем, является ли пользователь администратором
    is_admin = user is not None and telegram_user_id in ADMIN_IDS

    if is_admin:
        # Для администратора показываем статистику
        total_users = await count_all_users()
        pending_questions = await moderation_count_pending()

        welcome_text = (
            f"<b>Администратор</b>\n\n"
            f"👥 Пользователей: <b>{total_users}</b>\n"
            f"📋 Вопросов на модерацию: <b>{pending_questions}</b>\n\n"
            f"Выберите режим работы:"
        )

        await message.answer(
            welcome_text,
            reply_markup=get_admin_start_keyboard(),
        )
    else:
        # Для обычного пользователя стандартное приветствие
        welcome_text = (
            "Рад, что Вы присоединились! Я Ваш агроном!🙏\n\n"
            "Моя задача — помочь, посоветовать и научить выращиванию ягодных культур.\n\n"
            "<b>Я даю индивидуальные рекомендации, с поправкой на климат Вашего региона</b> "
            "и условия выращивания.\n\n"
            "В моей базе знаний огромное количество профильной литературы, "
            "<b>но главное — в меня заложен практический опыт ягодных хозяйств.</b>\n\n"
            "<b>То, что я расскажу, — это не сухая теория, а успешная практика, "
            "применяемая в промышленных хозяйствах и интерпретированная для садоводов.</b> "
            "Это очень важно!\n\n"
            "Со мной у Вас будут богатые урожаи при минимуме ухода!\n\n"
            "Предлагаю начать, нажмите кнопку\n"
            "<b>«🧑‍🌾 Консультация»</b>!"
        )

        await message.answer(
            welcome_text,
            reply_markup=get_main_keyboard(),
            parse_mode="HTML",
        )

    await log_message(
        user_id=user_id,
        direction="bot",
        text=welcome_text,
        session_id=session_id,
        topic_id=topic_id,
    )

    # Очищаем состояние и контекст консультации при /start
    if user is not None:
        CONSULTATION_STATE.pop(user.id, None)
        CONSULTATION_CONTEXT.pop(user.id, None)


@router.message(F.text == "👤 Режим пользователя")
async def handle_user_mode(message: Message) -> None:
    """
    Переключение администратора в режим обычного пользователя.
    """
    user = message.from_user
    if user is None or user.id not in ADMIN_IDS:
        return

    welcome_text = (
        "Рад, что Вы присоединились! Я Ваш агроном!🙏\n\n"
        "Моя задача — помочь, посоветовать и научить выращиванию ягодных культур.\n\n"
        "<b>Я даю индивидуальные рекомендации, с поправкой на климат Вашего региона</b> "
        "и условия выращивания.\n\n"
        "В моей базе знаний огромное количество профильной литературы, "
        "<b>но главное — в меня заложен практический опыт ягодных хозяйств.</b>\n\n"
        "<b>То, что я расскажу, — это не сухая теория, а успешная практика, "
        "применяемая в промышленных хозяйствах и интерпретированная для садоводов.</b> "
        "Это очень важно!\n\n"
        "Со мной у Вас будут богатые урожаи при минимуме ухода!\n\n"
        "Предлагаю начать, нажмите кнопку\n"
        "<b>«🧑‍🌾 Консультация»</b>!"
    )

    await message.answer(
        welcome_text,
        reply_markup=get_main_keyboard(),
        parse_mode="HTML",
    )

    # Логируем нажатие кнопки + ответ бота
    internal_user_id = await get_or_create_user(
        telegram_user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )
    await log_message(
        user_id=internal_user_id,
        direction="user",
        text="👤 Режим пользователя",
        session_id=f"tg:{user.id}",
        meta={"type": "callback", "callback_data": "user_mode"},
    )
    await log_message(
        user_id=internal_user_id,
        direction="bot",
        text=welcome_text,
        session_id=f"tg:{user.id}",
    )


@router.message(F.text == "🛠 Режим администратора")
async def handle_admin_mode(message: Message) -> None:
    """
    Переключение в режим администратора.
    """
    user = message.from_user
    if user is None or user.id not in ADMIN_IDS:
        await message.answer("Эта функция доступна только администраторам.")
        return

    # Импортируем клавиатуру админа
    from src.keyboards.admin.menu import admin_main_menu_kb

    await message.answer(
        "Меню администратора:",
        reply_markup=admin_main_menu_kb()
    )


@router.message(F.text == "🧑‍🌾 Консультация")
async def handle_consultation_button(message: Message) -> None:
    """
    Обработка нажатия кнопки '🧑‍🌾 Консультация'.
    Теперь сразу просит вопрос без выбора категории.
    Категория и культура определяются автоматически из текста вопроса.
    """
    user = message.from_user
    if user is None:
        return

    # Получаем внутренний user_id
    from src.services.db.users_repo import get_or_create_user
    internal_user_id = await get_or_create_user(
        telegram_user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    # Закрываем все открытые топики перед началом новой консультации
    from src.services.db.topics_repo import close_open_topics
    await close_open_topics(internal_user_id)

    # Очищаем старый контекст
    CONSULTATION_CONTEXT.pop(user.id, None)

    # Устанавливаем новое состояние - ждем вопрос
    CONSULTATION_STATE[user.id] = "waiting_consultation_question"

    # Логируем нажатие кнопки пользователем
    await log_message(
        user_id=internal_user_id,
        direction="user",
        text="🧑‍🌾 Консультация",
        session_id=f"tg:{user.id}",
        meta={"type": "callback", "callback_data": "consultation"},
    )

    kb = get_example_questions_keyboard()
    await message.answer(CONSULTATION_ENTRY_TEXT, reply_markup=kb)
    await _log_bot_msg(
        CONSULTATION_ENTRY_TEXT,
        user_id=internal_user_id,
        session_id=f"tg:{user.id}",
        meta=serialize_keyboard(kb),
    )


@router.callback_query(F.data.startswith("consult_category:"))
async def handle_consultation_category(callback: CallbackQuery) -> None:
    """
    Обработка выбора категории консультации через инлайн-кнопки.

    ВАЖНО:
        - для категории 'nutrition' (Питание растений) запускаем отдельный сценарий
          с состоянием 'waiting_nutrition_root';
        - для остальных категорий используем общее состояние 'waiting_root'.
    """
    user = callback.from_user
    if user is None:
        await callback.answer()
        return

    # "consult_category:nutrition" → ("consult_category", "nutrition")
    _, category_code = callback.data.split(":", maxsplit=1)

    category_names = {
        "sort_place": "Подбор сорта/места",
        "plant_care": "Посадка и общий уход",
        "nutrition": "Питание растений",
        "soil": "Улучшение почвы",
        "protection": "Защита растений",
        "other": "Другая тема",
    }

    category_title = category_names.get(category_code, "Другая тема")

    # Логируем нажатие кнопки пользователем
    await _log_user_callback(f"[Кнопка] Категория: {category_title}", callback=callback)

    # Убираем инлайн-клавиатуру у старого сообщения
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)

    # Получаем внутренний user_id из таблицы users
    from src.services.db.users_repo import get_or_create_user
    internal_user_id = await get_or_create_user(
        telegram_user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    # Закрываем все открытые топики перед началом новой консультации
    from src.services.db.topics_repo import close_open_topics
    await close_open_topics(internal_user_id)

    # Очищаем старый контекст перед началом новой консультации
    CONSULTATION_CONTEXT.pop(user.id, None)

    # Специальная ветка для питания растений
    if category_code == "nutrition":
        CONSULTATION_STATE[user.id] = "waiting_nutrition_root"
        print(f"[menu] Установлено состояние waiting_nutrition_root для user {user.id}")
        text = "Напишите свой вопрос по питанию ягодных культур."
    else:
        CONSULTATION_STATE[user.id] = "waiting_root"
        print(f"[menu] Установлено состояние waiting_root для user {user.id}")
        text = (
            f"Вы выбрали тему: «{category_title}».\n\n"
            "Опишите, пожалуйста, ваш вопрос одним сообщением:\n"
            "— какая культура (и сорт, если знаете);\n"
            "— в каком регионе/климате вы находитесь;\n"
            "— что именно вас волнует (посадка, уход, болезнь, слабый урожай и т.п.)."
        )

    if callback.message:
        await callback.message.answer(text)
        await _log_bot_msg(
            text,
            user_id=internal_user_id,
            session_id=f"tg:{user.id}",
        )

    await callback.answer()


@router.callback_query(F.data == "consult_close")
async def handle_close_menu(callback: CallbackQuery) -> None:
    """
    Удаляет сообщение с меню консультаций и закрывает открытые топики.
    """
    user = callback.from_user
    if user:
        # Получаем внутренний user_id
        from src.services.db.users_repo import get_or_create_user
        internal_user_id = await get_or_create_user(
            telegram_user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )
        # Закрываем все открытые топики пользователя при возврате в главное меню
        from src.services.db.topics_repo import close_open_topics
        await close_open_topics(internal_user_id)

    try:
        if callback.message:
            await callback.message.delete()
    except Exception:
        # Если сообщение уже удалено или недоступно — игнорируем ошибку
        pass

    await callback.answer()


@router.callback_query(F.data.startswith("example_q:"))
async def handle_example_question(callback: CallbackQuery) -> None:
    """
    Обработчик нажатия инлайн-кнопки с примером вопроса.
    Сохраняет выбранный пример и просит уточнить детали (культура, регион и т.д.).
    """
    user = callback.from_user
    if user is None or callback.message is None:
        await callback.answer()
        return

    key = callback.data.split(":")[1]
    question_text = EXAMPLE_QUESTIONS.get(key)
    if not question_text:
        await callback.answer()
        return

    # Логируем нажатие кнопки пользователем
    await _log_user_callback(f"[Кнопка] Пример: {question_text}", callback=callback)

    # Убираем инлайн-клавиатуру
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.answer()

    # Очищаем старый контекст и сразу запускаем пайплайн с примером вопроса
    CONSULTATION_CONTEXT.pop(user.id, None)
    CONSULTATION_STATE[user.id] = "waiting_consultation_question"

    await run_consultation_pipeline(
        message=callback.message,
        telegram_user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        question_text=question_text,
    )


@router.callback_query(F.data == "custom_question")
async def handle_custom_question(callback: CallbackQuery) -> None:
    """Обработчик кнопки 'Свой вопрос' — переводит в режим ожидания вопроса."""
    user = callback.from_user
    if user is None or callback.message is None:
        await callback.answer()
        return

    # Логируем нажатие кнопки пользователем
    await _log_user_callback("[Кнопка] Свой вопрос", callback=callback)

    # Убираем инлайн-клавиатуру
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.answer()

    CONSULTATION_STATE[user.id] = "waiting_consultation_question"
    custom_prompt = "✏️ Напишите ваш вопрос:"
    await callback.message.answer(custom_prompt)
    await _log_bot_msg(custom_prompt, telegram_user_id=user.id)


@router.message(F.text == "⬅️ Назад в меню")
async def handle_back_to_menu(message: Message) -> None:
    """
    Обработчик кнопки "⬅️ Назад в меню" из консультации.
    Закрывает текущий топик, очищает состояние консультации и возвращает пользователя в главное меню.
    """
    user = message.from_user
    if user is None:
        return

    # Получаем внутренний user_id для закрытия топика
    internal_user_id = await get_or_create_user(
        telegram_user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    # Закрываем текущий топик
    from src.services.db.topics_repo import close_open_topics
    await close_open_topics(internal_user_id)

    # Очистить состояние консультации
    if user.id in CONSULTATION_STATE:
        del CONSULTATION_STATE[user.id]
    if user.id in CONSULTATION_CONTEXT:
        del CONSULTATION_CONTEXT[user.id]

    # Логируем нажатие кнопки пользователем
    await log_message(
        user_id=internal_user_id,
        direction="user",
        text="⬅️ Назад в меню",
        session_id=f"tg:{user.id}",
        meta={"type": "callback", "callback_data": "back_to_menu"},
    )

    # Вернуть главное меню
    menu_text = "Главное меню:"
    kb = get_main_keyboard()
    await message.answer(menu_text, reply_markup=kb)
    await _log_bot_msg(menu_text, user_id=internal_user_id, session_id=f"tg:{user.id}", meta=serialize_keyboard(kb))


@router.message(F.text == "👤 Мой профиль")
async def handle_profile(message: Message) -> None:
    """
    Обработчик кнопки "Мой профиль".
    Показывает баланс токенов и статистику пользователя.
    """
    user = message.from_user
    if user is None:
        return

    # Получаем внутренний user_id
    internal_user_id = await get_or_create_user(
        telegram_user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    # Получаем баланс токенов
    from src.services.db.tokens_repo import get_token_balance
    balance = await get_token_balance(internal_user_id)

    # Получаем количество консультаций
    from src.services.db.pool import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        topics_count = await conn.fetchval(
            "SELECT COUNT(*) FROM topics WHERE user_id = $1",
            internal_user_id,
        )

    # Получаем активную подписку, план, скидки
    from src.services.db.user_subscription_repo import get_active_subscription
    from src.services.db.subscription_plan_repo import get_by_id as get_plan_by_id
    from src.services.db.invite_link_repo import get_user_active_discount
    from src.services.db.tokens_repo import get_split_balance

    subscription = await get_active_subscription(internal_user_id)
    plan = None
    if subscription:
        plan = await get_plan_by_id(subscription["subscription_plan_id"])

    split = await get_split_balance(internal_user_id)
    ref_discount = await get_user_active_discount(internal_user_id) or 0

    # Русские названия месяцев для форматирования дат
    _RU_MONTHS = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля",
        5: "мая", 6: "июня", 7: "июля", 8: "августа",
        9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
    }

    def _fmt_date(dt) -> str:
        if not dt:
            return "—"
        return f"{dt.day} {_RU_MONTHS[dt.month]} {dt.year}"

    # ── Блок тарифа ──────────────────────────────────────
    if subscription and plan:
        plan_name = plan.get("name", "—")
        expires_at = subscription["expires_at"]
        auto_renew = subscription.get("auto_renew", False)
        auto_renew_str = "✅ активно" if auto_renew else "❌ не активно"
        sub_line = f"📋 <b>Тариф:</b>\n<b>{plan_name}</b>  ✅\nПодписка до: {_fmt_date(expires_at)}\nАвтопродление: {auto_renew_str}"
    else:
        plan_name = "Пробный"
        sub_line = "📋 <b>Тариф:</b>\n<b>Пробный</b>  |  Без подписки"

    # ── Лимит токенов ────────────────────────────────────
    # Подписочные: лимит = tokens_granted, перенос по max_carryover
    # Докупленные: переносятся все (не сгорают), тратятся последними
    # Израсходовано считается по транзакциям с момента started_at
    pool = get_pool()
    async with pool.acquire() as conn:
        if subscription:
            period_start = subscription["started_at"]
            sub_granted = subscription.get("tokens_granted", 0)
            purchased_in_period = await conn.fetchval(
                """
                SELECT COALESCE(SUM(amount), 0)
                FROM token_transactions
                WHERE user_id = $1
                  AND operation_type IN ('payment_yookassa', 'buy_questions')
                  AND amount > 0
                  AND created_at >= $2
                """,
                internal_user_id, period_start,
            ) or 0
        else:
            first_grant = await conn.fetchrow(
                """
                SELECT created_at, amount FROM token_transactions
                WHERE user_id = $1
                  AND operation_type IN ('trial_grant', 'referral_bonus')
                  AND amount > 0
                ORDER BY created_at ASC LIMIT 1
                """,
                internal_user_id,
            )
            sub_granted = first_grant["amount"] if first_grant else 0
            period_start = first_grant["created_at"] if first_grant else None
            purchased_in_period = 0

        # Всего потрачено за период
        if period_start:
            total_spent = await conn.fetchval(
                """
                SELECT COALESCE(SUM(ABS(amount)), 0)
                FROM token_transactions
                WHERE user_id = $1 AND amount < 0 AND created_at >= $2
                """,
                internal_user_id, period_start,
            ) or 0
        else:
            total_spent = 0

    # Текущие остатки из split_balance (реальный баланс)
    sub_remaining = split["subscription_tokens"]   # остаток подписочных
    pur_remaining = split["purchased_tokens"]       # остаток докупленных

    # Потрачено подписочных = sub_granted - sub_remaining (но не меньше 0)
    sub_used = max(0, sub_granted - sub_remaining)
    # Потрачено докупленных = purchased_in_period - pur_remaining (но не меньше 0)
    pur_used = max(0, purchased_in_period - pur_remaining)

    def _bar(used: int, total: int, length: int = 13) -> str:
        filled = int((used / total) * length) if total > 0 else 0
        return "█" * filled + "░" * (length - filled)

    if subscription and plan:
        sub_bar = _bar(sub_used, sub_granted)
        limit_block = (
            f"🪙 <b>Лимит токенов</b>\n"
            f"  [{sub_bar}]\n"
            f"  Использовано: {sub_used} из {sub_granted}"
        )
        max_carryover = plan.get("max_carryover", 0)
        if max_carryover and max_carryover > 0:
            carryover_val = min(sub_remaining, max_carryover)
            limit_block += f"\n  ↩️ Перенос на след. месяц: <b>{carryover_val}</b> (макс. {max_carryover})"

        # Шкала докупленных токенов (если есть)
        if purchased_in_period > 0:
            pur_bar = _bar(pur_used, purchased_in_period)
            limit_block += (
                f"\n\n➕ <b>Докупленные токены</b>  <i>(переносятся)</i>\n"
                f"  [{pur_bar}]\n"
                f"  Использовано: {pur_used} из {purchased_in_period}"
            )
    else:
        sub_bar = _bar(sub_used, sub_granted if sub_granted else 1)
        limit_block = (
            f"🪙 <b>Лимит токенов</b>\n"
            f"  [{sub_bar}]\n"
            f"  Использовано: {sub_used} из {sub_granted}"
        )

    # ── Скидки ───────────────────────────────────────────
    token_discount = plan.get("token_discount_percent", 0) if plan else 0
    total_token_discount = min(100, token_discount + ref_discount)

    discount_lines = ""
    if ref_discount > 0 or token_discount > 0:
        discount_lines = "\n\n🎁 <b>Ваши скидки</b>\n"
        if ref_discount > 0:
            discount_lines += f"  Скидка на тарифы (реф):       −{ref_discount}%\n"
        if token_discount > 0 or ref_discount > 0:
            discount_lines += f"  Скидка на доп. токены:\n"
            parts = []
            if token_discount > 0:
                parts.append(f"тариф {token_discount}%")
            if ref_discount > 0:
                parts.append(f"реф {ref_discount}%")
            formula = " + ".join(parts)
            discount_lines += f"    {formula} = <b>−{total_token_discount}%</b>"

    # ── Итоговый текст ───────────────────────────────────
    profile_text = (
        f"🌿 <b>Ваш профиль</b>\n\n"
        f"{sub_line}\n\n"
        f"{limit_block}"
        f"{discount_lines}"
    )

    # Добавляем inline кнопки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💰 Пополнить баланс",
            callback_data="show_payment_menu"
        )],
        [InlineKeyboardButton(
            text="📣 Реферальная программа",
            callback_data="show_referral_program"
        )],
    ])

    await message.answer(profile_text, parse_mode="HTML", reply_markup=keyboard)

    # Логируем нажатие кнопки + ответ бота
    await log_message(
        user_id=internal_user_id,
        direction="user",
        text="👤 Мой профиль",
        session_id=f"tg:{user.id}",
        meta={"type": "callback", "callback_data": "profile"},
    )
    await _log_bot_msg(
        profile_text,
        user_id=internal_user_id,
        session_id=f"tg:{user.id}",
        meta=serialize_keyboard(keyboard),
    )


@router.message(F.text == "📅 План сезона")
async def handle_season_plan(message: Message) -> None:
    """
    Обработчик кнопки "📅 План сезона".
    Открывает WebApp календаря в Telegram.
    """
    user = message.from_user
    if user is None:
        return

    # Получаем внутренний user_id
    internal_user_id = await get_or_create_user(
        telegram_user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    # Логируем нажатие кнопки
    await log_message(
        user_id=internal_user_id,
        direction="user",
        text="📅 План сезона",
        session_id=f"tg:{user.id}",
        meta={"type": "callback", "callback_data": "season_plan"},
    )

    # Проверяем, настроен ли URL WebApp
    if not settings.webapp_url:
        unavailable_text = "Календарь работ временно недоступен.\nОбратитесь к администратору."
        await message.answer(unavailable_text)
        await _log_bot_msg(unavailable_text, user_id=internal_user_id, session_id=f"tg:{user.id}")
        return

    # Создаём inline-кнопку с WebApp
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📅 Открыть календарь",
                    web_app=WebAppInfo(url=settings.webapp_url)
                )
            ]
        ]
    )

    calendar_text = "Нажмите кнопку ниже, чтобы открыть календарь работ:"
    await message.answer(calendar_text, reply_markup=keyboard)
    await _log_bot_msg(calendar_text, user_id=internal_user_id, session_id=f"tg:{user.id}", meta=serialize_keyboard(keyboard))


@router.callback_query(F.data == "show_referral_program")
async def handle_show_referral_program(callback: CallbackQuery) -> None:
    """Показывает реферальную программу: ссылку, статистику, кнопку поделиться."""
    user = callback.from_user
    if user is None:
        await callback.answer()
        return

    internal_user_id = await get_or_create_user(
        telegram_user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    from src.services.db.referral_repo import get_or_create_referral_code, get_referral_stats
    ref_code = await get_or_create_referral_code(internal_user_id)
    ref_stats = await get_referral_stats(internal_user_id)

    bot_me = await callback.bot.me()
    bot_username = bot_me.username

    referral_text = (
        f"<b>📣 Реферальная программа</b>\n\n"
        f"Ваша ссылка:\n"
        f"<code>https://t.me/{bot_username}?start=ref_{ref_code}</code>\n\n"
        f"Приглашено друзей: <b>{ref_stats['total_referrals']}</b>\n\n"
        f"Пригласите друга и получите бонусные токены!"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📣 Поделиться ссылкой",
            callback_data="share_referral_link"
        )],
    ])

    if callback.message:
        await callback.message.answer(referral_text, parse_mode="HTML", reply_markup=keyboard)

    # Логируем
    await _log_user_callback("[Кнопка] Реферальная программа", callback=callback)
    await _log_bot_msg(
        referral_text,
        user_id=internal_user_id,
        session_id=f"tg:{user.id}",
        meta=serialize_keyboard(keyboard),
    )

    await callback.answer()


@router.callback_query(F.data == "share_referral_link")
async def handle_share_referral(callback: CallbackQuery) -> None:
    """Отправляет текст реферальной ссылки для пересылки друзьям."""
    user = callback.from_user
    if user is None:
        await callback.answer()
        return

    internal_user_id = await get_or_create_user(
        telegram_user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    from src.services.db.referral_repo import get_or_create_referral_code
    ref_code = await get_or_create_referral_code(internal_user_id)

    bot_me = await callback.bot.me()
    bot_username = bot_me.username

    share_text = (
        "Привет! Я пользуюсь экспертным сервисом для садоводов — "
        "здесь можно получить профессиональную консультацию по ягодным культурам.\n\n"
        "Переходи по ссылке и получи бонусные токены:\n"
        f"https://t.me/{bot_username}?start=ref_{ref_code}"
    )

    if callback.message:
        await callback.message.answer(share_text)

    # Логируем нажатие кнопки + ответ бота
    await _log_user_callback("[Кнопка] Поделиться ссылкой", callback=callback)
    await _log_bot_msg(share_text, user_id=internal_user_id, session_id=f"tg:{user.id}")

    await callback.answer("Перешлите это сообщение друзьям!")
