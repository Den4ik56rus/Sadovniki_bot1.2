-- schema_12_composed_question.sql
-- Добавляет поле composed_question для хранения сформированного вопроса для RAG-поиска

ALTER TABLE consultation_logs
ADD COLUMN IF NOT EXISTS composed_question TEXT;

COMMENT ON COLUMN consultation_logs.composed_question IS 'Полный сформированный вопрос для RAG-поиска (составлен LLM из root_question + уточнений)';
