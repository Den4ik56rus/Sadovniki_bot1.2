-- schema_89_presentation_batches.sql
-- Пакетная генерация презентаций

CREATE TABLE IF NOT EXISTS presentation_batches (
    id SERIAL PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',        -- pending | running | completed | cancelled
    -- Настройки (общие для всех презентаций в пакете)
    style_id INTEGER REFERENCES presentation_styles(id),
    template_id INTEGER REFERENCES presentation_templates(id),
    llm_model TEXT,
    reasoning_effort TEXT,
    image_model TEXT,
    custom_system_prompt TEXT,
    -- Прогресс
    total_items INTEGER NOT NULL DEFAULT 0,
    completed_items INTEGER NOT NULL DEFAULT 0,
    failed_items INTEGER NOT NULL DEFAULT 0,
    current_item_index INTEGER,
    -- Стоимость
    total_cost_usd NUMERIC(10,4) DEFAULT 0,
    -- Мета
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS presentation_batch_items (
    id SERIAL PRIMARY KEY,
    batch_id INTEGER NOT NULL REFERENCES presentation_batches(id) ON DELETE CASCADE,
    -- Что генерировать
    culture_key TEXT NOT NULL,
    variety_key TEXT,
    problem_key TEXT NOT NULL,
    -- Результат
    status TEXT NOT NULL DEFAULT 'pending',          -- pending | generating | completed | failed | skipped
    presentation_id INTEGER REFERENCES presentations(id),
    content_pdf_path TEXT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    -- Мета
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_batch_items_batch_id ON presentation_batch_items(batch_id);
CREATE INDEX IF NOT EXISTS idx_batches_status ON presentation_batches(status);
