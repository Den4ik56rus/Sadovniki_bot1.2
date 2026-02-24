# src/shutdown.py

"""
Координатор graceful shutdown.

При получении SIGTERM (docker stop / deploy):
1. Ставит флаг is_shutting_down = True
2. Ждёт завершения всех активных LLM-задач (до timeout секунд)
3. Только после этого продолжается остановка бота

Это гарантирует, что пользователь получит полный ответ даже во время деплоя.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


class ShutdownCoordinator:
    def __init__(self) -> None:
        self._shutting_down = False
        self._active_tasks: set[asyncio.Task] = set()
        self._drain_event = asyncio.Event()
        self._drain_event.set()  # изначально "пусто" — нет активных задач

    @property
    def is_shutting_down(self) -> bool:
        return self._shutting_down

    @property
    def active_count(self) -> int:
        return len(self._active_tasks)

    def register_task(self, task: asyncio.Task) -> None:
        """Зарегистрировать активную LLM-задачу для отслеживания."""
        if self._shutting_down:
            return  # не регистрируем новые задачи во время shutdown
        self._active_tasks.add(task)
        self._drain_event.clear()
        task.add_done_callback(self._on_task_done)

    def _on_task_done(self, task: asyncio.Task) -> None:
        self._active_tasks.discard(task)
        if not self._active_tasks:
            self._drain_event.set()

    async def begin_shutdown(self, timeout: float = 60.0) -> None:
        """
        Начать graceful shutdown.
        Ставит флаг и ждёт завершения активных LLM-задач до timeout секунд.
        """
        self._shutting_down = True
        active = len(self._active_tasks)

        if active == 0:
            logger.info("[shutdown] Нет активных LLM-задач, продолжаем остановку")
            return

        logger.info(f"[shutdown] Ждём завершения {active} активных LLM-задач (таймаут {timeout}с)...")
        try:
            await asyncio.wait_for(self._drain_event.wait(), timeout=timeout)
            logger.info("[shutdown] Все LLM-задачи завершены, продолжаем остановку")
        except asyncio.TimeoutError:
            remaining = len(self._active_tasks)
            logger.warning(
                f"[shutdown] Таймаут! {remaining} задач не завершились за {timeout}с. "
                f"Crash recovery подберёт их при следующем запуске."
            )


# Глобальный синглтон
shutdown_coordinator = ShutdownCoordinator()
