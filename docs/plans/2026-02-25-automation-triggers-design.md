# Система автоматических триггеров для воронок

## Контекст

Сейчас в проекте есть базовый механизм триггеров: таблица `funnel_stage_triggers` привязывает рассылку к этапу воронки. Когда клиент перемещается на этап — ему отправляется broadcast (или платёжный оффер). Это работает только в одну сторону и без условий.

**Задача**: создать полноценную систему автоматизации с:
- 4 типами событий (этап воронки, оплата, теги, подписка истекает/скоро истечёт)
- Условия/фильтры с AND/OR группами (теги, инвайт-ссылки, этапы воронок)
- 4 типа действий (рассылка, перемещение, теги, кастомные поля)
- Множественные действия в одном триггере
- Отдельная страница в админке + быстрый доступ с этапа воронки
- Без каскада (действия триггеров НЕ вызывают другие триггеры)

---

## Фаза 1: База данных + Репозиторий

### Файл: `db/schema_80_automation_triggers.sql`

Две новые таблицы заменяют `funnel_stage_triggers` + `funnel_trigger_log`:

**`automation_triggers`** — определение триггера:
- `id` SERIAL PK
- `name` VARCHAR(200) — человекопонятное имя
- `description` TEXT — опциональное описание
- `event_type` VARCHAR(30) — `stage_transition | payment_success | tag_changed | subscription_expiring`
- `event_config` JSONB — параметры события (зависят от типа)
- `conditions` JSONB NULL — AND/OR дерево условий (null = без условий)
- `actions` JSONB — массив действий (выполняются последовательно)
- `delay_minutes` INT DEFAULT 0
- `is_active` BOOLEAN DEFAULT true
- `created_at`, `updated_at` TIMESTAMPTZ

**`automation_trigger_log`** — лог выполнения:
- `id` SERIAL PK
- `trigger_id` INT FK → automation_triggers(id) CASCADE
- `user_id` INT FK → users(id) CASCADE
- `event_snapshot` JSONB NULL — снимок event_data (для дедупликации subscription_expiring: содержит subscription_id)
- `status` VARCHAR(20) — `pending | sent | failed | skipped`
- `send_at` TIMESTAMPTZ — когда выполнять (для отложенных)
- `executed_at` TIMESTAMPTZ
- `actions_result` JSONB — результат каждого действия
- `error_message` TEXT
- `created_at` TIMESTAMPTZ

Индексы: по event_type (WHERE is_active), по status+send_at (WHERE pending).

Миграция данных из `funnel_stage_triggers` → `automation_triggers` внутри этой же SQL миграции.

### event_config по типам:
```
stage_transition:     { "funnel_id": "crm", "stage_key": "paid" }
payment_success:      { "payment_type": "subscription|tokens|null", "plan_id": 3|null }
tag_changed:          { "tag_id": 5, "action": "added|removed" }
subscription_expiring: { "days_before": 0 }
```

**subscription_expiring.days_before**:
- `0` = подписка уже истекла (момент истечения)
- `1` = за 1 день до истечения
- `3` = за 3 дня до истечения
- `7` = за неделю до истечения
- Можно создать НЕСКОЛЬКО триггеров с разными days_before (например: за 7 дней — напоминание, за 1 день — последнее предупреждение, 0 — подписка истекла)

Движок проверяет: `subscription_expires_at - days_before * interval '1 day' <= NOW() < subscription_expires_at - (days_before - 1) * interval '1 day'`
Для `days_before=0`: `subscription_expires_at <= NOW()` (как раньше).

Дедупликация: в `automation_trigger_log` записывается `(trigger_id, user_id, subscription_id)` — один триггер на одну подписку срабатывает один раз.

### conditions (AND/OR дерево):
```json
{
  "operator": "AND",
  "groups": [
    {
      "operator": "OR",
      "rules": [
        { "type": "has_tag", "tag_id": 5 },
        { "type": "has_tag", "tag_id": 8 }
      ]
    },
    {
      "operator": "AND",
      "rules": [
        { "type": "from_invite_link", "invite_link_id": 12 }
      ]
    }
  ]
}
```

Типы правил: `has_tag`, `not_has_tag`, `from_invite_link`, `at_funnel_stage`, `not_at_funnel_stage`

### actions (массив):
```json
[
  { "type": "send_broadcast", "broadcast_id": 42 },
  { "type": "move_to_stage", "funnel_id": "crm", "stage_key": "paid" },
  { "type": "add_tag", "tag_id": 5 },
  { "type": "remove_tag", "tag_id": 3 },
  { "type": "set_custom_field", "field_id": 7, "value": "VIP" },
  { "type": "send_payment_offer", "plan_id": 1, "custom_price": 490, "bonus_tokens": 5 }
]
```

### Файл: `src/services/db/automation_trigger_repo.py`

CRUD по паттерну `funnel_trigger_repo.py`:
- `get_all_triggers(event_type?, funnel_id?, stage_key?)` — с фильтрами
- `get_trigger_by_id(id)`
- `create_trigger(name, event_type, event_config, conditions, actions, delay_minutes)`
- `update_trigger(id, ...)`
- `delete_trigger(id)` — CASCADE удалит лог
- `toggle_trigger(id, is_active)`
- `get_active_triggers_by_event(event_type)` — для движка
- `log_trigger_execution(trigger_id, user_id, status, send_at?, actions_result?, error?)`
- `get_pending_triggers_due(limit)` — pending с send_at <= NOW()
- `update_trigger_log_status(log_id, status, actions_result?, error?)`
- `delete_trigger_log_entry(log_id)`
- `get_trigger_log(trigger_id, limit, offset)` — для просмотра в UI

---

## Фаза 2: Движок автоматизации (Backend)

### Новые файлы:
- `src/services/automation/__init__.py`
- `src/services/automation/engine.py` — главная точка входа
- `src/services/automation/conditions.py` — оценка условий
- `src/services/automation/executor.py` — выполнение действий

### `engine.py` — `emit_automation_event(event_type, user_id, telegram_user_id, event_data)`

Главная функция. Вызывается как `asyncio.create_task()` из точек событий:

1. Получить все активные триггеры для `event_type`
2. Для каждого — проверить совпадение `event_config`
3. Оценить `conditions` (загрузить контекст пользователя, пройти AND/OR дерево)
4. Если delay > 0 — записать pending в лог
5. Иначе — выполнить немедленно через executor

### `conditions.py` — `evaluate_conditions(conditions, user_id)`

Загрузка контекста пользователя (1 запрос):
- Теги: `SELECT tag_id FROM client_tag_links WHERE user_id = $1`
- Инвайт: `SELECT invite_link_id FROM invite_link_users WHERE user_id = $1`
- Воронки: `SELECT funnel_id, stage_key FROM client_funnel_position WHERE user_id = $1`

Рекурсивная оценка AND/OR дерева по правилам.

### `executor.py` — `execute_actions(actions, user_id, telegram_user_id)`

Последовательное выполнение действий. Каждое действие:
- `send_broadcast` → переиспользовать `broadcast_sender.send_to_single_user()`
- `move_to_stage` → `funnel_repo.move_client_to_stage()` с флагом `_from_automation=True`
- `add_tag` / `remove_tag` → `client_crm_repo.add_client_tag()` / `remove_client_tag()`
- `set_custom_field` → `client_crm_repo` (новая функция или существующая)
- `send_payment_offer` → переиспользовать `funnel_trigger_sender.send_payment_offer()`

Возвращает массив результатов для записи в `actions_result`.

### Точки подключения событий:

| Событие | Файл | Функция | Что добавить |
|---------|------|---------|-------------|
| `stage_transition` | `src/services/db/funnel_repo.py:764,872` | `move_client_to_stage`, `auto_move_client_in_crm` | Заменить `execute_stage_triggers()` на `emit_automation_event()`. Добавить параметр `_from_automation=True` чтобы не вызывать при каскаде |
| `payment_success` | `src/services/payments/payment_service.py:853` | `process_payment_success` | В конце функции: `emit_automation_event('payment_success', ...)` с данными о типе платежа |
| `tag_changed` | `src/services/db/client_crm_repo.py` | `add_client_tag`, `remove_client_tag`, `set_client_tags` | После изменения: `emit_automation_event('tag_changed', ...)`. С `_from_automation` флагом |
| `subscription_expiring` | `src/main.py` (новый cron loop) | `check_subscription_expiring_triggers` | Новый фоновый цикл (каждый час): для каждого триггера `subscription_expiring` с `days_before=N` — найти подписки которые истекают через N дней (±12ч окно) и ещё не были обработаны → `emit_automation_event()`. Для `days_before=0` — дополнительно вызывается из `expire_old_subscriptions` для каждого реально истёкшего юзера |

### Фоновый планировщик

В `src/main.py`:

**1. `_automation_scheduler_loop`** (каждые 30 сек):
- Проверять `get_pending_triggers_due()` — отложенные триггеры у которых пришло время
- Для каждого — выполнить через executor

**2. `_subscription_expiring_loop`** (каждый час):
- Получить все активные триггеры с `event_type='subscription_expiring'`
- Для каждого уникального `days_before`:
  - Найти пользователей с подписками, истекающими через `days_before` дней (±12ч окно)
  - Проверить по `automation_trigger_log` что триггер ещё не срабатывал для этой подписки
  - Для каждого подходящего юзера: `emit_automation_event('subscription_expiring', user_id, tg_id, {days_before, subscription_id})`
- Для `days_before=0`: также вызывается из `expire_old_subscriptions()` для каждого юзера чья подписка реально только что истекла

**SQL для поиска "скоро истекающих":**
```sql
SELECT u.id, u.telegram_user_id, us.id as subscription_id, us.expires_at
FROM user_subscriptions us
JOIN users u ON u.id = us.user_id
WHERE us.status = 'active'
  AND us.expires_at BETWEEN NOW() + ($1 - 0.5) * INTERVAL '1 day'
                        AND NOW() + ($1 + 0.5) * INTERVAL '1 day'
-- $1 = days_before
```

---

## Фаза 3: API эндпоинты

### Файл: `src/api/handlers/automation.py`

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/admin/triggers` | Список триггеров с фильтрами (event_type, funnel_id, stage_key) |
| POST | `/api/admin/triggers` | Создать триггер |
| GET | `/api/admin/triggers/{id}` | Получить триггер |
| PUT | `/api/admin/triggers/{id}` | Обновить триггер |
| DELETE | `/api/admin/triggers/{id}` | Удалить триггер |
| PATCH | `/api/admin/triggers/{id}/toggle` | Вкл/выкл триггер |
| GET | `/api/admin/triggers/{id}/log` | Лог выполнения |
| POST | `/api/admin/triggers/preview-users` | Превью пользователей по условиям |

### Регистрация: `src/api/routes.py`

---

## Фаза 4: Admin UI — Страница триггеров

### Новые файлы:

```
admin-webapp/src/components/triggers/
  TriggersPage.tsx              — Главная: список + боковая панель
  TriggersPage.module.css
  TriggerList.tsx               — Список с фильтрами
  TriggerList.module.css
  TriggerEditor.tsx             — Создание/редактирование (3 шага)
  TriggerEditor.module.css
  EventTypeSelector.tsx         — Шаг 1: тип события + конфиг
  ConditionBuilder.tsx          — Шаг 2: AND/OR группы условий
  ConditionBuilder.module.css
  ActionListEditor.tsx          — Шаг 3: список действий
  ActionListEditor.module.css
  TriggerLogView.tsx            — Лог выполнений
```

### Роутинг и навигация:
- Добавить `'triggers'` в `SIMPLE_VIEWS` (`admin-webapp/src/router/index.ts`)
- Добавить пункт в сайдбар (`admin-webapp/src/components/layout/Sidebar.tsx`) — между "Рассылки" и "Задачи"
- Иконка: ⚡ или молния

### Store: `admin-webapp/src/store/triggerStore.ts` (Zustand)

CRUD операции + состояние фильтров + лог. По паттерну `broadcastStore.ts`.

### Types: `admin-webapp/src/types/index.ts`

Новые типы: `AutomationTrigger`, `TriggerEventType`, `TriggerActionType`, `ConditionGroup`, `ConditionRule`, `TriggerAction`, `TriggerLogEntry`, `CreateTriggerDto`

### UI компоненты:

**TriggersPage** — split-panel (как BroadcastPage):
- Слева: список триггеров с фильтрами по типу события и воронке
- Каждая карточка: имя, бейдж типа события, кол-во действий, toggle активности
- Справа: редактор (создание/редактирование) или лог

**TriggerEditor** — 3 шага вертикальной формы:

1. **Событие** (EventTypeSelector): радио-кнопки 4 типов, каждый с доп. конфигом:
   - `stage_transition`: дропдаун воронки + дропдаун этапа
   - `payment_success`: тип платежа (any/subscription/tokens) + опционально план
   - `tag_changed`: выбор тега + действие (added/removed)
   - `subscription_expiring`: числовое поле "За сколько дней до истечения" (0 = в момент истечения, 1 = за день, 3 = за 3 дня, 7 = за неделю). Пресеты-кнопки: "В момент истечения", "За 1 день", "За 3 дня", "За 7 дней" + ручной ввод

2. **Условия** (ConditionBuilder):
   - Кнопка "Добавить группу условий"
   - Каждая группа: карточка с AND/OR переключателем вверху
   - Внутри: список правил (дропдаун типа + селектор значения + удалить)
   - "Добавить правило" внутри группы
   - Группы соединяются верхнеуровневым AND/OR
   - Кнопка "Проверить — N клиентов подходят" (preview API)

3. **Действия** (ActionListEditor):
   - Список карточек действий (порядок важен)
   - Каждая: тип действия (дропдаун) + поля в зависимости от типа + удалить
   - "Добавить действие"
   - Типы: отправить рассылку, переместить по воронке, добавить/удалить тег, изменить поле, отправить оплату

**Задержка**: часы + минуты (как в StageTriggerEditor)

---

## Фаза 5: Интеграция с воронками (StageTriggerEditor)

### Файл: `admin-webapp/src/components/funnel/StageTriggerEditor.tsx`

Обновить компонент:
- Читать триггеры из нового API (`/api/admin/triggers?event_type=stage_transition&funnel_id=X&stage_key=Y`)
- Показывать карточки с именем триггера, количеством условий/действий, toggle
- Кнопка "Добавить триггер" → переход на страницу триггеров с предзаполненным event
- Кнопка "Открыть" на каждом триггере → переход на страницу редактирования

---

## Фаза 6: Очистка

- Удалить/пометить deprecated старый код: `funnel_trigger_repo.py`, `funnel_trigger_sender.py`
- Обновить `CLAUDE.md`, `docs/PROJECT_MAP.md`, `session-summary.md`
- Обновить фоновые задачи в `main.py`

---

## Критические файлы для модификации

| Файл | Что делаем |
|------|-----------|
| `db/schema_80_automation_triggers.sql` | **Создать** — новая миграция |
| `src/services/db/automation_trigger_repo.py` | **Создать** — CRUD + лог |
| `src/services/automation/engine.py` | **Создать** — emit_automation_event, матчинг |
| `src/services/automation/conditions.py` | **Создать** — оценка AND/OR условий |
| `src/services/automation/executor.py` | **Создать** — выполнение действий |
| `src/api/handlers/automation.py` | **Создать** — REST API |
| `src/api/routes.py` | **Изменить** — регистрация маршрутов |
| `src/services/db/funnel_repo.py` | **Изменить** — строки 762-767, 868-873: заменить execute_stage_triggers → emit_automation_event, добавить `_from_automation` |
| `src/services/payments/payment_service.py` | **Изменить** — добавить emit в конце process_payment_success (~строка 853+) |
| `src/services/db/client_crm_repo.py` | **Изменить** — добавить emit в add/remove_client_tag, set_client_tags |
| `src/services/payments/subscription_service.py` | **Изменить** — добавить emit в expire_old_subscriptions для days_before=0 |
| `src/services/automation/subscription_checker.py` | **Создать** — cron-задача для проверки "скоро истекающих" подписок (days_before > 0) |
| `src/main.py` | **Изменить** — обновить/добавить scheduler loop |
| `admin-webapp/src/types/index.ts` | **Изменить** — добавить типы триггеров |
| `admin-webapp/src/store/triggerStore.ts` | **Создать** — Zustand store |
| `admin-webapp/src/services/api.ts` | **Изменить** — добавить API функции |
| `admin-webapp/src/router/index.ts` | **Изменить** — добавить triggers view |
| `admin-webapp/src/components/layout/Sidebar.tsx` | **Изменить** — добавить пункт меню |
| `admin-webapp/src/components/triggers/*.tsx` | **Создать** — 8 компонентов |
| `admin-webapp/src/components/funnel/StageTriggerEditor.tsx` | **Изменить** — интеграция с новым API |

---

## Порядок реализации

1. **DB + Repo** — schema_80 + automation_trigger_repo.py
2. **Engine** — automation/engine.py, conditions.py, executor.py
3. **Event wiring** — подключить stage_transition первым (самый простой для тестирования)
4. **API** — automation.py + routes.py
5. **Admin UI types + store** — types/index.ts + triggerStore.ts + api.ts
6. **Triggers page** — TriggersPage + TriggerList (базовый CRUD)
7. **Trigger editor** — EventTypeSelector + ConditionBuilder + ActionListEditor
8. **Remaining events** — payment_success, tag_changed, subscription_expiring
9. **StageTriggerEditor integration** — обновить компонент воронки
10. **Cleanup** — убрать старый код, обновить документацию

---

## Верификация

1. **DB**: Применить миграцию на dev-базе, проверить что данные из old triggers мигрировались
2. **Engine**: Создать тестовый триггер через API (curl), переместить клиента на этап в CRM → проверить что триггер сработал в логе
3. **Conditions**: Создать триггер с условием "has_tag VIP", проверить что срабатывает только для VIP клиентов
4. **Delay**: Создать триггер с delay_minutes=1, проверить что pending запись появилась и через ~30с (scheduler) выполнилась
5. **Admin UI**: Открыть `localhost:5174`, перейти в Триггеры → создать триггер через UI → проверить через Playwright MCP
6. **Integration**: На странице воронки → нажать "Добавить триггер" на этапе → проверить что перенаправляет на страницу триггеров с предзаполненным типом
