# CRM Data Models — Единые справочники

**Версия:** 1.0.0
**Обновлён:** 2025-12-14

---

## Назначение

Этот документ определяет единые справочники, статусы и типы данных для всей CRM-системы. Все компоненты (БД, API, UI) должны использовать эти определения.

---

## 1. Статусные модели

### 1.1 TopicStatus — Статус топика (консультации)

| Значение | Описание | Переход из | Переход в |
|----------|----------|------------|-----------|
| `open` | Активный топик, пользователь может продолжать диалог | — | `closed`, `archived` |
| `closed` | Завершённый топик (по таймауту или вручную) | `open` | `archived` |
| `archived` | Архивный топик (скрыт из основного списка) | `open`, `closed` | — |

**Текущее состояние БД:** Поле `status` в таблице `topics` (varchar).

---

### 1.2 SupportStage — Этапы кейса поддержки (Kanban)

| Значение | Описание | Действия |
|----------|----------|----------|
| `new` | Новый кейс, ожидает обработки | Взять в работу |
| `in_progress` | В работе у оператора | Ответить клиенту, передать коллеге |
| `waiting_client` | Ожидаем ответа от клиента | — |
| `resolved` | Решён, ожидает подтверждения | Закрыть |
| `closed` | Закрыт | Переоткрыть (→ new) |

**Диаграмма переходов:**
```
new → in_progress → waiting_client → in_progress → resolved → closed
                 ↘                  ↗
                   └────────────────┘
```

---

### 1.3 SubscriptionStatus — Статус подписки

| Значение | Описание |
|----------|----------|
| `none` | Нет подписки (бесплатный пользователь) |
| `trial` | Пробный период |
| `active` | Активная оплаченная подписка |
| `expired` | Подписка истекла |
| `cancelled` | Отменена пользователем |
| `suspended` | Приостановлена (неоплата) |

---

### 1.4 ModerationStatus — Статус модерации KB

| Значение | Описание |
|----------|----------|
| `pending` | Ожидает проверки |
| `approved` | Одобрено, добавлено в KB |
| `rejected` | Отклонено |
| `needs_edit` | Требует доработки |

**Текущее состояние БД:** Используется в `moderation_queue`.

---

### 1.5 PaymentStatus — Статус платежа

| Значение | Описание |
|----------|----------|
| `pending` | Ожидает оплаты |
| `processing` | В обработке |
| `success` | Успешно оплачен |
| `failed` | Ошибка оплаты |
| `refunded` | Возврат средств |
| `cancelled` | Отменён |

---

### 1.6 TaskStatus — Статус задачи (Этап 6)

| Значение | Описание |
|----------|----------|
| `new` | Новая задача |
| `in_progress` | В работе |
| `done` | Выполнена |
| `cancelled` | Отменена |

---

## 2. Типы событий (EventLog)

### 2.1 Пользовательские события

| Тип | Описание | Данные (payload) |
|-----|----------|------------------|
| `user_started` | Пользователь нажал /start | `{source?, referral_code?}` |
| `user_registered` | Новая регистрация | `{telegram_user_id, username?}` |
| `user_updated` | Обновлены данные профиля | `{fields_changed[]}` |

### 2.2 События консультаций

| Тип | Описание | Данные (payload) |
|-----|----------|------------------|
| `topic_created` | Создан новый топик | `{topic_id, culture, category}` |
| `topic_closed` | Топик закрыт | `{topic_id, reason, messages_count}` |
| `message_sent` | Сообщение от пользователя | `{topic_id, message_id}` |
| `bot_response` | Ответ бота | `{topic_id, message_id, cost_usd}` |

### 2.3 События подписок

| Тип | Описание | Данные (payload) |
|-----|----------|------------------|
| `subscription_started` | Подписка активирована | `{plan_id, expires_at, questions_limit}` |
| `subscription_renewed` | Подписка продлена | `{plan_id, new_expires_at}` |
| `subscription_expired` | Подписка истекла | `{plan_id}` |
| `subscription_cancelled` | Подписка отменена | `{reason?}` |
| `questions_depleted` | Лимит вопросов исчерпан | `{used, limit}` |

### 2.4 События оплаты

| Тип | Описание | Данные (payload) |
|-----|----------|------------------|
| `payment_initiated` | Платёж инициирован | `{payment_id, amount, currency}` |
| `payment_success` | Платёж успешен | `{payment_id, amount, provider}` |
| `payment_failed` | Платёж неуспешен | `{payment_id, error_code}` |
| `refund_processed` | Возврат обработан | `{payment_id, amount}` |

### 2.5 События поддержки

| Тип | Описание | Данные (payload) |
|-----|----------|------------------|
| `support_case_created` | Создан кейс поддержки | `{case_id, topic_id?, priority}` |
| `support_case_assigned` | Кейс назначен оператору | `{case_id, operator_id}` |
| `support_case_resolved` | Кейс решён | `{case_id, resolution_time_hours}` |
| `support_case_closed` | Кейс закрыт | `{case_id}` |

### 2.6 События рефералов

| Тип | Описание | Данные (payload) |
|-----|----------|------------------|
| `referral_link_created` | Создана реферальная ссылка | `{referrer_id, code}` |
| `referral_joined` | Реферал зарегистрировался | `{referrer_id, referee_id}` |
| `referral_activated` | Реферал активировался (N сообщений) | `{referrer_id, referee_id}` |
| `referral_converted` | Реферал оплатил | `{referrer_id, referee_id, amount}` |
| `referral_bonus_credited` | Начислен бонус рефереру | `{referrer_id, bonus_type, value}` |

### 2.7 Административные события

| Тип | Описание | Данные (payload) |
|-----|----------|------------------|
| `admin_login` | Вход в админку | `{admin_id, ip?}` |
| `kb_entry_approved` | KB запись одобрена | `{entry_id, admin_id}` |
| `kb_entry_rejected` | KB запись отклонена | `{entry_id, admin_id, reason}` |
| `user_blocked` | Пользователь заблокирован | `{user_id, admin_id, reason}` |

---

## 3. Справочник культур

### 3.1 Основные культуры

| ID | Код | Название RU | Группа |
|----|-----|-------------|--------|
| 1 | `strawberry_summer` | Клубника летняя | strawberry |
| 2 | `strawberry_remontant` | Клубника ремонтантная (НСД) | strawberry |
| 3 | `raspberry_summer` | Малина летняя | raspberry |
| 4 | `raspberry_remontant` | Малина ремонтантная | raspberry |
| 5 | `blackberry` | Ежевика | raspberry |
| 6 | `currant_black` | Смородина чёрная | b_berries |
| 7 | `currant_red` | Смородина красная | b_berries |
| 8 | `blueberry` | Голубика | b_berries |
| 9 | `honeysuckle` | Жимолость | b_berries |
| 10 | `gooseberry` | Крыжовник | b_berries |
| 11 | `irga` | Ирга | b_berries |
| 12 | `aronia` | Арония (черноплодная рябина) | b_berries |

### 3.2 Группы культур (для промптов)

| Группа | Культуры | Промпт-файл |
|--------|----------|-------------|
| `group_strawberry` | strawberry_summer, strawberry_remontant | `nutrition.py` |
| `group_raspberry` | raspberry_summer, raspberry_remontant, blackberry | `nutrition.py` |
| `group_b_berries` | currant_*, blueberry, honeysuckle, gooseberry, irga, aronia | `nutrition.py` |

### 3.3 Синонимы для классификации

```python
CULTURE_SYNONYMS = {
    "клубника": "strawberry_summer",
    "земляника": "strawberry_summer",
    "нсд": "strawberry_remontant",
    "ремонтантная клубника": "strawberry_remontant",
    "малина": "raspberry_summer",
    "ремонтантная малина": "raspberry_remontant",
    "ежевика": "blackberry",
    "смородина": "currant_black",
    "чёрная смородина": "currant_black",
    "красная смородина": "currant_red",
    "голубика": "blueberry",
    "жимолость": "honeysuckle",
    "крыжовник": "gooseberry",
    "ирга": "irga",
    "арония": "aronia",
    "черноплодка": "aronia",
}
```

---

## 4. Категории консультаций

| ID | Код | Название RU | Промпт-файл |
|----|-----|-------------|-------------|
| 1 | `nutrition` | Питание растений | `nutrition.py` |
| 2 | `planting_care` | Посадка и уход | `planting_care.py` |
| 3 | `diseases_pests` | Защита растений | `diseases_pests.py` |
| 4 | `soil_improvement` | Улучшение почвы | `soil_improvement.py` |
| 5 | `variety_selection` | Подбор сортов | `variety_selection.py` |
| 6 | `other` | Другие вопросы | — (base prompt) |

---

## 5. Планы подписок

### 5.1 Структура плана

```typescript
interface SubscriptionPlan {
  id: string;
  name: string;
  price_rub: number;
  duration_days: number;
  questions_limit: number;  // -1 = unlimited
  features: string[];
}
```

### 5.2 Примеры планов (будет уточняться)

| ID | Название | Цена | Срок | Лимит вопросов |
|----|----------|------|------|----------------|
| `free` | Бесплатный | 0 | ∞ | 5 |
| `basic` | Базовый | 990 | 30 дней | 30 |
| `pro` | Профессионал | 2490 | 30 дней | 100 |
| `unlimited` | Безлимит | 4990 | 30 дней | -1 |

---

## 6. Приоритеты поддержки

| Значение | Описание | SLA (часы) |
|----------|----------|------------|
| `low` | Низкий | 48 |
| `medium` | Средний | 24 |
| `high` | Высокий | 8 |
| `critical` | Критический | 2 |

---

## 7. Схема EventLog (таблица БД)

```sql
CREATE TABLE event_log (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    user_id INTEGER REFERENCES users(id),
    entity_type VARCHAR(30),  -- topic, payment, subscription, support_case
    entity_id INTEGER,
    payload JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Индексы
    INDEX idx_event_log_type (event_type),
    INDEX idx_event_log_user (user_id),
    INDEX idx_event_log_entity (entity_type, entity_id),
    INDEX idx_event_log_created (created_at)
);
```

---

## 8. Валидация данных

### 8.1 Правила нормализации культур

1. Привести к нижнему регистру
2. Убрать лишние пробелы
3. Найти в `CULTURE_SYNONYMS`
4. Если не найдено — вернуть `null` и логировать

### 8.2 Правила валидации событий

1. `event_type` должен быть из списка выше
2. `user_id` обязателен для пользовательских событий
3. `entity_id` обязателен если указан `entity_type`
4. `payload` валидируется по схеме для каждого `event_type`

---

## История изменений

| Дата | Версия | Изменения |
|------|--------|-----------|
| 2025-12-14 | 1.0.0 | Начальная версия |
