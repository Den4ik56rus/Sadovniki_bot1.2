-- schema_84_presentations.sql
-- Презентации — AI-генерация слайдов в админке

-- Стили презентаций (многоразовые XML)
CREATE TABLE IF NOT EXISTS presentation_styles (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    style_xml TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Презентации
CREATE TABLE IF NOT EXISTS presentations (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    source_text TEXT NOT NULL,
    style_id INTEGER REFERENCES presentation_styles(id),
    status TEXT NOT NULL DEFAULT 'draft',  -- draft|generating|completed|failed
    slide_count INTEGER DEFAULT 0,
    llm_model TEXT,
    reasoning_effort TEXT,
    -- Cost tracking
    text_prompt_tokens INTEGER DEFAULT 0,
    text_completion_tokens INTEGER DEFAULT 0,
    text_cost_usd NUMERIC(10,6) DEFAULT 0,
    image_input_tokens INTEGER DEFAULT 0,
    image_output_tokens INTEGER DEFAULT 0,
    image_cost_usd NUMERIC(10,6) DEFAULT 0,
    total_cost_usd NUMERIC(10,6) DEFAULT 0,
    pdf_path TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Слайды
CREATE TABLE IF NOT EXISTS presentation_slides (
    id SERIAL PRIMARY KEY,
    presentation_id INTEGER NOT NULL REFERENCES presentations(id) ON DELETE CASCADE,
    slide_index INTEGER NOT NULL,
    slide_title TEXT,
    slide_prompt TEXT NOT NULL,  -- NBP prompt от GPT
    slide_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(presentation_id, slide_index)
);

-- Версии слайдов (каждая генерация = версия)
CREATE TABLE IF NOT EXISTS slide_versions (
    id SERIAL PRIMARY KEY,
    slide_id INTEGER NOT NULL REFERENCES presentation_slides(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL DEFAULT 1,
    image_path TEXT,
    edit_instruction TEXT,  -- NULL для первой генерации
    nbp_prompt TEXT NOT NULL,
    nbp_input_tokens INTEGER DEFAULT 0,
    nbp_output_tokens INTEGER DEFAULT 0,
    nbp_cost_usd NUMERIC(10,6) DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending|generating|completed|failed
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(slide_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_presentations_status ON presentations(status);
CREATE INDEX IF NOT EXISTS idx_pres_slides_pres_id ON presentation_slides(presentation_id);
CREATE INDEX IF NOT EXISTS idx_slide_versions_slide_id ON slide_versions(slide_id);
