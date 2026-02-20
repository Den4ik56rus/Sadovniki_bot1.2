-- schema_59: поддержка отложенных подписок
-- Добавляем поле tokens_granted_at для отслеживания факта начисления токенов

ALTER TABLE user_subscriptions
    ADD COLUMN IF NOT EXISTS tokens_granted_at TIMESTAMPTZ DEFAULT NULL;
