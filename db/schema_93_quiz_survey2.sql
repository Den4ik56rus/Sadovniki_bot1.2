-- schema_93: Второй опрос после оплаты quiz_plan (upsell flow)

-- Ответы на 3 вопроса (срочность, цель, график)
CREATE TABLE IF NOT EXISTS user_quiz_survey2 (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    urgency TEXT,    -- 'early' | 'progressing' | 'urgent'
    goal TEXT,       -- 'save' | 'restore' | 'yield' | 'prevent'
    schedule TEXT,   -- 'regular' | 'irregular' | 'minimal'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id)
);

CREATE INDEX IF NOT EXISTS idx_quiz_survey2_user_id ON user_quiz_survey2(user_id);

-- Выбор CTA-кнопки (аналитика интереса)
CREATE TABLE IF NOT EXISTS user_upsell_choice (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    choice TEXT NOT NULL,  -- 'seasonal_program' | 'consultation_subscription'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id)
);

CREATE INDEX IF NOT EXISTS idx_upsell_choice_user_id ON user_upsell_choice(user_id);
