# Многоэтапный поток консультаций

Документация по системе многоэтапных консультаций с автоматическим определением культуры и управлением состояниями пользователя.

## Оглавление

1. [Обзор](#обзор)
2. [Архитектура состояний](#архитектура-состояний)
3. [Три сценария обработки](#три-сценария-обработки)
4. [Уточнение типа культуры](#уточнение-типа-культуры)
5. [Управление контекстом](#управление-контекстом)
6. [Интеграция с RAG](#интеграция-с-rag)
7. [Примеры потоков](#примеры-потоков)
8. [Связанные документы](#связанные-документы)
9. [Файлы в проекте](#файлы-в-проекте)

---

## Обзор

Система консультаций использует **конечный автомат состояний** для управления многоэтапными диалогами. В зависимости от определённой культуры бот может:

- Задать уточняющие вопросы БЕЗ использования RAG
- Запросить тип культуры (летняя/ремонтантная)
- Дать финальный ответ С использованием RAG

### Основные компоненты

```
┌─────────────────────────────────────────────────────────────┐
│                    CONSULTATION FLOW                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Определение культуры (detect_culture_name)              │
│           ↓                                                 │
│  2. Проверка типа культуры:                                 │
│     • не определено / общая информация                      │
│     • клубника общая / малина общая                         │
│     • конкретная культура                                   │
│           ↓                                                 │
│  3. Выбор сценария обработки                                │
│           ↓                                                 │
│  4. Управление состоянием + контекстом                      │
│           ↓                                                 │
│  5. Вызов LLM (с RAG или без)                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Архитектура состояний

### Словари состояний

Система использует два глобальных словаря для отслеживания состояния пользователя:

```python
# src/handlers/common.py

# Состояние консультации: telegram_user_id -> название состояния
CONSULTATION_STATE: Dict[int, str] = {}

# Контекст консультации: telegram_user_id -> данные
CONSULTATION_CONTEXT: Dict[int, Dict[str, Any]] = {}
```

### Возможные состояния

| Состояние | Описание | Триггер |
|-----------|----------|---------|
| `waiting_variety_clarification` | Ожидание ответа на вопрос о типе культуры (летняя/ремонтантная) | Определена общая культура (клубника общая, малина общая) |
| `waiting_clarification_answer` | Ожидание ответа на уточняющий вопрос LLM | LLM задал уточняющий вопрос при неопределённой культуре |
| *(отсутствует)* | Обычная обработка без активного состояния | Культура конкретна или первое сообщение |

### Структура контекста

```python
CONSULTATION_CONTEXT[telegram_user_id] = {
    "category": "общая консультация",
    "root_question": "Как подкормить малину?",
    "culture": "малина общая",
    "user_id": 123,
    "topic_id": 456,
    "session_id": "tg:987654321",
    "telegram_user_id": 987654321,
}
```

---

## Три сценария обработки

### CASE 1: Культура неясна

**Условие:** `culture in ("не определено", "общая информация")`

**Логика:**
1. Вызов LLM **БЕЗ RAG** (`skip_rag=True`)
2. Проверка, является ли ответ уточняющим вопросом
3. Если да — переход в состояние `waiting_clarification_answer`
4. Если нет — финальный ответ, логирование

```python
# src/handlers/consultation/entry.py

# CASE 1: Культура неясна → уточняющие вопросы БЕЗ RAG
if culture in ("не определено", "общая информация"):
    reply_text = await ask_consultation_llm(
        user_id=user_id,
        telegram_user_id=telegram_user_id,
        text=user_text,
        session_id=session_id,
        consultation_category="общая консультация",
        culture=culture,
        skip_rag=True,  # БЕЗ RAG!
    )

    # Проверка на уточняющий вопрос
    if is_clarification_question(reply_text):
        CONSULTATION_STATE[telegram_user_id] = "waiting_clarification_answer"
        CONSULTATION_CONTEXT[telegram_user_id] = {
            "category": "общая консультация",
            "root_question": user_text,
            "culture": culture,
            "user_id": user_id,
            "topic_id": topic_id,
            "session_id": session_id,
            "telegram_user_id": telegram_user_id,
        }
        # Логируем уточняющий вопрос, НЕ добавляем в moderation
        return
```

**Функция определения уточняющего вопроса:**

```python
def is_clarification_question(text: str) -> bool:
    """
    Определяет, является ли ответ LLM уточняющим вопросом.

    Признаки:
    - Короткий ответ (< 300 символов)
    - Содержит типичные фразы или вопросительный знак
    """
    return (
        len(text) < 300 and
        (
            "уточните" in text.lower()
            or "о какой культуре" in text.lower()
            or "какая у вас" in text.lower()
            or "?" in text
        )
    )
```

---

### CASE 2: Общая культура (клубника/малина)

**Условие:** `culture in ("клубника общая", "малина общая")`

**Логика:**
1. Формирование вопроса о типе культуры
2. Переход в состояние `waiting_variety_clarification`
3. Сохранение контекста с корневым вопросом

```python
# CASE 2: Культура общая → запрос типа
elif culture in ("клубника общая", "малина общая"):
    if culture == "клубника общая":
        variety_question = "Какая у вас клубника: летняя (июньская) или ремонтантная (НСД)?"
    else:  # малина общая
        variety_question = "Какая у вас малина: летняя (обычная) или ремонтантная?"

    CONSULTATION_STATE[telegram_user_id] = "waiting_variety_clarification"
    CONSULTATION_CONTEXT[telegram_user_id] = {
        "category": "общая консультация",
        "root_question": user_text,
        "culture": culture,
        "user_id": user_id,
        "topic_id": topic_id,
        "session_id": session_id,
        "telegram_user_id": telegram_user_id,
    }

    await message.answer(variety_question)
    return  # НЕ логируем системный вопрос
```

**Диаграмма потока:**

```
Пользователь: "Как подкормить клубнику?"
       ↓
  Определена культура: "клубника общая"
       ↓
  Бот: "Какая у вас клубника: летняя (июньская) или ремонтантная (НСД)?"
       ↓
  Состояние: waiting_variety_clarification
       ↓
  Пользователь: "Летняя"
       ↓
  Уточнённая культура: "клубника летняя"
       ↓
  Финальный ответ С RAG
```

---

### CASE 3: Конкретная культура

**Условие:** Все остальные случаи (конкретная культура определена)

**Логика:**
1. Вызов LLM **С RAG** (`skip_rag=False`)
2. Отправка финального ответа
3. Логирование в БД
4. Добавление в очередь модерации

```python
# CASE 3: Культура конкретна → финальный ответ С RAG
else:
    reply_text = await ask_consultation_llm(
        user_id=user_id,
        telegram_user_id=telegram_user_id,
        text=user_text,
        session_id=session_id,
        consultation_category="общая консультация",
        culture=culture,
        skip_rag=False,  # С RAG!
    )

    await message.answer(reply_text)

    # Логируем ответ
    await log_message(
        user_id=user_id,
        direction="bot",
        text=reply_text,
        session_id=session_id,
        topic_id=topic_id,
    )

    # Добавляем в moderation
    await moderation_add(
        user_id=user_id,
        topic_id=topic_id,
        question=user_text,
        answer=reply_text,
        category_guess=None,
    )
```

---

## Уточнение типа культуры

### Обработчик 1: Ответ на вопрос о типе

```python
@router.message(
    lambda m: m.from_user is not None
    and CONSULTATION_STATE.get(m.from_user.id) == "waiting_variety_clarification"
)
async def handle_variety_clarification(message: Message) -> None:
    """
    Обрабатывает ответ пользователя на вопрос о типе культуры.

    Примеры ответов:
    - "Летняя" → клубника летняя / малина летняя
    - "Ремонтантная" → клубника ремонтантная / малина ремонтантная
    - "НСД" → клубника ремонтантная / малина ремонтантная
    """
```

**Логика распознавания типа:**

```python
variety_answer = (message.text or "").lower()

# Ремонтантная
if "ремонтант" in variety_answer or "нсд" in variety_answer:
    if old_culture == "клубника общая":
        new_culture = "клубника ремонтантная"
    else:  # малина общая
        new_culture = "малина ремонтантная"

# Летняя
elif "летн" in variety_answer or "обычн" in variety_answer or "традицион" in variety_answer or "июньск" in variety_answer:
    if old_culture == "клубника общая":
        new_culture = "клубника летняя"
    else:  # малина общая
        new_culture = "малина летняя"

# Не удалось распознать - повторная классификация
else:
    combined_text = f"{root_question} {variety_answer}"
    new_culture = await detect_culture_name(combined_text)
```

**После уточнения:**

1. Обновление культуры в БД (`set_topic_culture`)
2. Логирование ответа пользователя
3. Формирование полного вопроса
4. Вызов LLM **С RAG**
5. Очистка состояния

```python
# Обновляем культуру
await set_topic_culture(topic_id, new_culture)

# Логируем ответ пользователя
await log_message(
    user_id=user_id,
    direction="user",
    text=variety_answer,
    session_id=session_id,
    topic_id=topic_id,
)

# Полный вопрос для LLM
full_question = f"{root_question} ({variety_answer})"

# Финальный ответ С RAG
reply_text = await ask_consultation_llm(
    user_id=user_id,
    telegram_user_id=telegram_user_id,
    text=full_question,
    session_id=session_id,
    consultation_category="общая консультация",
    culture=new_culture,
    skip_rag=False,  # С RAG!
)

# Очистка состояния
CONSULTATION_STATE.pop(telegram_user_id, None)
CONSULTATION_CONTEXT.pop(telegram_user_id, None)
```

---

### Обработчик 2: Ответ на уточняющие вопросы LLM

```python
@router.message(
    lambda m: m.from_user is not None
    and CONSULTATION_STATE.get(m.from_user.id) == "waiting_clarification_answer"
)
async def handle_clarification_answer(message: Message) -> None:
    """
    Обрабатывает ответ пользователя на уточняющие вопросы LLM.

    Сценарии:
    1. Культура всё ещё неясна → запрос снова
    2. Культура общая (клубника/малина общая) → переход в waiting_variety_clarification
    3. Культура конкретна → финальный ответ С RAG
    """
```

**Логика переопределения культуры:**

```python
# Комбинируем корневой вопрос + ответ пользователя
combined_text = f"{root_question} {clarification_answer}"
new_culture = await detect_culture_name(combined_text)

# Обновляем культуру в БД
await set_topic_culture(topic_id, new_culture)
```

**Три ветки после переопределения:**

```python
# 1. Культура всё ещё неясна
if new_culture in ("не определено", "общая информация"):
    await message.answer("Уточните, пожалуйста, о какой конкретно культуре идёт речь?")
    # Оставляем состояние без изменений
    return

# 2. Культура общая → запрос типа
elif new_culture in ("клубника общая", "малина общая"):
    if new_culture == "клубника общая":
        variety_question = "Какая у вас клубника: летняя (июньская) или ремонтантная (НСД)?"
    else:
        variety_question = "Какая у вас малина: летняя (обычная) или ремонтантная?"

    CONSULTATION_STATE[telegram_user_id] = "waiting_variety_clarification"
    CONSULTATION_CONTEXT[telegram_user_id]["culture"] = new_culture
    CONSULTATION_CONTEXT[telegram_user_id]["root_question"] = full_question

    await message.answer(variety_question)
    return

# 3. Культура конкретна → финальный ответ С RAG
else:
    reply_text = await ask_consultation_llm(
        user_id=user_id,
        telegram_user_id=telegram_user_id,
        text=full_question,
        session_id=session_id,
        consultation_category="общая консультация",
        culture=new_culture,
        skip_rag=False,  # С RAG!
    )
    # ... логирование, moderation, очистка состояния
```

---

## Управление контекстом

### Определение followup-вопроса

```python
# Проверка ПЕРЕД логированием сообщения!
message_count_before = await get_topic_message_count(topic_id)
topic_status = await get_topic_status(topic_id)
culture = await get_topic_culture(topic_id)

# Это followup только если:
# 1. Топик открыт
# 2. Культура уже определена
# 3. Нет активного состояния
# 4. В топике УЖЕ ЕСТЬ сообщения
is_followup = (
    topic_status == "open"
    and culture is not None
    and telegram_user_id not in CONSULTATION_STATE
    and message_count_before > 0
)
```

### Логика переопределения культуры

```python
if is_followup:
    # Уточняющий вопрос в рамках темы - используем сохранённую культуру
    print(f"[CULTURE] Используем сохранённую культуру: {culture}")
else:
    # Новый вопрос - переопределяем культуру
    detected_culture = await detect_culture_name(user_text)
    if detected_culture:
        await set_topic_culture(topic_id, detected_culture)
        culture = detected_culture
    else:
        await set_topic_culture(topic_id, "не определено")
        culture = "не определено"
```

---

## Интеграция с RAG

### Условия использования RAG

| Сценарий | RAG | Причина |
|----------|-----|---------|
| Культура неясна (CASE 1) | ❌ | Нельзя выбрать релевантные документы без знания культуры |
| Уточняющий вопрос LLM | ❌ | Бот собирает информацию, а не отвечает |
| Общая культура (CASE 2) | ❌ | Системный вопрос о типе культуры |
| Конкретная культура (CASE 3) | ✅ | Полная информация для поиска в базе знаний |
| После уточнения типа | ✅ | Культура уточнена до конкретной |

### Вызов LLM с RAG

```python
# src/services/llm/consultation_llm.py

async def ask_consultation_llm(
    user_id: int,
    telegram_user_id: int,
    text: str,
    session_id: str,
    consultation_category: str = "общая консультация",
    culture: str = "не определено",
    skip_rag: bool = False,  # КЛЮЧЕВОЙ ПАРАМЕТР
) -> str:
    # Если skip_rag=True, не вызываем RAG
    if skip_rag:
        kb_snippets = []
    else:
        # Извлечение из базы знаний
        kb_snippets = await retrieve_kb_snippets(
            query_text=text,
            category=consultation_category,
            subcategory=culture,
            limit=5,
        )

    # Формирование промпта с учётом RAG
    system_prompt = await build_consultation_system_prompt(
        culture=culture,
        kb_snippets=kb_snippets,
        consultation_category=consultation_category,
    )

    # Вызов OpenAI
    return await create_chat_completion(messages=messages, ...)
```

---

## Примеры потоков

### Пример 1: Неопределённая культура

```
[1] Пользователь: "Как правильно подкармливать?"
       ↓
    culture = "не определено" (CASE 1)
       ↓
    LLM (БЕЗ RAG): "О какой культуре речь? Клубника, малина, смородина?"
       ↓
    Состояние: waiting_clarification_answer

[2] Пользователь: "Про малину"
       ↓
    Комбинированный текст: "Как правильно подкармливать? Про малину"
       ↓
    detect_culture_name() → "малина общая" (CASE 2)
       ↓
    Бот: "Какая у вас малина: летняя (обычная) или ремонтантная?"
       ↓
    Состояние: waiting_variety_clarification

[3] Пользователь: "Ремонтантная"
       ↓
    new_culture = "малина ремонтантная"
       ↓
    full_question = "Как правильно подкармливать? Про малину (Ремонтантная)"
       ↓
    LLM (С RAG) → Финальный детальный ответ
       ↓
    Очистка состояния
```

### Пример 2: Общая культура

```
[1] Пользователь: "Когда обрезать клубнику?"
       ↓
    culture = "клубника общая" (CASE 2)
       ↓
    Бот: "Какая у вас клубника: летняя (июньская) или ремонтантная (НСД)?"
       ↓
    Состояние: waiting_variety_clarification

[2] Пользователь: "Летняя"
       ↓
    new_culture = "клубника летняя"
       ↓
    full_question = "Когда обрезать клубнику? (Летняя)"
       ↓
    LLM (С RAG) → Финальный ответ с учётом типа клубники
```

### Пример 3: Конкретная культура сразу

```
[1] Пользователь: "Как ухаживать за голубикой?"
       ↓
    culture = "голубика" (CASE 3)
       ↓
    LLM (С RAG) → Финальный ответ сразу
       ↓
    Логирование + moderation
```

### Пример 4: Followup-вопрос

```
[1] Пользователь: "Как подкормить малину ремонтантную?"
       ↓
    culture = "малина ремонтантная"
    topic_id = 123, message_count = 0
       ↓
    Новый вопрос → переопределяем культуру
       ↓
    LLM (С RAG) → Финальный ответ

[2] Пользователь: "А в какое время лучше?"
       ↓
    topic_id = 123, message_count = 2
    culture = "малина ремонтантная" (сохранённая)
       ↓
    is_followup = True → используем сохранённую культуру
       ↓
    LLM (С RAG) → Ответ в контексте той же культуры
```

---

## Связанные документы

- [Классификация культур](./CLASSIFICATION.md) - Детали работы `detect_culture_name()`
- [RAG система](./RAG_SYSTEM.md) - Извлечение из базы знаний
- [Управление темами](./TOPIC_MANAGEMENT.md) - Логика session_id и topics
- [Модерация](./MODERATION.md) - Добавление Q&A в очередь модерации

---

## Файлы в проекте

### Основные обработчики

- `/Users/denis/Desktop/Main/Sadovniki-bot/Sadovniki_bot1.2/src/handlers/consultation/entry.py` - Точка входа для всех консультаций
- `/Users/denis/Desktop/Main/Sadovniki-bot/Sadovniki_bot1.2/src/handlers/common.py` - Управление состояниями и контекстом

### Сервисы

- `/Users/denis/Desktop/Main/Sadovniki-bot/Sadovniki_bot1.2/src/services/llm/consultation_llm.py` - Вызов LLM с RAG
- `/Users/denis/Desktop/Main/Sadovniki-bot/Sadovniki_bot1.2/src/services/llm/classification_llm.py` - Определение культуры
- `/Users/denis/Desktop/Main/Sadovniki-bot/Sadovniki_bot1.2/src/services/rag/kb_retriever.py` - Поиск в базе знаний

### Репозитории БД

- `/Users/denis/Desktop/Main/Sadovniki-bot/Sadovniki_bot1.2/src/services/db/topics_repo.py` - Управление темами
- `/Users/denis/Desktop/Main/Sadovniki-bot/Sadovniki_bot1.2/src/services/db/messages_repo.py` - Логирование сообщений
- `/Users/denis/Desktop/Main/Sadovniki-bot/Sadovniki_bot1.2/src/services/db/moderation_repo.py` - Очередь модерации

### Промпты

- `/Users/denis/Desktop/Main/Sadovniki-bot/Sadovniki_bot1.2/src/prompts/consultation_prompts.py` - Построение системных промптов
