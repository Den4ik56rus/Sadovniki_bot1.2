"""
YooKassa API клиент для работы с платежами.

Основные методы:
    - create_payment — создание платежа
    - get_payment — получение информации о платеже
    - capture_payment — подтверждение платежа
    - cancel_payment — отмена платежа
"""

import base64
import uuid
import logging
from typing import Dict, Any, Optional, List
from decimal import Decimal

import aiohttp

from src.config import settings

logger = logging.getLogger(__name__)


class YooKassaClient:
    """Клиент для работы с YooKassa API."""

    def __init__(self):
        self.shop_id = settings.YOOKASSA_SHOP_ID
        self.secret_key = settings.YOOKASSA_SECRET_KEY
        self.api_url = "https://api.yookassa.ru/v3"
        self.test_mode = settings.YOOKASSA_TEST_MODE

    def _get_auth_header(self) -> str:
        """Генерирует заголовок авторизации Basic Auth."""
        credentials = f"{self.shop_id}:{self.secret_key}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def _get_headers(self, idempotence_key: Optional[str] = None) -> Dict[str, str]:
        """
        Генерирует заголовки для запроса.

        Args:
            idempotence_key: Ключ идемпотентности (генерируется автоматически если не указан)

        Returns:
            Словарь заголовков
        """
        headers = {
            "Authorization": self._get_auth_header(),
            "Content-Type": "application/json",
        }

        if idempotence_key:
            headers["Idempotence-Key"] = idempotence_key
        else:
            headers["Idempotence-Key"] = str(uuid.uuid4())

        return headers

    async def create_payment(
        self,
        amount_rub: Decimal,
        description: str,
        return_url: str,
        user_telegram_id: int,
        user_email: Optional[str] = None,
        receipt_items: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        idempotence_key: Optional[str] = None,
        save_payment_method: bool = False,
        payment_method_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Создает платеж в YooKassa.

        Args:
            amount_rub: Сумма в рублях
            description: Описание платежа
            return_url: URL для возврата после оплаты
            user_telegram_id: Telegram ID пользователя
            user_email: Email пользователя (для чека)
            receipt_items: Элементы чека (для 54-ФЗ)
            metadata: Дополнительные данные
            idempotence_key: Ключ идемпотентности

        Returns:
            Объект платежа от YooKassa

        Raises:
            aiohttp.ClientError: При ошибке HTTP запроса
        """
        if not idempotence_key:
            idempotence_key = str(uuid.uuid4())

        payload = {
            "amount": {
                "value": str(amount_rub),
                "currency": "RUB"
            },
            "capture": True,  # Автоматическое списание
            "confirmation": {
                "type": "redirect",
                "return_url": return_url
            },
            "description": description,
            "metadata": metadata or {"telegram_user_id": str(user_telegram_id)}
        }

        # Для рекуррентных платежей
        if save_payment_method:
            payload["save_payment_method"] = True

        # Использовать сохраненный способ оплаты
        if payment_method_id:
            payload["payment_method_id"] = payment_method_id

        # Добавить чек если нужно
        if settings.YOOKASSA_SEND_RECEIPT and receipt_items:
            # Если email не указан, используем заглушку
            customer_email = user_email or f"user_{user_telegram_id}@sadovniki.bot"

            payload["receipt"] = {
                "customer": {
                    "email": customer_email
                },
                "items": receipt_items
            }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/payments",
                    headers=self._get_headers(idempotence_key),
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.info(
                            f"Payment created: {data['id']}, "
                            f"status={data['status']}, amount={amount_rub}"
                        )
                        return data
                    else:
                        error_data = await resp.text()
                        logger.error(
                            f"YooKassa API error: status={resp.status}, "
                            f"response={error_data}"
                        )
                        raise aiohttp.ClientError(
                            f"YooKassa returned {resp.status}: {error_data}"
                        )

        except aiohttp.ClientError as e:
            logger.error(f"Failed to create payment: {e}")
            raise

    async def get_payment(self, payment_id: str) -> Dict[str, Any]:
        """
        Получает информацию о платеже.

        Args:
            payment_id: ID платежа в YooKassa

        Returns:
            Объект платежа

        Raises:
            aiohttp.ClientError: При ошибке HTTP запроса
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_url}/payments/{payment_id}",
                    headers=self._get_headers(),
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.debug(f"Payment retrieved: {payment_id}, status={data['status']}")
                        return data
                    else:
                        error_data = await resp.text()
                        logger.error(
                            f"Failed to get payment {payment_id}: "
                            f"status={resp.status}, response={error_data}"
                        )
                        raise aiohttp.ClientError(
                            f"YooKassa returned {resp.status}: {error_data}"
                        )

        except aiohttp.ClientError as e:
            logger.error(f"Failed to get payment {payment_id}: {e}")
            raise

    async def capture_payment(
        self,
        payment_id: str,
        amount_rub: Optional[Decimal] = None,
        idempotence_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Подтверждает платеж (для двухстадийных платежей).

        Args:
            payment_id: ID платежа в YooKassa
            amount_rub: Сумма для подтверждения (может быть меньше исходной)
            idempotence_key: Ключ идемпотентности

        Returns:
            Объект платежа

        Raises:
            aiohttp.ClientError: При ошибке HTTP запроса
        """
        payload = {}
        if amount_rub:
            payload["amount"] = {
                "value": str(amount_rub),
                "currency": "RUB"
            }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/payments/{payment_id}/capture",
                    headers=self._get_headers(idempotence_key),
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.info(f"Payment captured: {payment_id}")
                        return data
                    else:
                        error_data = await resp.text()
                        logger.error(
                            f"Failed to capture payment {payment_id}: "
                            f"status={resp.status}, response={error_data}"
                        )
                        raise aiohttp.ClientError(
                            f"YooKassa returned {resp.status}: {error_data}"
                        )

        except aiohttp.ClientError as e:
            logger.error(f"Failed to capture payment {payment_id}: {e}")
            raise

    async def cancel_payment(
        self,
        payment_id: str,
        idempotence_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Отменяет платеж.

        Args:
            payment_id: ID платежа в YooKassa
            idempotence_key: Ключ идемпотентности

        Returns:
            Объект платежа

        Raises:
            aiohttp.ClientError: При ошибке HTTP запроса
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/payments/{payment_id}/cancel",
                    headers=self._get_headers(idempotence_key),
                    json={},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.info(f"Payment canceled: {payment_id}")
                        return data
                    else:
                        error_data = await resp.text()
                        logger.error(
                            f"Failed to cancel payment {payment_id}: "
                            f"status={resp.status}, response={error_data}"
                        )
                        raise aiohttp.ClientError(
                            f"YooKassa returned {resp.status}: {error_data}"
                        )

        except aiohttp.ClientError as e:
            logger.error(f"Failed to cancel payment {payment_id}: {e}")
            raise

    def create_receipt_items(
        self,
        description: str,
        amount_rub: Decimal,
        quantity: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Создает элементы чека для 54-ФЗ.

        Args:
            description: Описание товара/услуги
            amount_rub: Цена
            quantity: Количество

        Returns:
            Список элементов чека
        """
        return [
            {
                "description": description,
                "quantity": str(quantity),
                "amount": {
                    "value": str(amount_rub),
                    "currency": "RUB"
                },
                "vat_code": 1,  # НДС не облагается
                "payment_mode": "full_prepayment",  # Полная предоплата
                "payment_subject": "service"  # Услуга
            }
        ]


# Глобальный экземпляр клиента
yookassa_client = YooKassaClient()
