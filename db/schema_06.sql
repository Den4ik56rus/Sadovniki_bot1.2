-- schema_06.sql: Двухэтапная обработка RAG документов
-- Добавляет поддержку разделения chunking и embedding

-- 1. Добавляем поля для статистики chunking
ALTER TABLE documents ADD COLUMN IF NOT EXISTS chunking_tokens INTEGER DEFAULT 0;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS chunking_cost_usd NUMERIC(10, 6) DEFAULT 0;

-- 2. Флаг: документ загружен в библиотеку (embeddings сгенерированы)
ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_embedded BOOLEAN DEFAULT FALSE;

-- 3. Обновляем существующие документы: если есть embedding_cost, значит embedded
UPDATE documents
SET is_embedded = TRUE
WHERE embedding_cost_usd > 0 OR embedding_tokens > 0;

-- 4. Комментарии для ясности
COMMENT ON COLUMN documents.chunking_tokens IS 'Токены для semantic chunking (определение границ чанков)';
COMMENT ON COLUMN documents.chunking_cost_usd IS 'Стоимость semantic chunking в USD';
COMMENT ON COLUMN documents.is_embedded IS 'Флаг: embeddings сгенерированы и документ готов к поиску';
