# Архитектура системы Sadovniki-bot

## Краткое описание

Sadovniki-bot — Telegram-бот для профессиональных консультаций по ягодным культурам, построенный на современном стеке технологий с использованием RAG (Retrieval-Augmented Generation), векторного поиска и LLM.

Система реализует многоуровневую архитектуру с четким разделением ответственности: обработка событий Telegram (handlers), бизнес-логика (services), хранение данных (PostgreSQL + pgvector), интеграция с OpenAI API.

## Оглавление

1. [Схема потока запросов](#схема-потока-запросов)
2. [Организация модулей](#организация-модулей)
3. [Точки входа приложения](#точки-входа-приложения)
4. [Ключевые зависимости](#ключевые-зависимости)
5. [Принципы архитектуры](#принципы-архитектуры)
6. [Связанные документы](#связанные-документы)

---

## Схема потока запросов

```
┌─────────────────────────────────────────────────────┐
│              Telegram Bot API                       │
└───────────────────┬─────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────┐
│           Aiogram Framework (v3.x)                  │
│  ┌──────────────────────────────────────────────┐   │
│  │    Handlers Layer (Router-based)             │   │
│  │  - Menu handlers                             │   │
│  │  - Consultation handlers (by category)       │   │
│  │  - Admin handlers                            │   │
│  └────────────────┬─────────────────────────────┘   │
└───────────────────┼─────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────┐
│         Services Layer (Business Logic)             │
│  ┌──────────────────────────────────────────────┐   │
│  │  LLM Services                                │   │
│  │  - consultation_llm (оркестратор)            │   │
│  │  - classification_llm (определение культуры) │   │
│  │  - embeddings_llm (генерация векторов)       │   │
│  │  - core_llm (OpenAI клиент)                  │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │  RAG Services                                │   │
│  │  - unified_retriever (поиск по 3 уровням)    │   │
│  │  - kb_retriever (поиск Q&A)                  │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │  Document Services                           │   │
│  │  - processor (обработка PDF)                 │   │
│  │  - chunker (разбиение текста)                │   │
│  └──────────────────────────────────────────────┘   │
└───────────────────┬─────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────┐
│         Data Layer (Repositories)                   │
│  - users_repo                                       │
│  - topics_repo                                      │
│  - messages_repo                                    │
│  - kb_repo (knowledge_base)                         │
│  - document_chunks_repo                             │
│  - moderation_repo                                  │
│  - terminology_repo                                 │
└───────────────────┬─────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────┐
│      PostgreSQL + pgvector                          │
│  - Реляционные данные                               │
│  - Векторные индексы (HNSW)                         │
│  - 1536-мерные embeddings                           │
└─────────────────────────────────────────────────────┘
```

**Поток обработки запроса пользователя:**

1. **Telegram Bot API** → Пользователь отправляет сообщение
2. **Aiogram Handler** → Обрабатывает событие, извлекает данные
3. **Services Layer** → Выполняет бизнес-логику:
   - Классификация культуры (classification_llm)
   - Поиск в базе знаний (unified_retriever)
   - Генерация ответа (consultation_llm)
4. **Data Layer** → Работа с БД (сохранение сообщений, топиков, поиск по векторам)
5. **PostgreSQL** → Хранение данных + векторный поиск
6. **Aiogram Handler** → Отправляет ответ пользователю

---

## Организация модулей

### src/handlers/
**Назначение:** Обработка событий Telegram (команды, сообщения, callback queries)

**Принцип:** Только Aiogram-логика, без бизнес-логики

**Структура:**
```
src/handlers/
├── __init__.py           # Регистрация всех роутеров
├── menu.py               # Главное меню, /start, переключение режимов
├── common.py             # Общие состояния (CONSULTATION_STATE, CONSULTATION_CONTEXT)
├── consultation/         # Консультационные сценарии
│   ├── router.py         # Фабрика роутеров
│   ├── entry.py          # Универсальный обработчик текста
│   ├── pitanie_rastenii.py   # Питание растений (продвинутый сценарий)
│   ├── posadka_uhod.py       # Посадка и уход
│   ├── zashita_rastenii.py   # Защита растений
│   ├── uluchshenie_pochvi.py # Улучшение почвы
│   └── podbor_sorta.py       # Подбор сорта
└── admin/                # Административная панель
    ├── moderation.py     # Модерация базы знаний
    └── terminology.py    # Управление терминологией
```

### src/services/
**Назначение:** Бизнес-логика, работа с БД, LLM-вызовы

**Принцип:** Все сложные операции и алгоритмы

**Структура:**
```
src/services/
├── llm/                  # LLM-сервисы
│   ├── core_llm.py       # Низкоуровневый OpenAI клиент
│   ├── embeddings_llm.py # Генерация векторов
│   ├── classification_llm.py # Классификация культур
│   └── consultation_llm.py   # Оркестратор консультаций
├── rag/                  # RAG-система
│   ├── kb_retriever.py   # Поиск Q&A пар
│   └── unified_retriever.py # Унифицированный поиск (Q&A + документы)
├── db/                   # Репозитории (доступ к БД)
│   ├── pool.py           # Управление пулом подключений
│   ├── users_repo.py     # CRUD пользователей
│   ├── topics_repo.py    # Управление топиками (сессиями)
│   ├── messages_repo.py  # Логирование сообщений
│   ├── kb_repo.py        # База знаний (Q&A с векторами)
│   ├── document_chunks_repo.py # Фрагменты документов
│   ├── moderation_repo.py     # Очередь модерации
│   └── terminology_repo.py    # Словарь терминов
└── documents/            # Обработка документов
    ├── processor.py      # Обработка PDF (извлечение текста, эмбеддинг)
    └── chunker.py        # Разбиение текста на фрагменты
```

### src/keyboards/
**Назначение:** Клавиатуры Telegram (Reply и Inline)

**Принцип:** Только UI-компоненты, без логики

**Структура:**
```
src/keyboards/
├── main/                 # Главное меню
├── consultation/         # Консультационные клавиатуры
└── admin/                # Административные клавиатуры
```

### src/models/
**Назначение:** Pydantic-модели для валидации данных

**Структура:**
```
src/models/
├── base_models.py        # Базовые модели
├── consultation_models.py # Модели консультаций
├── kb_models.py          # Модели базы знаний
└── user_models.py        # Модели пользователей
```

### src/prompts/
**Назначение:** Системные промпты для LLM

**Структура:**
```
src/prompts/
├── base_prompt.py        # Базовый промпт (роль, scope, формат)
├── consultation_prompts.py # Оркестратор (сборка финального промпта)
└── category_prompts/     # Категорийные промпты
    ├── nutrition.py      # Питание растений
    ├── planting_care.py  # Посадка и уход
    ├── diseases_pests.py # Защита растений
    ├── soil_improvement.py # Улучшение почвы
    └── variety_selection.py # Подбор сорта
```

### src/utils/
**Назначение:** Вспомогательные функции

**Структура:**
```
src/utils/
├── logging_utils.py      # Конфигурация логирования
├── text_utils.py         # Обработка текста
└── json_utils.py         # Работа с JSON
```

---

## Точки входа приложения

### 1. src/main.py
**Главная точка входа приложения**

```python
async def main():
    # 1. Инициализация пула подключений к БД
    await init_db_pool()

    # 2. Создание бота и диспетчера
    bot, dp = create_bot_and_dispatcher()

    # 3. Запуск polling
    await dp.start_polling(bot)

    # 4. Закрытие пула при завершении
    await close_db_pool()
```

**Ответственность:**
- Инициализация и завершение работы приложения
- Управление lifecycle БД-пула
- Запуск polling Telegram Bot API

### 2. src/bot.py
**Фабрика бота и диспетчера**

```python
def create_bot_and_dispatcher():
    bot = Bot(token=settings.telegram_bot_token, parse_mode="HTML")
    dp = Dispatcher()

    # Регистрация роутеров
    setup_routers(dp)

    return bot, dp
```

**Ответственность:**
- Создание экземпляров Bot и Dispatcher
- Регистрация всех роутеров
- Конфигурация middlewares

### 3. src/handlers/__init__.py
**Регистрация роутеров**

```python
def setup_routers(dp: Dispatcher):
    dp.include_router(menu_router)
    dp.include_router(consultation_router)
    dp.include_router(admin_router)
```

**Ответственность:**
- Подключение всех handler-роутеров к диспетчеру
- Определение порядка обработки

---

## Ключевые зависимости

### Backend
- **Python 3.11+** — язык программирования
- **Aiogram 3.x** — асинхронный фреймворк для Telegram Bot API
- **asyncpg** — асинхронный драйвер PostgreSQL
- **pydantic / pydantic-settings** — валидация данных и управление конфигурацией

### AI/ML
- **OpenAI API** (GPT-4.1-mini) — генерация ответов
- **text-embedding-3-small** — генерация векторных представлений (1536 измерений)

### База данных
- **PostgreSQL 16** с расширением **pgvector**
- **HNSW индексы** для быстрого векторного поиска (m=16, ef_construction=64)

### Infrastructure
- **Docker / Docker Compose** — контейнеризация PostgreSQL
- **Environment Variables** (.env) — управление конфигурацией

---

## Принципы архитектуры

### 1. Слоистая архитектура (Layered Architecture)

```
[Presentation Layer]   → Handlers (Aiogram события)
[Business Logic Layer] → Services (бизнес-логика, LLM, RAG)
[Data Access Layer]    → Repositories (работа с БД)
[Database Layer]       → PostgreSQL + pgvector
```

**Преимущества:**
- Четкое разделение ответственности
- Легко тестировать каждый слой независимо
- Простота замены реализации на каждом уровне

### 2. Repository Pattern

Все операции с БД изолированы в репозиториях:
- `users_repo.py` — работа с пользователями
- `topics_repo.py` — управление топиками
- `kb_repo.py` — база знаний с векторным поиском

**Преимущества:**
- Единая точка доступа к данным
- Легко тестировать с mock-репозиториями
- Простота миграции на другую БД

### 3. Service Layer Pattern

Вся бизнес-логика вынесена в services:
- LLM-сервисы (`llm/`)
- RAG-сервисы (`rag/`)
- Обработка документов (`documents/`)

**Преимущества:**
- Handlers остаются простыми и читаемыми
- Легко переиспользовать логику
- Простота unit-тестирования

### 4. Модульность промптов

Система промптов разделена на:
- **Базовый промпт** (роль, scope, формат) — единый для всех
- **Категорийные промпты** (специфика по типам консультаций) — 6 модулей
- **Оркестратор** (сборка финального промпта с RAG-контекстом и терминологией)

**Преимущества:**
- Легко A/B тестировать промпты
- Простота добавления новых категорий
- Нет дублирования базовых правил

### 5. Асинхронность (Async/Await)

Все операции с БД и LLM — асинхронные:
- `asyncpg` для PostgreSQL
- `AsyncOpenAI` для OpenAI API
- Aiogram 3.x (полностью асинхронный)

**Преимущества:**
- Высокая пропускная способность (multiple users concurrently)
- Эффективное использование ресурсов
- Неблокирующие операции

---

## Связанные документы

### Архитектура
- [DATABASE.md](DATABASE.md) — Архитектура базы данных, пул подключений, репозитории, pgvector
- [LLM_INTEGRATION.md](LLM_INTEGRATION.md) — Интеграция с OpenAI, embeddings, consultation orchestration
- [RAG_SYSTEM.md](RAG_SYSTEM.md) — RAG-система с трехуровневым приоритетным поиском

### Функциональность
- [../features/CONSULTATION_FLOW.md](../features/CONSULTATION_FLOW.md) — Multi-turn консультации, state machine
- [../features/CLASSIFICATION.md](../features/CLASSIFICATION.md) — Классификация культур (12 типов)
- [../features/MODERATION.md](../features/MODERATION.md) — Административная модерация базы знаний
- [../features/TERMINOLOGY.md](../features/TERMINOLOGY.md) — Управление терминологией
- [../features/TOPIC_MANAGEMENT.md](../features/TOPIC_MANAGEMENT.md) — Управление сессиями (топиками)
- [../features/PROMPTS.md](../features/PROMPTS.md) — Система промптов
- [../features/DOCUMENT_PIPELINE.md](../features/DOCUMENT_PIPELINE.md) — Обработка PDF-документов

### Разработка
- [../development/SETUP.md](../development/SETUP.md) — Установка и настройка окружения
- [../development/TESTING.md](../development/TESTING.md) — Тестирование функциональности

---

## Файлы в проекте

**Точки входа:**
- [src/main.py](../../src/main.py) — Главная точка входа
- [src/bot.py](../../src/bot.py) — Фабрика бота и диспетчера
- [src/config.py](../../src/config.py) — Конфигурация (Settings)

**Handlers:**
- [src/handlers/__init__.py](../../src/handlers/__init__.py) — Регистрация роутеров
- [src/handlers/menu.py](../../src/handlers/menu.py) — Главное меню
- [src/handlers/consultation/](../../src/handlers/consultation/) — Консультационные сценарии
- [src/handlers/admin/](../../src/handlers/admin/) — Административная панель

**Services:**
- [src/services/llm/](../../src/services/llm/) — LLM-сервисы
- [src/services/rag/](../../src/services/rag/) — RAG-система
- [src/services/db/](../../src/services/db/) — Репозитории
- [src/services/documents/](../../src/services/documents/) — Обработка документов

**Конфигурация:**
- [requirements.txt](../../requirements.txt) — Python-зависимости
- [docker-compose.yml](../../docker-compose.yml) — PostgreSQL + pgvector
- [.env](../../.env) — Переменные окружения (не в git)
