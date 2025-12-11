-- Миграция: добавление полей стоимости обработки документов

-- Добавляем поля для отслеживания токенов и стоимости
ALTER TABLE documents ADD COLUMN IF NOT EXISTS embedding_tokens INTEGER DEFAULT 0;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS embedding_cost_usd DECIMAL(10, 6) DEFAULT 0;

-- Комментарии для документации
COMMENT ON COLUMN documents.embedding_tokens IS 'Количество токенов для генерации embeddings';
COMMENT ON COLUMN documents.embedding_cost_usd IS 'Стоимость генерации embeddings в USD';
