-- Схема для хранения документов и их фрагментов (chunks) для RAG-системы

-- Таблица метаданных документов
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT UNIQUE NOT NULL,
    file_size_bytes INTEGER,

    -- Категоризация (соответствует knowledge_base)
    category TEXT NOT NULL,
    subcategory TEXT,

    -- Статус обработки
    uploaded_at TIMESTAMP DEFAULT NOW(),
    processing_status TEXT DEFAULT 'pending', -- pending, processing, completed, failed
    processing_error TEXT,
    total_chunks INTEGER DEFAULT 0,

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Таблица фрагментов документов с embeddings
CREATE TABLE IF NOT EXISTS document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    -- Позиция и содержимое фрагмента
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_size INTEGER,
    page_number INTEGER, -- для PDF

    -- Векторное представление для RAG
    embedding VECTOR(1536) NOT NULL,

    -- Категоризация (дублируется для быстрого поиска)
    category TEXT NOT NULL,
    subcategory TEXT,

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Индексы для производительности
CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category);
CREATE INDEX IF NOT EXISTS idx_documents_subcategory ON documents(subcategory);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(file_hash);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(processing_status);

CREATE INDEX IF NOT EXISTS idx_chunks_document ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_category ON document_chunks(category);
CREATE INDEX IF NOT EXISTS idx_chunks_subcategory ON document_chunks(subcategory);

-- Векторный индекс для быстрого поиска по схожести
-- Используем HNSW вместо ivfflat, т.к. он поддерживает больше измерений
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON document_chunks
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
