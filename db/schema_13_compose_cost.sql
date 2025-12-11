-- schema_13_compose_cost.sql
-- Добавляет поля для отслеживания стоимости и токенов форматирования вопроса

ALTER TABLE consultation_logs
ADD COLUMN IF NOT EXISTS compose_cost_usd DECIMAL(10,6) DEFAULT 0;

ALTER TABLE consultation_logs
ADD COLUMN IF NOT EXISTS compose_tokens INTEGER DEFAULT 0;

-- Комментарии к полям
COMMENT ON COLUMN consultation_logs.compose_cost_usd IS 'Стоимость вызова LLM для форматирования вопроса (compose_full_question)';
COMMENT ON COLUMN consultation_logs.compose_tokens IS 'Токены использованные для форматирования вопроса (gpt-4o-mini)';
