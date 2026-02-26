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


async def _subscription_expiring_loop(check_fn) -> None:
    """
    Фоновая задача для проверки «скоро истекающих» подписок.
    Запускается каждый час.
    """
    import logging
    logger = logging.getLogger(__name__)
    while True:
        try:
            processed = await check_fn()
            if processed > 0:
                logger.info(f"Subscription expiring checker: processed {processed} events")
        except Exception as e:
            logger.error(f"Error in subscription expiring loop: {e}", exc_info=True)
        await asyncio.sleep(3600)


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
    6) При завершении: ждёт handler-задачи → закрывает ресурсы.
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

    # Запускаем фоновую задачу для отложенных триггеров воронки (legacy)
    from src.services.funnel_trigger_sender import process_pending_triggers as _process_pending_triggers
    trigger_task = asyncio.create_task(_trigger_scheduler_loop(_process_pending_triggers))
    print("Фоновая задача триггеров воронки запущена.")

    # Запускаем фоновую задачу для отложенных автоматизационных триггеров
    from src.services.automation.engine import process_pending_automation_triggers
    automation_trigger_task = asyncio.create_task(_trigger_scheduler_loop(process_pending_automation_triggers))
    print("Фоновая задача автоматизационных триггеров запущена.")

    # Запускаем фоновую задачу для проверки истекающих подписок (subscription_expiring)
    from src.services.automation.subscription_checker import check_subscription_expiring_triggers
    subscription_check_task = asyncio.create_task(_subscription_expiring_loop(check_subscription_expiring_triggers))
    print("Фоновая задача проверки подписок запущена.")

    # Graceful shutdown: сохраняем ссылку на dispatcher и ставим свои signal handlers.
    # При SIGTERM наш handler ставит флаг + сигнализирует aiogram остановить polling.
    # start_polling(close_bot_session=False) НЕ закрывает bot.session —
    # мы закрываем её сами ПОСЛЕ завершения всех handler-задач.
    shutdown_coordinator.set_dispatcher(dp)
    shutdown_coordinator.install_signal_handlers()

    print("Бот запущен. Нажмите Ctrl+C, чтобы остановить его.")

    try:
        # handle_signals=False — мы сами обрабатываем SIGTERM/SIGINT
        # close_bot_session=False — НЕ закрываем bot.session внутри start_polling,
        # иначе handler-задачи не смогут отправить ответы после остановки polling
        await dp.start_polling(bot, handle_signals=False, close_bot_session=False)
    finally:
        # Корректное закрытие
        print("Останавливаю бота...")

        # Ждём завершения всех активных handler-задач aiogram (LLM-ответы)
        # КРИТИЧНО: это происходит ДО закрытия bot.session,
        # поэтому handler-задачи ещё могут отправлять сообщения
        print("Ожидаю завершения активных ответов пользователям...")
        await shutdown_coordinator.wait_aiogram_handlers(timeout=65.0)
        await shutdown_coordinator.wait_registered_tasks(timeout=65.0)

        # Теперь закрываем bot.session (после этого отправка невозможна)
        print("Закрываю сессию бота...")
        await bot.session.close()
        print("Сессия бота закрыта.")

        # Останавливаем фоновые задачи
        webhook_consumer_task.cancel()
        background_task.cancel()
        broadcast_task.cancel()
        trigger_task.cancel()
        automation_trigger_task.cancel()
        subscription_check_task.cancel()
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
            await automation_trigger_task
        except asyncio.CancelledError:
            print("Фоновая задача автоматизационных триггеров остановлена.")
        try:
            await subscription_check_task
        except asyncio.CancelledError:
            print("Фоновая задача проверки подписок остановлена.")
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
