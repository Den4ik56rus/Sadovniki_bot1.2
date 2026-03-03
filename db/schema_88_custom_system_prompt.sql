-- schema_88: Кастомный system prompt для GPT разбивки на слайды
-- Позволяет переопределять дефолтный системный промпт при создании презентации

ALTER TABLE presentations ADD COLUMN IF NOT EXISTS custom_system_prompt TEXT;
