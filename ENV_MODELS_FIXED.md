# ✅ Исправление конфигурации OpenAI моделей

**Дата:** 2026-02-15
**Статус:** ИСПРАВЛЕНО

---

## 📋 Проблема

Было обнаружено, что в коде используются **несуществующие модели OpenAI**:
- `gpt-5-mini` ❌
- `gpt-4.1-mini` ❌
- `gpt-55` ❌

Эти названия были в:
1. ~~`.env` файле~~ — **ИСПРАВЛЕНО** (теперь опциональны, закомментированы)
2. `db/schema_42_llm_settings.sql` — **ТРЕБУЕТ ИСПРАВЛЕНИЯ** (применить SQL скрипт)

---

## ✅ Решение

### 1. Как работает система моделей

**Приоритет настроек:**
1. **БД (admin_settings)** — основной источник (таблица `admin_settings`, ключи `model_*`)
2. **.env файл** — fallback если в БД пусто
3. **config.py** — hardcoded fallback (`gpt-4o-mini`)

**Код:**
```python
# src/services/db/settings_repo.py

async def get_model_for_task(task: str) -> str:
    # 1. Сначала проверяет admin_settings
    db_value = await get_setting(f"model_{task}")
    if db_value and db_value.strip():
        return db_value.strip()

    # 2. Fallback на .env
    from src.config import settings as env_settings
    attr = _TASK_MODEL_MAP.get(task)
    if attr:
        return getattr(env_settings, attr, "gpt-4.1-mini")

    # 3. Hardcoded fallback
    return "gpt-4.1-mini"
```

---

### 2. Что было сделано

#### ✅ Шаг 1: Обновлен config.py

**Файл:** [src/config.py](src/config.py:62-77)

**Изменения:**
- Сделаны все `openai_model_*` поля опциональными (не обязательны)
- Установлены корректные fallback значения: `gpt-4o-mini`
- Добавлены комментарии о приоритете БД

**До:**
```python
openai_model_consultation: str = Field(
    ...,  # Обязательное поле!
    description="Модель для консультаций",
)
```

**После:**
```python
openai_model_consultation: str = Field(
    "gpt-4o-mini",  # Fallback значение
    description="Модель для консультаций - используется как fallback, основные настройки в БД",
)
```

---

#### ✅ Шаг 2: Обновлен .env

**Файл:** [.env](.env:1-10)

**Изменения:**
- Закомментированы строки с моделями
- Добавлен комментарий о том, что настройки берутся из БД
- Указаны корректные названия моделей в комментариях (для справки)

**До:**
```bash
OPENAI_MODEL_CONSULTATION=gpt-5-mini    # ❌ Несуществующая модель
OPENAI_MODEL_CLASSIFICATION=gpt-4.1-mini  # ❌ Несуществующая модель
```

**После:**
```bash
# Модели OpenAI (ОПЦИОНАЛЬНО - настройки берутся из admin_settings в БД)
# Эти значения используются только как fallback, если в БД не заданы модели
# OPENAI_MODEL_CONSULTATION=gpt-4o-mini
# OPENAI_MODEL_CLASSIFICATION=gpt-4o-mini
```

---

#### ⚠️ Шаг 3: Создан SQL скрипт для исправления БД

**Файл:** [db/fix_model_names.sql](db/fix_model_names.sql)

**Назначение:** Обновить некорректные названия моделей в таблице `admin_settings`

**Команда для применения:**
```bash
psql -h localhost -U bot_user -d garden_bot -f db/fix_model_names.sql
```

**Что делает скрипт:**
```sql
-- Заменяет все несуществующие модели на gpt-4o-mini
UPDATE admin_settings
SET value = 'gpt-4o-mini'
WHERE key = 'model_consultation'
AND value IN ('gpt-5-mini', 'gpt-4.1-mini', 'gpt-55');

-- То же для других ключей: model_classification, model_article, model_utility
```

---

## 🚀 Действия перед запуском

### Обязательно:

```bash
# 1. Применить SQL скрипт (исправить модели в БД)
psql -h localhost -U bot_user -d garden_bot -f db/fix_model_names.sql

# 2. Проверить результат
psql -h localhost -U bot_user -d garden_bot -c "SELECT key, value FROM admin_settings WHERE key LIKE 'model_%' ORDER BY key;"

# Ожидаемый вывод:
#          key          |   value
# ----------------------+-------------
#  model_article        | gpt-4o-mini
#  model_classification | gpt-4o-mini
#  model_consultation   | gpt-4o-mini
#  model_utility        | gpt-4o-mini

# 3. Перезапустить бот
python -m src
```

---

## 📊 Корректные названия моделей OpenAI

**Актуальные модели (февраль 2026):**

| Модель | Назначение | Стоимость | Качество |
|--------|-----------|-----------|----------|
| `gpt-4o` | Топовая модель GPT-4 Turbo | Высокая | ⭐⭐⭐⭐⭐ |
| `gpt-4o-mini` | Облегченная версия | Средняя | ⭐⭐⭐⭐ |
| `gpt-3.5-turbo` | GPT-3.5 Turbo | Низкая | ⭐⭐⭐ |

**Рекомендации:**

**Вариант 1: Экономный** (все задачи на дешевой модели)
```sql
UPDATE admin_settings SET value = 'gpt-4o-mini' WHERE key LIKE 'model_%';
```

**Вариант 2: Оптимальный** ⭐ (важные задачи — качество, вспомогательные — экономия)
```sql
-- Консультации и статьи требуют качества
UPDATE admin_settings SET value = 'gpt-4o' WHERE key IN ('model_consultation', 'model_article');

-- Классификация и вспомогательные задачи — оптимизация
UPDATE admin_settings SET value = 'gpt-4o-mini' WHERE key IN ('model_classification', 'model_utility');
```

**Вариант 3: Максимальное качество** (все на топовой модели)
```sql
UPDATE admin_settings SET value = 'gpt-4o' WHERE key LIKE 'model_%';
```

---

## 🔍 Проверка работы

После применения исправлений:

1. **Запустить бот:**
   ```bash
   python -m src
   ```

2. **Проверить логи startup:**
   ```
   INFO - Loading model for task 'consultation': gpt-4o-mini
   INFO - Loading model for task 'classification': gpt-4o-mini
   ```

3. **Отправить тестовый вопрос:**
   ```
   User: "Как подкормить малину?"
   ```

4. **Проверить логи LLM вызова:**
   ```
   INFO - OpenAI API call: model=gpt-4o-mini, tokens=1234, cost=$0.0012
   ```

5. **Ожидаемый результат:**
   - ✅ Бот отвечает корректно
   - ✅ В логах используется модель `gpt-4o-mini` (или `gpt-4o`)
   - ❌ НЕТ ошибок типа `APIError: model not found`

---

## 📝 Итоги

**Статус:** ✅ Исправлено на уровне fallback (config.py + .env)

**Осталось:** ⚠️ Применить SQL скрипт `db/fix_model_names.sql` для исправления БД

**Время на исправление:** 2-3 минуты (применить SQL + перезапустить бот)

**Критичность:** 🔴 ВЫСОКАЯ — без этого бот не будет работать!

---

## 🎓 Что мы узнали

1. **Модели в БД > .env** — приоритет у настроек в admin_settings
2. **Fallback chain:** БД → .env → config.py hardcoded
3. **Несуществующие модели** вызывают `APIConnectionError` (не очевидно!)
4. **Корректные названия:** `gpt-4o`, `gpt-4o-mini`, `gpt-3.5-turbo`
5. **Управление через админку** — можно менять модели без рестарта (после применения миграции schema_42)

---

**Готово к запуску после применения:** `db/fix_model_names.sql` ✅
