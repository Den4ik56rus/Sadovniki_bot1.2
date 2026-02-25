# src/shutdown.py

"""
Координатор graceful shutdown.

При получении SIGTERM (docker stop / deploy):
1. Ставит флаг is_shutting_down = True
2. Сигнализирует aiogram остановить polling (перестать принимать новые updates)
3. В finally блоке main.py ждём завершения ВСЕХ активных handler-задач
4. Только после этого закрываем bot.session, DB pool и т.д.

Ключевое отличие от стандартного поведения aiogram:
aiogram при SIGTERM сразу отменяет polling и ЗАКРЫВАЕТ bot.session,
после чего handler-задачи не могут отправить ответы пользователям.
Мы передаём close_bot_session=False и закрываем сессию сами — ПОСЛЕ
завершения всех handler-задач.
"""

import asyncio
import logging
import signal
from typing import Optional, Set

logger = logging.getLogger(__name__)


class ShutdownCoordinator:
    def __init__(self) -> None:
        self._shutting_down = False
        self._active_tasks: set[asyncio.Task] = set()
        self._drain_event = asyncio.Event()
        self._drain_event.set()  # изначально "пусто" — нет активных задач

        # Ссылки на aiogram Dispatcher для программной остановки
        self._dispatcher = None
        self._aiogram_tasks: Optional[Set[asyncio.Task]] = None

    @property
    def is_shutting_down(self) -> bool:
        return self._shutting_down

    @property
    def active_count(self) -> int:
        return len(self._active_tasks)

    def set_dispatcher(self, dp) -> None:
        """Сохраняет ссылку на Dispatcher для доступа к _handle_update_tasks."""
        self._dispatcher = dp
        self._aiogram_tasks = dp._handle_update_tasks

    def register_task(self, task: asyncio.Task) -> None:
        """Зарегистрировать активную LLM-задачу для отслеживания."""
        self._active_tasks.add(task)
        self._drain_event.clear()
        task.add_done_callback(self._on_task_done)

    def _on_task_done(self, task: asyncio.Task) -> None:
        self._active_tasks.discard(task)
        if not self._active_tasks:
            self._drain_event.set()

    def install_signal_handlers(self) -> None:
        """
        Ставит свои SIGTERM/SIGINT хендлеры.

        При сигнале:
        - Ставим флаг _shutting_down
        - Сигнализируем aiogram остановить polling (dp._stop_signal.set())
        - start_polling завершается → попадаем в finally блок main.py
        - Там ждём handler-задачи и закрываем ресурсы
        """
        loop = asyncio.get_running_loop()

        def _on_signal(sig: signal.Signals) -> None:
            if self._shutting_down:
                logger.warning(f"[shutdown] Повторный {sig.name}, уже останавливаемся")
                return
            logger.warning(f"[shutdown] Получен {sig.name}, начинаем graceful shutdown...")
            self._shutting_down = True

            # Сигнализируем aiogram остановить polling — start_polling() вернётся
            if self._dispatcher and self._dispatcher._stop_signal:
                self._dispatcher._stop_signal.set()

        loop.add_signal_handler(signal.SIGTERM, _on_signal, signal.SIGTERM)
        loop.add_signal_handler(signal.SIGINT, _on_signal, signal.SIGINT)
        logger.info("[shutdown] Свои signal handlers установлены (SIGTERM, SIGINT)")

    async def wait_aiogram_handlers(self, timeout: float = 65.0) -> None:
        """
        Ждём пока dp._handle_update_tasks опустеет.
        Polling-цикл: каждые 5 секунд проверяем, не появились ли новые задачи.
        """
        if self._aiogram_tasks is None:
            return

        if not self._aiogram_tasks:
            logger.info("[shutdown] Нет активных aiogram handler-задач")
            return

        deadline = asyncio.get_event_loop().time() + timeout

        while self._aiogram_tasks:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                logger.warning(
                    f"[shutdown] Таймаут! {len(self._aiogram_tasks)} aiogram handler-задач "
                    f"не завершились за {timeout}с"
                )
                break

            count = len(self._aiogram_tasks)
            logger.info(f"[shutdown] Ждём {count} aiogram handler-задач (осталось {remaining:.0f}с)...")

            # Берём снимок текущих задач и ждём их
            tasks_snapshot = set(self._aiogram_tasks)
            if not tasks_snapshot:
                break

            try:
                await asyncio.wait(tasks_snapshot, timeout=min(remaining, 5.0))
            except Exception as e:
                logger.error(f"[shutdown] Ошибка при ожидании aiogram задач: {e}")
                break

        if not self._aiogram_tasks:
            logger.info("[shutdown] Все aiogram handler-задачи завершены")

    async def wait_registered_tasks(self, timeout: float = 65.0) -> None:
        """
        Ждём завершения зарегистрированных LLM-задач.
        """
        active = len(self._active_tasks)
        if active == 0:
            logger.info("[shutdown] Нет зарегистрированных LLM-задач")
            return

        logger.info(f"[shutdown] Ждём {active} зарегистрированных LLM-задач (таймаут {timeout}с)...")
        try:
            await asyncio.wait_for(self._drain_event.wait(), timeout=timeout)
            logger.info("[shutdown] Все зарегистрированные LLM-задачи завершены")
        except asyncio.TimeoutError:
            remaining = len(self._active_tasks)
            logger.warning(
                f"[shutdown] Таймаут! {remaining} LLM-задач не завершились за {timeout}с. "
                f"Crash recovery подберёт их при следующем запуске."
            )


# Глобальный синглтон
shutdown_coordinator = ShutdownCoordinator()
