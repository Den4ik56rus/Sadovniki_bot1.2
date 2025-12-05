-- Миграция для добавления системы токенов
-- Применять после schema_05_follow_up_questions.sql

-- Добавляем баланс токенов в таблицу users
ALTER TABLE users ADD COLUMN IF NOT EXISTS token_balance INTEGER DEFAULT 0;

-- Добавляем комментарий для документации
COMMENT ON COLUMN users.token_balance IS 'Текущий баланс токенов пользователя';

-- Создаём таблицу истории транзакций токенов
CREATE TABLE IF NOT EXISTS token_transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,              -- положительное = пополнение, отрицательное = списание
    operation_type TEXT NOT NULL,         -- 'admin_credit', 'new_topic', 'buy_questions'
    description TEXT,                     -- описание операции
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_token_transactions_user_id ON token_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_token_transactions_created_at ON token_transactions(created_at);

-- Комментарии к таблице
COMMENT ON TABLE token_transactions IS 'История операций с токенами пользователей';
COMMENT ON COLUMN token_transactions.amount IS 'Сумма операции (+ пополнение, - списание)';
COMMENT ON COLUMN token_transactions.operation_type IS 'Тип операции: admin_credit, new_topic, buy_questions';
