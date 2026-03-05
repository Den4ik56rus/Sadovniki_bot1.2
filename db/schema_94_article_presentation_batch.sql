-- schema_94_article_presentation_batch.sql
-- Расширение таблиц для пакетной генерации презентаций по статьям

-- Добавляем тип пакета (problem = по проблемам, article = по статьям)
ALTER TABLE presentation_batches
    ADD COLUMN IF NOT EXISTS batch_type TEXT DEFAULT 'problem';

-- Добавляем category_key и is_season_plan для элементов по статьям
ALTER TABLE presentation_batch_items
    ADD COLUMN IF NOT EXISTS category_key TEXT,
    ADD COLUMN IF NOT EXISTS is_season_plan BOOLEAN DEFAULT FALSE;
