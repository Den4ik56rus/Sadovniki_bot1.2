"""
Точка входа в приложение бота.

Запуск:
    python -m src.main
"""

import asyncio

from aiohttp import web

# Создание Bot и Dispatcher
from src.bot import create_bot_and_dispatcher

# Пул БД
from src.services.db.pool import init_db_pool, close_db_pool

# Регистрация меню команд
from src.keyboards.main.bot_commands import set_main_menu_commands

# API сервер
from src.api import create_api_app
from src.config import settings
from src.api.handlers.webhooks import set_webhook_queue, webhook_consumer
from src.services.payments.payment_reconciliation import payment_reconciliation_loop
from src.shutdown import shutdown_coordinator


async def _trigger_scheduler_loop(process_fn) -> None:
    """
    Фоновая задача для отложенных триггеров воронки.
    Проверяет каждые 30 секунд pending-триггеры и отправляет те, чьё время пришло.
    """
    import logging
    logger = logging.getLogger(__name__)
    while True:
        try:
            processed = await process_fn()
            if processed > 0:
                logger.info(f"Trigger scheduler: processed {processed} pending triggers")
        except Exception as e:
            logger.error(f"Error in trigger scheduler: {e}", exc_info=True)
        await asyncio.sleep(30)


async def _subscription_renewal_task() -> None:
    """
    Фоновая задача для автоматического продления подписок.
    Проверяет каждый час, нужно ли создать платеж для продления.
    """
    from src.services.payments.subscription_service import process_auto_renewals, expire_old_subscriptions
    import logging

    logger = logging.getLogger(__name__)

    while True:
        try:
            # Обрабатываем автопродления
            renewals_count = await process_auto_renewals()
            if renewals_count > 0:
                logger.info(f"Processed {renewals_count} auto-renewals")

            # Истекаем старые подписки
            expired_count = await expire_old_subscriptions()
            if expired_count > 0:
                logger.info(f"Expired {expired_count} old subscriptions")

        except Exception as e:
            logger.error(f"Error in subscription renewal task: {e}", exc_info=True)

        # Проверяем каждый час
        await asyncio.sleep(3600)


async def main() -> None:
    """
    Основная асинхронная функция:

    1) Инициализирует пул подключений к базе данных.
    2) Создаёт bot и dispatcher.
    3) Запускает API сервер для WebApp.
    4) Регистрирует команды бота (показываются при вводе / ).
    5) Запускает long polling.
    6) При завершении закрывает пул БД и API сервер.
    """

    print("Инициализирую пул подключений к БД...")
    await init_db_pool()
    print("Пул подключений к БД инициализирован.")

    # Создаём bot и dp
    bot, dp = create_bot_and_dispatcher()

    # Создаём и запускаем API сервер
    print(f"Запускаю API сервер на {settings.api_host}:{settings.api_port}...")
    api_app = await create_api_app()
    runner = web.AppRunner(api_app)
    await runner.setup()
    site = web.TCPSite(runner, settings.api_host, settings.api_port)
    await site.start()
    print(f"API сервер запущен на http://{settings.api_host}:{settings.api_port}")

    # Регистрируем команды бота в выезжающем меню Telegram
    print("Регистрирую команды бота...")
    await set_main_menu_commands(bot)
    print("Команды зарегистрированы.")

    # Восстановление после рестарта: уведомляем пользователей и восстанавливаем состояния
    from src.startup_recovery import run_startup_recovery
    print("Запускаю восстановление после рестарта...")
    await run_startup_recovery(bot)
    print("Восстановление завершено.")

    # Создаём очередь вебхуков и регистрируем её в handler
    webhook_queue = asyncio.Queue(maxsize=100)
    set_webhook_queue(webhook_queue)
    webhook_consumer_task = asyncio.create_task(webhook_consumer(webhook_queue))
    print("Webhook consumer запущен.")

    # Запускаем фоновую задачу для автопродления подписок
    background_task = asyncio.create_task(_subscription_renewal_task())
    print("Фоновая задача автопродления подписок запущена.")

    # Запускаем фоновую задачу для запланированных рассылок
    from src.services.broadcast_scheduler import broadcast_scheduler_loop
    broadcast_task = asyncio.create_task(broadcast_scheduler_loop())
    print("Фоновая задача рассылок запущена.")

    # Запускаем фоновую задачу сверки платежей
    reconciliation_task = asyncio.create_task(payment_reconciliation_loop())
    print("Фоновая задача сверки платежей запущена.")

    # Запускаем фоновую задачу для отложенных триггеров воронки
    from src.services.funnel_trigger_sender import process_pending_triggers as _process_pending_triggers
    trigger_task = asyncio.create_task(_trigger_scheduler_loop(_process_pending_triggers))
    print("Фоновая задача триггеров воронки запущена.")

    # Graceful shutdown: сохраняем ссылку на dispatcher и ставим свои signal handlers
    # ВАЖНО: aiogram по умолчанию перехватывает SIGTERM и сразу отменяет handler-задачи.
    # Мы ставим свои хендлеры, которые СНАЧАЛА ждут завершения всех LLM-ответов,
    # и только потом сигнализируют aiogram остановить polling.
    shutdown_coordinator.set_dispatcher(dp)
    shutdown_coordinator.install_signal_handlers()

    print("Бот запущен. Нажмите Ctrl+C, чтобы остановить его.")

    try:
        # Старт long polling (handle_signals=False — мы сами обрабатываем SIGTERM/SIGINT)
        await dp.start_polling(bot, handle_signals=False)
    finally:
        # Корректное закрытие
        print("Останавливаю бота...")

        # Если shutdown прошёл через наш signal handler — задачи уже дождены.
        # Если start_polling завершился по другой причине — ждём здесь.
        if not shutdown_coordinator.is_shutting_down:
            await shutdown_coordinator.begin_shutdown(timeout=60.0)

        # Останавливаем фоновые задачи
        webhook_consumer_task.cancel()
        background_task.cancel()
        broadcast_task.cancel()
        trigger_task.cancel()
        reconciliation_task.cancel()
        try:
            await webhook_consumer_task
        except asyncio.CancelledError:
            print("Webhook consumer остановлен.")
        try:
            await background_task
        except asyncio.CancelledError:
            print("Фоновая задача автопродления остановлена.")
        try:
            await broadcast_task
        except asyncio.CancelledError:
            print("Фоновая задача рассылок остановлена.")
        try:
            await trigger_task
        except asyncio.CancelledError:
            print("Фоновая задача триггеров воронки остановлена.")
        try:
            await reconciliation_task
        except asyncio.CancelledError:
            print("Фоновая задача сверки платежей остановлена.")

        # Закрываем SSE соединения перед остановкой API сервера
        from src.api.sse_manager import sse_manager
        print("Закрываю SSE соединения...")
        await sse_manager.shutdown()

        # Закрываем API сервер (с таймаутом чтобы не зависал)
        print("Останавливаю API сервер...")
        try:
            await asyncio.wait_for(runner.cleanup(), timeout=5.0)
        except asyncio.TimeoutError:
            print("API сервер не остановился за 5 секунд, принудительное завершение.")
        print("API сервер остановлен.")

        # Закрываем пул БД
        print("Закрываю пул БД...")
        await close_db_pool()
        print("Пул БД закрыт.")


if __name__ == "__main__":
    asyncio.run(main())
