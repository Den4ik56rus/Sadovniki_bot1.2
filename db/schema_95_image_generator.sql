-- schema_95_image_generator.sql
-- Таблица для AI генератора картинок в админке

CREATE TABLE IF NOT EXISTS generated_images (
    id SERIAL PRIMARY KEY,
    user_prompt TEXT NOT NULL,
    optimized_prompt TEXT,
    preset VARCHAR(50) NOT NULL DEFAULT 'free',
    image_path TEXT,
    reference_image_path TEXT,
    image_model VARCHAR(100) DEFAULT 'gemini-3.1-flash-image-preview',
    status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    prompt_tokens INTEGER DEFAULT 0,
    prompt_completion_tokens INTEGER DEFAULT 0,
    cost_usd NUMERIC(10, 6) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_generated_images_created ON generated_images(created_at DESC);
