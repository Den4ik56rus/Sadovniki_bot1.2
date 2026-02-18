-- =============================================================================
-- Schema 48: Complexity Tracking + Classifier Settings
-- Добавляет отслеживание сложности вопросов в consultation_logs
-- и настройки модели для классификатора сложности
-- =============================================================================

-- 1. Новые колонки в consultation_logs для shadow mode трекинга
ALTER TABLE consultation_logs
ADD COLUMN IF NOT EXISTS complexity_tier VARCHAR(50),
ADD COLUMN IF NOT EXISTS complexity_metadata JSONB DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS complexity_classification_cost_usd NUMERIC(10,6) DEFAULT 0,
ADD COLUMN IF NOT EXISTS complexity_classification_tokens INTEGER DEFAULT 0;

-- Индекс для аналитики по сложности
CREATE INDEX IF NOT EXISTS idx_consultation_logs_complexity
ON consultation_logs(complexity_tier)
WHERE complexity_tier IS NOT NULL;

COMMENT ON COLUMN consultation_logs.complexity_tier IS
'Уровень сложности ответа: short_answer | long_answer | turnkey_solution';

COMMENT ON COLUMN consultation_logs.complexity_metadata IS
'Метаданные классификации: current_phase, next_phase, topics, user_requested_more';

-- 2. Настройка модели для классификатора сложности
INSERT INTO admin_settings (key, value, description)
VALUES ('model_complexity', 'gpt-4.1-mini', 'Модель для классификации сложности вопросов')
ON CONFLICT (key) DO NOTHING;

INSERT INTO admin_settings (key, value, description)
VALUES ('temp_complexity', '', 'Temperature для классификатора сложности (пусто = не передавать)')
ON CONFLICT (key) DO NOTHING;

INSERT INTO admin_settings (key, value, description)
VALUES ('reasoning_complexity', '', 'Reasoning effort для классификатора сложности (none/low/medium/high)')
ON CONFLICT (key) DO NOTHING;
