# Обработка PDF-документов для RAG

## Краткое описание

Система автоматически обрабатывает PDF-документы: извлечение текста, разбиение на фрагменты (chunks по 800 символов с перекрытием 200), генерация эмбеддингов батчами по 20 штук с retry-логикой (3 попытки, экспоненциальная задержка), сохранение в таблицы `documents` и `document_chunks`.

## Оглавление

1. [Workflow обработки](#workflow-обработки)
2. [Извлечение текста из PDF](#извлечение-текста-из-pdf)
3. [Chunking strategy](#chunking-strategy)
4. [Генерация эмбеддингов](#генерация-эмбеддингов)
5. [Хранение в БД](#хранение-в-бд)
6. [Скрипт импорта](#скрипт-импорта)
7. [Связанные документы](#связанные-документы)
8. [Файлы в проекте](#файлы-в-проекте)

---

## Workflow обработки

```
┌───────────────────────────────────────────────────────┐
│  1. Загрузка PDF файла                                │
│     data/documents/{культура}/{имя_файла}.pdf         │
└──────────────────────┬────────────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────────────┐
│  2. Проверка дубликата (SHA256 hash)                  │
│     get_document_by_hash()                            │
└──────────────────────┬────────────────────────────────┘
                       │ Если не существует
                       ▼
┌───────────────────────────────────────────────────────┐
│  3. Извлечение текста (PyPDF2)                        │
│     processor.extract_text_from_pdf()                 │
└──────────────────────┬────────────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────────────┐
│  4. Разбиение на chunks (800 chars, 200 overlap)      │
│     chunker.chunk_text()                              │
└──────────────────────┬────────────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────────────┐
│  5. Генерация эмбеддингов (батчами по 20)             │
│     - OpenAI text-embedding-3-small                   │
│     - Retry logic: 3 попытки, exponential backoff     │
└──────────────────────┬────────────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────────────┐
│  6. Сохранение в БД                                   │
│     - documents (метаданные)                          │
│     - document_chunks (фрагменты + embeddings)        │
└───────────────────────────────────────────────────────┘
```

---

## Извлечение текста из PDF

### Функция `extract_text_from_pdf()`

**Расположение:** src/services/documents/processor.py

```python
import PyPDF2

def extract_text_from_pdf(file_path: str) -> str:
    """
    Извлекает текст из PDF-файла постранично.
    
    Возвращает:
        Объединённый текст всех страниц
    """
    with open(file_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ""
        
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    
    return text.strip()
```

### Дедупликация через hash

```python
import hashlib

def calculate_file_hash(file_path: str) -> str:
    """
    Вычисляет SHA256 хеш файла.
    """
    sha256_hash = hashlib.sha256()
    
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    
    return sha256_hash.hexdigest()

# Проверка дубликата
file_hash = calculate_file_hash(pdf_path)
existing = await get_document_by_hash(file_hash)

if existing:
    print(f"Документ уже существует: {existing['filename']}")
    return  # Пропускаем обработку
```

---

## Chunking strategy

### Параметры разбиения

| Параметр | Значение | Обоснование |
|----------|----------|-------------|
| `chunk_size` | 800 символов | Баланс между контекстом и точностью поиска |
| `chunk_overlap` | 200 символов | Сохранение связности между фрагментами |

### Функция `chunk_text()`

**Расположение:** src/services/documents/chunker.py

```python
def chunk_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 200
) -> List[str]:
    """
    Разбивает текст на перекрывающиеся фрагменты.
    
    Пример:
        text = "ABCDEFGHIJ" (10 символов)
        chunk_size = 4
        chunk_overlap = 2
        
        Результат:
        - Chunk 0: "ABCD" (0:4)
        - Chunk 1: "CDEF" (2:6) — перекрытие "CD"
        - Chunk 2: "EFGH" (4:8) — перекрытие "EF"
        - Chunk 3: "GHIJ" (6:10) — перекрытие "GH"
    """
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        
        # Сдвиг с учётом overlap
        start += (chunk_size - chunk_overlap)
    
    return chunks
```

### Пример разбиения

```
Исходный текст (2000 символов):
"Малина ремонтантная требует регулярной подкормки азотными удобрениями..."

Разбиение:
┌────────────────────────────────────────┐
│ Chunk 0 (0:800)                        │
│ "Малина ремонтантная требует..."       │
└───────────┬────────────────────────────┘
            │ Overlap 200
            ▼
┌────────────────────────────────────────┐
│ Chunk 1 (600:1400)                     │
│ "...регулярной подкормки..."           │
└───────────┬────────────────────────────┘
            │ Overlap 200
            ▼
┌────────────────────────────────────────┐
│ Chunk 2 (1200:2000)                    │
│ "...в начале вегетации..."             │
└────────────────────────────────────────┘
```

---

## Генерация эмбеддингов

### Батчинг (20 chunks за запрос)

```python
# src/services/documents/processor.py

BATCH_SIZE = 20  # chunks per batch

async def process_chunks_with_embeddings(chunks: List[str], subcategory: str):
    """
    Обрабатывает chunks батчами для уменьшения количества API-запросов.
    """
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        
        # Генерация эмбеддингов для батча
        embeddings = await generate_batch_embeddings(batch)
        
        # Сохранение в БД
        for chunk_text, embedding in zip(batch, embeddings):
            await insert_document_chunk(
                document_id=doc_id,
                chunk_index=chunk_idx,
                chunk_text=chunk_text,
                embedding=embedding,
                subcategory=subcategory,
            )
```

### Retry logic с экспоненциальной задержкой

```python
import asyncio
from typing import List

async def generate_batch_embeddings(
    texts: List[str],
    max_retries: int = 3
) -> List[List[float]]:
    """
    Генерирует эмбеддинги с retry-логикой.
    
    Retry strategy:
    - Попытка 1: сразу
    - Попытка 2: задержка 2^1 = 2 сек
    - Попытка 3: задержка 2^2 = 4 сек
    """
    for attempt in range(max_retries):
        try:
            # Вызов OpenAI API
            embeddings = await get_text_embeddings_batch(texts)
            return embeddings
            
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"Retry {attempt + 1}/{max_retries} after {wait_time}s: {e}")
                await asyncio.sleep(wait_time)
            else:
                print(f"Failed after {max_retries} attempts: {e}")
                # Возвращаем zero vectors как fallback
                return [[0.0] * 1536 for _ in texts]
```

---

## Хранение в БД

### Таблица `documents`

```sql
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT UNIQUE NOT NULL,  -- SHA256 для дедупликации
    file_size_bytes INTEGER,
    subcategory TEXT NOT NULL,       -- Культура растения
    processing_status TEXT DEFAULT 'pending',
    processing_error TEXT,
    total_chunks INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Таблица `document_chunks`

```sql
CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_size INTEGER,
    page_number INTEGER,
    embedding VECTOR(1536) NOT NULL,
    subcategory TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- HNSW индекс для векторного поиска
CREATE INDEX idx_chunks_embedding ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

---

## Скрипт импорта

### scripts/import_documents.py

```bash
# Структура папок
data/documents/
├── клубника_летняя/
│   ├── посадка.pdf
│   └── уход.pdf
├── малина_ремонтантная/
│   └── обрезка.pdf
└── голубика/
    └── pH_почвы.pdf

# Запуск импорта
python scripts/import_documents.py

# Логика:
# 1. Сканирование всех PDF в data/documents/
# 2. Определение subcategory из имени папки
# 3. Обработка каждого PDF
# 4. Вывод статистики
```

### Пример использования

```python
# scripts/import_documents.py

import asyncio
from pathlib import Path
from src.services.documents.processor import process_pdf_document

async def import_all_documents():
    """
    Импортирует все PDF из data/documents/
    """
    base_path = Path("data/documents")
    
    for subfolder in base_path.iterdir():
        if not subfolder.is_dir():
            continue
        
        subcategory = subfolder.name  # "клубника_летняя", "малина_ремонтантная" и т.п.
        
        for pdf_file in subfolder.glob("*.pdf"):
            print(f"Processing: {pdf_file}")
            
            await process_pdf_document(
                file_path=str(pdf_file),
                subcategory=subcategory,
            )

if __name__ == "__main__":
    asyncio.run(import_all_documents())
```

---

## Связанные документы

- [../architecture/DATABASE.md](../architecture/DATABASE.md) — Таблицы documents и document_chunks
- [../architecture/RAG_SYSTEM.md](../architecture/RAG_SYSTEM.md) — Использование chunks в RAG-поиске
- [../architecture/LLM_INTEGRATION.md](../architecture/LLM_INTEGRATION.md) — Генерация эмбеддингов

---

## Файлы в проекте

- src/services/documents/processor.py — Извлечение текста, дедупликация, batch processing
- src/services/documents/chunker.py — Разбиение на chunks (800/200)
- src/services/db/documents_repo.py — Операции с таблицей documents
- src/services/db/document_chunks_repo.py — Операции с таблицей document_chunks
- scripts/import_documents.py — Скрипт массового импорта

**Версия:** 1.0  
**Дата:** 2025-12-05
