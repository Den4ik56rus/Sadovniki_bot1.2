# Модерация базы знаний

## Краткое описание

Система модерации позволяет администраторам просматривать, редактировать и одобрять Q&A пары из консультаций для добавления в базу знаний. Включает LLM-редактор, автоматическое определение категорий и регенерацию эмбеддингов при одобрении.

## Оглавление

1. [Workflow модерации](#workflow-модерации)
2. [Очередь модерации](#очередь-модерации)
3. [Админские команды](#админские-команды)
4. [Редактирование с LLM](#редактирование-с-llm)
5. [Управление категориями](#управление-категориями)
6. [Связанные документы](#связанные-документы)
7. [Файлы в проекте](#файлы-в-проекте)

---

## Workflow модерации

```
┌──────────────────────────────────────────────────────┐
│  1. Автоматическое добавление в очередь              │
│     После каждой консультации: moderation_add()      │
│     Статус: pending                                  │
└───────────────────┬──────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────┐
│  2. Админ открывает /kb_pending                      │
│     Показываются все записи со статусом pending      │
└───────────────────┬──────────────────────────────────┘
                    │
         ┌──────────┴──────────┬────────────────┐
         │                     │                │
         ▼                     ▼                ▼
┌────────────────┐   ┌─────────────────┐   ┌────────────┐
│  ОДОБРИТЬ      │   │  РЕДАКТИРОВАТЬ  │   │  ОТКЛОНИТЬ │
└────────┬───────┘   └────────┬────────┘   └─────┬──────┘
         │                    │                   │
         ▼                    ▼                   ▼
┌────────────────┐   ┌─────────────────┐   ┌────────────┐
│ Генерация      │   │ LLM-редактор    │   │ Статус:    │
│ эмбеддинга     │   │ + инструкции    │   │ rejected   │
│                │   │                 │   │            │
│ Вставка в      │   │ Повторная       │   │ Запись     │
│ knowledge_base │   │ проверка        │   │ удаляется  │
│                │   │                 │   │ из очереди │
│ Статус:        │   └────────┬────────┘   └────────────┘
│ approved       │            │
│                │            ▼
│ kb_id сохранён │   ┌─────────────────┐
└────────────────┘   │ Админ одобряет  │
                     │ или отклоняет   │
                     └─────────────────┘
```

---

## Очередь модерации

### Таблица `moderation_queue`

```sql
CREATE TABLE moderation_queue (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    topic_id INTEGER REFERENCES topics(id),
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    category_guess TEXT,  -- Автоматически определённая категория
    status TEXT DEFAULT 'pending',  -- pending / approved / rejected
    admin_id INTEGER REFERENCES users(id),
    kb_id INTEGER REFERENCES knowledge_base(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Автоматическое добавление

```python
# src/handlers/consultation/entry.py

# После финального ответа бота
await moderation_add(
    user_id=user_id,
    topic_id=topic_id,
    question=user_text,
    answer=reply_text,
    category_guess=None,
)
```

---

## Админские команды

### /admin — Панель администратора

```python
@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """
    Показывает админ-панель с кнопками:
    - Очередь модерации (/kb_pending)
    - Управление терминологией (/terms)
    - Статистика
    """
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return
    
    keyboard = admin_main_keyboard()
    await message.answer("Панель администратора:", reply_markup=keyboard)
```

### /kb_pending — Очередь модерации

```python
@router.message(Command("kb_pending"))
async def cmd_kb_pending(message: Message):
    """
    Показывает все записи в очереди модерации (status='pending').
    
    Для каждой записи:
    - Вопрос пользователя
    - Ответ бота
    - Кнопки: [Одобрить] [Редактировать] [Отклонить]
    """
    items = await get_pending_moderation_items()
    
    if not items:
        await message.answer("Очередь модерации пуста.")
        return
    
    for item in items:
        text = f"**Вопрос:** {item['question']}\n\n**Ответ:** {item['answer']}"
        keyboard = moderation_item_keyboard(item['id'])
        await message.answer(text, reply_markup=keyboard)
```

---

## Редактирование с LLM

### Workflow редактирования

```python
# Админ нажимает кнопку "Редактировать"
@router.callback_query(F.data.startswith("mod_edit_"))
async def handle_edit_request(callback: CallbackQuery):
    """
    Запрашивает у админа инструкции по редактированию.
    """
    item_id = int(callback.data.split("_")[2])
    
    # Сохраняем ID в состояние
    EDIT_STATE[admin_user_id] = item_id
    
    await callback.message.answer(
        "Введите инструкции по редактированию ответа (например: 'Сократить до 3 абзацев, убрать лишние детали'):"
    )
```

### LLM-редактор

```python
@router.message(lambda m: m.from_user.id in EDIT_STATE)
async def handle_edit_instructions(message: Message):
    """
    Получает инструкции и вызывает LLM для редактирования.
    """
    item_id = EDIT_STATE.pop(message.from_user.id)
    instructions = message.text
    
    # Получаем исходный ответ
    item = await get_moderation_item(item_id)
    original_answer = item['answer']
    
    # Вызываем LLM
    edited_answer = await edit_answer_with_llm(
        original_answer=original_answer,
        instructions=instructions,
    )
    
    # Обновляем в БД
    await update_moderation_answer(item_id, edited_answer)
    
    await message.answer(f"Ответ отредактирован:\n\n{edited_answer}")
```

### Промпт для редактирования

```python
async def edit_answer_with_llm(original_answer: str, instructions: str) -> str:
    """
    Использует LLM для редактирования ответа согласно инструкциям.
    """
    messages = [
        {
            "role": "system",
            "content": "Ты редактор текста. Отредактируй ответ согласно инструкциям, сохранив точность информации."
        },
        {
            "role": "user",
            "content": f"Исходный ответ:\n{original_answer}\n\nИнструкции:\n{instructions}"
        }
    ]
    
    return await create_chat_completion(messages=messages, temperature=0.3)
```

---

## Управление категориями

### Автоматическое определение категории

При добавлении в очередь система пытается определить категорию:

```python
# Простейшая эвристика
category_guess = None
if "подкорм" in question.lower() or "удобр" in question.lower():
    category_guess = "питание растений"
elif "болезн" in question.lower() or "вредител" in question.lower():
    category_guess = "защита растений"
elif "посад" in question.lower() or "уход" in question.lower():
    category_guess = "посадка и уход"
```

### Ручное указание категории

```python
@router.callback_query(F.data.startswith("mod_category_"))
async def handle_category_selection(callback: CallbackQuery):
    """
    Админ выбирает категорию перед одобрением.
    """
    item_id, category = parse_callback_data(callback.data)
    
    await update_moderation_category(item_id, category)
    await callback.answer(f"Категория установлена: {category}")
```

### Одобрение с регенерацией эмбеддинга

```python
@router.callback_query(F.data.startswith("mod_approve_"))
async def handle_approve(callback: CallbackQuery):
    """
    Одобряет Q&A пару и добавляет в knowledge_base.
    """
    item_id = int(callback.data.split("_")[2])
    item = await get_moderation_item(item_id)
    
    # Генерация эмбеддинга
    embedding = await get_text_embedding(item['question'])
    
    # Вставка в knowledge_base
    kb_id = await kb_insert(
        category=item['category_guess'] or "общая консультация",
        subcategory=item.get('culture'),
        question=item['question'],
        answer=item['answer'],
        embedding=embedding,
        source_type="moderation",
    )
    
    # Обновление статуса
    await approve_moderation_item(
        item_id=item_id,
        admin_id=callback.from_user.id,
        kb_id=kb_id,
    )
    
    await callback.answer("✅ Добавлено в базу знаний!")
```

---

## Связанные документы

- [../architecture/DATABASE.md](../architecture/DATABASE.md) — Таблицы moderation_queue и knowledge_base
- [CONSULTATION_FLOW.md](./CONSULTATION_FLOW.md) — Автоматическое добавление в очередь
- [../architecture/LLM_INTEGRATION.md](../architecture/LLM_INTEGRATION.md) — LLM-редактор

---

## Файлы в проекте

- src/handlers/admin/moderation.py — Админ-панель и workflow модерации (строки 271-925)
- src/services/db/moderation_repo.py — Операции с moderation_queue
- src/keyboards/admin/moderation_keyboard.py — Клавиатуры для модерации
- src/config.py — ADMIN_IDS

**Версия:** 1.0  
**Дата:** 2025-12-05
