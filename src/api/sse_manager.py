"""
SSE Manager для управления Server-Sent Events подключениями.

Обеспечивает:
- Регистрацию и удаление SSE клиентов
- Broadcast событий всем подключённым клиентам
- Keep-alive через heartbeat события
- Cleanup неактивных клиентов
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class SSEClient:
    """Представляет подключённого SSE клиента."""

    client_id: str
    queue: asyncio.Queue
    endpoint_type: str  # 'live-feed' | 'logs' | 'documents'
    entity_id: Optional[int] = None  # topic_id или document_id для фильтрации
    last_event_id: Optional[str] = None
    connected_at: datetime = field(default_factory=datetime.now)
    last_heartbeat: datetime = field(default_factory=datetime.now)


class SSEManager:
    """
    Singleton менеджер для управления SSE подключениями.

    Использование:
        await sse_manager.add_client(client_id, queue, 'live-feed')
        await sse_manager.broadcast('new_log', log_data, 'live-feed')
        await sse_manager.remove_client(client_id)
    """

    _instance: Optional['SSEManager'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.clients: Dict[str, SSEClient] = {}
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._initialized = True

        logger.info("SSEManager initialized")

    async def add_client(
        self,
        client_id: str,
        queue: asyncio.Queue,
        endpoint_type: str,
        entity_id: Optional[int] = None,
        last_event_id: Optional[str] = None
    ) -> None:
        """
        Регистрирует нового SSE клиента.

        Args:
            client_id: Уникальный ID клиента (UUID)
            queue: Очередь для отправки событий клиенту
            endpoint_type: Тип endpoint ('live-feed', 'logs', 'documents')
            entity_id: ID сущности для фильтрации (topic_id, document_id)
            last_event_id: ID последнего полученного события (для reconnect)
        """
        client = SSEClient(
            client_id=client_id,
            queue=queue,
            endpoint_type=endpoint_type,
            entity_id=entity_id,
            last_event_id=last_event_id
        )

        self.clients[client_id] = client

        logger.info(
            f"SSE client added: {client_id} "
            f"(type={endpoint_type}, entity_id={entity_id}). "
            f"Total clients: {len(self.clients)}"
        )

        # Запускаем heartbeat и cleanup tasks если ещё не запущены
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def remove_client(self, client_id: str) -> None:
        """
        Удаляет клиента и закрывает его очередь.

        Args:
            client_id: ID клиента для удаления
        """
        if client_id in self.clients:
            client = self.clients[client_id]

            # Отправляем сигнал завершения (None) в очередь
            try:
                await client.queue.put(None)
            except Exception as e:
                logger.error(f"Error closing queue for {client_id}: {e}")

            del self.clients[client_id]

            logger.info(
                f"SSE client removed: {client_id}. "
                f"Remaining clients: {len(self.clients)}"
            )

    async def broadcast(
        self,
        event_type: str,
        data: Any,
        endpoint_type: str,
        entity_id: Optional[int] = None
    ) -> int:
        """
        Отправляет событие всем подходящим клиентам.

        Args:
            event_type: Тип события ('new_log', 'status_update', etc.)
            data: Данные события (будут сериализованы в JSON)
            endpoint_type: Тип endpoint для фильтрации клиентов
            entity_id: ID сущности для дополнительной фильтрации

        Returns:
            Количество клиентов, которым отправлено событие
        """
        event = {
            'type': event_type,
            'data': data,
            'id': data.get('id') if isinstance(data, dict) else None
        }

        # Фильтруем клиентов по endpoint_type и entity_id
        target_clients = [
            client for client in self.clients.values()
            if client.endpoint_type == endpoint_type and (
                entity_id is None or
                client.entity_id is None or
                client.entity_id == entity_id
            )
        ]

        if not target_clients:
            logger.debug(
                f"No clients for broadcast: type={endpoint_type}, "
                f"entity_id={entity_id}"
            )
            return 0

        # Отправляем событие в очереди всех подходящих клиентов
        sent_count = 0
        for client in target_clients:
            try:
                # Проверяем что очередь не переполнена
                if client.queue.qsize() < 100:
                    await client.queue.put(event)
                    sent_count += 1
                else:
                    logger.warning(
                        f"Queue full for client {client.client_id}, "
                        f"dropping event"
                    )
            except Exception as e:
                logger.error(
                    f"Error broadcasting to {client.client_id}: {e}"
                )

        logger.debug(
            f"Broadcast event '{event_type}' to {sent_count} clients "
            f"(type={endpoint_type}, entity_id={entity_id})"
        )

        return sent_count

    async def _heartbeat_loop(self) -> None:
        """
        Отправляет heartbeat события всем клиентам каждые 15 секунд.
        Необходимо для поддержания соединения и обнаружения отключений.
        """
        while True:
            try:
                await asyncio.sleep(15)

                if not self.clients:
                    continue

                heartbeat_event = {
                    'type': 'heartbeat',
                    'data': {'timestamp': datetime.now().isoformat()},
                    'id': None
                }

                for client in list(self.clients.values()):
                    try:
                        if client.queue.qsize() < 100:
                            await client.queue.put(heartbeat_event)
                            client.last_heartbeat = datetime.now()
                    except Exception as e:
                        logger.error(
                            f"Error sending heartbeat to {client.client_id}: {e}"
                        )

                logger.debug(f"Heartbeat sent to {len(self.clients)} clients")

            except asyncio.CancelledError:
                logger.info("Heartbeat loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")

    async def _cleanup_loop(self) -> None:
        """
        Удаляет неактивных клиентов каждые 60 секунд.
        Клиент считается неактивным если не получал heartbeat > 90 секунд.
        """
        while True:
            try:
                await asyncio.sleep(60)

                now = datetime.now()
                inactive_clients = []

                for client_id, client in self.clients.items():
                    seconds_since_heartbeat = (now - client.last_heartbeat).seconds
                    if seconds_since_heartbeat > 90:
                        inactive_clients.append(client_id)

                for client_id in inactive_clients:
                    logger.warning(
                        f"Removing inactive client: {client_id}"
                    )
                    await self.remove_client(client_id)

                if inactive_clients:
                    logger.info(
                        f"Cleanup: removed {len(inactive_clients)} "
                        f"inactive clients"
                    )

            except asyncio.CancelledError:
                logger.info("Cleanup loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Возвращает статистику по подключённым клиентам.

        Returns:
            Словарь со статистикой
        """
        stats = {
            'total_clients': len(self.clients),
            'by_endpoint_type': {},
            'by_entity': {}
        }

        for client in self.clients.values():
            # По типу endpoint
            endpoint_type = client.endpoint_type
            if endpoint_type not in stats['by_endpoint_type']:
                stats['by_endpoint_type'][endpoint_type] = 0
            stats['by_endpoint_type'][endpoint_type] += 1

            # По entity_id
            if client.entity_id is not None:
                key = f"{endpoint_type}:{client.entity_id}"
                if key not in stats['by_entity']:
                    stats['by_entity'][key] = 0
                stats['by_entity'][key] += 1

        return stats

    async def shutdown(self) -> None:
        """Закрывает все подключения и останавливает background tasks."""
        logger.info("Shutting down SSEManager...")

        # Останавливаем background tasks
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Закрываем все клиентские подключения
        client_ids = list(self.clients.keys())
        for client_id in client_ids:
            await self.remove_client(client_id)

        logger.info("SSEManager shut down complete")


# Singleton instance
sse_manager = SSEManager()
