-- db/schema_71_broadcast_discounts.sql
-- Персональные скидки, активированные через кнопку рассылки

CREATE TABLE IF NOT EXISTS user_broadcast_discounts (
    id SERIAL PRIMARY KEY,
    user_id           INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    broadcast_id      INT NOT NULL REFERENCES broadcasts(id) ON DELETE CASCADE,
    option_key        VARCHAR(50) NOT NULL,
    discount_percent  INT NOT NULL,
    bonus_tokens      INT NOT NULL DEFAULT 0,
    activated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at        TIMESTAMPTZ NOT NULL,
    UNIQUE(user_id)
);

CREATE INDEX IF NOT EXISTS idx_ubd_user    ON user_broadcast_discounts(user_id);
CREATE INDEX IF NOT EXISTS idx_ubd_expires ON user_broadcast_discounts(expires_at);
