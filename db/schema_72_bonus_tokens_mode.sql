-- schema_72_bonus_tokens_mode.sql
-- Добавляет режим бонусных токенов: 'absolute' (фиксированное число) или 'percent' (% от токенов тарифа)

ALTER TABLE user_broadcast_discounts
    ADD COLUMN IF NOT EXISTS bonus_tokens_mode VARCHAR(10) DEFAULT 'absolute';
