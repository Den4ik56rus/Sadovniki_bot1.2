-- schema_50_user_avatars.sql
-- Добавляет поле для хранения пути к аватару пользователя

ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_path TEXT;
