# A/B тестирование воронок — Design Document

**Дата:** 2026-02-26
**Статус:** Approved

## Контекст

Бот накопил базу пользователей по текущей воронке (Тип А). Нужна инфраструктура для тестирования новой воронки (Тип Б) с возможностью сравнивать конверсию в оплату между группами. Администратор должен одной кнопкой переключать, какую воронку получают новые пользователи, и видеть аналитику в разрезе двух групп.

## Требования

- Глобальный переключатель: все новые пользователи попадают в активный вариант (A или B)
- Каждый пользователь сохраняет свой вариант навсегда (не меняется при переключении)
- Аналитика: количество пользователей и конверсия в оплату по каждому варианту
- Скелет воронки Б — контент заполняется позже, сейчас только инфраструктура

## Архитектура

### База данных

**Новая таблица `bot_settings`** (ключ-значение для глобальных настроек):
```sql
CREATE TABLE bot_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
INSERT INTO bot_settings (key, value) VALUES ('active_funnel_variant', 'A');
```

**Новое поле `users.funnel_variant`**:
```sql
ALTER TABLE users ADD COLUMN funnel_variant TEXT DEFAULT 'A';
```
Все существующие пользователи получают 'A' через DEFAULT.

### Бот (Python)

**`src/services/db/bot_settings_repo.py`** (новый файл):
- `get_setting(key) -> str`
- `set_setting(key, value) -> None`

**`src/handlers/menu.py`** изменения в `cmd_start()`:
1. При регистрации нового пользователя: читать `active_funnel_variant` из `bot_settings`
2. Сохранять вариант в `users.funnel_variant`
3. Если вариант 'B' → вызвать `start_funnel_b(message, user)` вместо стандартного флоу

**`src/handlers/funnel_b.py`** (новый файл, скелет):
```python
async def start_funnel_b(message, user):
    # TODO: новая воронка — контент будет добавлен позже
    await message.answer("Добро пожаловать!")  # временный плейсхолдер
```

### API (Python)

**`src/api/handlers/ab_test.py`** (новый файл):
- `GET /api/admin/ab-test/stats` — статистика по группам
- `POST /api/admin/ab-test/variant` — смена активного варианта `{variant: 'A'|'B'}`

Ответ `GET /api/admin/ab-test/stats`:
```json
{
  "active_variant": "A",
  "variants": {
    "A": {"users": 247, "paid": 23, "conversion": 9.3},
    "B": {"users": 12, "paid": 2, "conversion": 16.7}
  }
}
```

SQL для расчёта:
```sql
SELECT
  u.funnel_variant,
  COUNT(DISTINCT u.id) as users,
  COUNT(DISTINCT p.user_id) as paid
FROM users u
LEFT JOIN payments p ON p.user_id = u.id AND p.status = 'paid'
GROUP BY u.funnel_variant
```

### Admin Webapp (React)

**`admin-webapp/src/components/pages/Dashboard.tsx`** — добавить секцию "A/B тест":

1. **Плашка-переключатель** (новый компонент `ABTestToggle.tsx`):
   ```
   ┌─────────────────────────────────────────────────┐
   │  Воронка для новых пользователей               │
   │  [■ Тип А ■]  [ Тип Б  ]  ← активная жирная  │
   └─────────────────────────────────────────────────┘
   ```
   При клике — POST запрос + confirm диалог "Все новые пользователи будут получать Тип Б. Продолжить?"

2. **Сравнительная таблица** (новый компонент `ABTestStats.tsx`):
   ```
                  Тип А    Тип Б
   Пользователей   247       12
   Оплатили         23        2
   Конверсия       9.3%    16.7%
   ```

**`admin-webapp/src/api/abTestApi.ts`** (новый файл):
- `fetchABTestStats()` → GET запрос
- `setActiveVariant(variant)` → POST запрос

## Файлы для изменения/создания

### Новые файлы:
- `db/schema_79_funnel_variant.sql` — миграция БД
- `src/services/db/bot_settings_repo.py` — репозиторий настроек
- `src/handlers/funnel_b.py` — скелет воронки Б
- `src/api/handlers/ab_test.py` — API эндпойнты
- `admin-webapp/src/api/abTestApi.ts` — клиентский API
- `admin-webapp/src/components/abtest/ABTestToggle.tsx` — переключатель
- `admin-webapp/src/components/abtest/ABTestStats.tsx` — статистика

### Изменяемые файлы:
- `src/handlers/menu.py` — разветвление в `cmd_start()`
- `src/api/routes.py` (или аналог) — регистрация новых роутов
- `admin-webapp/src/components/pages/Dashboard.tsx` — добавить секцию

## Верификация

1. Запустить бота локально, зайти как новый пользователь → проверить поле `funnel_variant` в БД
2. Переключить вариант в админке → снова зайти как новый пользователь → проверить что вариант изменился
3. Открыть Dashboard → убедиться что таблица с конверсией показывает данные
4. Playwright: `browser_navigate` → `localhost:5174` → Dashboard → проверить секцию A/B

---

## Фаза 2: Отдельная страница A/B аналитики (2026-02-26)

**Статус:** Approved

### Цель

Добавить полноценную страницу "A/B тест" в группу "Аналитика" сайдбара. Визуализация — amoCRM-стиль: этапы воронки как колонки, варианты A и B как строки, с прогресс-барами и переключателем активного варианта.

### Изменения API

**`src/api/handlers/ab_test.py`** — расширить SQL для возврата `tried` и `trial_ended`:

```sql
SELECT
    u.funnel_variant,
    COUNT(DISTINCT u.id) AS users,
    COUNT(DISTINCT CASE WHEN u.crm_status IN ('tried','trial_ended','paid') THEN u.id END) AS tried,
    COUNT(DISTINCT CASE WHEN u.crm_status IN ('trial_ended','paid') THEN u.id END) AS trial_ended,
    COUNT(DISTINCT p.user_id) AS paid
FROM users u
LEFT JOIN payments p ON p.user_id = u.id AND p.status = 'paid'
WHERE u.funnel_variant IS NOT NULL
GROUP BY u.funnel_variant
ORDER BY u.funnel_variant
```

Новый ответ:
```json
{
  "active_variant": "A",
  "variants": {
    "A": { "users": 150, "tried": 80, "trial_ended": 50, "paid": 20, "conversion": 13.3 },
    "B": { "users": 90,  "tried": 40, "trial_ended": 20, "paid": 5,  "conversion": 5.6 }
  }
}
```

### Изменения Store

**`admin-webapp/src/store/index.ts`** — расширить `ABTestVariantStats`:
```ts
interface ABTestVariantStats {
  users: number
  tried: number        // NEW
  trial_ended: number  // NEW
  paid: number
  conversion: number
}
```

### Новый компонент ABTestPage

**Новые файлы:**
- `admin-webapp/src/components/abtest/ABTestPage.tsx`
- `admin-webapp/src/components/abtest/ABTestPage.module.css`

**Структура:**
```
Заголовок "A/B тест воронок"
[Кнопка: Тип А ●] [Кнопка: Тип Б] — переключение активного варианта

Таблица (4 колонки этапов + строки вариантов):
┌──────────┬────────────┬──────────────┬──────────────────┬──────────┐
│          │  Новые     │ Попробовали  │Триал закончился  │ Оплатили │
│          │  (синий)   │ (фиолетовый) │   (жёлтый)       │ (зелёный)│
├──────────┼────────────┼──────────────┼──────────────────┼──────────┤
│ Тип А (●)│  N чел.    │  N чел.      │  N чел.          │  N чел.  │
│          │ ████░░ N%  │ ███░░░ N%    │ ██░░░░ N%        │ конв. N% │
├──────────┼────────────┼──────────────┼──────────────────┼──────────┤
│ Тип Б    │  N чел.    │  N чел.      │  N чел.          │  N чел.  │
│          │ ████░░ N%  │ ...          │ ...              │ конв. N% │
└──────────┴────────────┴──────────────┴──────────────────┴──────────┘

Карточки сравнения: итоговая конверсия A vs B, выделить лидера
```

Прогресс-бары: `stage_count / variant_users * 100%`.

### Навигация

**`admin-webapp/src/components/layout/Sidebar.tsx`:**
```ts
// в stats-group submenu добавить:
{ id: 'ab-test', label: 'A/B тест' }
```

**`admin-webapp/src/App.tsx`:**
```tsx
{currentView === 'ab-test' && <ABTestPage />}
```

**`admin-webapp/src/types/index.ts`** — добавить `'ab-test'` в union `View`.

### Файлы к изменению

| Файл | Изменение |
|------|-----------|
| `src/api/handlers/ab_test.py` | Расширить SQL, добавить `tried`/`trial_ended` |
| `admin-webapp/src/store/index.ts` | Расширить тип `ABTestVariantStats` |
| `admin-webapp/src/components/abtest/ABTestPage.tsx` | Новый компонент |
| `admin-webapp/src/components/abtest/ABTestPage.module.css` | Новые стили |
| `admin-webapp/src/components/layout/Sidebar.tsx` | Добавить `ab-test` в submenu |
| `admin-webapp/src/App.tsx` | Добавить роут `ab-test` |
| `admin-webapp/src/types/index.ts` | Добавить `'ab-test'` в View |
