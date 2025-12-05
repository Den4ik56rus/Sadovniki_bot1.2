# Управление терминологией

## Краткое описание

Словарь терминов позволяет администраторам задавать предпочитаемые формулировки, которые автоматически инжектируются в системные промпты LLM. Workflow: term → preferred_phrase → инъекция в промпт.

## Оглавление

1. [Назначение](#назначение)
2. [Структура таблицы](#структура-таблицы)
3. [Админский интерфейс](#админский-интерфейс)
4. [Инъекция в промпты](#инъекция-в-промпты)
5. [Примеры использования](#примеры-использования)
6. [Связанные документы](#связанные-документы)
7. [Файлы в проекте](#файлы-в-проекте)

---

## Назначение

Система терминологии решает задачу **единообразия формулировок** в ответах бота:

**Проблема:** Бот может использовать разные формулировки для одного понятия.

**Решение:** Админ задаёт правило: "навоз" → "удобрения естественного происхождения"

**Результат:** LLM автоматически использует предпочитаемую формулировку.

---

## Структура таблицы

```sql
CREATE TABLE terminology (
    id SERIAL PRIMARY KEY,
    term VARCHAR(255) NOT NULL,
    preferred_phrase TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_terminology_term ON terminology(term);

-- Примеры
INSERT INTO terminology (term, preferred_phrase, description) VALUES
('навоз', 'удобрения естественного происхождения', 'Вместо слова "навоз"'),
('помёт', 'органические азотные удобрения', 'Вместо "помёт"');
```

---

## Админский интерфейс

### Команды

```
/terms          - Показать все термины
/add_term       - Добавить новый термин
/delete_term    - Удалить термин
```

### Добавление термина

```python
@router.message(Command("add_term"))
async def cmd_add_term(message: Message):
    """
    Двухшаговый процесс:
    1. Админ вводит term
    2. Админ вводит preferred_phrase
    """
    if not is_admin(message.from_user.id):
        return
    
    TERM_STATE[message.from_user.id] = "waiting_term"
    await message.answer("Введите термин (например: навоз):")

@router.message(lambda m: TERM_STATE.get(m.from_user.id) == "waiting_term")
async def handle_term_input(message: Message):
    term = message.text
    TERM_CONTEXT[message.from_user.id] = {"term": term}
    TERM_STATE[message.from_user.id] = "waiting_phrase"
    await message.answer(f"Термин: {term}\nТеперь введите предпочитаемую формулировку:")

@router.message(lambda m: TERM_STATE.get(m.from_user.id) == "waiting_phrase")
async def handle_phrase_input(message: Message):
    preferred_phrase = message.text
    context = TERM_CONTEXT.pop(message.from_user.id)
    term = context["term"]
    
    await add_term(term=term, preferred_phrase=preferred_phrase)
    
    await message.answer(f"✅ Добавлено:\n{term} → {preferred_phrase}")
    TERM_STATE.pop(message.from_user.id)
```

---

## Инъекция в промпты

### Загрузка терминологии

```python
# src/prompts/consultation_prompts.py (строки 80-98)

async def build_consultation_system_prompt(
    culture: str,
    kb_snippets: List[Dict],
    consultation_category: str,
    ...
) -> str:
    # Загрузка всех терминов
    terms = await get_all_terms()
    
    # Формирование секции терминологии
    if terms:
        terminology_section = "\n## ТЕРМИНОЛОГИЯ (используй эти формулировки):\n\n"
        for term_row in terms:
            terminology_section += f"- Вместо '{term_row['term']}' используй '{term_row['preferred_phrase']}'\n"
    else:
        terminology_section = ""
    
    # Построение финального промпта
    system_prompt = f"""Ты — профессиональный агроном-консультант.

{terminology_section}

Культура: {culture}
Категория: {consultation_category}

{RAG_контекст}

Отвечай точно, используя предпочитаемые формулировки из терминологии.
"""
    return system_prompt
```

### Пример промпта с терминологией

```
Ты — профессиональный агроном-консультант по ягодным культурам.

## ТЕРМИНОЛОГИЯ (используй эти формулировки):

- Вместо 'навоз' используй 'удобрения естественного происхождения'
- Вместо 'помёт' используй 'органические азотные удобрения'
- Вместо 'куриный помёт' используй 'органическое азотное удобрение птичьего происхождения'

Культура: малина ремонтантная
Категория: питание растений

## БАЗА ЗНАНИЙ:
...

Ответь на вопрос пользователя.
```

---

## Примеры использования

### До внедрения терминологии

**Вопрос:** "Можно ли использовать навоз для подкормки?"

**Ответ бота:** "Да, навоз — отличное органическое удобрение..."

### После внедрения терминологии

**Админ добавляет:** `навоз` → `удобрения естественного происхождения`

**Вопрос:** "Можно ли использовать навоз для подкормки?"

**Ответ бота:** "Да, удобрения естественного происхождения — отличный источник питательных веществ..."

---

## Связанные документы

- [../architecture/DATABASE.md](../architecture/DATABASE.md) — Таблица terminology
- [../architecture/LLM_INTEGRATION.md](../architecture/LLM_INTEGRATION.md) — Промпт-инжиниринг
- [PROMPTS.md](./PROMPTS.md) — Система промптов

---

## Файлы в проекте

- src/handlers/admin/terminology.py — Админский интерфейс
- src/services/db/terminology_repo.py — get_all_terms(), add_term(), delete_term()
- src/prompts/consultation_prompts.py — Инъекция в промпты (строки 80-98)
- db/schema_terminology.sql — SQL-схема

**Версия:** 1.0  
**Дата:** 2025-12-05
