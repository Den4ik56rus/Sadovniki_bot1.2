# Установка и настройка проекта

## Краткое описание

Полное руководство по установке Sadovniki-bot: от установки зависимостей до первого запуска. Включает настройку PostgreSQL с pgvector через Docker, конфигурацию OpenAI API и применение всех SQL-схем.

## Оглавление

1. [Требования](#требования)
2. [Установка зависимостей](#установка-зависимостей)
3. [Настройка базы данных](#настройка-базы-данных)
4. [Конфигурация .env](#конфигурация-env)
5. [Первый запуск](#первый-запуск)
6. [Устранение проблем](#устранение-проблем)
7. [Связанные документы](#связанные-документы)

---

## Требования

### Системные требования

- **Python:** 3.11 или выше
- **PostgreSQL:** 16+ с расширением pgvector
- **Docker:** (опционально) для запуска PostgreSQL
- **Git:** для клонирования репозитория

### API ключи

- **Telegram Bot Token:** получить через [@BotFather](https://t.me/BotFather)
- **OpenAI API Key:** получить на [platform.openai.com](https://platform.openai.com/)

---

## Установка зависимостей

### 1. Клонирование репозитория

```bash
git clone <repo-url>
cd Sadovniki_bot1.2
```

### 2. Создание виртуального окружения

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac

# Windows:
# venv\Scripts\activate
```

### 3. Установка Python-зависимостей

```bash
pip install -r requirements.txt
```

**Основные зависимости (requirements.txt):**
```
aiogram==3.x
asyncpg
openai
pydantic-settings
PyPDF2
python-dotenv
```

---

## Настройка базы данных

### Вариант 1: Docker (рекомендуется)

```bash
# Запуск PostgreSQL + pgvector
docker-compose up -d

# Проверка статуса
docker-compose ps
```

**docker-compose.yml:**
```yaml
version: '3.8'
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: garden_bot
      POSTGRES_USER: bot_user
      POSTGRES_PASSWORD: secure_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### Вариант 2: Локальный PostgreSQL

```bash
# Установка PostgreSQL 16+
sudo apt-get install postgresql-16

# Установка pgvector
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# Создание БД
sudo -u postgres psql
CREATE DATABASE garden_bot;
CREATE USER bot_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE garden_bot TO bot_user;
\q
```

### Применение SQL-схем

```bash
# Подключение к БД
export PGPASSWORD=secure_password

# Применение схем (в правильном порядке!)
psql -h localhost -U bot_user -d garden_bot -f db/schema.sql
psql -h localhost -U bot_user -d garden_bot -f db/schema_topics.sql
psql -h localhost -U bot_user -d garden_bot -f db/schema_terminology.sql
psql -h localhost -U bot_user -d garden_bot -f db/schema_documents.sql

# Проверка таблиц
psql -h localhost -U bot_user -d garden_bot -c "\dt"
```

**Ожидаемый вывод:**
```
                    List of relations
 Schema |        Name        | Type  |  Owner   
--------+--------------------+-------+----------
 public | document_chunks    | table | bot_user
 public | documents          | table | bot_user
 public | knowledge_base     | table | bot_user
 public | messages           | table | bot_user
 public | moderation_queue   | table | bot_user
 public | terminology        | table | bot_user
 public | topics             | table | bot_user
 public | users              | table | bot_user
(8 rows)
```

---

## Конфигурация .env

### Создание файла

```bash
cp .env.example .env  # Если есть пример
# или
touch .env
```

### Заполнение переменных

**.env:**
```bash
# Telegram Bot
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# OpenAI API
OPENAI_API_KEY=sk-proj-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
OPENAI_MODEL=gpt-4.1-mini
OPENAI_EMBEDDINGS_MODEL=text-embedding-3-small

# PostgreSQL
DB_HOST=localhost
DB_PORT=5432
DB_NAME=garden_bot
DB_USER=bot_user
DB_PASSWORD=secure_password

# Администраторы (Telegram user IDs через запятую)
ADMIN_IDS=123456789,987654321
```

### Как узнать Telegram user ID

1. Отправьте сообщение боту [@userinfobot](https://t.me/userinfobot)
2. Бот вернёт ваш user ID
3. Добавьте его в `ADMIN_IDS`

---

## Первый запуск

### 1. Проверка конфигурации

```bash
# Тест подключения к БД
python -c "from src.config import settings; print(settings.db_name)"
# Ожидаемый вывод: garden_bot

# Проверка всех настроек
python -c "from src.config import settings; print(settings.model_dump())"
```

### 2. Запуск бота

```bash
python -m src.main
```

**Ожидаемый вывод:**
```
✓ Пул подключений к БД инициализирован
✓ Бот запущен и готов к работе
INFO:aiogram.dispatcher:Start polling
```

### 3. Тестирование

1. Откройте Telegram
2. Найдите вашего бота по username
3. Отправьте `/start`
4. Задайте тестовый вопрос: "Как ухаживать за клубникой?"

**Ожидаемое поведение:**
- Бот спросит: "Какая у вас клубника: летняя (июньская) или ремонтантная (НСД)?"
- После ответа выдаст консультацию

---

## Устранение проблем

### Проблема 1: Ошибка подключения к БД

```
asyncpg.exceptions.InvalidPasswordError: password authentication failed
```

**Решение:**
```bash
# Проверьте credentials в .env
cat .env | grep DB_

# Проверьте, запущен ли PostgreSQL
docker-compose ps  # для Docker
sudo systemctl status postgresql  # для локального
```

### Проблема 2: Модуль не найден

```
ModuleNotFoundError: No module named 'aiogram'
```

**Решение:**
```bash
# Проверьте активацию venv
which python  # Должно показать путь внутри venv/

# Переустановите зависимости
pip install -r requirements.txt
```

### Проблема 3: pgvector расширение не установлено

```
asyncpg.exceptions.UndefinedObjectError: type "vector" does not exist
```

**Решение:**
```bash
# Подключитесь к БД
psql -h localhost -U bot_user -d garden_bot

# Создайте расширение
CREATE EXTENSION IF NOT EXISTS vector;

# Проверьте
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### Проблема 4: OpenAI API ошибки

```
openai.error.AuthenticationError: Invalid API key
```

**Решение:**
```bash
# Проверьте ключ
echo $OPENAI_API_KEY

# Проверьте в .env
cat .env | grep OPENAI_API_KEY

# Перезапустите с явной загрузкой .env
python -m src.main
```

---

## Связанные документы

- [../architecture/DATABASE.md](../architecture/DATABASE.md) — Подробности о схемах БД
- [../architecture/LLM_INTEGRATION.md](../architecture/LLM_INTEGRATION.md) — Настройка OpenAI API
- [TESTING.md](./TESTING.md) — Тестирование функциональности

**Версия:** 1.0  
**Дата:** 2025-12-05
