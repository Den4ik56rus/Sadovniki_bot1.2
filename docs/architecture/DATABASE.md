# Архитектура базы данных

## Краткое описание

Система использует PostgreSQL 16+ с расширением **pgvector** для векторного поиска. База данных состоит из 8 таблиц, организованных в 4 функциональные группы: пользователи и сессии, база знаний, документы и терминология. Доступ к БД реализован через **паттерн Repository** с использованием **пула подключений asyncpg**.

## Оглавление

1. [Схема базы данных](#схема-базы-данных)
   - [Группа 1: Пользователи и сессии](#группа-1-пользователи-и-сессии)
   - [Группа 2: База знаний и модерация](#группа-2-база-знаний-и-модерация)
   - [Группа 3: Документы для RAG](#группа-3-документы-для-rag)
   - [Группа 4: Терминология](#группа-4-терминология)
2. [Управление пулом подключений](#управление-пулом-подключений)
3. [Паттерн репозиториев](#паттерн-репозиториев)
4. [Векторный поиск с pgvector](#векторный-поиск-с-pgvector)
5. [Связанные документы](#связанные-документы)
6. [Файлы в проекте](#файлы-в-проекте)

---

## Схема базы данных

### Архитектурная диаграмма

```
┌────────────────────────────────────────────────────────────────┐
│                    PostgreSQL 16 + pgvector                    │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌─────────────────────┐      ┌──────────────────────┐        │
│  │  Пользователи       │      │  База знаний         │        │
│  ├─────────────────────┤      ├──────────────────────┤        │
│  │ users               │      │ knowledge_base       │        │
│  │ topics              │─────▶│   └─ VECTOR(1536)    │        │
│  │ messages            │      │ moderation_queue     │        │
│  └─────────────────────┘      └──────────────────────┘        │
│                                                                │
│  ┌─────────────────────┐      ┌──────────────────────┐        │
│  │  Документы          │      │  Терминология        │        │
│  ├─────────────────────┤      ├──────────────────────┤        │
│  │ documents           │      │ terminology          │        │
│  │ document_chunks     │      └──────────────────────┘        │
│  │   └─ VECTOR(1536)   │                                      │
│  │   └─ HNSW index     │                                      │
│  └─────────────────────┘                                      │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### Группа 1: Пользователи и сессии

#### Таблица `users`

Хранит профили пользователей Telegram.

```sql
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_user_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    token_balance INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_user_id);
```

**Описание полей:**
- `id` — внутренний идентификатор (первичный ключ)
- `telegram_user_id` — Telegram ID пользователя (уникальный)
- `username` — @никнейм пользователя (может быть NULL)
- `first_name` / `last_name` — имя и фамилия из Telegram
- `token_balance` — баланс токенов пользователя (по умолчанию 0)
- `created_at` / `updated_at` — временные метки

**Операции:**
- Создание/поиск: `get_or_create_user()` в [users_repo.py](../../src/services/db/users_repo.py)
- Подсчёт: `count_all_users()` для статистики админ-панели
- Работа с токенами: см. [tokens_repo.py](../../src/services/db/tokens_repo.py)

---

#### Таблица `topics`

Хранит сессии диалогов (топики) пользователей.

```sql
CREATE TABLE IF NOT EXISTS topics (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    status TEXT DEFAULT 'open',
    culture TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_topics_user_status ON topics(user_id, status);
```

**Описание полей:**
- `id` — идентификатор топика
- `user_id` — ссылка на `users.id`
- `session_id` — идентификатор сессии (строится из метаданных сообщения)
- `status` — статус топика: `'open'` (активный) или `'closed'` (завершён)
- `culture` — выбранная культура (клубника, малина и т.п.)
- `created_at` / `updated_at` — временные метки

**Операции:**
- Создание/поиск открытого топика: `get_or_create_open_topic()` в [topics_repo.py](../../src/services/db/topics_repo.py)
- Закрытие топика: `close_topic()`
- Обновление культуры: `update_topic_culture()`

**См. также:** [TOPIC_MANAGEMENT.md](../features/TOPIC_MANAGEMENT.md) — подробная документация по управлению топиками

---

#### Таблица `messages`

Хранит все сообщения пользователей и бота для истории диалога.

```sql
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    direction TEXT NOT NULL,
    text TEXT NOT NULL,
    session_id TEXT NOT NULL,
    topic_id INTEGER REFERENCES topics(id),
    meta JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_topic ON messages(topic_id);
```

**Описание полей:**
- `id` — идентификатор сообщения
- `user_id` — автор сообщения (пользователь или бот)
- `direction` — направление: `'incoming'` (от пользователя) или `'outgoing'` (от бота)
- `text` — текст сообщения
- `session_id` — идентификатор сессии
- `topic_id` — ссылка на топик (может быть NULL)
- `meta` — JSON-метаданные (дополнительная информация)
- `created_at` — время отправки

**Операции:**
- Логирование сообщения: `log_message()` в [messages_repo.py](../../src/services/db/messages_repo.py)
- Получение истории: `get_topic_messages()` для контекста LLM

---

#### Таблица `token_transactions`

Хранит историю операций с токенами пользователей.

```sql
CREATE TABLE IF NOT EXISTS token_transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,
    operation_type TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_token_transactions_user_id ON token_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_token_transactions_created_at ON token_transactions(created_at);
```

**Описание полей:**
- `id` — идентификатор транзакции
- `user_id` — ссылка на `users.id`
- `amount` — сумма операции (положительное = пополнение, отрицательное = списание)
- `operation_type` — тип операции: `'admin_credit'`, `'new_topic'`, `'buy_questions'`
- `description` — описание операции
- `created_at` — время операции

**Операции:**
- Списание токенов: `deduct_tokens()` в [tokens_repo.py](../../src/services/db/tokens_repo.py)
- Начисление токенов: `add_tokens()` (для администратора)
- Проверка баланса: `get_token_balance()`, `has_sufficient_tokens()`

**Стоимость операций (из [config.py](../../src/config.py)):**
- Новая консультация: 1 токен
- Покупка 3 доп. вопросов: 1 токен

---

### Группа 2: База знаний и модерация

#### Таблица `knowledge_base`

Хранит одобренные Q&A пары с эмбеддингами для RAG-поиска.

```sql
CREATE TABLE IF NOT EXISTS knowledge_base (
    id SERIAL PRIMARY KEY,
    category TEXT NOT NULL,
    subcategory TEXT,
    question TEXT,
    answer TEXT NOT NULL,
    source_type TEXT DEFAULT 'manual',
    embedding VECTOR(1536) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kb_category ON knowledge_base(category);
CREATE INDEX IF NOT EXISTS idx_kb_subcategory ON knowledge_base(subcategory);
CREATE INDEX IF NOT EXISTS idx_kb_embedding ON knowledge_base
    USING hnsw (embedding vector_cosine_ops);
```

**Описание полей:**
- `id` — идентификатор записи
- `category` — категория консультации: `'питание растений'`, `'посадка и уход'`, `'защита растений'` и т.п.
- `subcategory` — культура: `'клубника летняя'`, `'малина ремонтантная'`, `'голубика'` и т.п. (может быть NULL для общих вопросов)
- `question` — текст вопроса (может быть NULL)
- `answer` — текст ответа (обязательно)
- `source_type` — источник: `'manual'`, `'faq'`, `'admin_qa'`
- `embedding` — векторное представление (1536 измерений) для семантического поиска
- `is_active` — флаг активности (для мягкого удаления)
- `created_at` / `updated_at` — временные метки

**Операции:**
- Вставка записи: `kb_insert()` в [kb_repo.py](../../src/services/db/kb_repo.py)
- Векторный поиск: `kb_search()` с фильтрацией по `category` и `subcategory`

**См. также:** [RAG_SYSTEM.md](RAG_SYSTEM.md) — архитектура RAG-системы с приоритетами

---

#### Таблица `moderation_queue`

Очередь Q&A пар, ожидающих модерации администратором.

```sql
CREATE TABLE IF NOT EXISTS moderation_queue (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    topic_id INTEGER REFERENCES topics(id),
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    category_guess TEXT,
    status TEXT DEFAULT 'pending',
    admin_id INTEGER REFERENCES users(id),
    kb_id INTEGER REFERENCES knowledge_base(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_moderation_status ON moderation_queue(status);
CREATE INDEX IF NOT EXISTS idx_moderation_created ON moderation_queue(created_at);
```

**Описание полей:**
- `id` — идентификатор кандидата
- `user_id` — автор вопроса
- `topic_id` — ссылка на топик диалога
- `question` / `answer` — текст вопроса и ответа
- `category_guess` — автоматически определённая категория (LLM)
- `status` — статус: `'pending'` (ожидает), `'approved'` (одобрено), `'rejected'` (отклонено)
- `admin_id` — администратор, проверивший запись
- `kb_id` — ссылка на запись в `knowledge_base` (после одобрения)
- `created_at` / `updated_at` — временные метки

**Операции:**
- Добавление в очередь: `add_to_moderation_queue()` в [moderation_repo.py](../../src/services/db/moderation_repo.py)
- Получение очереди: `get_pending_moderation_items()`
- Одобрение/отклонение: `approve_moderation_item()`, `reject_moderation_item()`

**См. также:** [MODERATION.md](../features/MODERATION.md) — workflow модерации базы знаний

---

### Группа 3: Документы для RAG

#### Таблица `documents`

Хранит метаданные загруженных PDF-документов.

```sql
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT UNIQUE NOT NULL,
    file_size_bytes INTEGER,
    category TEXT DEFAULT 'общая_информация',
    subcategory TEXT NOT NULL,
    uploaded_at TIMESTAMP DEFAULT NOW(),
    processing_status TEXT DEFAULT 'pending',
    processing_error TEXT,
    total_chunks INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_documents_subcategory ON documents(subcategory);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(file_hash);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(processing_status);
```

**Описание полей:**
- `id` — идентификатор документа
- `filename` — имя файла
- `file_path` — путь к файлу на диске
- `file_hash` — SHA256-хеш для дедупликации (уникальный)
- `file_size_bytes` — размер файла
- `category` — оставлено для совместимости (не используется)
- `subcategory` — культура растения: `'клубника_летняя'`, `'малина_общая'` и т.п. (обязательно)
- `uploaded_at` — время загрузки
- `processing_status` — статус обработки: `'pending'`, `'processing'`, `'completed'`, `'failed'`
- `processing_error` — текст ошибки (если `status = 'failed'`)
- `total_chunks` — количество фрагментов (chunks) после обработки
- `is_active` — флаг активности
- `created_at` — время создания записи

**Операции:**
- Создание документа: `create_document()` в [documents_repo.py](../../src/services/db/documents_repo.py)
- Проверка дубликата: `get_document_by_hash()`
- Обновление статуса: `update_document_status()`

**Файловая структура документов:**

```
data/documents/
├── клубника_летняя/
│   ├── посадка.pdf
│   └── удобрения.pdf
├── малина_ремонтантная/
│   └── обрезка.pdf
└── голубика_общая/
    └── pH_почвы.pdf
```

**См. также:** [DOCUMENT_PIPELINE.md](../features/DOCUMENT_PIPELINE.md) — обработка PDF-документов

---

#### Таблица `document_chunks`

Хранит фрагменты (chunks) документов с эмбеддингами для RAG-поиска.

```sql
CREATE TABLE IF NOT EXISTS document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_size INTEGER,
    page_number INTEGER,
    embedding VECTOR(1536) NOT NULL,
    category TEXT DEFAULT 'общая_информация',
    subcategory TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_document ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_subcategory ON document_chunks(subcategory);

-- Векторный индекс HNSW для быстрого поиска по схожести
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON document_chunks
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
```

**Описание полей:**
- `id` — идентификатор фрагмента
- `document_id` — ссылка на родительский документ (каскадное удаление)
- `chunk_index` — порядковый номер фрагмента в документе
- `chunk_text` — текст фрагмента (800 символов с перекрытием 200)
- `chunk_size` — длина текста в символах
- `page_number` — номер страницы PDF (если применимо)
- `embedding` — векторное представление (1536 измерений)
- `category` — оставлено для совместимости (не используется)
- `subcategory` — культура растения (дублируется для быстрого поиска)
- `is_active` — флаг активности
- `created_at` — время создания

**HNSW индекс:**
- Алгоритм: **Hierarchical Navigable Small World** (HNSW)
- Оператор: `vector_cosine_ops` (косинусное расстояние)
- Параметры:
  - `m = 16` — количество связей в графе (баланс скорости/точности)
  - `ef_construction = 64` — размер динамического списка при построении индекса

**Операции:**
- Вставка фрагментов: `insert_document_chunks()` в [document_chunks_repo.py](../../src/services/db/document_chunks_repo.py)
- Векторный поиск: `search_document_chunks()` с фильтрацией по `subcategory`

---

### Группа 4: Терминология

#### Таблица `terminology`

Словарь терминов для замены формулировок в промптах LLM.

```sql
CREATE TABLE IF NOT EXISTS terminology (
    id SERIAL PRIMARY KEY,
    term VARCHAR(255) NOT NULL,
    preferred_phrase TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_terminology_term ON terminology(term);
```

**Описание полей:**
- `id` — идентификатор термина
- `term` — исходный термин (например, `'навоз'`)
- `preferred_phrase` — предпочитаемая формулировка (например, `'удобрения естественного происхождения'`)
- `description` — пояснение для администратора
- `created_at` — время создания

**Примеры начальных данных:**

```sql
INSERT INTO terminology (term, preferred_phrase, description) VALUES
('навоз', 'удобрения естественного происхождения', 'Вместо слова "навоз" использовать формулировку "удобрения естественного происхождения"'),
('помёт', 'органические азотные удобрения', 'Вместо "помёт" использовать "органические азотные удобрения"')
ON CONFLICT DO NOTHING;
```

**Механизм работы:**

1. Администратор добавляет пару `term` → `preferred_phrase`
2. При генерации ответа система загружает все термины из таблицы
3. Термины инжектируются в системный промпт LLM (см. [consultation_prompts.py:80-98](../../src/prompts/consultation_prompts.py))
4. LLM использует `preferred_phrase` вместо `term` в ответах

**Операции:**
- Получение всех терминов: `get_all_terms()` в [terminology_repo.py](../../src/services/db/terminology_repo.py)
- Добавление термина: `add_term()`
- Удаление термина: `delete_term()`

**См. также:** [TERMINOLOGY.md](../features/TERMINOLOGY.md) — управление терминологией

---

## Управление пулом подключений

### Архитектура пула

```
┌──────────────────────────────────────────────────────────┐
│                   main.py (application)                  │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  startup:   init_db_pool()  ────────┐                   │
│                                     │                   │
│  runtime:   get_pool()  ◀────────────────── repos       │
│                  │                  │                   │
│                  ▼                  │                   │
│          asyncpg.Pool               │                   │
│          ├─ conn1                   │                   │
│          ├─ conn2                   │                   │
│          ├─ conn3                   │                   │
│          ├─ conn4                   │                   │
│          └─ conn5                   │                   │
│                  │                  │                   │
│  shutdown:  close_db_pool()  ───────┘                   │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Жизненный цикл пула

Пул подключений управляется тремя функциями в [src/services/db/pool.py](../../src/services/db/pool.py):

#### 1. Инициализация пула — `init_db_pool()`

Вызывается **один раз** при старте бота в [src/main.py](../../src/main.py).

```python
async def init_db_pool() -> None:
    """
    Создаёт пул подключений к базе данных.
    Вызывается один раз при старте бота.
    """
    global _db_pool

    if _db_pool is not None:
        return

    _db_pool = await asyncpg.create_pool(
        host=settings.db_host,         # localhost
        port=settings.db_port,         # 5432
        database=settings.db_name,     # garden_bot
        user=settings.db_user,         # bot_user
        password=settings.db_password, # secure_password
        min_size=1,                    # Минимум 1 соединение
        max_size=5,                    # Максимум 5 соединений
    )
```

**Параметры пула:**
- `min_size=1` — минимальное количество соединений (всегда открыто)
- `max_size=5` — максимальное количество соединений (достаточно для Telegram-бота с низкой нагрузкой)

**Конфигурация в `.env`:**

```bash
DB_HOST=localhost
DB_PORT=5432
DB_NAME=garden_bot
DB_USER=bot_user
DB_PASSWORD=secure_password
```

---

#### 2. Получение пула — `get_pool()`

Вызывается **во всех репозиториях** для доступа к БД.

```python
def get_pool() -> asyncpg.Pool:
    """
    Возвращает текущий пул подключений.
    Если пул не инициализирован — выбрасывает ошибку.
    """
    if _db_pool is None:
        raise RuntimeError(
            "Пул подключений к БД не инициализирован. "
            "Сначала вызовите init_db_pool()."
        )

    return _db_pool
```

**Пример использования в репозитории:**

```python
# src/services/db/users_repo.py

from src.services/db.pool import get_pool

async def get_or_create_user(telegram_user_id: int, ...) -> int:
    pool = get_pool()  # Получаем пул

    async with pool.acquire() as conn:  # Берём соединение из пула
        row = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_user_id = $1",
            telegram_user_id,
        )

        if row is not None:
            return row["id"]

        # ... создание нового пользователя
```

**Паттерн `pool.acquire()`:**
- `async with pool.acquire() as conn` — берёт свободное соединение из пула
- После выхода из блока `with` соединение **автоматически возвращается в пул**
- Пул управляет переиспользованием соединений (connection reuse)

---

#### 3. Закрытие пула — `close_db_pool()`

Вызывается **при остановке бота** в [src/main.py](../../src/main.py).

```python
async def close_db_pool() -> None:
    """
    Корректно закрывает пул подключений к базе данных.
    Вызывается при остановке бота.
    """
    global _db_pool

    if _db_pool is None:
        return

    await _db_pool.close()  # Закрываем все соединения
    _db_pool = None         # Обнуляем ссылку
```

---

### Пример жизненного цикла в main.py

```python
# src/main.py

import asyncio
from src.services.db.pool import init_db_pool, close_db_pool
from src.bot import create_bot_and_dispatcher

async def main():
    # 1. Инициализация пула при старте
    await init_db_pool()
    print("✓ Пул подключений к БД инициализирован")

    # 2. Создание бота и диспетчера
    bot, dp = create_bot_and_dispatcher()

    try:
        # 3. Запуск polling (бот работает, репозитории используют get_pool())
        await dp.start_polling(bot)

    finally:
        # 4. Закрытие пула при остановке
        await close_db_pool()
        print("✓ Пул подключений к БД закрыт")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Паттерн репозиториев

### Архитектура слоя доступа к данным

```
┌─────────────────────────────────────────────────────────┐
│              Handlers (src/handlers/)                   │
│  ┌───────────────────────────────────────────────────┐  │
│  │  consultation/entry.py                            │  │
│  │  admin/moderation.py                              │  │
│  └───────────────┬───────────────────────────────────┘  │
└──────────────────┼──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│           Repositories (src/services/db/)               │
│  ┌────────────────────┐  ┌────────────────────────┐    │
│  │ users_repo.py      │  │ kb_repo.py             │    │
│  │ topics_repo.py     │  │ document_chunks_repo.py│    │
│  │ messages_repo.py   │  │ moderation_repo.py     │    │
│  │ documents_repo.py  │  │ terminology_repo.py    │    │
│  └────────────────────┘  └────────────────────────┘    │
│               │                      │                  │
│               ▼                      ▼                  │
│           get_pool() ────────────▶ asyncpg.Pool         │
└─────────────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│              PostgreSQL Database                        │
└─────────────────────────────────────────────────────────┘
```

### Принципы организации репозиториев

**1. Один репозиторий = одна таблица**

Каждый репозиторий отвечает за операции с одной таблицей:

| Репозиторий | Таблица | Ответственность |
|-------------|---------|-----------------|
| [users_repo.py](../../src/services/db/users_repo.py) | `users` | Создание/поиск пользователей |
| [tokens_repo.py](../../src/services/db/tokens_repo.py) | `users`, `token_transactions` | Работа с токенами |
| [topics_repo.py](../../src/services/db/topics_repo.py) | `topics` | Управление сессиями диалогов |
| [messages_repo.py](../../src/services/db/messages_repo.py) | `messages` | Логирование сообщений |
| [kb_repo.py](../../src/services/db/kb_repo.py) | `knowledge_base` | Векторный поиск в базе знаний |
| [documents_repo.py](../../src/services/db/documents_repo.py) | `documents` | Метаданные PDF-документов |
| [document_chunks_repo.py](../../src/services/db/document_chunks_repo.py) | `document_chunks` | Векторный поиск в документах |
| [moderation_repo.py](../../src/services/db/moderation_repo.py) | `moderation_queue` | Очередь модерации |
| [terminology_repo.py](../../src/services/db/terminology_repo.py) | `terminology` | Словарь терминов |

**2. Чистые async-функции без классов**

Репозитории — это модули с async-функциями, не ООП-классы:

```python
# src/services/db/users_repo.py

from src.services.db.pool import get_pool

async def get_or_create_user(...) -> int:
    pool = get_pool()
    async with pool.acquire() as conn:
        # SQL-запросы
        ...

async def count_all_users() -> int:
    pool = get_pool()
    async with pool.acquire() as conn:
        # SQL-запросы
        ...
```

**Почему не классы:**
- Простота: нет необходимости в инстанцировании
- Прямой доступ: `await users_repo.get_or_create_user(...)`
- Пул подключений глобальный (`get_pool()`)

**3. Один вызов пула на функцию**

Каждая функция репозитория:
1. Получает пул через `get_pool()`
2. Берёт соединение через `pool.acquire()`
3. Выполняет SQL-запросы
4. Автоматически возвращает соединение в пул (context manager)

**Пример:**

```python
async def log_message(
    user_id: int,
    direction: str,
    text: str,
    session_id: str,
    topic_id: Optional[int] = None,
    meta: Optional[dict] = None,
) -> int:
    pool = get_pool()  # 1. Получаем пул

    async with pool.acquire() as conn:  # 2. Берём соединение
        row = await conn.fetchrow(  # 3. Выполняем запрос
            """
            INSERT INTO messages (user_id, direction, text, session_id, topic_id, meta)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id;
            """,
            user_id,
            direction,
            text,
            session_id,
            topic_id,
            meta,
        )

        return row["id"]  # 4. Соединение автоматически возвращается в пул
```

---

### Пример: полный workflow консультации

```
1. Пользователь отправляет сообщение
        │
        ▼
2. consultation/entry.py (handler)
        │
        ├──▶ users_repo.get_or_create_user()
        │        └─ SELECT/INSERT users
        │
        ├──▶ topics_repo.get_or_create_open_topic()
        │        └─ SELECT/INSERT topics
        │
        ├──▶ messages_repo.log_message()
        │        └─ INSERT messages (direction='incoming')
        │
        ├──▶ kb_repo.kb_search()
        │        └─ SELECT knowledge_base WHERE ... ORDER BY embedding <=> ...
        │
        ├──▶ LLM генерирует ответ
        │
        ├──▶ messages_repo.log_message()
        │        └─ INSERT messages (direction='outgoing')
        │
        └──▶ moderation_repo.add_to_moderation_queue()
                 └─ INSERT moderation_queue
```

---

## Векторный поиск с pgvector

### Архитектура векторного поиска

```
┌────────────────────────────────────────────────────────┐
│              Запрос пользователя                       │
│              "Когда пересаживать клубнику?"            │
└─────────────────────┬──────────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────────┐
│       OpenAI text-embedding-3-small                    │
│       query_embedding = [0.123, -0.456, ..., 0.789]    │
│                  (1536 чисел)                          │
└─────────────────────┬──────────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────────┐
│    PostgreSQL + pgvector (векторный поиск)             │
│                                                        │
│  SELECT question, answer                               │
│  FROM knowledge_base                                   │
│  WHERE category = 'посадка и уход'                     │
│    AND subcategory = 'клубника летняя'                 │
│  ORDER BY embedding <=> $query_embedding               │
│  LIMIT 3;                                              │
│                                                        │
│  ┌─────────────────────────────────────────┐           │
│  │ HNSW Index (vector_cosine_ops)          │           │
│  │ m=16, ef_construction=64                │           │
│  │ Косинусное расстояние: <=>              │           │
│  └─────────────────────────────────────────┘           │
└─────────────────────┬──────────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────────┐
│          3 наиболее релевантных ответа                 │
│          (distance < 0.6 для Q&A)                      │
└────────────────────────────────────────────────────────┘
```

### Расширение pgvector

**Установка (PostgreSQL 16+):**

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

**Тип данных `VECTOR(n)`:**

```sql
CREATE TABLE knowledge_base (
    id SERIAL PRIMARY KEY,
    embedding VECTOR(1536) NOT NULL,  -- 1536 измерений
    ...
);
```

**Размерность 1536:**
- OpenAI `text-embedding-3-small` генерирует векторы размерности 1536
- Все таблицы с эмбеддингами используют `VECTOR(1536)`:
  - `knowledge_base.embedding`
  - `document_chunks.embedding`

---

### HNSW индекс

**Hierarchical Navigable Small World (HNSW)** — алгоритм приближённого поиска ближайших соседей (ANN).

**Создание индекса:**

```sql
CREATE INDEX idx_chunks_embedding ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

**Параметры:**

| Параметр | Значение | Описание |
|----------|----------|----------|
| `m` | 16 | Количество двунаправленных связей в графе. Больше → точнее, но медленнее. |
| `ef_construction` | 64 | Размер динамического списка при построении индекса. Больше → точнее построение. |

**Оператор `vector_cosine_ops`:**
- Использует **косинусное расстояние** для сравнения векторов
- Оператор `<=>` в SQL-запросах:

```sql
SELECT * FROM knowledge_base
ORDER BY embedding <=> '[0.123,-0.456,...,0.789]'
LIMIT 3;
```

**Косинусное расстояние:**
- Формула: `distance = 1 - cos(θ)`, где `θ` — угол между векторами
- Диапазон: `[0, 2]` (0 = идентичные векторы, 2 = противоположные)
- Не зависит от длины вектора, только от направления

---

### Пример векторного поиска

**Функция `kb_search()` в [kb_repo.py](../../src/services/db/kb_repo.py):**

```python
async def kb_search(
    *,
    category: str,                 # 'питание растений'
    query_embedding: List[float],  # [0.123, -0.456, ..., 0.789]
    subcategory: Optional[str] = None,  # 'клубника летняя' или None
    limit: int = 3,
    distance_threshold: Optional[float] = 0.35,  # Порог расстояния
):
    pool = get_pool()

    # Нормализация эмбеддинга до 1536 измерений
    norm_embedding = _normalize_embedding(query_embedding)
    vector_str = "[" + ",".join(f"{x:.6f}" for x in norm_embedding) + "]"

    async with pool.acquire() as conn:
        if subcategory:
            # Поиск с фильтрацией по культуре
            query = """
                SELECT id, category, subcategory, question, answer,
                       (embedding <=> $1::vector) AS distance
                FROM knowledge_base
                WHERE category = $2
                  AND subcategory = $3
                  AND is_active = TRUE
                ORDER BY embedding <=> $1::vector
                LIMIT $4;
            """
            rows = await conn.fetch(query, vector_str, category, subcategory, limit)
        else:
            # Поиск по всем культурам внутри категории
            query = """
                SELECT id, category, subcategory, question, answer,
                       (embedding <=> $1::vector) AS distance
                FROM knowledge_base
                WHERE category = $2
                  AND is_active = TRUE
                ORDER BY embedding <=> $1::vector
                LIMIT $4;
            """
            rows = await conn.fetch(query, vector_str, category, limit)

        # Фильтрация по порогу расстояния
        if distance_threshold is not None:
            rows = [r for r in rows if r["distance"] < distance_threshold]

        return [dict(r) for r in rows]
```

**Пороги расстояния:**

| Источник | Порог | Описание |
|----------|-------|----------|
| Q&A пары (`knowledge_base`) | 0.6 | Строгий порог для Q&A |
| Документы (`document_chunks`) | 0.75 | Более мягкий порог для документов |

**См. также:** [RAG_SYSTEM.md](RAG_SYSTEM.md) — трёхуровневая система приоритетов

---

### Нормализация эмбеддингов

**Функция `_normalize_embedding()` в [kb_repo.py](../../src/services/db/kb_repo.py):**

```python
KB_VECTOR_DIM = 1536

def _normalize_embedding(embedding: List[float]) -> List[float]:
    """
    Приводит эмбеддинг к размерности KB_VECTOR_DIM:
      - если вектор длиннее — обрезаем;
      - если короче — дополняем нулями.
    """
    if embedding is None:
        return [0.0] * KB_VECTOR_DIM

    emb = list(embedding)
    n = len(emb)

    if n == KB_VECTOR_DIM:
        return emb
    elif n > KB_VECTOR_DIM:
        # Обрезаем лишнее
        return emb[:KB_VECTOR_DIM]
    else:
        # Дополняем нулями
        return emb + [0.0] * (KB_VECTOR_DIM - n)
```

**Почему нужна нормализация:**
- PostgreSQL `VECTOR(1536)` требует точно 1536 измерений
- Без нормализации возникает ошибка: `expected 1536 dimensions, not 3072`

---

### Производительность векторного поиска

**Оценка скорости:**

| Операция | Без индекса (IVFFlat/Seq Scan) | С HNSW индексом |
|----------|--------------------------------|-----------------|
| Поиск в 1000 записях | ~50-100 мс | ~5-10 мс |
| Поиск в 10000 записей | ~500-1000 мс | ~10-20 мс |
| Поиск в 100000 записей | ~5-10 сек | ~20-50 мс |

**Рекомендации:**
- HNSW индекс **обязателен** для таблиц с >1000 векторов
- Параметры `m=16, ef_construction=64` — баланс скорости и точности
- Для более точного поиска: `m=32, ef_construction=128` (в 2 раза медленнее построение индекса)

---

## Связанные документы

- [OVERVIEW.md](OVERVIEW.md) — Обзор архитектуры системы
- [LLM_INTEGRATION.md](LLM_INTEGRATION.md) — Интеграция с OpenAI API (генерация эмбеддингов)
- [RAG_SYSTEM.md](RAG_SYSTEM.md) — Трёхуровневая RAG-система с приоритетами
- [../features/TOPIC_MANAGEMENT.md](../features/TOPIC_MANAGEMENT.md) — Управление сессиями диалогов
- [../features/MODERATION.md](../features/MODERATION.md) — Модерация базы знаний
- [../features/DOCUMENT_PIPELINE.md](../features/DOCUMENT_PIPELINE.md) — Обработка PDF-документов
- [../features/TERMINOLOGY.md](../features/TERMINOLOGY.md) — Управление терминологией
- [../development/SETUP.md](../development/SETUP.md) — Установка и настройка БД

---

## Файлы в проекте

### SQL-схемы

- [db/schema.sql](../../db/schema.sql) — Основная схема (users, messages, knowledge_base, moderation_queue)
- [db/schema_topics.sql](../../db/schema_topics.sql) — Таблица topics
- [db/schema_documents.sql](../../db/schema_documents.sql) — Таблицы documents и document_chunks
- [db/schema_terminology.sql](../../db/schema_terminology.sql) — Таблица terminology
- [db/schema_05_follow_up_questions.sql](../../db/schema_05_follow_up_questions.sql) — Счётчик уточняющих вопросов
- [db/schema_06_tokens.sql](../../db/schema_06_tokens.sql) — Система токенов (token_balance, token_transactions)

### Пул подключений

- [src/services/db/pool.py](../../src/services/db/pool.py) — Управление пулом asyncpg
- [src/main.py](../../src/main.py) — Жизненный цикл пула (init/close)

### Репозитории

- [src/services/db/users_repo.py](../../src/services/db/users_repo.py) — Операции с users
- [src/services/db/tokens_repo.py](../../src/services/db/tokens_repo.py) — Операции с токенами (users.token_balance, token_transactions)
- [src/services/db/topics_repo.py](../../src/services/db/topics_repo.py) — Операции с topics
- [src/services/db/messages_repo.py](../../src/services/db/messages_repo.py) — Операции с messages
- [src/services/db/kb_repo.py](../../src/services/db/kb_repo.py) — Векторный поиск в knowledge_base
- [src/services/db/documents_repo.py](../../src/services/db/documents_repo.py) — Операции с documents
- [src/services/db/document_chunks_repo.py](../../src/services/db/document_chunks_repo.py) — Векторный поиск в document_chunks
- [src/services/db/moderation_repo.py](../../src/services/db/moderation_repo.py) — Операции с moderation_queue
- [src/services/db/terminology_repo.py](../../src/services/db/terminology_repo.py) — Операции с terminology

### Конфигурация

- [src/config.py](../../src/config.py) — Настройки подключения к БД и стоимость операций в токенах
- [docker-compose.yml](../../docker-compose.yml) — PostgreSQL + pgvector в Docker

---

**Версия документа:** 1.0
**Дата последнего обновления:** 2025-12-05
