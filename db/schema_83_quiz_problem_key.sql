-- Добавляем колонку problem_key для хранения ключа проблемы (для авто-консультации после оплаты)
ALTER TABLE user_quiz_answers ADD COLUMN IF NOT EXISTS problem_key TEXT;
