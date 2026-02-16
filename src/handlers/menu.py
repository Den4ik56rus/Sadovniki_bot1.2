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

    # Обработка реферальной ссылки (только для новых пользователей)
    if is_new_user and referral_code:
        from src.services.db.referral_repo import (
            get_user_id_by_referral_code, create_referral, grant_referral_bonuses
        )
        referrer_id = await get_user_id_by_referral_code(referral_code)
        if referrer_id and referrer_id != user_id:
            await create_referral(referrer_id, user_id)
            await grant_referral_bonuses(referrer_id, user_id)
            # Источник трафика — реферал
            from src.services.db.client_funnel_repo import set_initial_source
            await set_initial_source(user_id, "Реферал")

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
            "Добро пожаловать в экспертный сервис для садоводов.\n\n"
            "Здесь вы можете получить ответ практически на любой вопрос, связанный "
            "с выращиванием ягодных культур — от выбора сорта и закладки плантации "
            "до питания, защиты и повышения урожайности.\n\n"
            "Все рекомендации основаны на тщательно отобранной профессиональной "
            "литературе и практическом опыте ведущих агрономов в сфере ягодных культур.\n\n"
            "Каждый ответ дополнительно проверяется специалистом-агрономом, что обеспечивает "
            "высокую точность, актуальность и практическую применимость информации.\n\n"
            "Нажмите кнопку «🧑‍🌾 Консультация», чтобы начать."
        )

        await message.answer(
            welcome_text,
            reply_markup=get_main_keyboard(),
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
        "Добро пожаловать в экспертный сервис для садоводов.\n\n"
        "Здесь вы можете получить ответ практически на любой вопрос, связанный "
        "с выращиванием ягодных культур — от выбора сорта и закладки плантации "
        "до питания, защиты и повышения урожайности.\n\n"
        "Все рекомендации основаны на тщательно отобранной профессиональной "
        "литературе и практическом опыте ведущих агрономов в сфере ягодных культур.\n\n"
        "Каждый ответ дополнительно проверяется специалистом-агрономом, что обеспечивает "
        "высокую точность, актуальность и практическую применимость информации.\n\n"
        "Нажмите кнопку «🧑‍🌾 Консультация», чтобы начать."
    )

    await message.answer(
        welcome_text,
        reply_markup=get_main_keyboard(),
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

    await message.answer(CONSULTATION_ENTRY_TEXT, reply_markup=get_example_questions_keyboard())


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

    # Убираем инлайн-клавиатуру
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.answer()

    # Сохраняем выбранный пример в контексте
    CONSULTATION_CONTEXT[user.id] = {"example_question": question_text}
    CONSULTATION_STATE[user.id] = "waiting_example_details"

    # Просим пользователя уточнить детали
    await callback.message.answer(
        f"📝 Вы выбрали: «{question_text}»\n\n"
        "Напишите уточнения — например, какая культура, регион, "
        "сорт или другие детали, чтобы ответ был максимально полезным:"
    )


@router.callback_query(F.data == "custom_question")
async def handle_custom_question(callback: CallbackQuery) -> None:
    """Обработчик кнопки 'Свой вопрос' — переводит в режим ожидания вопроса."""
    user = callback.from_user
    if user is None or callback.message is None:
        await callback.answer()
        return

    # Убираем инлайн-клавиатуру
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.answer()

    CONSULTATION_STATE[user.id] = "waiting_consultation_question"
    await callback.message.answer("✏️ Напишите ваш вопрос:")


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

    # Вернуть главное меню
    await message.answer(
        "Главное меню:",
        reply_markup=get_main_keyboard()
    )


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

    # Получаем реферальный код и статистику
    from src.services.db.referral_repo import get_or_create_referral_code, get_referral_stats
    ref_code = await get_or_create_referral_code(internal_user_id)
    ref_stats = await get_referral_stats(internal_user_id)

    # Формируем текст профиля
    profile_text = (
        f"<b>👤 Ваш профиль</b>\n\n"
        f"❓ Баланс вопросов: <b>{balance}</b>\n"
        f"📊 Консультаций: <b>{topics_count}</b>\n\n"
        f"<b>Стоимость операций:</b>\n"
        f"• Питание и защита растений: 2 вопроса\n"
        f"• Остальные темы: 1 вопрос\n\n"
        f"<b>📣 Реферальная программа</b>\n"
        f"Ваша ссылка:\n"
        f"<code>https://t.me/sadovniki_bot?start=ref_{ref_code}</code>\n"
        f"Приглашено друзей: <b>{ref_stats['total_referrals']}</b>\n\n"
        f"Пригласите друга и получите бонусные вопросы!"
    )

    # Добавляем inline кнопки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📣 Поделиться ссылкой",
            callback_data="share_referral_link"
        )],
        [InlineKeyboardButton(
            text="💰 Пополнить баланс",
            callback_data="show_payment_menu"
        )],
    ])

    await message.answer(profile_text, parse_mode="HTML", reply_markup=keyboard)


@router.message(F.text == "📅 План сезона")
async def handle_season_plan(message: Message) -> None:
    """
    Обработчик кнопки "📅 План сезона".
    Открывает WebApp календаря в Telegram.
    """
    user = message.from_user
    if user is None:
        return

    # Проверяем, настроен ли URL WebApp
    if not settings.webapp_url:
        await message.answer(
            "Календарь работ временно недоступен.\n"
            "Обратитесь к администратору."
        )
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

    await message.answer(
        "Нажмите кнопку ниже, чтобы открыть календарь работ:",
        reply_markup=keyboard
    )


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

    share_text = (
        "Привет! Я пользуюсь экспертным сервисом для садоводов — "
        "здесь можно получить профессиональную консультацию по ягодным культурам.\n\n"
        "Переходи по ссылке и получи бонусные вопросы:\n"
        f"https://t.me/sadovniki_bot?start=ref_{ref_code}"
    )

    if callback.message:
        await callback.message.answer(share_text)

    await callback.answer("Перешлите это сообщение друзьям!")
