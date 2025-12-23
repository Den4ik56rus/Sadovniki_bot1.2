-- schema_32_culture_subtypes_jsonb.sql
-- Миграция: culture_subtype VARCHAR → culture_subtypes JSONB
-- Позволяет хранить подтип для каждой культуры отдельно

-- 1. Добавляем новую колонку JSONB
ALTER TABLE document_chunks
ADD COLUMN IF NOT EXISTS culture_subtypes JSONB DEFAULT '{}';

-- 2. Мигрируем данные из старой колонки
-- Если был culture_subtype и есть cultures, присваиваем подтип первой культуре
UPDATE document_chunks
SET culture_subtypes = jsonb_build_object(cultures[1], culture_subtype)
WHERE culture_subtype IS NOT NULL
  AND cardinality(cultures) > 0;

-- 3. Создаём индекс для JSONB
CREATE INDEX IF NOT EXISTS idx_document_chunks_culture_subtypes ON document_chunks USING GIN (culture_subtypes);

-- Примечание: старая колонка culture_subtype НЕ удаляется для обратной совместимости
