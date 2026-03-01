-- schema_82: Таблица ответов квиза воронки Б
-- Хранит выбранные пользователем культуру, регион и проблему при прохождении онбординга

CREATE TABLE IF NOT EXISTS user_quiz_answers (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    culture TEXT,
    region TEXT,
    problem TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id)
);
