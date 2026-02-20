-- schema_58_restart_recovery.sql
-- Персистентное хранилище состояния консультации для восстановления после рестарта бота

CREATE TABLE IF NOT EXISTS user_bot_state (
    id SERIAL PRIMARY KEY,
    telegram_user_id BIGINT NOT NULL UNIQUE,
    state_key TEXT NOT NULL,
    context_json JSONB DEFAULT '{}'::jsonb,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_bot_state_tg_id ON user_bot_state(telegram_user_id);

COMMENT ON TABLE user_bot_state IS
'Персистентное состояние консультации пользователя. Синхронизируется с CONSULTATION_STATE/CONSULTATION_CONTEXT при каждом изменении. Используется для восстановления после рестарта бота.';

COMMENT ON COLUMN user_bot_state.state_key IS
'Ключ состояния, например: waiting_clarification_answer, waiting_variety_clarification';

COMMENT ON COLUMN user_bot_state.context_json IS
'Сериализованный CONSULTATION_CONTEXT — только примитивные поля (без объектов Message, Bot)';
