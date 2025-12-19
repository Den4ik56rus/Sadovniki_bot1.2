-- Schema 27: RAG v2.0 - Chunk Passportization
-- Добавляет поля паспорта для чанков и справочные таблицы

-- ============================================
-- ФАЗА 0: Очистка старых RAG-документов
-- ============================================
-- ВНИМАНИЕ: prompt_documents НЕ трогаем!
TRUNCATE TABLE document_chunks CASCADE;
TRUNCATE TABLE documents CASCADE;

-- ============================================
-- ФАЗА 1: Новые поля для documents
-- ============================================
-- Поля для подсчёта стоимости генерации контекста
ALTER TABLE documents ADD COLUMN IF NOT EXISTS context_generation_cost DECIMAL(10, 6) DEFAULT 0;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS context_generation_tokens INTEGER DEFAULT 0;

-- ============================================
-- ФАЗА 2: Новые поля для document_chunks
-- ============================================
-- Поля паспорта
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS culture VARCHAR(50);
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS culture_subtype VARCHAR(50);
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS goal VARCHAR(100);
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS growth_phase VARCHAR(100);

-- Сгенерированные поля
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS prefix TEXT;
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS context TEXT;

-- Индексы для фильтрации по паспорту
CREATE INDEX IF NOT EXISTS idx_chunks_culture ON document_chunks(culture);
CREATE INDEX IF NOT EXISTS idx_chunks_goal ON document_chunks(goal);
CREATE INDEX IF NOT EXISTS idx_chunks_phase ON document_chunks(growth_phase);

-- ============================================
-- ФАЗА 3: Справочные таблицы паспорта
-- ============================================

-- Культуры
CREATE TABLE IF NOT EXISTS passport_cultures (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Подтипы культур (связано с культурой)
CREATE TABLE IF NOT EXISTS passport_subtypes (
    id SERIAL PRIMARY KEY,
    culture_id INTEGER REFERENCES passport_cultures(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(culture_id, name)
);

-- Цели (типы работ)
CREATE TABLE IF NOT EXISTS passport_goals (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Фазы роста
CREATE TABLE IF NOT EXISTS passport_phases (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- ФАЗА 4: Заполнение справочников
-- ============================================

-- Культуры
INSERT INTO passport_cultures (name, sort_order) VALUES
    ('малина', 0),
    ('клубника', 1),
    ('голубика', 2),
    ('смородина', 3),
    ('ежевика', 4),
    ('жимолость', 5),
    ('крыжовник', 6),
    ('общая', 99)
ON CONFLICT (name) DO NOTHING;

-- Подтипы для малины
INSERT INTO passport_subtypes (culture_id, name, sort_order)
SELECT id, 'ремонтантная', 0 FROM passport_cultures WHERE name = 'малина'
ON CONFLICT DO NOTHING;
INSERT INTO passport_subtypes (culture_id, name, sort_order)
SELECT id, 'летняя', 1 FROM passport_cultures WHERE name = 'малина'
ON CONFLICT DO NOTHING;
INSERT INTO passport_subtypes (culture_id, name, sort_order)
SELECT id, 'общая', 2 FROM passport_cultures WHERE name = 'малина'
ON CONFLICT DO NOTHING;

-- Подтипы для клубники
INSERT INTO passport_subtypes (culture_id, name, sort_order)
SELECT id, 'ремонтантная', 0 FROM passport_cultures WHERE name = 'клубника'
ON CONFLICT DO NOTHING;
INSERT INTO passport_subtypes (culture_id, name, sort_order)
SELECT id, 'летняя', 1 FROM passport_cultures WHERE name = 'клубника'
ON CONFLICT DO NOTHING;
INSERT INTO passport_subtypes (culture_id, name, sort_order)
SELECT id, 'общая', 2 FROM passport_cultures WHERE name = 'клубника'
ON CONFLICT DO NOTHING;

-- Цели (типы работ)
INSERT INTO passport_goals (name, sort_order) VALUES
    ('питание', 0),
    ('защита', 1),
    ('посадка', 2),
    ('уход', 3),
    ('обрезка', 4),
    ('размножение', 5),
    ('сорта', 6),
    ('общая', 99)
ON CONFLICT (name) DO NOTHING;

-- Фазы роста
INSERT INTO passport_phases (name, sort_order) VALUES
    ('весна', 0),
    ('цветение', 1),
    ('плодоношение', 2),
    ('после сбора', 3),
    ('осень', 4),
    ('зима', 5),
    ('общая', 99)
ON CONFLICT (name) DO NOTHING;

-- ============================================
-- Индексы для справочников
-- ============================================
CREATE INDEX IF NOT EXISTS idx_passport_subtypes_culture ON passport_subtypes(culture_id);
