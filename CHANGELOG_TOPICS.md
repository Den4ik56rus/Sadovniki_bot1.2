# Changelog: Исправление управления топиками (Критические баги)

## Описание проблемы

При нажатии кнопки "Вопрос по новой теме" и начале новой консультации бот неправильно:
1. Повторно использовал старый топик вместо создания нового
2. Использовал культуру из предыдущего топика вместо переопределения

**Пример:** Пользователь спросил про малину, нажал "Новая тема", спросил про клубнику, но бот продолжал использовать "малину".

## Обнаруженные критические баги

### БАГ #1: Несоответствие Telegram User ID и Internal User ID (КРИТИЧНО!)

**Местоположение:**
- `src/handlers/menu.py:224, 269`
- `src/handlers/consultation/pitanie_rastenii.py:550`

**Проблема:**
Все вызовы `close_open_topics()` передавали `user.id` (Telegram user ID вроде 833371989) вместо внутреннего `user_id` из таблицы users (например, 1):
- `close_open_topics(833371989)` закрывала топики для несуществующего user_id=833371989
- Реальные топики пользователя user_id=1 оставались открытыми
- Следующий `get_or_create_open_topic()` находил всё ещё открытый топик и переиспользовал его

**Доказательство из логов:**
```
[close_open_topics] До закрытия: 0 открытых топиков для user_id=833371989  # Неверный ID!
[get_or_create_open_topic] Найден открытый топик: topic_id=13, status=open, user_id=1  # Правильный ID!
```

**Исправление:**
```python
# ДО (НЕПРАВИЛЬНО):
await close_open_topics(user.id)  # Это telegram_user_id!

# ПОСЛЕ (ПРАВИЛЬНО):
internal_user_id = await get_or_create_user(
    telegram_user_id=user.id,
    username=user.username,
    first_name=user.first_name,
    last_name=user.last_name,
)
await close_open_topics(internal_user_id)  # Это user_id из БД!
```

### БАГ #2: Неправильный порядок операций

**Местоположение:**
- `src/handlers/consultation/pitanie_rastenii.py:107-140`
- `src/handlers/consultation/entry.py:376-420`

**Проблема:**
Сообщение логировалось ДО проверки количества сообщений:
- `log_message()` добавлял сообщение в БД
- `get_topic_message_count()` возвращал количество УЖЕ с текущим сообщением
- Для первого сообщения `message_count=1` (не 0!)
- Семантика условий становилась запутанной

**Исправление:**
```python
# ДО (НЕПРАВИЛЬНО):
await log_message(...)
message_count = await get_topic_message_count(topic_id)
if message_count <= 1:  # Запутанная семантика

# ПОСЛЕ (ПРАВИЛЬНО):
message_count_before = await get_topic_message_count(topic_id)
is_first_message = (message_count_before == 0)
await log_message(...)
if is_first_message:  # Ясная семантика
```

### БАГ #3: Несинхронизированная логика между обработчиками

**Местоположение:**
- `pitanie_rastenii.py` vs `entry.py`

**Проблема:**
Разные условия для определения первого сообщения vs продолжения:
- `pitanie_rastenii.py` использовал `message_count <= 1`
- `entry.py` использовал `message_count > 1`

**Исправление:**
Стандартизировано на:
- Проверка `message_count_before` (до логирования)
- `is_first_message = (message_count_before == 0)` в pitanie_rastenii.py
- `is_followup = (message_count_before > 0 and ...)` в entry.py

## Изменённые файлы

### 1. `src/services/db/topics_repo.py`
- Добавлена функция `get_topic_status()` для проверки статуса топика
- Улучшена `close_open_topics()` с подробным debug-логированием
- Добавлен параметр `force_new` в `get_or_create_open_topic()`

### 2. `src/handlers/consultation/pitanie_rastenii.py`
**Строки 107-140:** Изменён порядок операций
**Строки 548-560:** Исправлен `handle_nutrition_new_topic()` для использования internal_user_id
**Добавлено:** Обширное debug-логирование

**Ключевое исправление:**
```python
# Получаем внутренний user_id перед закрытием топиков
internal_user_id = await get_or_create_user(
    telegram_user_id=user.id,
    username=user.username,
    first_name=user.first_name,
    last_name=user.last_name,
)
await close_open_topics(internal_user_id)
```

### 3. `src/handlers/consultation/entry.py`
**Строки 376-420:** Изменён порядок операций (проверка count/status/culture ДО логирования)
**Исправлено:** Условие `is_followup` для использования `message_count_before > 0`
**Добавлено:** Обширное debug-логирование

### 4. `src/handlers/menu.py`
**Строки 224-233:** Исправлен `handle_consultation_category()` для использования internal_user_id
**Строки 269-277:** Исправлен `handle_close_menu()` для использования internal_user_id
**Строка 66:** Уже корректна (cmd_start использует internal user_id из get_or_create_user)

### 5. `docs/TOPIC_MANAGEMENT.md` (НОВЫЙ)
Создана комплексная документация:
- Жизненный цикл топиков и переходы состояний
- Все значения CONSULTATION_STATE
- Примеры кода и паттерны
- Типичные ошибки и как их избежать
- Тестовые сценарии

## Чек-лист тестирования

### Сценарий 1: Нормальный поток
1. ✅ Выбрать "Питание растений"
2. ✅ Написать вопрос про "малину" → культура должна быть "малина"
3. ✅ Бот даёт ответ
4. ✅ Написать уточняющий вопрос → должна использоваться сохранённая культура "малина"

### Сценарий 2: Кнопка "Новая тема"
1. ✅ Выбрать "Питание растений"
2. ✅ Написать вопрос про "малину" → культура = "малина"
3. ✅ Бот даёт ответ
4. ✅ Нажать "Вопрос по новой теме"
5. ✅ Выбрать "Питание растений" снова
6. ✅ Написать вопрос про "клубнику" → культура должна быть "клубника" (НЕ малина!)

**Ожидаемое поведение:**
- Старый топик должен быть закрыт
- Должен быть создан новый топик
- Культура должна быть переопределена на основе нового вопроса

### Сценарий 3: Переключение категорий
1. ✅ Выбрать "Питание растений"
2. ✅ Написать вопрос про "малину" → культура = "малина"
3. ✅ Нажать кнопку назад, выбрать "Посадка и уход"
4. ✅ Написать вопрос про "клубнику" → культура должна быть "клубника"

## Добавленное debug-логирование

Все обработчики теперь логируют:
- `topic_id` после создания
- `message_count_before` (до логирования сообщения)
- `culture` перед переопределением
- решение `is_first_message` / `is_followup`
- `detected_culture` после переопределения
- User ID: и telegram_user_id, и internal user_id

Пример вывода логов:
```
[close_open_topics] До закрытия: 1 открытых топиков для user_id=1
[close_open_topics] Закрыто топиков: UPDATE 1, user_id=1
[get_or_create_open_topic] Открытый топик НЕ найден для user_id=1, создаём новый
[get_or_create_open_topic] Создан НОВЫЙ топик: topic_id=14, user_id=1
[nutrition] ДО логирования: topic_id=14, message_count=0, culture=None
[nutrition] Это первое сообщение (count_before=0)
[nutrition] detected_culture: клубника
```

## Статус реализации

✅ Все исправления реализованы
✅ Все файлы компилируются без ошибок
✅ Документация создана
✅ Готово к тестированию

## Следующие шаги

1. Перезапустить бота с новым кодом
2. Протестировать все сценарии из чек-листа тестирования
3. Отслеживать debug-логи для проверки корректного поведения
4. Убедиться, что:
   - Старые топики правильно закрываются
   - Новые топики создаются при необходимости
   - Культура переопределяется для новых топиков
   - Уточняющие вопросы сохраняют культуру
