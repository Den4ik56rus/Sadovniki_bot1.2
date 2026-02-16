-- schema_46_referrals.sql
-- Реферальная система: связи, коды, бонусы

-- Реферальный код в таблице users
ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_code VARCHAR(12) UNIQUE;

-- Таблица реферальных связей
CREATE TABLE IF NOT EXISTS referrals (
    id SERIAL PRIMARY KEY,
    referrer_id INTEGER NOT NULL REFERENCES users(id),
    referee_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
    referrer_bonus_granted BOOLEAN DEFAULT FALSE,
    referee_bonus_granted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id);
