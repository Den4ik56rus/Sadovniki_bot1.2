-- schema_92_article_batch_reasoning.sql
-- Добавляем reasoning_effort в article_batches

ALTER TABLE article_batches ADD COLUMN IF NOT EXISTS reasoning_effort TEXT;
