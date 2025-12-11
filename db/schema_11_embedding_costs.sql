-- schema_11_embedding_costs.sql
-- Добавляет поля для трекинга стоимости embeddings

-- Добавляем поля embeddings в consultation_logs
ALTER TABLE consultation_logs ADD COLUMN IF NOT EXISTS embedding_tokens INTEGER DEFAULT 0;
ALTER TABLE consultation_logs ADD COLUMN IF NOT EXISTS embedding_cost_usd DECIMAL(10, 6) DEFAULT 0;
ALTER TABLE consultation_logs ADD COLUMN IF NOT EXISTS embedding_model TEXT;

-- Добавляем модель embeddings в documents (токены и cost уже есть из schema_10)
ALTER TABLE documents ADD COLUMN IF NOT EXISTS embedding_model TEXT;

-- Комментарии
COMMENT ON COLUMN consultation_logs.embedding_tokens IS 'Токены для embeddings запроса (RAG поиск)';
COMMENT ON COLUMN consultation_logs.embedding_cost_usd IS 'Стоимость embeddings запроса в USD';
COMMENT ON COLUMN consultation_logs.embedding_model IS 'Модель embeddings (text-embedding-3-small и т.п.)';
COMMENT ON COLUMN documents.embedding_model IS 'Модель embeddings для документа';
