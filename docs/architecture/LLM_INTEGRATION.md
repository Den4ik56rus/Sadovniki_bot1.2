# Интеграция с OpenAI API

## Краткое описание

Система использует OpenAI API для генерации ответов на вопросы пользователей и создания векторных представлений (embeddings) для RAG-поиска. Архитектура построена на **трёх уровнях абстракции**: базовый клиент (core_llm), генерация эмбеддингов (embeddings_llm) и оркестрация консультаций (consultation_llm). Все LLM-сервисы используют **асинхронный клиент** AsyncOpenAI для эффективной обработки запросов.

## Оглавление

1. [Архитектура LLM-сервисов](#архитектура-llm-сервисов)
2. [Базовый клиент (core_llm)](#базовый-клиент-core_llm)
3. [Генерация эмбеддингов (embeddings_llm)](#генерация-эмбеддингов-embeddings_llm)
4. [Оркестрация консультаций (consultation_llm)](#оркестрация-консультаций-consultation_llm)
5. [Конфигурация моделей](#конфигурация-моделей)
6. [Обработка ошибок](#обработка-ошибок)
7. [Связанные документы](#связанные-документы)
8. [Файлы в проекте](#файлы-в-проекте)

---

## Архитектура LLM-сервисов

### Трёхуровневая архитектура

```
┌──────────────────────────────────────────────────────────┐
│         Уровень 3: Бизнес-логика (Orchestration)         │
├──────────────────────────────────────────────────────────┤
│  consultation_llm.py                                     │
│  ├─ ask_consultation_llm()                               │
│  │  ├─ Получение истории диалога (messages_repo)         │
│  │  ├─ Генерация эмбеддинга запроса (embeddings_llm)     │
│  │  ├─ RAG-поиск (unified_retriever)                     │
│  │  ├─ Построение системного промпта (prompts)           │
│  │  └─ Вызов LLM (core_llm)                              │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│      Уровень 2: Специализированные сервисы               │
├──────────────────────────────────────────────────────────┤
│  embeddings_llm.py                                       │
│  └─ get_text_embedding()                                 │
│      └─ Генерация векторов (1536 измерений)              │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│          Уровень 1: Базовый клиент (Core)                │
├──────────────────────────────────────────────────────────┤
│  core_llm.py                                             │
│  ├─ get_client() → AsyncOpenAI                           │
│  └─ create_chat_completion()                             │
│      └─ client.chat.completions.create()                 │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│               OpenAI API (REST)                          │
│  ├─ Chat Completions API (gpt-4.1-mini)                  │
│  └─ Embeddings API (text-embedding-3-small)              │
└──────────────────────────────────────────────────────────┘
```

### Принципы разделения ответственности

| Уровень | Модуль | Ответственность |
|---------|--------|-----------------|
| **1. Core** | core_llm.py | Низкоуровневый клиент OpenAI, управление HTTP-запросами |
| **2. Specialized** | embeddings_llm.py | Генерация векторных представлений текста |
| **3. Orchestration** | consultation_llm.py | Бизнес-логика: RAG + промпты + LLM → ответ |

**Почему три уровня:**
- **Переиспользование:** `core_llm` используется всеми сервисами
- **Тестирование:** Легко мокировать низкоуровневый клиент
- **Гибкость:** Можно заменить OpenAI на другого провайдера, изменив только `core_llm`

---

## Базовый клиент (core_llm)

### Назначение

Модуль [src/services/llm/core_llm.py](../../src/services/llm/core_llm.py) предоставляет **единственный экземпляр** асинхронного клиента OpenAI для всех LLM-запросов.

### Архитектура клиента

```python
# src/services/llm/core_llm.py

from openai import AsyncOpenAI
from src.config import settings

# Глобальный клиент OpenAI (создаётся один раз при импорте модуля)
_client = AsyncOpenAI(
    api_key=settings.openai_api_key
)

def get_client() -> AsyncOpenAI:
    """
    Возвращает асинхронного клиента OpenAI.
    """
    return _client
```

**Паттерн Singleton:**
- `_client` создаётся **один раз** при импорте модуля
- Все сервисы получают **один и тот же** экземпляр через `get_client()`
- HTTP-соединения переиспользуются (connection pooling внутри AsyncOpenAI)

**Почему не создаём клиента в каждом запросе:**
- Избежать overhead создания HTTP-сессий
- Переиспользование TCP-соединений
- Снижение latency на 10-20%

---

### Функция `create_chat_completion()`

Основная функция для генерации текстовых ответов.

```python
async def create_chat_completion(
    messages: List[Dict[str, Any]],  # История диалога
    model: str | None = None,        # Модель (по умолчанию из settings)
    temperature: float = 0.3,        # Креативность (0-1)
) -> str:
    """
    Выполняет chat completion и возвращает текст ответа.
    """
    model_name = model or settings.openai_model
    client = get_client()

    response = await client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=temperature,
    )

    content = response.choices[0].message.content
    return content or ""
```

**Параметры:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `messages` | `List[Dict[str, Any]]` | Список сообщений в формате `[{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]` |
| `model` | `str \| None` | Имя модели OpenAI. Если `None`, используется `settings.openai_model` |
| `temperature` | `float` | Параметр креативности: `0.0` = детерминированно, `1.0` = максимально вариативно |

**Возвращает:**
- `str` — текст ответа ассистента

**Пример использования:**

```python
from src.services.llm.core_llm import create_chat_completion

messages = [
    {"role": "system", "content": "Ты агроном-консультант по ягодным культурам."},
    {"role": "user", "content": "Когда лучше сажать клубнику?"},
]

response = await create_chat_completion(
    messages=messages,
    temperature=0.4,
)

print(response)  # "Оптимальное время посадки клубники — конец июля - начало августа..."
```

---

### Конфигурация temperature

| Сценарий | Temperature | Обоснование |
|----------|-------------|-------------|
| **Классификация культур** | 0.0 | Детерминированный выбор из 12 типов культур |
| **Генерация ответов** | 0.4 | Баланс между точностью и естественностью формулировок |
| **Уточняющие вопросы** | 0.3 | Структурированные вопросы без излишней вариативности |

**См. также:**
- [CLASSIFICATION.md](../features/CLASSIFICATION.md) — классификация с `temperature=0.0`
- [CONSULTATION_FLOW.md](../features/CONSULTATION_FLOW.md) — генерация ответов с `temperature=0.4`

---

## Генерация эмбеддингов (embeddings_llm)

### Назначение

Модуль [src/services/llm/embeddings_llm.py](../../src/services/llm/embeddings_llm.py) отвечает за генерацию **векторных представлений** текста для RAG-поиска.

### Функция `get_text_embedding()`

```python
# src/services/llm/embeddings_llm.py

from typing import List
from src.services.llm.core_llm import get_client
from src.config import settings

async def get_text_embedding(text: str) -> List[float]:
    """
    Считает эмбеддинг для текста с помощью OpenAI.

    Параметры:
        text — произвольная строка (вопрос, ответ, фрагмент базы знаний).

    Возвращает:
        Список чисел (List[float]) — эмбеддинг (1536 измерений).
    """
    client = get_client()

    response = await client.embeddings.create(
        model=settings.openai_embeddings_model,  # "text-embedding-3-small"
        input=text,
    )

    embedding = response.data[0].embedding
    return embedding
```

**Параметры:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `text` | `str` | Текст для векторизации (до 8191 токена для `text-embedding-3-small`) |

**Возвращает:**
- `List[float]` — вектор из 1536 чисел (размерность модели `text-embedding-3-small`)

---

### Модель text-embedding-3-small

**Характеристики:**

| Параметр | Значение |
|----------|----------|
| Название | `text-embedding-3-small` |
| Размерность | **1536** (фиксированная) |
| Максимальная длина | 8191 токен (~6000 слов) |
| Стоимость | $0.00002 / 1K токенов (в 10 раз дешевле text-embedding-ada-002) |
| Производительность | ~62.3% на MTEB Benchmark |

**Почему text-embedding-3-small:**
- Баланс стоимости и качества
- Достаточная размерность для семантического поиска
- Поддерживается PostgreSQL pgvector (`VECTOR(1536)`)

---

### Пример использования

```python
from src.services.llm.embeddings_llm import get_text_embedding

question = "Когда подкармливать малину весной?"
embedding = await get_text_embedding(question)

print(f"Размерность: {len(embedding)}")  # 1536
print(f"Первые 5 чисел: {embedding[:5]}")
# [0.123456, -0.789012, 0.345678, -0.901234, 0.567890]
```

---

### Применение эмбеддингов

**1. Сохранение в базу знаний:**

```python
# src/services/db/kb_repo.py

async def kb_insert(
    category: str,
    subcategory: Optional[str],
    question: Optional[str],
    answer: str,
    embedding: List[float],  # Вектор из get_text_embedding()
    source_type: str = "manual"
) -> int:
    # ... вставка в knowledge_base с эмбеддингом
```

**2. Поиск похожих фрагментов:**

```python
# src/services/db/kb_repo.py

async def kb_search(
    category: str,
    query_embedding: List[float],  # Эмбеддинг запроса
    subcategory: Optional[str] = None,
    limit: int = 3,
    distance_threshold: Optional[float] = 0.35,
):
    # SELECT ... ORDER BY embedding <=> query_embedding LIMIT 3
```

**См. также:**
- [DATABASE.md](DATABASE.md) — векторный поиск с pgvector
- [RAG_SYSTEM.md](RAG_SYSTEM.md) — трёхуровневый RAG-поиск

---

## Оркестрация консультаций (consultation_llm)

### Назначение

Модуль [src/services/llm/consultation_llm.py](../../src/services/llm/consultation_llm.py) — **главный оркестратор** для генерации ответов. Объединяет:
1. История диалога из БД
2. RAG-поиск в базе знаний
3. Системный промпт с контекстом
4. Вызов LLM

### Функция `ask_consultation_llm()`

```python
async def ask_consultation_llm(
    *,
    user_id: int,                         # ID пользователя в БД
    telegram_user_id: int,                # Telegram ID
    text: str,                            # Текущий вопрос
    session_id: str,                      # ID сессии
    consultation_category: Optional[str] = None,  # Тип консультации
    culture: Optional[str] = None,        # Культура
    default_location: str = "средняя полоса",
    default_growing_type: str = "открытый грунт",
    skip_rag: bool = False,               # Пропустить RAG-поиск
) -> str:
    """
    Основной вызов LLM для генерации ответа.
    """
    # 1. Получаем историю диалога
    history = await get_last_messages(user_id=user_id, limit=6)

    # 2. Генерируем эмбеддинг запроса
    query_embedding = await get_text_embedding(text)

    # 3. RAG-поиск (если не пропущен)
    kb_snippets = []
    if not skip_rag and consultation_category:
        kb_snippets = await retrieve_unified_snippets(
            category=consultation_category,
            subcategory=culture,
            query_embedding=query_embedding,
            qa_limit=20,
            doc_limit=30,
            qa_distance_threshold=0.6,
            doc_distance_threshold=0.75,
        )

    # 4. Построение системного промпта
    system_prompt = await build_consultation_system_prompt(
        culture=culture or "не определено",
        kb_snippets=kb_snippets,
        consultation_category=consultation_category or "",
        default_location=default_location,
        default_growing_type=default_growing_type,
    )

    # 5. Формируем messages
    messages = [
        {"role": "system", "content": system_prompt},
        *[{"role": "user" if item["direction"] == "user" else "assistant",
           "content": item["text"]} for item in history],
        {"role": "user", "content": text},
    ]

    # 6. Вызов LLM
    response = await create_chat_completion(
        messages=messages,
        model=settings.openai_model,
        temperature=0.4,
    )

    return response.strip()
```

---

### Workflow консультации

```
┌─────────────────────────────────────────────────────────┐
│  1. Получение истории диалога                           │
│     ├─ get_last_messages(user_id, limit=6)              │
│     └─ Последние 6 сообщений из БД                      │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  2. Генерация эмбеддинга запроса                        │
│     ├─ get_text_embedding(text)                         │
│     └─ [0.123, -0.456, ..., 0.789] (1536 чисел)         │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  3. RAG-поиск в базе знаний (если не пропущен)          │
│     ├─ retrieve_unified_snippets()                      │
│     │  ├─ Уровень 1: Q&A (knowledge_base)               │
│     │  ├─ Уровень 2: Документы по культуре              │
│     │  └─ Уровень 3: Общие документы                    │
│     └─ kb_snippets: List[Dict]                          │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  4. Построение системного промпта                       │
│     ├─ build_consultation_system_prompt()               │
│     │  ├─ Инъекция терминологии                         │
│     │  ├─ Категория консультации                        │
│     │  ├─ Культура растения                             │
│     │  └─ Контекст из RAG                               │
│     └─ system_prompt: str                               │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  5. Формирование messages для LLM                       │
│     ├─ [{"role": "system", "content": system_prompt}]   │
│     ├─ [{"role": "user", "content": "..."}, ...]        │
│     └─ [{"role": "user", "content": text}]              │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  6. Вызов OpenAI Chat Completions API                  │
│     ├─ create_chat_completion(messages, temp=0.4)       │
│     └─ response: str                                    │
└─────────────────────────────────────────────────────────┘
```

---

### Параметры температуры

```python
# src/services/llm/consultation_llm.py (строка 262)

response_text = await create_chat_completion(
    messages=messages,
    model=settings.openai_model,
    temperature=0.4,  # Баланс точности и естественности
)
```

**Почему 0.4:**
- **0.0-0.2:** Слишком шаблонные ответы, повторяющиеся формулировки
- **0.4-0.5:** Оптимальный баланс для консультаций (факты + естественный язык)
- **0.7-1.0:** Избыточная креативность, возможны отклонения от фактов

---

### RAG-поиск (интеграция)

```python
# src/services/llm/consultation_llm.py (строки 175-183)

kb_snippets = await retrieve_unified_snippets(
    category=consultation_category,  # 'питание растений', 'посадка и уход' и т.п.
    subcategory=culture,             # 'малина ремонтантная', 'клубника летняя' и т.п.
    query_embedding=query_embedding, # Вектор из get_text_embedding()
    qa_limit=20,                     # Макс. 20 Q&A пар
    doc_limit=30,                    # Макс. 30 фрагментов документов
    qa_distance_threshold=0.6,       # Порог для Q&A
    doc_distance_threshold=0.75,     # Порог для документов
)
```

**Логика приоритетов RAG:**

| Уровень | Источник | Порог distance | Описание |
|---------|----------|----------------|----------|
| **1** | `knowledge_base` (Q&A) | 0.6 | Одобренные администратором Q&A пары |
| **2** | `document_chunks` (специфичные) | 0.75 | Документы по конкретной культуре (например, "малина ремонтантная") |
| **3** | `document_chunks` (общие) | 0.75 | Общие документы по культуре (например, "малина общая") |

**Fallback-логика:**
1. Если нет результатов для `subcategory="малина ремонтантная"` → ищем `subcategory="малина общая"`
2. Если всё равно нет → ищем `subcategory="общая информация"`
3. Если база знаний пуста → LLM генерирует ответ без контекста

**См. также:** [RAG_SYSTEM.md](RAG_SYSTEM.md) — подробная архитектура RAG

---

### Логирование RAG-поиска

```python
# src/services/llm/consultation_llm.py (строки 158-208)

print(f"\n{'='*60}")
print(f"[RAG] Начинаем поиск в базе знаний")
print(f"[RAG] Категория: {rag_category}")
print(f"[RAG] Подкатегория (культура): {rag_subcategory or 'не указана'}")
print(f"[RAG] Запрос пользователя: {text[:100]}...")

# ... RAG-поиск ...

print(f"[RAG] Найдено фрагментов: {len(kb_snippets)}")

if kb_snippets:
    for idx, snippet in enumerate(kb_snippets, 1):
        print(f"  #{idx} [УРОВЕНЬ {snippet['priority_level']}] [{snippet['source_type']}]")
        print(f"      Категория: {snippet['category']} / Подкатегория: {snippet['subcategory']}")
        print(f"      Distance: {snippet['distance']:.4f}")
else:
    print(f"[RAG] ⚠️ НИЧЕГО НЕ НАЙДЕНО в базе знаний!")

print(f"{'='*60}\n")
```

**Пример вывода:**

```
============================================================
[RAG] Начинаем поиск в базе знаний
[RAG] Категория: питание растений
[RAG] Подкатегория (культура): малина ремонтантная
[RAG] Запрос пользователя: Чем подкормить малину весной?...
[RAG] Получен эмбеддинг запроса (размер: 1536)
[RAG] Найдено фрагментов: 5
  #1 [УРОВЕНЬ 1] [qa]
      Категория: питание растений / Подкатегория: малина ремонтантная
      Distance: 0.2341
  #2 [УРОВЕНЬ 2] [document]
      Категория: питание растений / Подкатегория: малина ремонтантная
      Distance: 0.4521
  #3 [УРОВЕНЬ 3] [document]
      Категория: питание растений / Подкатегория: малина общая
      Distance: 0.6123
============================================================
```

---

## Конфигурация моделей

### Настройки в src/config.py

```python
# src/config.py (строки 57-69)

class Settings(BaseSettings):
    # ... другие поля ...

    openai_api_key: str = Field(
        ...,  # Обязательное поле
        description="API-ключ OpenAI",
    )

    openai_model: str = Field(
        "gpt-4.1-mini",  # Модель по умолчанию
        description="Имя модели OpenAI для чат-ответов",
    )

    openai_embeddings_model: str = Field(
        "text-embedding-3-small",  # Модель эмбеддингов
        description="Имя модели OpenAI для эмбеддингов",
    )
```

### Переменные окружения (.env)

```bash
# .env

OPENAI_API_KEY=sk-proj-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
OPENAI_MODEL=gpt-4.1-mini
OPENAI_EMBEDDINGS_MODEL=text-embedding-3-small
```

**Доступные модели для `openai_model`:**

| Модель | Стоимость (вход/выход) | Контекст | Рекомендация |
|--------|------------------------|----------|--------------|
| `gpt-4.1-mini` | $0.15 / $0.60 за 1M токенов | 128K | **Используется** — оптимальный баланс |
| `gpt-4o` | $2.50 / $10.00 за 1M токенов | 128K | Дорого для Telegram-бота |
| `gpt-3.5-turbo` | $0.50 / $1.50 за 1M токенов | 16K | Менее точные ответы |

**Доступные модели для `openai_embeddings_model`:**

| Модель | Размерность | Стоимость | Рекомендация |
|--------|-------------|-----------|--------------|
| `text-embedding-3-small` | 1536 | $0.00002 / 1K токенов | **Используется** — баланс цены/качества |
| `text-embedding-3-large` | 3072 | $0.00013 / 1K токенов | Избыточно для базы знаний |
| `text-embedding-ada-002` | 1536 | $0.0001 / 1K токенов | Устаревшая модель |

---

## Обработка ошибок

### Стратегия обработки ошибок

**1. Уровень core_llm:**

```python
# src/services/llm/core_llm.py

async def create_chat_completion(...) -> str:
    try:
        response = await client.chat.completions.create(...)
        return response.choices[0].message.content or ""
    except Exception as e:
        # Ошибка пробрасывается наверх
        raise
```

**2. Уровень consultation_llm:**

```python
# src/services/llm/consultation_llm.py (строки 258-272)

try:
    response_text = await create_chat_completion(...)

    if not response_text:
        return "Не удалось получить ответ от модели. Попробуйте ещё раз позже."

    return response_text.strip()

except Exception as e:
    print(f"[ask_consultation_llm][OpenAI error] {e}")
    return "Сейчас не получается связаться с моделью. Попробуйте ещё раз чуть позже."
```

**Почему ловим ошибки на верхнем уровне:**
- Пользователь получает понятное сообщение вместо 500 Internal Server Error
- Telegram-бот не падает при сбоях OpenAI API
- Логирование ошибок для диагностики

---

### Типичные ошибки OpenAI API

| Ошибка | Код | Причина | Решение |
|--------|-----|---------|---------|
| **RateLimitError** | 429 | Превышен лимит запросов | Retry через 60 секунд |
| **AuthenticationError** | 401 | Неверный API-ключ | Проверить `OPENAI_API_KEY` в .env |
| **InvalidRequestError** | 400 | Некорректные параметры | Проверить формат `messages` |
| **Timeout** | - | Таймаут запроса (>60 сек) | Retry с экспоненциальной задержкой |
| **APIConnectionError** | - | Сетевая ошибка | Проверить интернет-соединение |

**Пример retry-логики (будущее улучшение):**

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60)
)
async def create_chat_completion_with_retry(...):
    return await create_chat_completion(...)
```

---

### RAG-ошибки

```python
# src/services/llm/consultation_llm.py (строки 210-212)

except Exception as e:
    print(f"[ask_consultation_llm][KB/RAG error] {e}")
    kb_snippets = []  # Продолжаем без RAG
```

**Fallback-стратегия:**
- Если RAG-поиск упал → `kb_snippets = []`
- LLM генерирует ответ **без контекста** из базы знаний
- Пользователь получает ответ, но без персонализации

**Типичные RAG-ошибки:**
- Ошибка генерации эмбеддинга (OpenAI API)
- Ошибка векторного поиска (PostgreSQL pgvector)
- Превышен порог distance (все результаты отфильтрованы)

---

## Связанные документы

- [OVERVIEW.md](OVERVIEW.md) — Обзор архитектуры системы
- [DATABASE.md](DATABASE.md) — Векторный поиск с pgvector
- [RAG_SYSTEM.md](RAG_SYSTEM.md) — Трёхуровневая RAG-система
- [../features/CONSULTATION_FLOW.md](../features/CONSULTATION_FLOW.md) — Workflow консультаций
- [../features/PROMPTS.md](../features/PROMPTS.md) — Система промптов
- [../features/CLASSIFICATION.md](../features/CLASSIFICATION.md) — Классификация культур с LLM

---

## Файлы в проекте

### LLM-сервисы

- [src/services/llm/core_llm.py](../../src/services/llm/core_llm.py) — Базовый клиент OpenAI
- [src/services/llm/embeddings_llm.py](../../src/services/llm/embeddings_llm.py) — Генерация эмбеддингов
- [src/services/llm/consultation_llm.py](../../src/services/llm/consultation_llm.py) — Оркестрация консультаций
- [src/services/llm/classification_llm.py](../../src/services/llm/classification_llm.py) — Классификация культур

### Промпты

- [src/prompts/consultation_prompts.py](../../src/prompts/consultation_prompts.py) — Системные промпты для консультаций
- [src/prompts/base_prompt.py](../../src/prompts/base_prompt.py) — Базовые промпты
- [src/prompts/category_prompts/](../../src/prompts/category_prompts/) — Промпты для категорий

### Конфигурация

- [src/config.py](../../src/config.py) — Настройки OpenAI API
- [.env](.env) — Переменные окружения

### RAG

- [src/services/rag/unified_retriever.py](../../src/services/rag/unified_retriever.py) — Трёхуровневый RAG-поиск

---

**Версия документа:** 1.0
**Дата последнего обновления:** 2025-12-05
