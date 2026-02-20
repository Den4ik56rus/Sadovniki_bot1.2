-- schema_55_invite_link_active.sql
-- Добавляем возможность деактивировать инвайт-ссылки

ALTER TABLE invite_links ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;
