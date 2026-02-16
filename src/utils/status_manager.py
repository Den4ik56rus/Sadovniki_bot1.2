# src/utils/status_manager.py

"""
Менеджер статусных сообщений для показа прогресса обработки запроса.

Два режима:
1. Прогресс-бар — показывает реальный этап обработки (▰▰▱▱▱▱ 2/6 Ищу литературу...)
2. Стриминг — показывает текст ответа по мере генерации (edit каждые 3 сек)

Переход: progress → streaming → complete

Финальный ответ: стриминг-сообщение НЕ удаляется, а переиспользуется
для финального отформатированного ответа (без задержки на delete+send).
"""

import asyncio
import logging
from typing import Optional, Union, Callable, Awaitable
from aiogram.types import Message, CallbackQuery

from src.utils.formatting import markdown_to_telegram_html

logger = logging.getLogger(__name__)

# Интервал редактирования стриминг-сообщения (секунды)
STREAMING_EDIT_INTERVAL: float = 3.0

# Максимальная длина текста для стриминг-превью (Telegram лимит 4096)
MAX_STREAMING_DISPLAY: int = 3900


def _build_progress_bar(step: int, total: int, label: str) -> str:
    """Формирует строку прогресс-бара: ▰▰▰▱▱▱ 3/6 Ищу литературу..."""
    filled = "▰" * step
    empty = "▱" * (total - step)
    return f"{filled}{empty} {step}/{total} {label}"


class StatusMessageManager:
    """
    Управляет сообщениями прогресса и стриминга.

    Режим прогресса:
        Одно сообщение с прогресс-баром, обновляется через update().

    Режим стриминга:
        Прогресс-сообщение удаляется, создаётся новое для стриминга текста.
        Текст форматируется markdown→HTML и редактируется каждые 3 секунды.

    Финализация:
        Стриминг-сообщение можно забрать через get_streaming_message()
        для финального edit (без пересоздания) или удалить через complete().
    """

    def __init__(self, source: Union[Message, CallbackQuery], use_rag: bool = True):
        self._source = source
        self._use_rag = use_rag

        # Прогресс-режим
        self._progress_message: Optional[Message] = None

        # Стриминг-режим
        self._streaming_message: Optional[Message] = None
        self._streaming_text: str = ""
        self._streaming_dirty: bool = False
        self._streaming_task: Optional[asyncio.Task] = None

        self._mode: str = "idle"  # idle → progress → streaming → done

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.complete()
        return False

    def _get_chat(self):
        if isinstance(self._source, CallbackQuery):
            return self._source.message
        return self._source

    async def start(self, initial_text: Optional[str] = None) -> None:
        """Отправляет начальное сообщение с прогресс-баром."""
        total = 6 if self._use_rag else 3
        text = initial_text or _build_progress_bar(1, total, "Анализирую запрос...")

        try:
            chat = self._get_chat()
            self._progress_message = await chat.answer(text)
            self._mode = "progress"
        except Exception as e:
            logger.warning(f"[StatusManager] Failed to send progress message: {e}")

    async def update(self, step: int, total: int, label: str) -> None:
        """Обновляет прогресс-бар на текущий этап."""
        if self._mode != "progress" or not self._progress_message:
            return

        text = _build_progress_bar(step, total, label)
        try:
            await self._progress_message.edit_text(text)
        except Exception:
            pass  # message not modified или другая ошибка Telegram

    async def start_streaming(self) -> Callable[[str], Awaitable[None]]:
        """
        Переход из прогресс-режима в стриминг.

        Удаляет прогресс-сообщение, создаёт новое для стриминга.
        Возвращает callback для передачи накопленного текста.
        """
        self._mode = "streaming"

        # Удаляем прогресс-сообщение
        if self._progress_message:
            try:
                await self._progress_message.delete()
            except Exception:
                pass
            self._progress_message = None

        # Создаём сообщение для стриминга
        try:
            chat = self._get_chat()
            self._streaming_message = await chat.answer("⏳ Генерирую ответ...")
        except Exception as e:
            logger.warning(f"[StatusManager] Failed to send streaming message: {e}")

        # Запускаем фоновый цикл редактирования
        self._streaming_task = asyncio.create_task(self._streaming_edit_loop())

        return self._on_stream_chunk

    async def _on_stream_chunk(self, accumulated_text: str) -> None:
        """Callback: сохраняет накопленный текст для следующего edit."""
        self._streaming_text = accumulated_text
        self._streaming_dirty = True

    def _format_for_display(self, text: str) -> str:
        """Конвертирует markdown→HTML для отображения в Telegram."""
        try:
            return markdown_to_telegram_html(text)
        except Exception:
            # Fallback: отправляем как есть если форматирование сломалось
            return text

    async def _streaming_edit_loop(self) -> None:
        """Фоновая задача: редактирует стриминг-сообщение каждые 3 секунды."""
        # Анимация песочных часов пока ждём первый чанк от LLM
        _hourglass_frames = ["⏳", "⌛"]
        _hourglass_idx = 0

        try:
            while self._mode == "streaming":
                await asyncio.sleep(STREAMING_EDIT_INTERVAL)

                if self._mode != "streaming":
                    return
                if not self._streaming_message:
                    continue

                # Если текст ещё не пришёл — анимируем часы
                if not self._streaming_dirty or not self._streaming_text:
                    hg = _hourglass_frames[_hourglass_idx % len(_hourglass_frames)]
                    _hourglass_idx += 1
                    try:
                        await self._streaming_message.edit_text(f"{hg} Генерирую ответ...")
                    except Exception:
                        pass
                    continue

                self._streaming_dirty = False
                raw_text = self._streaming_text

                # Форматируем markdown → HTML
                display = self._format_for_display(raw_text)

                # Обрезаем если слишком длинное для Telegram
                if len(display) > MAX_STREAMING_DISPLAY:
                    display = display[:MAX_STREAMING_DISPLAY] + "\n\n⏳ Завершаю генерацию..."
                else:
                    # Курсор — индикатор что текст ещё генерируется
                    display += "\n\n▌"

                try:
                    await self._streaming_message.edit_text(display)
                except Exception:
                    pass  # message not modified
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"[StatusManager] Streaming edit loop error: {e}")

    def get_streaming_message(self) -> Optional[Message]:
        """
        Возвращает стриминг-сообщение для финального edit.

        Вызывать ПОСЛЕ complete(). Если сообщение было забрано,
        complete() не будет его удалять.
        """
        msg = self._streaming_message
        self._streaming_message = None  # Отдаём владение — complete() не удалит
        return msg

    async def complete(self) -> None:
        """Останавливает всё и удаляет все временные сообщения."""
        self._mode = "done"

        # Останавливаем стриминг-задачу
        if self._streaming_task and not self._streaming_task.done():
            self._streaming_task.cancel()
            try:
                await self._streaming_task
            except asyncio.CancelledError:
                pass

        # Удаляем прогресс-сообщение (если ещё есть)
        if self._progress_message:
            try:
                await self._progress_message.delete()
            except Exception:
                pass
            self._progress_message = None

        # Удаляем стриминг-сообщение (если не забрали через get_streaming_message)
        if self._streaming_message:
            try:
                await self._streaming_message.delete()
            except Exception:
                pass
            self._streaming_message = None

        self._streaming_text = ""
