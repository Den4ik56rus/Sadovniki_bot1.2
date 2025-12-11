-- schema_14_classification_cost.sql
-- Добавляет поля для отслеживания стоимости и токенов классификации (detect_culture, detect_category_and_culture)

ALTER TABLE consultation_logs
ADD COLUMN IF NOT EXISTS classification_cost_usd DECIMAL(10,6) DEFAULT 0;

ALTER TABLE consultation_logs
ADD COLUMN IF NOT EXISTS classification_tokens INTEGER DEFAULT 0;

-- Комментарии к полям
COMMENT ON COLUMN consultation_logs.classification_cost_usd IS 'Стоимость вызовов LLM для классификации (detect_culture_name, detect_category_and_culture)';
COMMENT ON COLUMN consultation_logs.classification_tokens IS 'Токены использованные для классификации (gpt-4o)';
