-- schema_44_trial_questions.sql
-- Добавляет колонку для отслеживания выдачи бесплатных вопросов новым пользователям

ALTER TABLE users ADD COLUMN IF NOT EXISTS trial_questions_granted BOOLEAN DEFAULT false;
