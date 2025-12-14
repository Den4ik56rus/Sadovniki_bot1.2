# src/utils/status_manager.py

"""
Менеджер статусных сообщений для показа прогресса обработки запроса.

Используется в хендлерах консультаций для отображения динамических
статусов во время генерации ответа.

Сообщения показываются по таймеру, независимо от реального прогресса,
чтобы создать плавный UX для пользователя.

Структура:
- Первое сообщение: "⏳ Подождите, рекомендация формируется..." (анимация часов + точки)
- Второе сообщение: динамические статусы (удаляется и пишется новое)
"""

import asyncio
import logging
from typing import Optional, Union, List
from aiogram.types import Message, CallbackQuery

logger = logging.getLogger(__name__)


# Статусы для полного RAG-потока
RAG_STATUSES: List[str] = [
    "📚 Загружаю историю диалога...",
    "🔍 Готовлю запрос для поиска...",
    "📖 Ищу подходящую литературу...",
    "🧠 Изучаю найденные материалы...",
]

# Статусы для упрощённого потока (без RAG)
SIMPLE_STATUSES: List[str] = [
    "📚 Анализирую Ваш вопрос...",
    "🔍 Определяю тему консультации...",
]

# Финальные статусы (зацикливаются пока не придёт ответ)
FINAL_LOOP_STATUSES: List[str] = [
    "✍️ Формирую ответ...",
    "📝 Структурирую информацию...",
    "✨ Проверяю рекомендации...",
    "🔄 Дорабатываю формулировки...",
]

# Интервал между сменой статусов (секунды)
STATUS_INTERVAL: float = 5.0

# Интервал анимации основного сообщения (секунды)
MAIN_ANIMATION_INTERVAL: float = 1.0

# Шаблоны для анимации основного сообщения (часы + точки)
MAIN_MESSAGE_FRAMES: List[str] = [
    "⏳ Подождите, рекомендация\nформируется",
    "⌛ Подождите, рекомендация\nформируется.",
    "⏳ Подождите, рекомендация\nформируется..",
    "⌛ Подождите, рекомендация\nформируется...",
]


class StatusMessageManager:
    """
    Управляет двумя сообщениями:
    1. Анимированное "⏳/⌛ Подождите, рекомендация формируется..." (часы + точки)
    2. Динамическое со статусами (удаляется и пишется новое)

    Пример использования:
        async with StatusMessageManager(message) as status_mgr:
            reply = await ask_consultation_llm(...)
        # Оба сообщения автоматически удалятся при выходе из контекста

    Или классический вариант:
        status_mgr = StatusMessageManager(message)
        await status_mgr.start()
        try:
            reply = await ask_consultation_llm(...)
        finally:
            await status_mgr.complete()
    """

    def __init__(self, source: Union[Message, CallbackQuery], use_rag: bool = True):
        """
        Инициализирует менеджер.

        Args:
            source: Message или CallbackQuery от пользователя
            use_rag: True для полного RAG-потока, False для упрощённого
        """
        self._source = source
        self._use_rag = use_rag
        self._main_message: Optional[Message] = None      # Анимированное сообщение
        self._status_message: Optional[Message] = None    # Динамическое сообщение
        self._current_status: str = ""
        self._status_task: Optional[asyncio.Task] = None
        self._main_task: Optional[asyncio.Task] = None
        self._running: bool = False

    async def __aenter__(self):
        """Поддержка async with."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Автоматическое завершение при выходе из контекста."""
        await self.complete()
        return False

    def _get_chat(self):
        """Возвращает чат для отправки сообщений."""
        if isinstance(self._source, CallbackQuery):
            return self._source.message
        return self._source

    async def start(self, initial_text: Optional[str] = None) -> None:
        """
        Отправляет два сообщения и запускает автоматическую смену статусов.

        Args:
            initial_text: Текст основного сообщения (опционально, игнорируется для анимации)
        """
        # Первый кадр анимации
        main_text = MAIN_MESSAGE_FRAMES[0]

        # Выбираем первый статус
        statuses = RAG_STATUSES if self._use_rag else SIMPLE_STATUSES
        first_status = statuses[0] if statuses else FINAL_LOOP_STATUSES[0]

        try:
            chat = self._get_chat()
            # Отправляем основное сообщение
            self._main_message = await chat.answer(main_text)
            # Отправляем сообщение со статусом
            self._status_message = await chat.answer(first_status)

            self._current_status = first_status

            # Запускаем фоновые задачи
            self._running = True
            self._status_task = asyncio.create_task(self._status_loop())
            self._main_task = asyncio.create_task(self._main_animation_loop())

        except Exception as e:
            logger.warning(f"[StatusManager] Failed to send messages: {e}")

    async def _main_animation_loop(self) -> None:
        """Фоновая задача: анимация основного сообщения (часы + точки)."""
        try:
            frame_index = 1  # Начинаем с 1, т.к. 0 уже показан
            while self._running:
                await asyncio.sleep(MAIN_ANIMATION_INTERVAL)
                if not self._running or not self._main_message:
                    return

                frame = MAIN_MESSAGE_FRAMES[frame_index % len(MAIN_MESSAGE_FRAMES)]
                try:
                    await self._main_message.edit_text(frame)
                except Exception:
                    pass  # Игнорируем ошибки редактирования

                frame_index += 1

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"[StatusManager] Main animation error: {e}")

    async def _status_loop(self) -> None:
        """Фоновая задача: меняет статусы по таймеру (удаление + новое сообщение)."""
        try:
            # Выбираем начальные статусы
            statuses = RAG_STATUSES if self._use_rag else SIMPLE_STATUSES

            # Пропускаем первый статус (уже показан) и проходим по остальным
            for status in statuses[1:]:
                if not self._running:
                    return
                await asyncio.sleep(STATUS_INTERVAL)
                if not self._running:
                    return
                await self._replace_status(status)

            # Затем зацикливаем финальные статусы
            loop_index = 0
            while self._running:
                await asyncio.sleep(STATUS_INTERVAL)
                if not self._running:
                    return
                status = FINAL_LOOP_STATUSES[loop_index % len(FINAL_LOOP_STATUSES)]
                await self._replace_status(status)
                loop_index += 1

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"[StatusManager] Status loop error: {e}")

    async def _replace_status(self, status_text: str) -> None:
        """Удаляет старое сообщение и отправляет новое с новым статусом."""
        if not self._status_message:
            return

        # Не меняем если текст не изменился
        if status_text == self._current_status:
            return

        try:
            chat = self._get_chat()

            # Удаляем старое сообщение
            try:
                await self._status_message.delete()
            except Exception:
                pass  # Игнорируем ошибки удаления

            # Отправляем новое сообщение
            self._status_message = await chat.answer(status_text)
            self._current_status = status_text

        except Exception as e:
            logger.debug(f"[StatusManager] Failed to replace status: {e}")

    async def update(self, status_text: str) -> None:
        """
        Ручное обновление статуса (для обратной совместимости).
        В новой версии это игнорируется, т.к. статусы меняются автоматически.
        """
        pass  # Игнорируем ручные вызовы

    async def complete(self) -> None:
        """Останавливает смену статусов и удаляет оба сообщения."""
        self._running = False

        # Отменяем фоновые задачи
        for task in [self._status_task, self._main_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Удаляем динамическое сообщение со статусом
        if self._status_message:
            try:
                await self._status_message.delete()
            except Exception as e:
                logger.debug(f"[StatusManager] Failed to delete status message: {e}")
            finally:
                self._status_message = None

        # Удаляем основное сообщение
        if self._main_message:
            try:
                await self._main_message.delete()
            except Exception as e:
                logger.debug(f"[StatusManager] Failed to delete main message: {e}")
            finally:
                self._main_message = None

        self._current_status = ""
