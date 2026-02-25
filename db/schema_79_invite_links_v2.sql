-- schema_79_invite_links_v2.sql
-- Invite Links v2: бонус токенов (%) + поддержка существующих пользователей

-- ============================================
-- Feature 1: Бонус токенов в процентах
-- ============================================
ALTER TABLE invite_links ADD COLUMN IF NOT EXISTS token_bonus_percent INTEGER NOT NULL DEFAULT 0;

DO $$ BEGIN
    ALTER TABLE invite_links ADD CONSTRAINT chk_token_bonus_percent
        CHECK (token_bonus_percent >= 0 AND token_bonus_percent <= 100);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================
-- Feature 2: Поддержка существующих пользователей
-- ============================================

-- Настройки на invite_links: разрешить существующим + чекбоксы какие бонусы давать
ALTER TABLE invite_links ADD COLUMN IF NOT EXISTS allow_existing_users BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE invite_links ADD COLUMN IF NOT EXISTS existing_user_bonus_tokens BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE invite_links ADD COLUMN IF NOT EXISTS existing_user_discount BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE invite_links ADD COLUMN IF NOT EXISTS existing_user_token_bonus BOOLEAN NOT NULL DEFAULT TRUE;

-- Метка "существующий юзер" на записи привязки
ALTER TABLE invite_link_users ADD COLUMN IF NOT EXISTS is_existing_user BOOLEAN NOT NULL DEFAULT FALSE;

-- Меняем UNIQUE(user_id) → UNIQUE(invite_link_id, user_id)
-- чтобы один юзер мог быть привязан к нескольким ссылкам
ALTER TABLE invite_link_users DROP CONSTRAINT IF EXISTS invite_link_users_user_id_key;

DO $$ BEGIN
    ALTER TABLE invite_link_users ADD CONSTRAINT invite_link_users_link_user_unique
        UNIQUE(invite_link_id, user_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
