# Admin Panel — Панель мониторинга консультаций

## Обзор

Admin Panel — веб-приложение для мониторинга консультаций бота в реальном времени. Построено на React + TypeScript + Zustand, использует SSE (Server-Sent Events) для мгновенного обновления данных.

## Архитектура

### Frontend (admin-webapp/)
- **React 18** + TypeScript + Vite
- **Zustand** для state management
- **SSE** для real-time обновлений
- **Playwright MCP** для автоматизированного тестирования UI

### Backend (src/api/)
- **aiohttp** HTTP сервер (порт 8080)
- **SSE Manager** для управления подключениями
- **REST API** для получения данных
- **SSE endpoints** для real-time обновлений

## Real-Time Updates (SSE)

### Принцип работы

Server-Sent Events обеспечивает одностороннюю передачу данных от сервера к клиенту:
- Клиент устанавливает HTTP connection
- Сервер держит connection открытым
- Сервер отправляет события при изменении данных
- Автоматический reconnect при разрыве соединения

### Backend SSE Implementation

#### SSE Manager (`src/api/sse_manager.py`)
```python
class SSEManager:
    clients: Dict[str, SSEClient] = {}  # client_id -> SSEClient

    async def add_client(client_id, response, endpoint_type, entity_id)
    async def remove_client(client_id)
    async def broadcast(event_type, data, endpoint_type, entity_id=None)
    async def start_heartbeat()  # Sends ping every 15 sec
    async def cleanup_inactive_clients()  # Removes stale connections
```

**Особенности:**
- Heartbeat каждые 15 секунд для поддержания соединения
- Cleanup неактивных клиентов (timeout 120 сек)
- Queue для событий каждого клиента
- Поддержка reconnect с восстановлением пропущенных событий

#### SSE Endpoints (`src/api/handlers/sse.py`)

**1. Live Feed Stream** — `/api/admin/events/live-feed`
```python
async def live_feed_stream(request: web.Request):
    # Подключение клиента к live-feed
    # Отправка пропущенных событий при reconnect (last_event_id)
    # Broadcast новых консультаций
```

**2. Topic Logs Stream** — `/api/admin/events/logs/{topic_id}`
```python
async def topic_logs_stream(request: web.Request):
    # Подключение к конкретному топику
    # Real-time обновления логов и сообщений
```

**3. Document Status Stream** — `/api/admin/events/documents/{document_id}`
```python
async def document_status_stream(request: web.Request):
    # Отслеживание обработки документа
    # Статусы: pending → processing → completed/failed
```

#### Database Integration

**Broadcast при сохранении** (`src/services/db/consultation_logs_repo.py`):
```python
async def log_consultation(...) -> int:
    # 1. INSERT в базу данных
    log_id = await pool.fetchval(...)

    # 2. Broadcast SSE event
    await sse_manager.broadcast(
        event_type='new_log',
        data=log_data,
        endpoint_type='live-feed'
    )

    return log_id
```

**Reconnect Recovery** (`get_logs_since_id()`):
```python
async def get_logs_since_id(last_id: int, limit: int = 50):
    # Получить все логи начиная с last_id
    # Используется при SSE reconnect
```

### Frontend SSE Implementation

#### SSE Hook (`admin-webapp/src/hooks/useSSE.ts`)
```typescript
export function useSSE({
  endpoint,           // SSE endpoint URL
  onMessage,          // Callback для событий
  enabled = true,     // Вкл/выкл подключение
  lastEventId,        // ID для reconnect
  reconnectInterval,  // Интервал переподключения
  maxReconnectAttempts
}): UseSSEReturn
```

**Особенности:**
- Автоматический reconnect с exponential backoff
- Отслеживание состояния подключения
- Обработка ошибок
- Cleanup при unmount

**Пример использования:**
```typescript
const { isConnected, error } = useSSE({
  endpoint: api.sse.liveFeed(lastId?.toString()),
  onMessage: (event) => {
    if (event.type === 'new_log') {
      const log = JSON.parse(event.data)
      addNewLog(log)
    }
  },
  enabled: !isPaused,
})
```

#### Scroll Preservation (`admin-webapp/src/hooks/useScrollPreservation.ts`)

**Проблема:** При добавлении нового элемента в начало списка, скролл прыгает вверх.

**Решение:**
```typescript
export function useScrollPreservation({
  enabled = true,
  autoScrollThreshold = 100  // px от низа
}): UseScrollPreservationReturn
```

**Логика:**
1. Перед обновлением: сохранить, находится ли пользователь внизу списка
2. После обновления: если был внизу — прокрутить вниз, иначе сохранить позицию

#### State Management (Zustand)

**LiveFeedStore:**
```typescript
interface LiveFeedState {
  logs: RecentLog[]
  lastId: number | null
  sseConnected: boolean

  // SSE methods
  addNewLog: (log: RecentLog) => void      // Добавить новый лог
  setSseConnected: (connected: boolean) => void
}
```

**LogsStore:**
```typescript
interface LogsState {
  logs: ConsultationLog[]
  messages: Message[]
  sseConnected: boolean

  // SSE methods
  addLog: (log: ConsultationLog) => void       // Добавить лог
  addMessage: (message: Message) => void       // Добавить сообщение
  setSseConnected: (connected: boolean) => void
}
```

**DocumentsStore:**
```typescript
interface DocumentsState {
  documents: Document[]

  // SSE method
  updateDocumentStatus: (id: number, status: Partial<Document>) => void
}
```

### Vite Proxy Configuration

**Проблема:** SSE требует особой настройки proxy для streaming.

**Решение** (`admin-webapp/vite.config.ts`):
```typescript
proxy: {
  '/api': {
    target: 'http://localhost:8080',
    changeOrigin: true,
    configure: (proxy, _options) => {
      proxy.on('proxyReq', (proxyReq, req, _res) => {
        if (req.url?.includes('/events/')) {
          proxyReq.setHeader('Connection', 'keep-alive')
          proxyReq.setHeader('Cache-Control', 'no-cache')
        }
      })
    },
  },
}
```

## Разделы Admin Panel

### 1. Live Feed
**URL:** `/` (default view)

**Функции:**
- Real-time список всех консультаций
- SSE подключение: показывает статус "🟢 Подключено" / "🔴 Отключено"
- Отображение:
  - Пользователь (имя/username)
  - Культура (малина, голубика, etc.)
  - Вопрос и ответ (truncated)
  - Метрики: токены, стоимость (₽), latency
  - Временная метка
- Scroll preservation при добавлении новых консультаций

### 2. Пользователи
**URL:** `/users`

**Функции:**
- Список всех пользователей бота
- Поиск по имени/username
- Статистика по пользователю:
  - Количество консультаций
  - Общее количество токенов
  - Общая стоимость (₽)
- Выбор пользователя → список топиков
- Выбор топика → детальный просмотр консультации

**Обновление:** HTTP polling каждые 30 секунд

### 3. Consultation View
**URL:** `/users` (при выборе топика)

**Функции:**
- Timeline консультации (сообщения + LLM вызовы)
- Real-time обновления через SSE
- Для каждого LLM вызова:
  - **Классификация:** категория, культура, стоимость
  - **RAG поиск:** composed question, найденные сниппеты, стоимость
  - **LLM консультация:** токены (prompt → completion), стоимость, latency
- Collapsible секции:
  - RAG Сниппеты (Q&A vs Documents)
  - Системный промпт
- Итоговая стоимость консультации с разбивкой

### 4. Статистика
**URL:** `/stats`

**Функции:**
- Статистика использования за период (7/30/90 дней)
- Графики:
  - Консультации по дням
  - Токены по дням
  - Стоимость по дням
- Топ культур
- Топ категорий

**Обновление:** HTTP polling каждые 60 секунд

### 5. Документы
**URL:** `/documents`

**Функции:**
- Список документов базы знаний
- Загрузка новых документов
- Статусы обработки:
  - `pending` → `processing` → `completed`/`failed`
- Метрики:
  - Количество chunks
  - Стоимость обработки (embedding)
- Удаление документов

**Обновление:**
- HTTP polling каждые 10 секунд (fallback)
- SSE для processing документов (когда реализовано)

## Polling vs SSE

### Что использует SSE (real-time)
- ✅ Live Feed — новые консультации
- ✅ Consultation View — логи конкретного топика
- 🔄 Documents (processing status) — планируется

### Что использует HTTP Polling
- 📊 Users list — 30 сек (некритично)
- 📊 Stats — 60 сек (некритично)
- 📄 Documents — 10 сек (fallback для SSE)

**Почему не всё SSE:**
- Users/Stats меняются редко → polling эффективнее
- SSE для критичных real-time данных
- Баланс между производительностью и нагрузкой

## Запуск и развёртывание

### Development

**Backend:**
```bash
# Запустить базу данных
docker-compose up -d db

# Запустить бота с API
source venv/bin/activate
python -m src
```

**Frontend:**
```bash
cd admin-webapp
npm install
npm run dev  # localhost:5174
```

**Проверка:**
- Открыть http://localhost:5174
- Проверить индикатор SSE: "🟢 Подключено"
- Задать вопрос боту в Telegram
- Увидеть мгновенное появление консультации в Live Feed

### Production

**Build:**
```bash
cd admin-webapp
npm run build  # -> dist/
```

**Деплой:**
- Статические файлы (`dist/`) на CDN/web server
- Backend API на сервере (порт 8080)
- Настроить nginx reverse proxy для SSE

**nginx config:**
```nginx
location /api/admin/events/ {
    proxy_pass http://localhost:8080;
    proxy_http_version 1.1;
    proxy_set_header Connection '';
    proxy_buffering off;
    proxy_cache off;
    chunked_transfer_encoding off;
}
```

## Тестирование

### Playwright MCP Testing

**Запуск:**
```bash
# Backend + Frontend должны быть запущены
# В Claude Code используем Playwright MCP tools:
```

**Проверки:**
1. `browser_navigate` → http://localhost:5174
2. `browser_snapshot` — структура UI
3. Проверить "🟢 Подключено" в Live Feed
4. `browser_click` — переключение между разделами
5. Задать вопрос боту → проверить появление в Live Feed
6. `browser_take_screenshot` для документации

## Известные проблемы и решения

### 1. SSE не подключается через Vite proxy
**Симптом:** "🔴 Отключено", в консоли ошибки SSE

**Причины:**
- Vite proxy буферизирует SSE поток
- Нужна специальная конфигурация

**Решение:** См. раздел "Vite Proxy Configuration"

### 2. Страница прыгает вверх при обновлении
**Симптом:** При добавлении новой консультации скролл возвращается наверх

**Причина:** React перерисовывает список, браузер сбрасывает scroll

**Решение:** Используй `useScrollPreservation` hook

### 3. Дублирование событий SSE
**Симптом:** Одна консультация появляется несколько раз

**Причина:** Нет дедупликации по ID

**Решение:** В store методах проверяем наличие элемента:
```typescript
if (state.logs.some((l) => l.id === log.id)) return state
```

## Дальнейшее развитие

### Планируемые фичи
- [ ] SSE для document processing status
- [ ] Фильтры в Live Feed (по культуре, категории)
- [ ] Экспорт данных (CSV, JSON)
- [ ] Уведомления при ошибках
- [ ] Метрики производительности SSE (latency, reconnects)
- [ ] Dashboard с графиками в реальном времени

### Оптимизации
- [ ] Виртуализация длинных списков (react-window)
- [ ] Компрессия SSE данных
- [ ] Batch updates для reduce re-renders
- [ ] Service Worker для offline support

## См. также

- [docs/architecture/OVERVIEW.md](../architecture/OVERVIEW.md) — Общая архитектура
- [docs/development/SETUP.md](../development/SETUP.md) — Установка и настройка
- [admin-webapp/DESIGN_SYSTEM.md](../../admin-webapp/DESIGN_SYSTEM.md) — Дизайн система UI
