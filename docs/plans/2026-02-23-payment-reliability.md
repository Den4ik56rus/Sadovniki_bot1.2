# Payment Reliability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Устранить потерю вебхуков YooKassa и зависания админки через async-очередь, периодическую сверку платежей, алерты и оптимизацию activity feed.

**Architecture:**
- Вебхук отвечает 200 мгновенно, обработку ставит в `asyncio.Queue` — consumer coroutine разгребает в фоне.
- Фоновая задача каждые 5 минут проверяет `pending` платежи старше 2 минут через YooKassa API и обрабатывает успешные.
- SSE-триггер в RightPanel дебаунсится по 2 сек и проверяет относится ли событие к текущему клиенту — лишние запросы не отправляются.

**Tech Stack:** Python asyncio, aiohttp, asyncpg, Aiogram 3.x, React/TypeScript

---

## Task 1: Функция get_stale_pending_payments в payment_repo

Нужен запрос к БД который возвращает `pending` платежи старше N минут (не expired — у них `expires_at` в прошлом, просто необработанные).

**Files:**
- Modify: `src/services/db/payment_repo.py` (добавить функцию после `get_expired_pending` на строке ~228)

**Step 1: Добавить функцию в payment_repo.py**

Открой `src/services/db/payment_repo.py`, найди функцию `get_expired_pending` (~строка 216), добавь ПОСЛЕ неё:

```python
async def get_stale_pending_payments(min_age_minutes: int = 2) -> List[Dict[str, Any]]:
    """
    Возвращает pending платежи старше N минут для периодической сверки с YooKassa.
    Исключает уже успешные и отменённые платежи.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM payments
            WHERE status = 'pending'
            AND paid = false
            AND created_at < NOW() - ($1 || ' minutes')::interval
            ORDER BY created_at ASC
            LIMIT 50
            """,
            str(min_age_minutes),
        )
        return [dict(row) for row in rows]
```

**Step 2: Проверить вручную на сервере (после деплоя)**

```bash
# Убедиться что запрос работает — выполнить в боте через docker exec
docker exec sadovniki_bot12-db-1 psql -U bot_user -d garden_bot \
  -c "SELECT id, status, created_at FROM payments WHERE status='pending' AND paid=false AND created_at < NOW() - '2 minutes'::interval LIMIT 5;"
```

Ожидание: либо пустой результат (все платежи обработаны), либо список старых pending.

**Step 3: Commit**

```bash
git add src/services/db/payment_repo.py
git commit -m "feat: add get_stale_pending_payments for reconciliation"
```

---

## Task 2: asyncio.Queue для вебхука YooKassa

Вместо синхронной обработки внутри handler — кладём задачу в очередь и сразу возвращаем 200.

**Files:**
- Modify: `src/api/handlers/webhooks.py` (полностью переписать)
- Modify: `src/main.py` (создать queue + запустить consumer)

**Step 1: Переписать webhooks.py**

Замени весь файл `src/api/handlers/webhooks.py`:

```python
"""
Webhook handlers для приема уведомлений от платежных систем.

Архитектура надёжности:
    - Вебхук немедленно отвечает 200 OK (< 10ms)
    - Обработка ставится в asyncio.Queue
    - Consumer coroutine разгребает очередь в фоне
    - Если queue недоступна — fallback на синхронную обработку
"""

import asyncio
import logging
from typing import Dict, Any, Optional

from aiohttp import web

logger = logging.getLogger(__name__)

# Глобальная очередь задач обработки вебхуков.
# Инициализируется в main.py через set_webhook_queue().
_webhook_queue: Optional[asyncio.Queue] = None


def set_webhook_queue(queue: asyncio.Queue) -> None:
    """Устанавливает глобальную очередь вебхуков (вызывается из main.py при старте)."""
    global _webhook_queue
    _webhook_queue = queue


def get_webhook_queue() -> Optional[asyncio.Queue]:
    return _webhook_queue


async def yookassa_webhook(request: web.Request) -> web.Response:
    """
    Обработка webhook от YooKassa.

    Немедленно возвращает 200 OK, обработку ставит в очередь.
    YooKassa ждёт ответ не более ~5 сек — мы отвечаем за <10ms.
    """
    try:
        payload = await request.json()
        event_type = payload.get("event")
        payment_object = payload.get("object")

        if not payment_object:
            logger.warning("Webhook received without payment object")
            return web.Response(status=400, text="Invalid payload")

        yookassa_payment_id = payment_object.get("id")
        status = payment_object.get("status")
        paid = payment_object.get("paid", False)

        logger.info(
            f"Webhook received: event={event_type}, "
            f"payment_id={yookassa_payment_id}, status={status}, paid={paid}"
        )

        # Ставим обработку в очередь — отвечаем немедленно
        queue = get_webhook_queue()
        if queue is not None:
            await queue.put({
                "event_type": event_type,
                "payment_object": payment_object,
                "yookassa_payment_id": yookassa_payment_id,
                "status": status,
                "paid": paid,
            })
            logger.info(f"Webhook queued: {yookassa_payment_id}, queue size: {queue.qsize()}")
        else:
            # Fallback: синхронная обработка если очередь не инициализирована
            logger.warning("Webhook queue not initialized, processing synchronously")
            await _process_webhook_payload(event_type, payment_object, yookassa_payment_id, status, paid)

        return web.Response(status=200, text="OK")

    except Exception as e:
        logger.error(f"Webhook processing error: {e}", exc_info=True)
        # Всегда 200 чтобы YooKassa не повторяла
        return web.Response(status=200, text="OK")


async def _process_webhook_payload(
    event_type: str,
    payment_object: Dict[str, Any],
    yookassa_payment_id: str,
    status: str,
    paid: bool,
) -> None:
    """Обработка payload вебхука (используется consumer и fallback)."""
    from src.services.payments import payment_service

    if event_type == "payment.succeeded" and paid and status == "succeeded":
        try:
            success = await payment_service.process_payment_success(
                yookassa_payment_id=yookassa_payment_id,
                yookassa_payment_object=payment_object,
            )
            if success:
                logger.info(f"Payment {yookassa_payment_id} processed successfully")
            else:
                logger.warning(f"Payment {yookassa_payment_id} could not be processed")
        except Exception as e:
            logger.error(
                f"Error processing payment success for {yookassa_payment_id}: {e}",
                exc_info=True,
            )

    elif event_type == "payment.canceled":
        try:
            await payment_service.process_payment_canceled(
                yookassa_payment_id=yookassa_payment_id,
                yookassa_payment_object=payment_object,
            )
            logger.info(f"Payment {yookassa_payment_id} canceled")
        except Exception as e:
            logger.error(
                f"Error processing payment cancellation for {yookassa_payment_id}: {e}",
                exc_info=True,
            )

    elif event_type == "payment.waiting_for_capture":
        logger.info(f"Payment {yookassa_payment_id} waiting for capture")

    else:
        logger.info(
            f"Unhandled webhook event: {event_type}, "
            f"payment_id={yookassa_payment_id}, status={status}"
        )


async def webhook_consumer(queue: asyncio.Queue) -> None:
    """
    Consumer coroutine для обработки вебхуков из очереди.
    Запускается как asyncio.create_task() в main.py.
    Работает вечно, обрабатывает по одному вебхуку за раз.
    """
    logger.info("Webhook consumer started")
    while True:
        try:
            item = await queue.get()
            try:
                await _process_webhook_payload(
                    event_type=item["event_type"],
                    payment_object=item["payment_object"],
                    yookassa_payment_id=item["yookassa_payment_id"],
                    status=item["status"],
                    paid=item["paid"],
                )
            except Exception as e:
                logger.error(f"Webhook consumer error for {item.get('yookassa_payment_id')}: {e}", exc_info=True)
            finally:
                queue.task_done()
        except asyncio.CancelledError:
            logger.info("Webhook consumer cancelled")
            break
        except Exception as e:
            logger.error(f"Unexpected error in webhook consumer: {e}", exc_info=True)
            await asyncio.sleep(1)


async def yookassa_webhook_test(request: web.Request) -> web.Response:
    """
    Тестовый endpoint для локальной проверки webhook логики.

    Использование:
        curl -X POST http://localhost:8080/api/webhooks/yookassa/test \\
          -H "Content-Type: application/json" \\
          -d '{
            "event": "payment.succeeded",
            "object": {
              "id": "test_payment_id",
              "status": "succeeded",
              "paid": true,
              "amount": {"value": "200.00", "currency": "RUB"},
              "metadata": {"telegram_user_id": "123456789"}
            }
          }'
    """
    try:
        payload = await request.json()
        logger.info(f"TEST webhook received: {payload}")
        response = await yookassa_webhook(request)
        return web.Response(
            status=200,
            text=f"Test webhook processed, response: {response.status}",
        )
    except Exception as e:
        logger.error(f"Test webhook error: {e}", exc_info=True)
        return web.Response(status=500, text=f"Error: {e}")
```

**Step 2: Обновить main.py — создать очередь и запустить consumer**

В `src/main.py` найди строку `from src.api import create_api_app` (~строка 22), добавь импорт:

```python
from src.api.handlers.webhooks import set_webhook_queue, webhook_consumer
```

Найди блок где запускаются фоновые задачи (~строка 112-122), добавь ПЕРЕД ними:

```python
    # Создаём очередь вебхуков и регистрируем её в handler
    webhook_queue = asyncio.Queue(maxsize=100)
    set_webhook_queue(webhook_queue)
    webhook_consumer_task = asyncio.create_task(webhook_consumer(webhook_queue))
    print("Webhook consumer запущен.")
```

Найди блок отмены задач при завершении (~строка 135-150), добавь отмену consumer:

```python
        webhook_consumer_task.cancel()
```

**Step 3: Проверить локально что импорты не сломаны**

```bash
cd /Users/denis/Desktop/Main/Sadovniki-bot/Sadovniki_bot1.2
python -c "from src.api.handlers.webhooks import yookassa_webhook, webhook_consumer, set_webhook_queue; print('OK')"
```

Ожидание: `OK`

**Step 4: Commit**

```bash
git add src/api/handlers/webhooks.py src/main.py
git commit -m "feat: webhook queue — answer 200 immediately, process async"
```

---

## Task 3: Periodic payment reconciliation

Фоновая задача каждые 5 минут сверяет `pending` платежи с YooKassa API.

**Files:**
- Create: `src/services/payments/payment_reconciliation.py`
- Modify: `src/main.py` (добавить запуск задачи)

**Step 1: Создать файл reconciliation**

```python
# src/services/payments/payment_reconciliation.py
"""
Периодическая сверка статусов платежей с YooKassa API.

Назначение: страховка от потерянных вебхуков.
Каждые 5 минут проверяет pending платежи старше 2 минут.
Если платёж succeeded в YooKassa — обрабатывает его.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)

# Интервал проверки (секунды)
RECONCILIATION_INTERVAL = 300  # 5 минут
# Минимальный возраст pending платежа для проверки
MIN_PAYMENT_AGE_MINUTES = 2


async def reconcile_pending_payments() -> int:
    """
    Проверяет все stale pending платежи через YooKassa API.
    Обрабатывает успешные, обновляет отменённые.

    Returns:
        Количество обработанных платежей.
    """
    from src.services.db import payment_repo
    from src.services.payments.yookassa_client import yookassa_client
    from src.services.payments import payment_service

    processed = 0

    try:
        stale_payments = await payment_repo.get_stale_pending_payments(MIN_PAYMENT_AGE_MINUTES)

        if not stale_payments:
            return 0

        logger.info(f"[reconciliation] Найдено {len(stale_payments)} stale pending платежей")

        for payment in stale_payments:
            yookassa_id = payment["yookassa_payment_id"]
            try:
                # Запросить актуальный статус у YooKassa
                yk_payment = await yookassa_client.get_payment(yookassa_id)
                yk_status = yk_payment.get("status")
                yk_paid = yk_payment.get("paid", False)

                if yk_status == "succeeded" and yk_paid:
                    logger.info(f"[reconciliation] Платёж {yookassa_id} succeeded — обрабатываем")
                    await payment_service.process_payment_success(
                        yookassa_payment_id=yookassa_id,
                        yookassa_payment_object=yk_payment,
                    )
                    processed += 1
                    # Алерт о восстановленном платеже
                    await _send_recovery_alert(payment, yk_payment)

                elif yk_status == "canceled":
                    logger.info(f"[reconciliation] Платёж {yookassa_id} canceled — обновляем")
                    await payment_service.process_payment_canceled(
                        yookassa_payment_id=yookassa_id,
                        yookassa_payment_object=yk_payment,
                    )
                    processed += 1

                else:
                    logger.debug(f"[reconciliation] Платёж {yookassa_id} всё ещё {yk_status} — пропускаем")

            except Exception as e:
                logger.error(f"[reconciliation] Ошибка проверки платежа {yookassa_id}: {e}", exc_info=True)
                # Не прерываем цикл — продолжаем следующий платёж
                continue

    except Exception as e:
        logger.error(f"[reconciliation] Ошибка получения stale платежей: {e}", exc_info=True)

    return processed


async def _send_recovery_alert(payment: dict, yk_payment: dict) -> None:
    """Алерт администратору о восстановленном платеже."""
    try:
        from src.bot import get_bot
        from src.config import settings
        from src.services.db.pool import get_pool

        bot = get_bot()
        if not settings.admin_ids:
            return

        admin_ids = [int(x.strip()) for x in settings.admin_ids.split(",") if x.strip()]
        if not admin_ids:
            return

        pool = get_pool()
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT telegram_user_id, username FROM users WHERE id = $1",
                payment["user_id"],
            )

        username = f"@{user['username']}" if user and user.get("username") else f"id={payment['user_id']}"
        amount = payment.get("amount_rub", "?")
        yookassa_id = payment["yookassa_payment_id"]

        text = (
            "⚠️ <b>Восстановлен потерянный платёж</b>\n\n"
            f"Пользователь: {username}\n"
            f"Сумма: {amount}₽\n"
            f"YooKassa ID: <code>{yookassa_id}</code>\n\n"
            "Платёж был в статусе pending, восстановлен через periodic reconciliation.\n"
            "Вебхук был потерян."
        )

        for admin_id in admin_ids[:1]:  # Отправляем первому администратору
            await bot.send_message(chat_id=admin_id, text=text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"[reconciliation] Ошибка отправки алерта: {e}", exc_info=True)


async def payment_reconciliation_loop() -> None:
    """
    Бесконечный цикл сверки платежей.
    Запускается как asyncio.create_task() в main.py.
    """
    logger.info("Payment reconciliation loop started")
    # Первая проверка через 1 минуту после старта (бот ещё инициализируется)
    await asyncio.sleep(60)

    while True:
        try:
            processed = await reconcile_pending_payments()
            if processed > 0:
                logger.info(f"[reconciliation] Обработано платежей: {processed}")
        except Exception as e:
            logger.error(f"[reconciliation] Ошибка в цикле: {e}", exc_info=True)

        await asyncio.sleep(RECONCILIATION_INTERVAL)
```

**Step 2: Добавить задачу в main.py**

В `src/main.py` добавить импорт рядом с другими импортами:

```python
from src.services.payments.payment_reconciliation import payment_reconciliation_loop
```

В блоке запуска фоновых задач добавить после `broadcast_task`:

```python
    reconciliation_task = asyncio.create_task(payment_reconciliation_loop())
    print("Фоновая задача сверки платежей запущена.")
```

В блоке отмены при завершении добавить:

```python
        reconciliation_task.cancel()
```

**Step 3: Проверить импорты**

```bash
cd /Users/denis/Desktop/Main/Sadovniki-bot/Sadovniki_bot1.2
python -c "from src.services.payments.payment_reconciliation import payment_reconciliation_loop, reconcile_pending_payments; print('OK')"
```

Ожидание: `OK`

**Step 4: Commit**

```bash
git add src/services/payments/payment_reconciliation.py src/main.py
git commit -m "feat: periodic payment reconciliation every 5 min"
```

---

## Task 4: Алерт при ошибке обработки вебхука

Если webhook consumer поймал ошибку при обработке успешного платежа — отправить алерт администратору.

**Files:**
- Modify: `src/api/handlers/webhooks.py` (добавить `_send_payment_error_alert`)

**Step 1: Добавить функцию алерта и вызов в consumer**

В `src/api/handlers/webhooks.py` добавить функцию после `webhook_consumer`:

```python
async def _send_payment_error_alert(yookassa_payment_id: str, error: str) -> None:
    """Алерт администратору при ошибке обработки платежа."""
    try:
        from src.bot import get_bot
        from src.config import settings

        bot = get_bot()
        if not settings.admin_ids:
            return

        admin_ids = [int(x.strip()) for x in settings.admin_ids.split(",") if x.strip()]
        if not admin_ids:
            return

        text = (
            "🚨 <b>Ошибка обработки платежа</b>\n\n"
            f"YooKassa ID: <code>{yookassa_payment_id}</code>\n"
            f"Ошибка: {error[:300]}\n\n"
            "Платёж будет восстановлен через periodic reconciliation (до 5 минут)."
        )

        for admin_id in admin_ids[:1]:
            await bot.send_message(chat_id=admin_id, text=text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Failed to send payment error alert: {e}")
```

Обновить блок `try/except` в `_process_webhook_payload` для `payment.succeeded`:

```python
    if event_type == "payment.succeeded" and paid and status == "succeeded":
        try:
            success = await payment_service.process_payment_success(
                yookassa_payment_id=yookassa_payment_id,
                yookassa_payment_object=payment_object,
            )
            if success:
                logger.info(f"Payment {yookassa_payment_id} processed successfully")
            else:
                logger.warning(f"Payment {yookassa_payment_id} could not be processed")
                await _send_payment_error_alert(yookassa_payment_id, "process_payment_success returned False")
        except Exception as e:
            logger.error(
                f"Error processing payment success for {yookassa_payment_id}: {e}",
                exc_info=True,
            )
            await _send_payment_error_alert(yookassa_payment_id, str(e))
```

**Step 2: Commit**

```bash
git add src/api/handlers/webhooks.py
git commit -m "feat: alert admin on payment processing failure"
```

---

## Task 5: Оптимизация activity feed — убрать лишние запросы

Проблема: каждое SSE-событие триггерит полный перезапрос `/activity?limit=500` (58КБ).
Решение: проверять тип SSE-события, рефетчить только если событие относится к текущему клиенту.

**Files:**
- Modify: `admin-webapp/src/components/crm/RightPanel/index.tsx` (строки 101-116)

**Step 1: Найти текущий SSE debounce и обновить логику**

Найди в `admin-webapp/src/components/crm/RightPanel/index.tsx` блок (строки ~101-116):

```typescript
  // SSE: debounced activity refetch when sseRefreshKey changes
  useEffect(() => {
    if (sseRefreshKey && sseRefreshKey > 0) {
      if (debounceRef.current) clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(() => {
        silentRefetchActivity()
      }, 500)
    }
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [sseRefreshKey, silentRefetchActivity])
```

Замени на:

```typescript
  // SSE: debounced activity refetch when sseRefreshKey changes
  // Увеличен debounce до 2 сек — SSE может прийти несколько событий подряд
  useEffect(() => {
    if (sseRefreshKey && sseRefreshKey > 0) {
      if (debounceRef.current) clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(() => {
        silentRefetchActivity()
      }, 2000)
    }
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [sseRefreshKey, silentRefetchActivity])
```

**Step 2: Снизить лимит activity с 500 до 200**

В том же файле найди оба места где `limit: 500` (строки ~74 и ~91), замени на `limit: 200`:

```typescript
      const data = await api.getClientActivity(clientId, {
        types: activeFilters.length === ALL_EVENT_TYPES.length ? undefined : activeFilters,
        limit: 200,  // было 500
      })
```

Оба вызова — в `fetchActivity` и `silentRefetchActivity`.

**Step 3: Проверить что UI работает корректно (через Playwright)**

```
browser_navigate → http://localhost:5174/funnel/crm
Открыть карточку клиента → проверить что activity feed загружается
```

**Step 4: Commit**

```bash
git add admin-webapp/src/components/crm/RightPanel/index.tsx
git commit -m "fix: increase activity SSE debounce to 2s, reduce limit 500→200"
```

---

## Task 6: Деплой на сервер и проверка

**Step 1: Пуш на GitHub**

```bash
git push origin main
```

**Step 2: Деплой бота на сервере**

```bash
ssh -i ~/.ssh/id_rsa_server root@72.56.121.98 \
  "cd /root/Sadovniki_bot1.2 && git pull && docker compose up -d --build bot"
```

**Step 3: Проверить логи запуска**

```bash
ssh -i ~/.ssh/id_rsa_server root@72.56.121.98 \
  "docker logs sadovniki_bot12-bot-1 --tail=20"
```

Ожидание в логах:
```
Webhook consumer запущен.
Фоновая задача сверки платежей запущена.
```

**Step 4: Тест webhook через curl — убедиться что отвечает быстро**

```bash
ssh -i ~/.ssh/id_rsa_server root@72.56.121.98 \
  "curl -s -X POST https://proagro56.ru/api/webhooks/yookassa \
   -H 'Content-Type: application/json' \
   -d '{\"event\":\"payment.waiting_for_capture\",\"object\":{\"id\":\"test-123\",\"status\":\"waiting_for_capture\",\"paid\":false}}' \
   -w '\nTime: %{time_total}s\nHTTP: %{http_code}\n'"
```

Ожидание: `HTTP: 200`, `Time: 0.0Xs` (меньше 100ms)

**Step 5: Проверить что reconciliation запустилась**

```bash
ssh -i ~/.ssh/id_rsa_server root@72.56.121.98 \
  "docker logs sadovniki_bot12-bot-1 --tail=50 | grep reconciliation"
```

Ожидание через 1 минуту после старта: `Payment reconciliation loop started`

**Step 6: Деплой nginx (для обновлённого frontend)**

```bash
ssh -i ~/.ssh/id_rsa_server root@72.56.121.98 \
  "nohup bash -c 'cd /root/Sadovniki_bot1.2 && git pull && docker compose up -d --build nginx > /tmp/nginx_build.log 2>&1' &"
```

Проверить через 3-5 минут:
```bash
ssh -i ~/.ssh/id_rsa_server root@72.56.121.98 \
  "tail /tmp/nginx_build.log && docker ps | grep nginx"
```

**Step 7: Обновить версию приложения**

В `admin-webapp/package.json` увеличить version на 0.1:

```bash
# Проверить текущую версию
grep '"version"' admin-webapp/package.json
```

Обновить вручную, затем:

```bash
git add admin-webapp/package.json
git commit -m "chore: bump version after payment reliability"
git push origin main
```

---

## Итог: что решили

| Проблема | Решение |
|---|---|
| Вебхук 499 (YooKassa timeout) | Queue — отвечаем <10ms, обрабатываем асинхронно |
| Нет recovery при потере вебхука | Reconciliation каждые 5 мин проверяет pending |
| Нет алертов при ошибках | Алерт в Telegram при ошибке обработки и recovery |
| Activity feed нагружает event loop | Debounce 2s вместо 0.5s, лимит 200 вместо 500 |
