# Этап 0: Подготовка скелета

**Статус:** :x: Not Started
**Приоритет:** Критический (блокирует все последующие этапы)

---

## Цель этапа

Зафиксировать единые правила данных и событий, чтобы аналитика, триггеры и рефералка работали стабильно.

**Выход этапа:** Можно "проигрывать" путь клиента и видеть события в админке.

---

## Требования

### Функциональные

1. **Единый словарь статусов**
   - TopicStatus, SupportStage, SubscriptionStatus, ModerationStatus
   - Определены в [DATA_MODELS.md](../DATA_MODELS.md)
   - Добавлены как PostgreSQL ENUM или справочные таблицы

2. **EventLog как отдельный поток**
   - Таблица `event_log` для всех бизнес-событий
   - Типы: start, topic_created, topic_closed, payment_success, subscription_*, referral_* и др.
   - JSONB payload для гибких данных
   - Индексы для быстрого поиска

3. **Нормализованный справочник культур**
   - Таблица `cultures` с нормализованными названиями
   - Маппинг синонимов → нормализованный ID
   - Особое внимание: НСД/летняя клубника, ремонтантная малина

4. **Тест-контур**
   - Тестовый бот (отдельный токен)
   - Тестовые пользователи с флагом `is_test`
   - Песочница оплат (если будет интеграция)

### Нефункциональные

- Минимальное влияние на текущую production-систему
- Backward compatibility с существующими данными
- Возможность миграции существующих данных

---

## Изменения БД

### Новый файл: `db/schema_15_crm_foundation.sql`

```sql
-- =============================================================================
-- CRM Foundation: Статусы, EventLog, Справочники
-- =============================================================================

-- 1. ENUM типы для статусов
CREATE TYPE topic_status AS ENUM ('open', 'closed', 'archived');
CREATE TYPE support_stage AS ENUM ('new', 'in_progress', 'waiting_client', 'resolved', 'closed');
CREATE TYPE subscription_status AS ENUM ('none', 'trial', 'active', 'expired', 'cancelled', 'suspended');
CREATE TYPE payment_status AS ENUM ('pending', 'processing', 'success', 'failed', 'refunded', 'cancelled');
CREATE TYPE task_status AS ENUM ('new', 'in_progress', 'done', 'cancelled');
CREATE TYPE priority_level AS ENUM ('low', 'medium', 'high', 'critical');

-- 2. Таблица событий (EventLog)
CREATE TABLE event_log (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    entity_type VARCHAR(30),  -- topic, payment, subscription, support_case, referral
    entity_id INTEGER,
    payload JSONB DEFAULT '{}',
    idempotency_key VARCHAR(100),  -- для дедупликации
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы для EventLog
CREATE INDEX idx_event_log_type ON event_log(event_type);
CREATE INDEX idx_event_log_user ON event_log(user_id);
CREATE INDEX idx_event_log_entity ON event_log(entity_type, entity_id);
CREATE INDEX idx_event_log_created ON event_log(created_at DESC);
CREATE UNIQUE INDEX idx_event_log_idempotency ON event_log(idempotency_key) WHERE idempotency_key IS NOT NULL;

-- 3. Справочник культур
CREATE TABLE cultures (
    id SERIAL PRIMARY KEY,
    code VARCHAR(30) UNIQUE NOT NULL,  -- strawberry_summer, raspberry_remontant
    name_ru VARCHAR(100) NOT NULL,     -- Клубника летняя
    culture_group VARCHAR(30) NOT NULL, -- strawberry, raspberry, b_berries
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Маппинг синонимов
CREATE TABLE culture_synonyms (
    id SERIAL PRIMARY KEY,
    synonym VARCHAR(100) NOT NULL,
    culture_id INTEGER REFERENCES cultures(id) ON DELETE CASCADE,
    UNIQUE(synonym)
);

CREATE INDEX idx_culture_synonyms_synonym ON culture_synonyms(LOWER(synonym));

-- 4. Первоначальные данные культур
INSERT INTO cultures (code, name_ru, culture_group) VALUES
    ('strawberry_summer', 'Клубника летняя', 'strawberry'),
    ('strawberry_remontant', 'Клубника ремонтантная (НСД)', 'strawberry'),
    ('raspberry_summer', 'Малина летняя', 'raspberry'),
    ('raspberry_remontant', 'Малина ремонтантная', 'raspberry'),
    ('blackberry', 'Ежевика', 'raspberry'),
    ('currant_black', 'Смородина чёрная', 'b_berries'),
    ('currant_red', 'Смородина красная', 'b_berries'),
    ('blueberry', 'Голубика', 'b_berries'),
    ('honeysuckle', 'Жимолость', 'b_berries'),
    ('gooseberry', 'Крыжовник', 'b_berries'),
    ('irga', 'Ирга', 'b_berries'),
    ('aronia', 'Арония (черноплодная рябина)', 'b_berries');

-- Синонимы
INSERT INTO culture_synonyms (synonym, culture_id) VALUES
    ('клубника', (SELECT id FROM cultures WHERE code = 'strawberry_summer')),
    ('земляника', (SELECT id FROM cultures WHERE code = 'strawberry_summer')),
    ('земляника садовая', (SELECT id FROM cultures WHERE code = 'strawberry_summer')),
    ('нсд', (SELECT id FROM cultures WHERE code = 'strawberry_remontant')),
    ('ремонтантная клубника', (SELECT id FROM cultures WHERE code = 'strawberry_remontant')),
    ('клубника нсд', (SELECT id FROM cultures WHERE code = 'strawberry_remontant')),
    ('малина', (SELECT id FROM cultures WHERE code = 'raspberry_summer')),
    ('ремонтантная малина', (SELECT id FROM cultures WHERE code = 'raspberry_remontant')),
    ('малина ремонтантная', (SELECT id FROM cultures WHERE code = 'raspberry_remontant')),
    ('ежевика', (SELECT id FROM cultures WHERE code = 'blackberry')),
    ('смородина', (SELECT id FROM cultures WHERE code = 'currant_black')),
    ('чёрная смородина', (SELECT id FROM cultures WHERE code = 'currant_black')),
    ('черная смородина', (SELECT id FROM cultures WHERE code = 'currant_black')),
    ('красная смородина', (SELECT id FROM cultures WHERE code = 'currant_red')),
    ('голубика', (SELECT id FROM cultures WHERE code = 'blueberry')),
    ('жимолость', (SELECT id FROM cultures WHERE code = 'honeysuckle')),
    ('крыжовник', (SELECT id FROM cultures WHERE code = 'gooseberry')),
    ('ирга', (SELECT id FROM cultures WHERE code = 'irga')),
    ('арония', (SELECT id FROM cultures WHERE code = 'aronia')),
    ('черноплодка', (SELECT id FROM cultures WHERE code = 'aronia')),
    ('черноплодная рябина', (SELECT id FROM cultures WHERE code = 'aronia'));

-- 5. Добавить флаг is_test в users (если не существует)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'users' AND column_name = 'is_test') THEN
        ALTER TABLE users ADD COLUMN is_test BOOLEAN DEFAULT false;
    END IF;
END $$;

-- 6. Функция для нормализации культуры
CREATE OR REPLACE FUNCTION normalize_culture(input_text TEXT)
RETURNS INTEGER AS $$
DECLARE
    result_id INTEGER;
BEGIN
    SELECT culture_id INTO result_id
    FROM culture_synonyms
    WHERE LOWER(synonym) = LOWER(TRIM(input_text));

    RETURN result_id;
END;
$$ LANGUAGE plpgsql;
```

---

## API endpoints

### Новые endpoints

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/admin/events` | Список событий с фильтрами |
| GET | `/api/admin/events/:user_id` | События пользователя |
| GET | `/api/admin/cultures` | Справочник культур |
| POST | `/api/admin/events/replay` | Воспроизведение пути клиента (debug) |

### Пример response `/api/admin/events`

```json
{
  "events": [
    {
      "id": 12345,
      "event_type": "topic_created",
      "user_id": 100,
      "entity_type": "topic",
      "entity_id": 500,
      "payload": {
        "culture": "strawberry_summer",
        "category": "nutrition"
      },
      "created_at": "2025-12-14T10:30:00Z"
    }
  ],
  "total": 1000,
  "page": 1,
  "per_page": 50
}
```

---

## UI компоненты (admin-webapp)

### Новые компоненты

1. **EventLogViewer** — просмотр событий в реальном времени
   - Фильтры по типу, пользователю, периоду
   - Группировка по сессиям
   - Timeline view

2. **CultureSelector** — выбор культуры из справочника
   - Автокомплит с синонимами
   - Используется в фильтрах

### Интеграция с существующими

- **UserList** — добавить колонку "Последнее событие"
- **ConsultationView** — показывать связанные события

---

## Backend изменения

### Новые файлы

| Файл | Назначение |
|------|------------|
| `src/services/db/event_log_repo.py` | CRUD для event_log |
| `src/services/db/cultures_repo.py` | Работа со справочником культур |
| `src/services/events/event_publisher.py` | Публикация событий |

### Изменения в существующих файлах

| Файл | Изменение |
|------|-----------|
| `src/handlers/menu/start.py` | Публикация `user_started` |
| `src/handlers/consultation/entry.py` | Публикация `topic_created`, `topic_closed` |
| `src/services/llm/consultation_llm.py` | Публикация `bot_response` с cost |

### Пример event_publisher.py

```python
from src.services.db.event_log_repo import EventLogRepo
import hashlib
import json

class EventPublisher:
    def __init__(self):
        self.repo = EventLogRepo()

    async def publish(
        self,
        event_type: str,
        user_id: int | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        payload: dict | None = None,
        idempotency_key: str | None = None
    ):
        """Публикация события в EventLog."""
        await self.repo.create_event(
            event_type=event_type,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload or {},
            idempotency_key=idempotency_key
        )

    def generate_idempotency_key(self, *args) -> str:
        """Генерация ключа для дедупликации."""
        data = json.dumps(args, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()[:32]

# Singleton
event_publisher = EventPublisher()
```

---

## Тесты

### Что проверить

1. **EventLog**
   - [ ] Создание событий всех типов
   - [ ] Идемпотентность (дубли не создаются)
   - [ ] Индексы работают (EXPLAIN ANALYZE)

2. **Справочник культур**
   - [ ] Нормализация синонимов (клубника → strawberry_summer)
   - [ ] НСД корректно определяется
   - [ ] Неизвестные культуры возвращают NULL

3. **Интеграция**
   - [ ] /start создаёт событие user_started
   - [ ] Новый топик создаёт topic_created
   - [ ] Закрытие топика создаёт topic_closed

### Тестовые команды

```bash
# Применить миграцию
docker exec -i sadovniki_db psql -U bot_user -d sadovniki_bot < db/schema_15_crm_foundation.sql

# Проверить таблицы
docker exec sadovniki_db psql -U bot_user -d sadovniki_bot -c "\dt event_log"
docker exec sadovniki_db psql -U bot_user -d sadovniki_bot -c "\dt cultures"

# Проверить нормализацию
docker exec sadovniki_db psql -U bot_user -d sadovniki_bot -c "SELECT normalize_culture('нсд');"
```

---

## Критерии готовности

- [ ] Миграция `schema_15_crm_foundation.sql` применена
- [ ] EventLog записывает события start, topic_created, topic_closed
- [ ] Справочник культур заполнен и нормализация работает
- [ ] API endpoint `/api/admin/events` возвращает данные
- [ ] В админке можно просмотреть события пользователя
- [ ] Тестовый пользователь `is_test=true` отфильтровывается в аналитике

---

## Риски и митигации

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| EventLog быстро растёт | Высокая | Партиционирование по месяцам, TTL 1 год |
| Несовместимость с текущими данными | Средняя | Миграция данных в отдельном скрипте |
| Производительность при большом количестве событий | Средняя | Индексы, пагинация, кэширование |

---

## Связь с другими этапами

- **Этап 1 (Карточка клиента):** Использует EventLog для показа активности
- **Этап 6 (Триггеры):** Подписывается на EventLog для автоматизации
- **Этап 7 (Рефералы):** События `referral_*` в EventLog
- **Этап 8 (Дашборды):** Агрегация EventLog для метрик

---

## История изменений

| Дата | Изменение |
|------|-----------|
| 2025-12-14 | Начальная версия спецификации |
