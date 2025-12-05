-- Миграция для добавления счётчика уточняющих вопросов
-- Применять после schema_topics.sql

-- Добавляем поле для счётчика уточняющих вопросов
ALTER TABLE topics ADD COLUMN IF NOT EXISTS follow_up_questions_left INTEGER DEFAULT 3;

-- Добавляем комментарий для документации
COMMENT ON COLUMN topics.follow_up_questions_left IS 'Количество оставшихся уточняющих вопросов по теме (по умолчанию 3)';

-- Обновляем существующие открытые топики (устанавливаем 3 вопроса)
UPDATE topics
SET follow_up_questions_left = 3
WHERE follow_up_questions_left IS NULL AND status = 'open';

-- Для закрытых топиков устанавливаем 0
UPDATE topics
SET follow_up_questions_left = 0
WHERE follow_up_questions_left IS NULL AND status = 'closed';
