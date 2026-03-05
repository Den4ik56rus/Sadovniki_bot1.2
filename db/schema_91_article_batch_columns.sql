-- schema_91_article_batch_columns.sql
-- Добавляем поля culture_key, variety_key, category_key, batch_id в admin_articles

ALTER TABLE admin_articles ADD COLUMN IF NOT EXISTS culture_key TEXT;
ALTER TABLE admin_articles ADD COLUMN IF NOT EXISTS variety_key TEXT;
ALTER TABLE admin_articles ADD COLUMN IF NOT EXISTS category_key TEXT;
ALTER TABLE admin_articles ADD COLUMN IF NOT EXISTS batch_id INTEGER REFERENCES article_batches(id) ON DELETE SET NULL;
