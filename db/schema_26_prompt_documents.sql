-- =============================================================================
-- Schema 26: Prompt Documents Management System
-- Документы для добавления в системные промпты по культурам и типам работ
-- =============================================================================

-- Культуры (Клубника, Малина, Кустарники)
CREATE TABLE IF NOT EXISTS prompt_cultures (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Значения по умолчанию
INSERT INTO prompt_cultures (name, sort_order) VALUES
    ('Клубника', 0),
    ('Малина', 1),
    ('Кустарники', 2)
ON CONFLICT (name) DO NOTHING;

-- =============================================================================
-- Подкультуры (летняя, ремонтантная, общая — для Клубника/Малина)
-- =============================================================================

CREATE TABLE IF NOT EXISTS prompt_subcultures (
    id SERIAL PRIMARY KEY,
    culture_id INTEGER NOT NULL REFERENCES prompt_cultures(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(culture_id, name)
);

-- Подкультуры для Клубники
INSERT INTO prompt_subcultures (culture_id, name, sort_order)
SELECT c.id, s.name, s.sort_order
FROM prompt_cultures c
CROSS JOIN (VALUES
    ('летняя', 0),
    ('ремонтантная', 1),
    ('общая', 2)
) AS s(name, sort_order)
WHERE c.name = 'Клубника'
ON CONFLICT (culture_id, name) DO NOTHING;

-- Подкультуры для Малины
INSERT INTO prompt_subcultures (culture_id, name, sort_order)
SELECT c.id, s.name, s.sort_order
FROM prompt_cultures c
CROSS JOIN (VALUES
    ('летняя', 0),
    ('ремонтантная', 1),
    ('общая', 2)
) AS s(name, sort_order)
WHERE c.name = 'Малина'
ON CONFLICT (culture_id, name) DO NOTHING;

-- =============================================================================
-- Типы работ
-- =============================================================================

CREATE TABLE IF NOT EXISTS prompt_work_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Значения по умолчанию
INSERT INTO prompt_work_types (name, sort_order) VALUES
    ('Питание растений', 0),
    ('Защита растений', 1),
    ('Посадка и уход', 2),
    ('Улучшение почвы', 3),
    ('Подбор сорта', 4)
ON CONFLICT (name) DO NOTHING;

-- =============================================================================
-- Документы для промптов
-- =============================================================================

CREATE TABLE IF NOT EXISTS prompt_documents (
    id SERIAL PRIMARY KEY,
    culture_id INTEGER NOT NULL REFERENCES prompt_cultures(id) ON DELETE CASCADE,
    subculture_id INTEGER REFERENCES prompt_subcultures(id) ON DELETE SET NULL,
    work_type_id INTEGER NOT NULL REFERENCES prompt_work_types(id) ON DELETE CASCADE,

    -- Метаданные файла
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    file_size INTEGER NOT NULL,
    file_type VARCHAR(10) NOT NULL,  -- 'pages', 'docx', 'pdf'

    -- Извлечённый контент
    content_text TEXT,
    content_extracted_at TIMESTAMPTZ,
    extraction_status VARCHAR(20) DEFAULT 'pending',  -- pending, completed, failed
    extraction_error TEXT,

    -- Метаданные
    uploaded_by_admin_id BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Один документ на комбинацию (культура + подкультура + тип работ)
    UNIQUE(culture_id, subculture_id, work_type_id)
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_prompt_docs_culture ON prompt_documents(culture_id);
CREATE INDEX IF NOT EXISTS idx_prompt_docs_subculture ON prompt_documents(subculture_id);
CREATE INDEX IF NOT EXISTS idx_prompt_docs_work_type ON prompt_documents(work_type_id);
CREATE INDEX IF NOT EXISTS idx_prompt_docs_hash ON prompt_documents(file_hash);
CREATE INDEX IF NOT EXISTS idx_prompt_docs_status ON prompt_documents(extraction_status);

-- Триггер для updated_at
CREATE OR REPLACE FUNCTION update_prompt_documents_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_prompt_documents_updated_at ON prompt_documents;
CREATE TRIGGER trigger_prompt_documents_updated_at
    BEFORE UPDATE ON prompt_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_prompt_documents_updated_at();
