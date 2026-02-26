-- db/schema_80_ab_test.sql
-- A/B тестирование воронок: таблица настроек и поле варианта для пользователей

-- Таблица глобальных настроек бота
CREATE TABLE IF NOT EXISTS bot_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Начальное значение: активная воронка — Тип А
INSERT INTO bot_settings (key, value)
VALUES ('active_funnel_variant', 'A')
ON CONFLICT (key) DO NOTHING;

-- Поле варианта воронки для каждого пользователя
ALTER TABLE users ADD COLUMN IF NOT EXISTS funnel_variant TEXT DEFAULT 'A';

-- Все существующие пользователи — Тип А
UPDATE users SET funnel_variant = 'A' WHERE funnel_variant IS NULL;
