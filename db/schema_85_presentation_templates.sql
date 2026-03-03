-- schema_85_presentation_templates.sql
-- Шаблоны структуры презентаций (текстовые blueprints для GPT)

CREATE TABLE IF NOT EXISTS presentation_templates (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    template_text TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Добавляем ссылку на шаблон в презентации
ALTER TABLE presentations ADD COLUMN IF NOT EXISTS template_id INTEGER REFERENCES presentation_templates(id);
