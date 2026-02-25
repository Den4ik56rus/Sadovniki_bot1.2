-- schema_78: Добавляем last_activity_at в таблицу users
-- Отслеживает ЛЮБУЮ активность пользователя в боте (сообщение, нажатие кнопки, /start и т.д.)
-- Ранее "последняя активность" считалась только по consultation_logs — теперь по всем действиям.

ALTER TABLE users ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMPTZ;

-- Инициализируем значения из consultation_logs для существующих пользователей
UPDATE users u
SET last_activity_at = GREATEST(
    (SELECT MAX(created_at) FROM consultation_logs cl WHERE cl.user_id = u.id),
    u.created_at
)
WHERE u.last_activity_at IS NULL;

-- Для пользователей без консультаций — ставим created_at
UPDATE users
SET last_activity_at = created_at
WHERE last_activity_at IS NULL;

-- Индекс для сортировки по активности
CREATE INDEX IF NOT EXISTS idx_users_last_activity_at ON users (last_activity_at DESC NULLS LAST);
