-- schema_90_article_batches.sql
-- Таблицы для пакетной генерации статей

CREATE TABLE IF NOT EXISTS article_batches (
    id SERIAL PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending|running|completed|cancelled
    llm_model TEXT,
    total_items INTEGER NOT NULL DEFAULT 0,
    completed_items INTEGER NOT NULL DEFAULT 0,
    failed_items INTEGER NOT NULL DEFAULT 0,
    current_item_index INTEGER,
    total_cost_usd NUMERIC(10,4) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS article_batch_items (
    id SERIAL PRIMARY KEY,
    batch_id INTEGER NOT NULL REFERENCES article_batches(id) ON DELETE CASCADE,
    culture_key TEXT NOT NULL,
    variety_key TEXT,
    category_key TEXT NOT NULL,       -- nutrition, planting_care, etc.
    topic TEXT NOT NULL,              -- авто: "Питание растений — Клубника летняя"
    culture_label TEXT NOT NULL,      -- "клубника летняя"
    category_label TEXT NOT NULL,     -- "питание растений"
    status TEXT NOT NULL DEFAULT 'pending',
    article_id INTEGER REFERENCES admin_articles(id),
    error_message TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    sort_order INTEGER NOT NULL DEFAULT 0
);
