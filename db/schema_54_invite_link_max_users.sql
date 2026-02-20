-- schema_54: Лимит пользователей для инвайт-ссылок
-- 0 = без лимита, N > 0 = принять не более N пользователей с бонусом

ALTER TABLE invite_links ADD COLUMN IF NOT EXISTS max_users INTEGER NOT NULL DEFAULT 0;
