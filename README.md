# Sadovniki-bot

**Telegram-бот для профессиональных консультаций по ягодным культурам**

Система использует RAG (Retrieval-Augmented Generation) с векторным поиском, автоматическую классификацию культур и LLM для генерации экспертных ответов по выращиванию ягод (клубника, малина, смородина, голубика, жимолость, крыжовник, ежевика).

## 🚀 Быстрый старт

### Требования
- Python 3.11+
- PostgreSQL 16+ с расширением pgvector
- Docker (опционально, для PostgreSQL)
- OpenAI API key

### Установка

```bash
# 1. Клонировать репозиторий
git clone <repo-url>
cd Sadovniki_bot1.2

# 2. Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Запустить PostgreSQL (через Docker)
docker-compose up -d

# 5. Применить схемы БД
psql -h localhost -U bot_user -d garden_bot -f db/schema.sql
psql -h localhost -U bot_user -d garden_bot -f db/schema_topics.sql
psql -h localhost -U bot_user -d garden_bot -f db/schema_terminology.sql
psql -h localhost -U bot_user -d garden_bot -f db/schema_documents.sql

# 6. Настроить .env
cp .env.example .env
# Отредактировать .env (добавить токены)

# 7. Запустить бота
python -m src
```

## 🖥️ Запуск приложений

Проект состоит из трёх компонентов, которые запускаются независимо:

### Бот + API сервер
```bash
# Активировать виртуальное окружение
source venv/bin/activate

# Запустить бота и API (порт 8080)
python -m src
```

### Календарь (Telegram Mini App)
```bash
cd webapp
npm install    # первый запуск
npm run dev    # запуск dev сервера на порту 5173
```
Открыть в браузере: http://localhost:5173

### Admin панель (мониторинг консультаций)
```bash
cd admin-webapp
npm install    # первый запуск
npm run dev    # запуск dev сервера на порту 5174
```
Открыть в браузере: http://localhost:5174

### Все компоненты одновременно (3 терминала)
```bash
# Терминал 1: Бот + API
python -m src

# Терминал 2: Календарь webapp
cd webapp && npm run dev

# Терминал 3: Admin webapp
cd admin-webapp && npm run dev
```

### Запуск через ngrok (доступ из интернета)

Для доступа к админ-панели из интернета (например, с телефона или другого устройства):

1. **Установить ngrok:**
   ```bash
   brew install ngrok  # macOS
   # или скачать с https://ngrok.com/download
   ```

2. **Авторизоваться в ngrok:**
   ```bash
   ngrok config add-authtoken YOUR_TOKEN
   # Получить токен: https://dashboard.ngrok.com/get-started/your-authtoken
   ```

3. **Запустить все сервисы (3 терминала):**
   ```bash
   # Терминал 1: Backend API
   python -m src

   # Терминал 2: Admin webapp
   cd admin-webapp && npm run dev

   # Терминал 3: ngrok туннель для webapp
   ngrok http 5174
   ```

4. **Использовать ngrok URL:**
   - Скопировать URL вида `https://xxxx.ngrok-free.app`
   - Открыть его в браузере на любом устройстве

**Важно:** API запросы проксируются через Vite (localhost:5174 → localhost:8080),
поэтому нужен туннель только для webapp. Backend должен работать локально.

### Переменные окружения (.env)

```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
OPENAI_API_KEY=your_openai_key_here
OPENAI_MODEL=gpt-4.1-mini
OPENAI_EMBEDDINGS_MODEL=text-embedding-3-small

DB_HOST=localhost
DB_PORT=5432
DB_NAME=garden_bot
DB_USER=bot_user
DB_PASSWORD=secure_password

ADMIN_IDS=123456789,987654321  # Telegram user IDs админов
```

## ✨ Основные возможности

### Для пользователей

1. **Консультации по 6 категориям**
   - Питание растений (подкормки, удобрения)
   - Посадка и уход (сроки, технология)
   - Защита растений (болезни, вредители)
   - Улучшение почвы (pH, структура)
   - Подбор сорта/места
   - Другие вопросы по ягодным культурам

2. **Автоматическая классификация культур**
   - 12 типов ягодных культур
   - Определение из текста вопроса
   - Уточнение типа (летняя/ремонтантная для клубники и малины)

3. **Контекстные ответы с RAG**
   - Трёхуровневый поиск: Q&A → специфичные документы → общие документы
   - Учёт истории диалога
   - Персонализация по региону и типу выращивания

### Для администраторов

4. **Модерация базы знаний**
   - Очередь Q&A пар из консультаций
   - Редактирование ответов с помощью LLM
   - Управление категориями
   - Одобрение/отклонение кандидатов

5. **Управление терминологией**
   - Словарь предпочитаемых формулировок
   - Автоматическая инъекция в промпты LLM

6. **Статистика и аналитика**
   - Количество пользователей
   - Очередь модерации
   - Логи всех консультаций

## 📚 Документация

### Архитектура
- [**OVERVIEW.md**](docs/architecture/OVERVIEW.md) — Обзор архитектуры системы
- [**DATABASE.md**](docs/architecture/DATABASE.md) — База данных, пул подключений, векторный поиск
- [**LLM_INTEGRATION.md**](docs/architecture/LLM_INTEGRATION.md) — Интеграция с OpenAI API
- [**RAG_SYSTEM.md**](docs/architecture/RAG_SYSTEM.md) — RAG-система с трёхуровневым поиском

### Функциональность
- [**CONSULTATION_FLOW.md**](docs/features/CONSULTATION_FLOW.md) — Multi-turn консультации, state machine
- [**CLASSIFICATION.md**](docs/features/CLASSIFICATION.md) — Классификация культур (12 типов)
- [**DOCUMENT_PIPELINE.md**](docs/features/DOCUMENT_PIPELINE.md) — Обработка PDF-документов
- [**MODERATION.md**](docs/features/MODERATION.md) — Модерация базы знаний
- [**TERMINOLOGY.md**](docs/features/TERMINOLOGY.md) — Управление терминологией
- [**TOPIC_MANAGEMENT.md**](docs/features/TOPIC_MANAGEMENT.md) — Управление сессиями (топиками)
- [**PROMPTS.md**](docs/features/PROMPTS.md) — Система промптов

### Разработка
- [**SETUP.md**](docs/development/SETUP.md) — Полная инструкция по установке
- [**TESTING.md**](docs/development/TESTING.md) — Тестирование функциональности
- [**CHANGELOG.md**](docs/development/CHANGELOG.md) — История изменений

## 🏗️ Технологический стек

**Backend:**
- Python 3.11+
- Aiogram 3.x (асинхронный фреймворк для Telegram Bot API)
- asyncpg (асинхронный PostgreSQL драйвер)
- pydantic-settings (управление конфигурацией)

**AI/ML:**
- OpenAI API (GPT-4.1-mini для генерации ответов)
- text-embedding-3-small (генерация векторов, 1536 измерений)

**База данных:**
- PostgreSQL 16 с расширением pgvector
- HNSW индексы для векторного поиска
- 8 таблиц (users, topics, messages, knowledge_base, documents, document_chunks, moderation_queue, terminology)

**Infrastructure:**
- Docker / Docker Compose
- Environment Variables (.env)

## 📁 Структура проекта

```
Sadovniki_bot1.2/
├── src/
│   ├── handlers/           # Обработчики событий Telegram
│   │   ├── consultation/   # Консультационные сценарии
│   │   └── admin/          # Административная панель
│   ├── services/
│   │   ├── llm/            # LLM-сервисы (OpenAI, embeddings, classification)
│   │   ├── rag/            # RAG-система (поиск в базе знаний)
│   │   ├── db/             # Репозитории (доступ к БД)
│   │   └── documents/      # Обработка PDF
│   ├── keyboards/          # Клавиатуры Telegram (UI)
│   ├── prompts/            # Системные промпты для LLM
│   ├── models/             # Pydantic модели
│   ├── utils/              # Утилиты
│   ├── config.py           # Конфигурация
│   ├── bot.py              # Фабрика бота
│   └── main.py             # Точка входа
├── docs/                   # Документация
│   ├── architecture/       # Архитектура
│   ├── features/           # Функциональность
│   └── development/        # Разработка
├── db/                     # SQL схемы
├── data/documents/         # PDF документы для RAG
├── scripts/                # Утилиты (импорт документов)
├── requirements.txt        # Python зависимости
├── docker-compose.yml      # PostgreSQL + pgvector
├── CLAUDE.md               # Инструкции для Claude Code
└── README.md               # Этот файл
```

## 🧪 Тестирование

```bash
# Запустить все тесты
python test_culture_classification.py
python test_culture_classification_advanced.py

# Проверить компиляцию всех Python файлов
python -m py_compile src/**/*.py
```

Подробнее: [docs/development/TESTING.md](docs/development/TESTING.md)

## 🤝 Вклад в проект

Проект находится в активной разработке. Перед внесением изменений:

1. Прочитайте [CLAUDE.md](CLAUDE.md) для понимания правил работы с кодом
2. Изучите [docs/architecture/OVERVIEW.md](docs/architecture/OVERVIEW.md) для понимания архитектуры
3. Следуйте существующим паттернам кода (handlers → services → repositories)

## 📄 Лицензия

Проект разработан для образовательных и коммерческих целей.

## 📞 Контакты

Для вопросов и предложений: создавайте Issues в репозитории проекта.

---

**Версия:** 1.2.3
**Последнее обновление:** 2025-12-15
