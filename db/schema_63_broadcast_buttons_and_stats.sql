-- schema_63: Inline-кнопки на рассылках + статистика кликов/опросов
-- Depends on: schema_62_broadcasts.sql

-- Inline-кнопки на рассылках (JSONB массив)
-- Формат: [{"row":0, "text":"Да!", "type":"quick_reply", "option_key":"opt_0"},
--           {"row":0, "text":"Нет", "type":"quick_reply", "option_key":"opt_1"},
--           {"row":1, "text":"Подробнее", "type":"url", "url":"https://..."}]
ALTER TABLE broadcasts ADD COLUMN IF NOT EXISTS inline_buttons JSONB;

-- Клики по quick_reply кнопкам
CREATE TABLE IF NOT EXISTS broadcast_button_clicks (
    id SERIAL PRIMARY KEY,
    broadcast_id INT NOT NULL REFERENCES broadcasts(id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(id),
    telegram_user_id BIGINT NOT NULL,
    option_key VARCHAR(50) NOT NULL,
    button_text VARCHAR(200) NOT NULL,
    clicked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(broadcast_id, user_id)  -- один ответ на юзера
);
CREATE INDEX IF NOT EXISTS idx_bbc_broadcast ON broadcast_button_clicks(broadcast_id);

-- Ответы на опросы (только неанонимные)
CREATE TABLE IF NOT EXISTS broadcast_poll_answers (
    id SERIAL PRIMARY KEY,
    broadcast_id INT NOT NULL REFERENCES broadcasts(id) ON DELETE CASCADE,
    user_id INT REFERENCES users(id),
    telegram_user_id BIGINT NOT NULL,
    telegram_poll_id VARCHAR(100) NOT NULL,
    option_ids JSONB NOT NULL,  -- [0] или [0,2] для multiple-choice
    answered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(broadcast_id, telegram_user_id)
);
CREATE INDEX IF NOT EXISTS idx_bpa_broadcast ON broadcast_poll_answers(broadcast_id);
CREATE INDEX IF NOT EXISTS idx_bpa_poll_id ON broadcast_poll_answers(telegram_poll_id);

-- Маппинг poll_id → broadcast через recipients
ALTER TABLE broadcast_recipients
    ADD COLUMN IF NOT EXISTS telegram_poll_id VARCHAR(100);
CREATE INDEX IF NOT EXISTS idx_br_poll_id ON broadcast_recipients(telegram_poll_id);
