# RAG-система с трёхуровневым поиском

## Краткое описание

Система Retrieval-Augmented Generation (RAG) использует **трёхуровневую архитектуру приоритетов** для поиска релевантной информации перед генерацией ответа LLM. Приоритет 1: одобренные администратором Q&A пары из `knowledge_base`. Приоритет 2: PDF-документы по конкретной культуре (например, "малина ремонтантная"). Приоритет 3: общие документы по культуре (fallback на "малина общая"). Поиск основан на **векторном сходстве** эмбеддингов с использованием PostgreSQL pgvector.

## Оглавление

1. [Архитектура RAG-системы](#архитектура-rag-системы)
2. [Уровень 1: Q&A пары (knowledge_base)](#уровень-1-qa-пары-knowledge_base)
3. [Уровень 2: Документы по культуре](#уровень-2-документы-по-культуре)
4. [Fallback-логика](#fallback-логика)
5. [Пороги расстояния (distance thresholds)](#пороги-расстояния-distance-thresholds)
6. [Интеграция с LLM](#интеграция-с-llm)
7. [Примеры работы](#примеры-работы)
8. [Связанные документы](#связанные-документы)
9. [Файлы в проекте](#файлы-в-проекте)

---

## Архитектура RAG-системы

### Трёхуровневая иерархия приоритетов

```
┌─────────────────────────────────────────────────────────────┐
│                  Запрос пользователя                        │
│      "Чем подкормить малину ремонтантную весной?"           │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│           Генерация эмбеддинга запроса                      │
│    get_text_embedding(text) → [0.123, -0.456, ..., 0.789]   │
│                   (1536 чисел)                              │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│         retrieve_unified_snippets() - ДВУХУРОВНЕВЫЙ         │
│                      ПОИСК                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ УРОВЕНЬ 1 (priority_level=1): Q&A пары              │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │ Источник: knowledge_base                            │   │
│  │ Поиск: kb_search(category, subcategory, embedding)   │   │
│  │ Порог: distance < 0.6                                │   │
│  │ Лимит: 20 фрагментов                                 │   │
│  │ Fallback: если subcategory пусто → поиск по category │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ УРОВЕНЬ 2 (priority_level=2): Документы по культуре │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │ Источник: document_chunks                           │   │
│  │ Поиск: chunks_search(subcategory, embedding)         │   │
│  │ Порог: distance < 0.75                               │   │
│  │ Лимит: 30 фрагментов                                 │   │
│  │ 2A: Точная культура ("малина ремонтантная")          │   │
│  │ 2B: Общая культура ("малина общая") - fallback       │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                  │
└──────────────────────────┼──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│        Объединение и сортировка результатов                 │
│   all_snippets.sort(key=lambda x: (priority_level, distance))│
│                                                             │
│   Результат: [                                              │
│     {priority_level: 1, distance: 0.23, content: "..."},    │
│     {priority_level: 1, distance: 0.45, content: "..."},    │
│     {priority_level: 2, distance: 0.51, content: "..."},    │
│     {priority_level: 2, distance: 0.68, content: "..."},    │
│   ]                                                         │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│            Инъекция в системный промпт LLM                  │
│  build_consultation_system_prompt(kb_snippets=...)          │
└─────────────────────────────────────────────────────────────┘
```

### Функция `retrieve_unified_snippets()`

**Расположение:** [src/services/rag/unified_retriever.py](../../src/services/rag/unified_retriever.py)

```python
async def retrieve_unified_snippets(
    *,
    category: str,                      # Тип консультации: 'питание растений', 'посадка и уход' и т.п.
    query_embedding: List[float],       # Эмбеддинг запроса (1536 чисел)
    subcategory: Optional[str] = None,  # Культура: 'малина ремонтантная', 'клубника летняя' и т.п.
    qa_limit: int = 2,                  # Макс. Q&A (УРОВЕНЬ 1)
    doc_limit: int = 3,                 # Макс. документы (УРОВЕНЬ 2)
    qa_distance_threshold: float = 0.4, # Порог для Q&A
    doc_distance_threshold: float = 0.35, # Порог для документов
) -> List[Dict[str, Any]]:
    """
    Двухуровневый поиск фрагментов с приоритизацией.

    Возвращает:
        Список словарей с полями:
            - source_type: 'qa' / 'document'
            - priority_level: 1 / 2
            - content: текст фрагмента
            - distance: расстояние до эмбеддинга
    """
```

**Вызов из consultation_llm.py:**

```python
# src/services/llm/consultation_llm.py (строка 175)

kb_snippets = await retrieve_unified_snippets(
    category=consultation_category,  # 'питание растений'
    subcategory=culture,             # 'малина ремонтантная'
    query_embedding=query_embedding,
    qa_limit=20,                     # Увеличено в 10 раз
    doc_limit=30,                    # Увеличено в 10 раз
    qa_distance_threshold=0.6,       # Порог Q&A
    doc_distance_threshold=0.75,     # Порог документов
)
```

---

## Уровень 1: Q&A пары (knowledge_base)

### Назначение

**ВЫСШИЙ ПРИОРИТЕТ:** Одобренные администратором Q&A пары из таблицы `knowledge_base`.

### Архитектура поиска

```python
# src/services/rag/unified_retriever.py (строки 109-147)

# УРОВЕНЬ 1: Q&A пары из knowledge_base
qa_rows = await kb_search(
    category=category,          # 'питание растений'
    subcategory=subcategory,    # 'малина ремонтантная'
    query_embedding=query_embedding,
    limit=qa_limit,             # 20
    distance_threshold=qa_distance_threshold,  # 0.6
)

# Fallback: если с subcategory ничего не нашли
if not qa_rows and subcategory is not None:
    qa_rows = await kb_search(
        category=category,
        subcategory=None,  # Поиск по всей категории
        query_embedding=query_embedding,
        limit=qa_limit,
        distance_threshold=qa_distance_threshold,
    )

# Преобразуем в единый формат
for row in qa_rows:
    all_snippets.append({
        "source_type": "qa",
        "priority_level": 1,  # ВЫСШИЙ ПРИОРИТЕТ
        "content": row["answer"],
        "distance": row["distance"],
        "id": row["id"],
        "category": row["category"],
        "subcategory": row["subcategory"],
        "question": row.get("question"),
    })
```

### SQL-запрос (kb_search)

**Расположение:** [src/services/db/kb_repo.py](../../src/services/db/kb_repo.py)

```sql
SELECT id, category, subcategory, question, answer,
       (embedding <=> $1::vector) AS distance
FROM knowledge_base
WHERE category = $2                 -- 'питание растений'
  AND subcategory = $3              -- 'малина ремонтантная'
  AND is_active = TRUE
ORDER BY embedding <=> $1::vector   -- Сортировка по косинусному расстоянию
LIMIT $4;                           -- 20
```

**Оператор `<=>`:** косинусное расстояние (pgvector)
- Диапазон: `[0, 2]` (0 = идентичные векторы, 2 = противоположные)
- Индекс: HNSW (`CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)`)

### Параметры уровня 1

| Параметр | Значение | Обоснование |
|----------|----------|-------------|
| `qa_limit` | 20 | Увеличено в 10 раз для большего контекста |
| `qa_distance_threshold` | 0.6 | Строгий порог: только высококачественные совпадения |
| `priority_level` | 1 | ВЫСШИЙ приоритет перед документами |

**Почему порог 0.6:**
- Q&A пары одобрены администратором → высокое качество
- Строгий порог предотвращает нерелевантные ответы
- Если distance > 0.6, фрагмент отфильтровывается

---

## Уровень 2: Документы по культуре

### Назначение

**СРЕДНИЙ ПРИОРИТЕТ:** PDF-документы, разбитые на фрагменты (chunks) в таблице `document_chunks`.

### Архитектура поиска

```python
# src/services/rag/unified_retriever.py (строки 154-194)

# УРОВЕНЬ 2: Документы по культуре
if subcategory:
    # Ищем документы с точной subcategory (малина ремонтантная)
    doc_rows = await chunks_search(
        subcategory=subcategory,  # 'малина ремонтантная'
        query_embedding=query_embedding,
        limit=doc_limit,          # 30
        distance_threshold=doc_distance_threshold,  # 0.75
    )

    # Fallback: если не нашли по точной культуре
    if not doc_rows:
        general_subcategory = get_general_subcategory(subcategory)
        # 'малина ремонтантная' → 'малина общая'

        if general_subcategory and general_subcategory != subcategory:
            doc_rows = await chunks_search(
                subcategory=general_subcategory,  # 'малина общая'
                query_embedding=query_embedding,
                limit=doc_limit,
                distance_threshold=doc_distance_threshold,
            )

    # Преобразуем в единый формат
    for row in doc_rows:
        all_snippets.append({
            "source_type": "document",
            "priority_level": 2,  # СРЕДНИЙ ПРИОРИТЕТ
            "content": row["chunk_text"],
            "distance": row["distance"],
            "id": row["id"],
            "document_id": row["document_id"],
            "page_number": row.get("page_number"),
            "subcategory": row["subcategory"],
        })
```

### SQL-запрос (chunks_search)

**Расположение:** [src/services/db/document_chunks_repo.py](../../src/services/db/document_chunks_repo.py)

```sql
SELECT id, document_id, chunk_text, page_number, subcategory,
       (embedding <=> $1::vector) AS distance
FROM document_chunks
WHERE subcategory = $2              -- 'малина ремонтантная'
  AND is_active = TRUE
ORDER BY embedding <=> $1::vector
LIMIT $3;                           -- 30
```

### Параметры уровня 2

| Параметр | Значение | Обоснование |
|----------|----------|-------------|
| `doc_limit` | 30 | Увеличено в 10 раз для большего покрытия документов |
| `doc_distance_threshold` | 0.75 | Более мягкий порог, чем для Q&A (документы могут быть менее точными) |
| `priority_level` | 2 | СРЕДНИЙ приоритет после Q&A |

**Почему порог 0.75:**
- Документы содержат длинный текст → больше шума
- Мягкий порог позволяет находить контекст даже при частичном совпадении
- Если distance > 0.75, фрагмент отфильтровывается

---

## Fallback-логика

### Двухуровневый fallback

```
Запрос: "Чем подкормить малину ремонтантную весной?"
subcategory = "малина ремонтантная"

┌────────────────────────────────────────────────────────┐
│ УРОВЕНЬ 1: Q&A пары                                    │
├────────────────────────────────────────────────────────┤
│ 1. Ищем: category='питание растений'                  │
│          subcategory='малина ремонтантная'             │
│    Результат: 0 записей                                │
│                                                        │
│ 2. Fallback: category='питание растений'               │
│              subcategory=None (все культуры)           │
│    Результат: 3 Q&A пары (общие вопросы по питанию)    │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ УРОВЕНЬ 2: Документы                                   │
├────────────────────────────────────────────────────────┤
│ 1. Ищем: subcategory='малина ремонтантная'             │
│    Результат: 0 фрагментов                             │
│                                                        │
│ 2. Fallback: subcategory='малина общая'                │
│              (через get_general_subcategory)           │
│    Результат: 5 фрагментов из документа                │
│              "data/documents/малина_общая/уход.pdf"    │
└────────────────────────────────────────────────────────┘

Итого найдено: 3 Q&A + 5 документов = 8 фрагментов
```

### Функция `get_general_subcategory()`

**Расположение:** [src/services/rag/unified_retriever.py:22-64](../../src/services/rag/unified_retriever.py)

```python
def get_general_subcategory(subcategory: Optional[str]) -> Optional[str]:
    """
    Преобразует специфичную подкатегорию в общую.

    Примеры:
        малина ремонтантная → малина общая
        малина летняя → малина общая
        клубника ремонтантная → клубника общая
        голубика → голубика (без изменений)
    """
    GENERAL_MAPPING = {
        # Малина
        "малина ремонтантная": "малина общая",
        "малина летняя": "малина общая",
        "малина общая": "малина общая",

        # Клубника
        "клубника ремонтантная": "клубника общая",
        "клубника летняя": "клубника общая",
        "клубника общая": "клубника общая",

        # Остальные культуры (без изменений)
        "голубика": "голубика",
        "смородина": "смородина",
        "жимолость": "жимолость",
        "крыжовник": "крыжовник",
        "ежевика": "ежевика",
        "общая информация": "общая информация",
    }

    return GENERAL_MAPPING.get(subcategory, subcategory)
```

**Почему только малина и клубника имеют общую категорию:**
- Только эти культуры имеют деление: летняя / ремонтантная / общая
- Для остальных культур (голубика, смородина и т.п.) нет подтипов

---

### Логика fallback в коде

**УРОВЕНЬ 1 (Q&A):**

```python
# src/services/rag/unified_retriever.py (строки 124-133)

# Fallback: если с subcategory ничего не нашли
if not qa_rows and subcategory is not None:
    print(f"[УРОВЕНЬ 1] Fallback: ищем Q&A без subcategory...")
    qa_rows = await kb_search(
        category=category,
        subcategory=None,  # Убираем фильтр по культуре
        query_embedding=query_embedding,
        limit=qa_limit,
        distance_threshold=qa_distance_threshold,
    )
```

**УРОВЕНЬ 2 (документы):**

```python
# src/services/rag/unified_retriever.py (строки 170-180)

# Fallback: если не нашли по точной культуре
if not doc_rows:
    general_subcategory = get_general_subcategory(subcategory)
    if general_subcategory and general_subcategory != subcategory:
        print(f"[УРОВЕНЬ 2] Fallback на общую культуру: {general_subcategory}")
        doc_rows = await chunks_search(
            subcategory=general_subcategory,  # 'малина общая'
            query_embedding=query_embedding,
            limit=doc_limit,
            distance_threshold=doc_distance_threshold,
        )
```

---

## Пороги расстояния (distance thresholds)

### Таблица порогов

| Источник | Порог | Логика |
|----------|-------|--------|
| **Q&A пары** (knowledge_base) | 0.6 | Строгий порог: только высокорелевантные ответы |
| **Документы** (document_chunks) | 0.75 | Мягкий порог: допускаем менее точные совпадения |

### Интерпретация расстояния

**Косинусное расстояние (pgvector `<=>` оператор):**

```
distance = 1 - cos(θ)

где θ — угол между векторами
```

| Distance | Косинусное сходство | Интерпретация |
|----------|---------------------|---------------|
| 0.0 - 0.2 | 0.8 - 1.0 | **Отлично:** Очень похожие фрагменты |
| 0.2 - 0.4 | 0.6 - 0.8 | **Хорошо:** Релевантные фрагменты |
| 0.4 - 0.6 | 0.4 - 0.6 | **Средне:** Частично релевантные (граница для Q&A) |
| 0.6 - 0.75 | 0.25 - 0.4 | **Слабо:** Слабое сходство (граница для документов) |
| 0.75+ | < 0.25 | **Нерелевантно:** Отфильтровывается |

### Пример фильтрации

```python
# src/services/db/kb_repo.py (строки 84-95)

async def kb_search(
    *,
    category: str,
    query_embedding: List[float],
    subcategory: Optional[str] = None,
    limit: int = 3,
    distance_threshold: Optional[float] = 0.35,
):
    # SQL-запрос возвращает все результаты с ORDER BY distance
    rows = await conn.fetch(query, vector_str, category, subcategory, limit)

    # Фильтруем по порогу в Python
    if distance_threshold is not None:
        rows = [r for r in rows if r["distance"] < distance_threshold]

    return [dict(r) for r in rows]
```

**Почему фильтруем в Python, а не в SQL:**
- pgvector HNSW индекс не поддерживает `WHERE distance < threshold` эффективно
- Сначала берём top-N по индексу, затем фильтруем в коде

---

## Интеграция с LLM

### Workflow интеграции

```
1. Пользователь задаёт вопрос
        │
        ▼
2. consultation_llm.ask_consultation_llm()
        │
        ├─▶ get_text_embedding(text) → query_embedding
        │
        ├─▶ retrieve_unified_snippets(
        │       category='питание растений',
        │       subcategory='малина ремонтантная',
        │       query_embedding=query_embedding,
        │   )
        │   └─▶ kb_snippets: List[Dict]
        │
        ├─▶ build_consultation_system_prompt(
        │       kb_snippets=kb_snippets,
        │       culture='малина ремонтантная',
        │       ...
        │   )
        │   └─▶ system_prompt: str
        │
        └─▶ create_chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.4
            )
            └─▶ response: str
```

### Инъекция контекста в промпт

**Расположение:** [src/prompts/consultation_prompts.py](../../src/prompts/consultation_prompts.py)

```python
async def build_consultation_system_prompt(
    *,
    culture: str,
    kb_snippets: List[Dict[str, Any]],  # Результаты RAG
    consultation_category: str,
    default_location: str,
    default_growing_type: str,
) -> str:
    """
    Строит системный промпт для LLM с инъекцией RAG-контекста.
    """
    # Начало промпта
    prompt = f"""Ты — профессиональный агроном-консультант...

Текущая культура: {culture}
Категория консультации: {consultation_category}
"""

    # Инъекция RAG-контекста
    if kb_snippets:
        prompt += "\n## БАЗА ЗНАНИЙ (используй эту информацию для ответа):\n\n"
        for idx, snippet in enumerate(kb_snippets, 1):
            source_type = snippet.get("source_type", "unknown")
            priority = snippet.get("priority_level", "?")
            content = snippet.get("content", "")

            prompt += f"### Фрагмент {idx} [УРОВЕНЬ {priority}] [{source_type}]\n"
            prompt += f"{content}\n\n"

    return prompt
```

**Пример инъецированного промпта:**

```
Ты — профессиональный агроном-консультант по ягодным культурам.

Текущая культура: малина ремонтантная
Категория консультации: питание растений

## БАЗА ЗНАНИЙ (используй эту информацию для ответа):

### Фрагмент 1 [УРОВЕНЬ 1] [qa]
Для весенней подкормки малины ремонтантной рекомендуется внести азотные удобрения
в дозе 10-15 г/м² (например, мочевина). Это стимулирует рост новых побегов.

### Фрагмент 2 [УРОВЕНЬ 1] [qa]
В начале вегетации (апрель-май) можно использовать комплексные удобрения типа
Fertika или Кемира с NPK 16-16-16.

### Фрагмент 3 [УРОВЕНЬ 2] [document]
Ремонтантные сорта малины требуют усиленного питания из-за двух волн плодоношения.
Весеннее внесение азота особенно важно для первого урожая на побегах прошлого года.
```

---

## Примеры работы

### Пример 1: Полный контекст

**Запрос:** "Когда обрезать клубнику ремонтантную?"

**RAG-поиск:**

```
[УРОВЕНЬ 1] Поиск Q&A пар...
  category=посадка и уход, subcategory=клубника ремонтантная
[УРОВЕНЬ 1] Найдено Q&A: 2

[УРОВЕНЬ 2] Поиск документов по культуре...
  subcategory=клубника ремонтантная
[УРОВЕНЬ 2] Найдено документов (точная культура): 3

Итого: 5 фрагментов
  #1 [УРОВЕНЬ 1] [qa] distance=0.21
  #2 [УРОВЕНЬ 1] [qa] distance=0.38
  #3 [УРОВЕНЬ 2] [document] distance=0.54
  #4 [УРОВЕНЬ 2] [document] distance=0.62
  #5 [УРОВЕНЬ 2] [document] distance=0.71
```

**Результат:** LLM получает 5 фрагментов контекста и генерирует точный ответ.

---

### Пример 2: Fallback на общую культуру

**Запрос:** "Какие болезни у малины ремонтантной?"

**RAG-поиск:**

```
[УРОВЕНЬ 1] Поиск Q&A пар...
  category=защита растений, subcategory=малина ремонтантная
[УРОВЕНЬ 1] Найдено Q&A: 0

[УРОВЕНЬ 1] Fallback: ищем Q&A без subcategory...
[УРОВЕНЬ 1] Найдено Q&A (fallback): 1

[УРОВЕНЬ 2] Поиск документов по культуре...
  subcategory=малина ремонтантная
[УРОВЕНЬ 2] Найдено документов (точная культура): 0

[УРОВЕНЬ 2] Fallback на общую культуру: малина общая
[УРОВЕНЬ 2] Найдено документов (общая культура): 4

Итого: 5 фрагментов (1 Q&A + 4 документа)
```

**Результат:** Благодаря fallback система находит контекст даже при отсутствии специфичных данных.

---

### Пример 3: Пустая база знаний

**Запрос:** "Как ухаживать за ежевикой?"

**RAG-поиск:**

```
[УРОВЕНЬ 1] Поиск Q&A пар...
  category=посадка и уход, subcategory=ежевика
[УРОВЕНЬ 1] Найдено Q&A: 0

[УРОВЕНЬ 1] Fallback: ищем Q&A без subcategory...
[УРОВЕНЬ 1] Найдено Q&A (fallback): 0

[УРОВЕНЬ 2] Поиск документов по культуре...
  subcategory=ежевика
[УРОВЕНЬ 2] Найдено документов (точная культура): 0

[RAG] ⚠️ НИЧЕГО НЕ НАЙДЕНО в базе знаний!
Возможные причины:
  - База знаний пуста
  - Нет документов для подкатегории 'ежевика'
  - Все найденные фрагменты за порогом distance
```

**Результат:** LLM генерирует ответ **без контекста** (на основе общих знаний модели).

---

## Связанные документы

- [OVERVIEW.md](OVERVIEW.md) — Обзор архитектуры системы
- [DATABASE.md](DATABASE.md) — Векторный поиск с pgvector, HNSW индексы
- [LLM_INTEGRATION.md](LLM_INTEGRATION.md) — Генерация эмбеддингов, интеграция с OpenAI
- [../features/CONSULTATION_FLOW.md](../features/CONSULTATION_FLOW.md) — Workflow консультаций
- [../features/DOCUMENT_PIPELINE.md](../features/DOCUMENT_PIPELINE.md) — Обработка PDF и создание chunks
- [../features/PROMPTS.md](../features/PROMPTS.md) — Инъекция RAG-контекста в промпты

---

## Файлы в проекте

### RAG-поиск

- [src/services/rag/unified_retriever.py](../../src/services/rag/unified_retriever.py) — Трёхуровневый unified поиск
- [src/services/rag/kb_retriever.py](../../src/services/rag/kb_retriever.py) — Поиск Q&A (устаревший, заменён unified)

### Database repositories

- [src/services/db/kb_repo.py](../../src/services/db/kb_repo.py) — Векторный поиск в knowledge_base
- [src/services/db/document_chunks_repo.py](../../src/services/db/document_chunks_repo.py) — Векторный поиск в document_chunks

### LLM integration

- [src/services/llm/consultation_llm.py](../../src/services/llm/consultation_llm.py) — Оркестрация RAG + LLM
- [src/services/llm/embeddings_llm.py](../../src/services/llm/embeddings_llm.py) — Генерация эмбеддингов

### Prompts

- [src/prompts/consultation_prompts.py](../../src/prompts/consultation_prompts.py) — Инъекция RAG-контекста

---

**Версия документа:** 1.0
**Дата последнего обновления:** 2025-12-05
