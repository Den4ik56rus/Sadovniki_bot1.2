-- schema_61_token_balance_constraints.sql
-- CHECK constraints: баланс токенов не может быть отрицательным

-- Защита от отрицательных балансов
ALTER TABLE users ADD CONSTRAINT IF NOT EXISTS chk_token_balance_non_negative
    CHECK (token_balance >= 0);

ALTER TABLE users ADD CONSTRAINT IF NOT EXISTS chk_sub_balance_non_negative
    CHECK (subscription_token_balance >= 0 OR subscription_token_balance IS NULL);

ALTER TABLE users ADD CONSTRAINT IF NOT EXISTS chk_pur_balance_non_negative
    CHECK (purchased_token_balance >= 0 OR purchased_token_balance IS NULL);
