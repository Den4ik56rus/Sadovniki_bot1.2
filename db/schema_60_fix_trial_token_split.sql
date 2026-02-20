-- Migration: Fix trial token split balance
-- Version: 60
-- Description: Sync purchased_token_balance for users where trial_grant tokens
--              were only added to token_balance but not to purchased_token_balance.
--              This affected users registered after schema_56 migration.
-- Date: 2026-02-20

-- Fix users who have token_balance > 0 but split balances don't add up
-- (subscription_token_balance + purchased_token_balance < token_balance)
UPDATE users
SET purchased_token_balance = token_balance - COALESCE(subscription_token_balance, 0)
WHERE token_balance > 0
  AND (COALESCE(subscription_token_balance, 0) + COALESCE(purchased_token_balance, 0)) < token_balance;
