-- schema_53_invite_link_bonuses.sql
-- Бонусные токены и скидки для инвайт-ссылок

-- Новые поля в invite_links
ALTER TABLE invite_links ADD COLUMN IF NOT EXISTS bonus_tokens INTEGER NOT NULL DEFAULT 0;
ALTER TABLE invite_links ADD COLUMN IF NOT EXISTS discount_percent INTEGER NOT NULL DEFAULT 0;
ALTER TABLE invite_links ADD COLUMN IF NOT EXISTS discount_duration_days INTEGER NOT NULL DEFAULT 0;

-- Поле для хранения даты окончания скидки у пользователя
ALTER TABLE invite_link_users ADD COLUMN IF NOT EXISTS discount_expires_at TIMESTAMPTZ;

-- Constraints
DO $$ BEGIN
    ALTER TABLE invite_links ADD CONSTRAINT chk_discount_percent
        CHECK (discount_percent >= 0 AND discount_percent <= 100);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE invite_links ADD CONSTRAINT chk_bonus_tokens
        CHECK (bonus_tokens >= 0);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE invite_links ADD CONSTRAINT chk_discount_duration
        CHECK (discount_duration_days >= 0);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Индекс для быстрого поиска активных скидок
CREATE INDEX IF NOT EXISTS idx_invite_link_users_discount
    ON invite_link_users(user_id, discount_expires_at)
    WHERE discount_expires_at IS NOT NULL;
