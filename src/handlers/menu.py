# src/handlers/menu.py

# Импортируем Router и F (фильтры) из aiogram
from aiogram import Router, F                  # Router — для группировки хендлеров, F — для фильтрации апдейтов
# Импортируем фильтр для команды /start
from aiogram.filters import CommandStart       # CommandStart — срабатывает на /start
# Импортируем типы сообщений и callback-запросов
from aiogram.types import Message, CallbackQuery  # Message — входящее сообщение, CallbackQuery — нажатие инлайн-кнопки

# Импортируем функции работы с БД: пользователи, темы, логи сообщений
from src.services.db.users_repo import get_or_create_user, count_all_users  # Создание/поиск пользователя по telegram_user_id
from src.services.db.topics_repo import get_or_create_open_topic     # Создание/поиск "открытой" темы (диалога)
from src.services.db.messages_repo import log_message                # Логирование сообщений в таблицу messages
from src.services.db.moderation_repo import moderation_count_pending # Подсчёт вопросов на модерации

# Импортируем глобальное состояние консультации и утилиту для сборки session_id
from src.handlers.common import CONSULTATION_STATE, build_session_id_from_message

# Импортируем функцию, создающую клавиатуру главного меню
from src.keyboards.main.main_menu import get_main_keyboard, get_admin_start_keyboard

# Импортируем инлайн-меню консультаций (6 тем + кнопка "Закрыть")
from src.keyboards.consultation.common import CONSULTATION_MENU_INLINE_KB

# Импортируем список админов
from src.handlers.admin import ADMIN_IDS

# Создаём роутер для этого модуля
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """
    Обработчик команды /start.

    1) Регистрирует (или находит) пользователя в БД.
    2) Находит или создаёт открытую тему (topic).
    3) Логирует /start и приветственный текст.
    4) Показывает клавиатуру главного меню (для админа - специальную).
    5) Сбрасывает состояние консультации для этого пользователя.
    """
    session_id = build_session_id_from_message(message)

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

    user_id = await get_or_create_user(
        telegram_user_id=telegram_user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
    )

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
            "Привет! Я бот-ассистент садовода.\n\n"
            "Нажмите кнопку «🧑‍🌾 Консультация», чтобы получить помощь по посадке, уходу и подбору ягодных культур."
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

    if user is not None and user.id in CONSULTATION_STATE:
        CONSULTATION_STATE.pop(user.id, None)


@router.message(F.text == "👤 Режим пользователя")
async def handle_user_mode(message: Message) -> None:
    """
    Переключение администратора в режим обычного пользователя.
    """
    user = message.from_user
    if user is None or user.id not in ADMIN_IDS:
        return

    welcome_text = (
        "Привет! Я бот-ассистент садовода.\n\n"
        "Нажмите кнопку «🧑‍🌾 Консультация», чтобы получить помощь по посадке, уходу и подбору ягодных культур."
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
    Показывает инлайн-подменю из 6 направлений консультаций.
    """
    user = message.from_user
    if user is not None:
        # фиксируем, что пользователь сейчас в ветке консультаций
        CONSULTATION_STATE[user.id] = "waiting_category"

    text = (
        "Доступны консультации по всем ягодным культурам.\n"
        "Вы можете выбрать одну из предложенных тем или указать свою."
    )

    await message.answer(
        text,
        reply_markup=CONSULTATION_MENU_INLINE_KB,
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

    # Убираем инлайн-клавиатуру у старого сообщения
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)

    # Специальная ветка для питания растений
    if category_code == "nutrition":
        CONSULTATION_STATE[user.id] = "waiting_nutrition_root"
        text = "Напишите свой вопрос по питанию ягодных культур."
    else:
        CONSULTATION_STATE[user.id] = "waiting_root"
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
    Удаляет сообщение с меню консультаций.
    """
    try:
        if callback.message:
            await callback.message.delete()
    except Exception:
        # Если сообщение уже удалено или недоступно — игнорируем ошибку
        pass

    await callback.answer()
