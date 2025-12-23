-- schema_31_passport_arrays.sql
-- Миграция: культуры, цели и фазы роста как массивы
-- Позволяет выбирать несколько значений для каждого поля

-- 1. Добавляем новые колонки-массивы
ALTER TABLE document_chunks
ADD COLUMN IF NOT EXISTS cultures TEXT[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS goals TEXT[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS growth_phases TEXT[] DEFAULT '{}';

-- 2. Мигрируем данные из старых колонок в новые
UPDATE document_chunks
SET
    cultures = CASE WHEN culture IS NOT NULL THEN ARRAY[culture] ELSE '{}' END,
    goals = CASE WHEN goal IS NOT NULL THEN ARRAY[goal] ELSE '{}' END,
    growth_phases = CASE WHEN growth_phase IS NOT NULL THEN ARRAY[growth_phase] ELSE '{}' END
WHERE culture IS NOT NULL OR goal IS NOT NULL OR growth_phase IS NOT NULL;

-- 3. Создаём индексы для быстрого поиска по массивам (GIN)
CREATE INDEX IF NOT EXISTS idx_document_chunks_cultures ON document_chunks USING GIN (cultures);
CREATE INDEX IF NOT EXISTS idx_document_chunks_goals ON document_chunks USING GIN (goals);
CREATE INDEX IF NOT EXISTS idx_document_chunks_growth_phases ON document_chunks USING GIN (growth_phases);

-- Примечание: старые колонки (culture, goal, growth_phase) НЕ удаляем для обратной совместимости
-- Они будут игнорироваться в новом коде
