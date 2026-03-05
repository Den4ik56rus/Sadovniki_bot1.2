"""
SSE (Server-Sent Events) handlers для админ-панели.

Endpoints:
- /api/admin/events/live-feed - стрим новых логов консультаций
- /api/admin/events/logs/{topic_id} - стрим логов конкретного топика
- /api/admin/events/documents/{document_id} - стрим статуса обработки документа
- /api/admin/events/funnel/{funnel_id} - стрим изменений воронки (CRM, Покупатели и т.д.)
- /api/admin/events/client/{user_id} - стрим событий конкретного клиента (сообщения, консультации, топики)
"""

import asyncio
import json
import logging
import uuid
from typing import Any, Optional

from aiohttp import web

from src.api.sse_manager import sse_manager
from src.services.db.consultation_logs_repo import get_logs_since_id

logger = logging.getLogger(__name__)


async def send_sse_event(
    response: web.StreamResponse,
    event_type: str,
    data: Any,
    event_id: Optional[Any] = None
) -> None:
    """
    Отправляет SSE событие клиенту.

    Формат SSE:
        event: <event_type>
        id: <event_id>
        data: <json>

    Args:
        response: StreamResponse для записи
        event_type: Тип события ('new_log', 'status_update', 'heartbeat')
        data: Данные события (будут сериализованы в JSON)
        event_id: ID события (опционально)
    """
    message = f"event: {event_type}\n"

    if event_id is not None:
        message += f"id: {event_id}\n"

    message += f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    try:
        await response.write(message.encode('utf-8'))
        await response.drain()
    except (ConnectionResetError, RuntimeError) as e:
        # Нормальное закрытие соединения - не засоряем логи
        error_msg = str(e)
        if "closing transport" in error_msg or "Connection lost" in error_msg:
            logger.debug(f"SSE connection closed: {e}")
        else:
            logger.warning(f"SSE connection error: {e}")
    except Exception as e:
        # Неожиданная ошибка - это действительно проблема
        logger.error(f"Unexpected SSE error: {e}", exc_info=True)


async def live_feed_stream(request: web.Request) -> web.StreamResponse:
    """
    SSE endpoint для Live Feed.

    Отправляет новые логи консультаций в реальном времени.

    Query params:
        last_event_id (str, optional): ID последнего полученного события
            Используется для восстановления пропущенных событий при reconnect
    """
    # 1. Создаём StreamResponse с правильными headers
    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'text/event-stream; charset=utf-8',
            'Cache-Control': 'no-cache, no-transform',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',  # Отключает буферизацию в nginx
        }
    )

    await response.prepare(request)

    # 2. Генерируем уникальный client_id
    client_id = str(uuid.uuid4())

    # 3. Создаём очередь для событий
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    # 4. Получаем last_event_id из query params
    last_event_id_str = request.query.get('last_event_id')

    logger.info(
        f"New SSE client connected: {client_id} "
        f"(live-feed, last_event_id={last_event_id_str})"
    )

    # 5. Регистрируем клиента в SSEManager
    await sse_manager.add_client(
        client_id=client_id,
        queue=queue,
        endpoint_type='live-feed',
        last_event_id=last_event_id_str
    )

    # 6. Если есть last_event_id, отправляем пропущенные события
    if last_event_id_str:
        try:
            last_event_id = int(last_event_id_str)
            missed_logs = await get_logs_since_id(last_event_id, limit=50)

            if missed_logs:
                logger.info(
                    f"Sending {len(missed_logs)} missed events "
                    f"to {client_id}"
                )

                for log in reversed(missed_logs):  # Отправляем в хронологическом порядке
                    log_dict = dict(log)
                    await send_sse_event(
                        response,
                        'new_log',
                        log_dict,
                        log_dict['id']
                    )
        except (ValueError, TypeError) as e:
            logger.warning(
                f"Invalid last_event_id '{last_event_id_str}': {e}"
            )
        except Exception as e:
            logger.error(
                f"Error fetching missed events for {client_id}: {e}"
            )

    # 7. Обрабатываем события из очереди
    try:
        while True:
            # Ждём событие из очереди
            event = await queue.get()

            # None - сигнал завершения
            if event is None:
                logger.info(f"Received shutdown signal for {client_id}")
                break

            # Отправляем событие клиенту
            await send_sse_event(
                response,
                event['type'],
                event['data'],
                event.get('id')
            )

    except asyncio.CancelledError:
        logger.info(f"SSE client {client_id} cancelled")
    except ConnectionResetError:
        logger.info(f"SSE client {client_id} connection reset")
    except Exception as e:
        logger.error(f"Error in live_feed_stream for {client_id}: {e}")
    finally:
        # 8. Удаляем клиента из менеджера
        await sse_manager.remove_client(client_id)

        # 9. Закрываем соединение
        try:
            await response.write_eof()
        except Exception as e:
            logger.error(f"Error closing response for {client_id}: {e}")

        logger.info(f"SSE client {client_id} disconnected (live-feed)")

    return response


async def topic_logs_stream(request: web.Request) -> web.StreamResponse:
    """
    SSE endpoint для логов конкретного топика.

    Отправляет новые логи консультации в реальном времени.

    Path params:
        topic_id (int): ID топика

    Query params:
        last_event_id (str, optional): ID последнего полученного события
    """
    # Получаем topic_id из path params
    try:
        topic_id = int(request.match_info['topic_id'])
    except (KeyError, ValueError) as e:
        logger.error(f"Invalid topic_id in path: {e}")
        raise web.HTTPBadRequest(text="Invalid topic_id")

    # Создаём StreamResponse
    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'text/event-stream; charset=utf-8',
            'Cache-Control': 'no-cache, no-transform',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )

    await response.prepare(request)

    # Генерируем client_id и создаём очередь
    client_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    last_event_id_str = request.query.get('last_event_id')

    logger.info(
        f"New SSE client connected: {client_id} "
        f"(logs, topic_id={topic_id}, last_event_id={last_event_id_str})"
    )

    # Регистрируем клиента
    await sse_manager.add_client(
        client_id=client_id,
        queue=queue,
        endpoint_type='logs',
        entity_id=topic_id,
        last_event_id=last_event_id_str
    )

    # Отправляем пропущенные события если нужно
    if last_event_id_str:
        try:
            last_event_id = int(last_event_id_str)
            # Получаем пропущенные логи для этого топика
            missed_logs = await get_logs_since_id(
                last_event_id,
                limit=50,
                topic_id=topic_id
            )

            if missed_logs:
                logger.info(
                    f"Sending {len(missed_logs)} missed events "
                    f"to {client_id} (topic={topic_id})"
                )

                for log in reversed(missed_logs):
                    log_dict = dict(log)
                    await send_sse_event(
                        response,
                        'new_log',
                        log_dict,
                        log_dict['id']
                    )
        except (ValueError, TypeError) as e:
            logger.warning(
                f"Invalid last_event_id '{last_event_id_str}': {e}"
            )
        except Exception as e:
            logger.error(
                f"Error fetching missed events for {client_id}: {e}"
            )

    # Обрабатываем события из очереди
    try:
        while True:
            event = await queue.get()

            if event is None:
                logger.info(f"Received shutdown signal for {client_id}")
                break

            await send_sse_event(
                response,
                event['type'],
                event['data'],
                event.get('id')
            )

    except asyncio.CancelledError:
        logger.info(f"SSE client {client_id} cancelled")
    except ConnectionResetError:
        logger.info(f"SSE client {client_id} connection reset")
    except Exception as e:
        logger.error(f"Error in topic_logs_stream for {client_id}: {e}")
    finally:
        await sse_manager.remove_client(client_id)

        try:
            await response.write_eof()
        except Exception as e:
            logger.error(f"Error closing response for {client_id}: {e}")

        logger.info(
            f"SSE client {client_id} disconnected "
            f"(logs, topic_id={topic_id})"
        )

    return response


async def document_status_stream(request: web.Request) -> web.StreamResponse:
    """
    SSE endpoint для статуса обработки документа.

    Отправляет обновления статуса в реальном времени.

    Path params:
        document_id (int): ID документа
    """
    # Получаем document_id из path params
    try:
        document_id = int(request.match_info['document_id'])
    except (KeyError, ValueError) as e:
        logger.error(f"Invalid document_id in path: {e}")
        raise web.HTTPBadRequest(text="Invalid document_id")

    # Создаём StreamResponse
    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'text/event-stream; charset=utf-8',
            'Cache-Control': 'no-cache, no-transform',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )

    await response.prepare(request)

    # Генерируем client_id и создаём очередь
    client_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    logger.info(
        f"New SSE client connected: {client_id} "
        f"(documents, document_id={document_id})"
    )

    # Регистрируем клиента
    await sse_manager.add_client(
        client_id=client_id,
        queue=queue,
        endpoint_type='documents',
        entity_id=document_id
    )

    # Обрабатываем события из очереди
    try:
        while True:
            event = await queue.get()

            if event is None:
                logger.info(f"Received shutdown signal for {client_id}")
                break

            await send_sse_event(
                response,
                event['type'],
                event['data'],
                event.get('id')
            )

    except asyncio.CancelledError:
        logger.info(f"SSE client {client_id} cancelled")
    except ConnectionResetError:
        logger.info(f"SSE client {client_id} connection reset")
    except Exception as e:
        logger.error(f"Error in document_status_stream for {client_id}: {e}")
    finally:
        await sse_manager.remove_client(client_id)

        try:
            await response.write_eof()
        except Exception as e:
            logger.error(f"Error closing response for {client_id}: {e}")

        logger.info(
            f"SSE client {client_id} disconnected "
            f"(documents, document_id={document_id})"
        )

    return response


async def funnel_stream(request: web.Request) -> web.StreamResponse:
    """
    SSE endpoint для real-time обновлений воронки (CRM, Покупатели, кастомные).

    Отправляет события при изменении клиентов в воронке:
    - client_moved — клиент перемещён между этапами
    - client_removed — клиент удалён из воронки
    - client_added — новый клиент добавлен в воронку
    - consultation_logged — новая консультация (обновляет метрики клиента)

    Path params:
        funnel_id (str): ID воронки ('crm', 'buyers', или UUID кастомной)
    """
    funnel_id = request.match_info.get('funnel_id', '')
    if not funnel_id:
        raise web.HTTPBadRequest(text="Missing funnel_id")

    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'text/event-stream; charset=utf-8',
            'Cache-Control': 'no-cache, no-transform',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )

    await response.prepare(request)

    client_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    # endpoint_type = 'funnel-crm', 'funnel-buyers', etc.
    endpoint_type = f'funnel-{funnel_id}'

    logger.info(
        f"New SSE client connected: {client_id} "
        f"({endpoint_type})"
    )

    await sse_manager.add_client(
        client_id=client_id,
        queue=queue,
        endpoint_type=endpoint_type,
    )

    try:
        while True:
            event = await queue.get()

            if event is None:
                logger.info(f"Received shutdown signal for {client_id}")
                break

            await send_sse_event(
                response,
                event['type'],
                event['data'],
                event.get('id')
            )

    except asyncio.CancelledError:
        logger.info(f"SSE client {client_id} cancelled")
    except ConnectionResetError:
        logger.info(f"SSE client {client_id} connection reset")
    except Exception as e:
        logger.error(f"Error in funnel_stream for {client_id}: {e}")
    finally:
        await sse_manager.remove_client(client_id)

        try:
            await response.write_eof()
        except Exception as e:
            logger.error(f"Error closing response for {client_id}: {e}")

        logger.info(
            f"SSE client {client_id} disconnected "
            f"({endpoint_type})"
        )

    return response


async def client_stream(request: web.Request) -> web.StreamResponse:
    """
    SSE endpoint для real-time обновлений конкретного клиента.

    Отправляет события при активности клиента:
    - new_message — новое сообщение (user или bot)
    - new_consultation — новая консультация залогирована
    - new_topic — новый топик создан

    Path params:
        user_id (int): Внутренний ID пользователя (users.id)
    """
    try:
        user_id = int(request.match_info['user_id'])
    except (KeyError, ValueError) as e:
        logger.error(f"Invalid user_id in path: {e}")
        raise web.HTTPBadRequest(text="Invalid user_id")

    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'text/event-stream; charset=utf-8',
            'Cache-Control': 'no-cache, no-transform',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )

    await response.prepare(request)

    client_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    logger.info(
        f"New SSE client connected: {client_id} "
        f"(client, user_id={user_id})"
    )

    await sse_manager.add_client(
        client_id=client_id,
        queue=queue,
        endpoint_type='client',
        entity_id=user_id,
    )

    try:
        while True:
            event = await queue.get()

            if event is None:
                logger.info(f"Received shutdown signal for {client_id}")
                break

            await send_sse_event(
                response,
                event['type'],
                event['data'],
                event.get('id')
            )

    except asyncio.CancelledError:
        logger.info(f"SSE client {client_id} cancelled")
    except ConnectionResetError:
        logger.info(f"SSE client {client_id} connection reset")
    except Exception as e:
        logger.error(f"Error in client_stream for {client_id}: {e}")
    finally:
        await sse_manager.remove_client(client_id)

        try:
            await response.write_eof()
        except Exception as e:
            logger.error(f"Error closing response for {client_id}: {e}")

        logger.info(
            f"SSE client {client_id} disconnected "
            f"(client, user_id={user_id})"
        )

    return response


async def broadcast_stream(request: web.Request) -> web.StreamResponse:
    """
    SSE endpoint для прогресса рассылки.

    Отправляет события:
    - broadcast_progress — обновление счётчиков (sent_count, failed_count, total)
    - broadcast_completed — рассылка завершена

    Path params:
        broadcast_id (int): ID рассылки
    """
    try:
        broadcast_id = int(request.match_info['broadcast_id'])
    except (KeyError, ValueError) as e:
        logger.error(f"Invalid broadcast_id in path: {e}")
        raise web.HTTPBadRequest(text="Invalid broadcast_id")

    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'text/event-stream; charset=utf-8',
            'Cache-Control': 'no-cache, no-transform',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )

    await response.prepare(request)

    client_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    logger.info(
        f"New SSE client connected: {client_id} "
        f"(broadcast, broadcast_id={broadcast_id})"
    )

    await sse_manager.add_client(
        client_id=client_id,
        queue=queue,
        endpoint_type='broadcast',
        entity_id=broadcast_id,
    )

    try:
        while True:
            event = await queue.get()

            if event is None:
                logger.info(f"Received shutdown signal for {client_id}")
                break

            await send_sse_event(
                response,
                event['type'],
                event['data'],
                event.get('id')
            )

    except asyncio.CancelledError:
        logger.info(f"SSE client {client_id} cancelled")
    except ConnectionResetError:
        logger.info(f"SSE client {client_id} connection reset")
    except Exception as e:
        logger.error(f"Error in broadcast_stream for {client_id}: {e}")
    finally:
        await sse_manager.remove_client(client_id)

        try:
            await response.write_eof()
        except Exception as e:
            logger.error(f"Error closing response for {client_id}: {e}")

        logger.info(
            f"SSE client {client_id} disconnected "
            f"(broadcast, broadcast_id={broadcast_id})"
        )

    return response


async def presentation_stream(request: web.Request) -> web.StreamResponse:
    """
    SSE endpoint для прогресса генерации презентации.

    Отправляет события:
    - generation_started — генерация началась
    - text_processing — GPT обрабатывает текст
    - slides_planned — GPT разбил текст на слайды
    - slide_generating — начинается генерация слайда N
    - slide_completed — слайд N сгенерирован
    - slide_failed — ошибка генерации слайда
    - building_pdf — сборка PDF
    - generation_completed — всё готово
    - generation_failed — ошибка

    Path params:
        presentation_id (int): ID презентации
    """
    try:
        presentation_id = int(request.match_info['presentation_id'])
    except (KeyError, ValueError) as e:
        logger.error(f"Invalid presentation_id in path: {e}")
        raise web.HTTPBadRequest(text="Invalid presentation_id")

    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'text/event-stream; charset=utf-8',
            'Cache-Control': 'no-cache, no-transform',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )

    await response.prepare(request)

    client_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    logger.info(
        f"New SSE client connected: {client_id} "
        f"(presentation, presentation_id={presentation_id})"
    )

    await sse_manager.add_client(
        client_id=client_id,
        queue=queue,
        endpoint_type='presentation',
        entity_id=presentation_id,
    )

    try:
        while True:
            event = await queue.get()

            if event is None:
                logger.info(f"Received shutdown signal for {client_id}")
                break

            await send_sse_event(
                response,
                event['type'],
                event['data'],
                event.get('id')
            )

    except asyncio.CancelledError:
        logger.info(f"SSE client {client_id} cancelled")
    except ConnectionResetError:
        logger.info(f"SSE client {client_id} connection reset")
    except Exception as e:
        logger.error(f"Error in presentation_stream for {client_id}: {e}")
    finally:
        await sse_manager.remove_client(client_id)

        try:
            await response.write_eof()
        except Exception as e:
            logger.error(f"Error closing response for {client_id}: {e}")

        logger.info(
            f"SSE client {client_id} disconnected "
            f"(presentation, presentation_id={presentation_id})"
        )

    return response


async def batch_stream(request: web.Request) -> web.StreamResponse:
    """
    SSE endpoint для прогресса пакетной генерации презентаций.

    Отправляет события:
    - batch_started — пакет запущен
    - batch_item_started — начало генерации элемента
    - batch_item_progress — прогресс внутри презентации
    - batch_item_completed — элемент готов
    - batch_item_failed — ошибка элемента
    - batch_completed — пакет завершён
    - batch_cancelled — пакет отменён

    Path params:
        batch_id (int): ID пакета
    """
    try:
        batch_id = int(request.match_info['batch_id'])
    except (KeyError, ValueError) as e:
        logger.error(f"Invalid batch_id in path: {e}")
        raise web.HTTPBadRequest(text="Invalid batch_id")

    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'text/event-stream; charset=utf-8',
            'Cache-Control': 'no-cache, no-transform',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )

    await response.prepare(request)

    client_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    logger.info(
        f"New SSE client connected: {client_id} "
        f"(batch, batch_id={batch_id})"
    )

    await sse_manager.add_client(
        client_id=client_id,
        queue=queue,
        endpoint_type='batch',
        entity_id=batch_id,
    )

    try:
        while True:
            event = await queue.get()

            if event is None:
                logger.info(f"Received shutdown signal for {client_id}")
                break

            await send_sse_event(
                response,
                event['type'],
                event['data'],
                event.get('id')
            )

    except asyncio.CancelledError:
        logger.info(f"SSE client {client_id} cancelled")
    except ConnectionResetError:
        logger.info(f"SSE client {client_id} connection reset")
    except Exception as e:
        logger.error(f"Error in batch_stream for {client_id}: {e}")
    finally:
        await sse_manager.remove_client(client_id)

        try:
            await response.write_eof()
        except Exception as e:
            logger.error(f"Error closing response for {client_id}: {e}")

        logger.info(
            f"SSE client {client_id} disconnected "
            f"(batch, batch_id={batch_id})"
        )

    return response


async def article_batch_stream(request: web.Request) -> web.StreamResponse:
    """
    SSE endpoint для прогресса пакетной генерации статей.

    Отправляет события:
    - article_batch_started — пакет запущен
    - article_batch_item_started — начало генерации элемента
    - article_batch_item_completed — элемент готов
    - article_batch_item_failed — ошибка элемента
    - article_batch_completed — пакет завершён
    - article_batch_cancelled — пакет отменён

    Path params:
        batch_id (int): ID пакета
    """
    try:
        batch_id = int(request.match_info['batch_id'])
    except (KeyError, ValueError) as e:
        logger.error(f"Invalid batch_id in path: {e}")
        raise web.HTTPBadRequest(text="Invalid batch_id")

    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'text/event-stream; charset=utf-8',
            'Cache-Control': 'no-cache, no-transform',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )

    await response.prepare(request)

    client_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    logger.info(
        f"New SSE client connected: {client_id} "
        f"(article_batch, batch_id={batch_id})"
    )

    await sse_manager.add_client(
        client_id=client_id,
        queue=queue,
        endpoint_type='article_batch',
        entity_id=batch_id,
    )

    try:
        while True:
            event = await queue.get()

            if event is None:
                logger.info(f"Received shutdown signal for {client_id}")
                break

            await send_sse_event(
                response,
                event['type'],
                event['data'],
                event.get('id')
            )

    except asyncio.CancelledError:
        logger.info(f"SSE client {client_id} cancelled")
    except ConnectionResetError:
        logger.info(f"SSE client {client_id} connection reset")
    except Exception as e:
        logger.error(f"Error in article_batch_stream for {client_id}: {e}")
    finally:
        await sse_manager.remove_client(client_id)

        try:
            await response.write_eof()
        except Exception as e:
            logger.error(f"Error closing response for {client_id}: {e}")

        logger.info(
            f"SSE client {client_id} disconnected "
            f"(article_batch, batch_id={batch_id})"
        )

    return response


async def sse_stats(request: web.Request) -> web.Response:
    """
    Endpoint для получения статистики по SSE подключениям.

    Возвращает количество подключённых клиентов по типам.
    """
    stats = sse_manager.get_stats()

    return web.json_response(stats)
