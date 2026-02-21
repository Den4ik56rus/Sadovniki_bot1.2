-- schema_61_token_balance_constraints.sql
-- CHECK constraints: баланс токенов не может быть отрицательным

-- Защита от отрицательных балансов
DO $$ BEGIN
    ALTER TABLE users ADD CONSTRAINT chk_token_balance_non_negative
        CHECK (token_balance >= 0);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE users ADD CONSTRAINT chk_sub_balance_non_negative
        CHECK (subscription_token_balance >= 0 OR subscription_token_balance IS NULL);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE users ADD CONSTRAINT chk_pur_balance_non_negative
        CHECK (purchased_token_balance >= 0 OR purchased_token_balance IS NULL);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
