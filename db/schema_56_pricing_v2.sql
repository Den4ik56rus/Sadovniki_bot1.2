-- Migration: Pricing Policy v2 — Tariffs, Tokens & Carryover
-- Version: 56
-- Description: New subscription plans (Старт/Базовый/Расширенный), token packages,
--              split token balances (subscription vs purchased), carryover, per-plan discount
-- Date: 2026-02-19

-- ============================================================================
-- 1. EXTEND subscription_plans — carryover + discount
-- ============================================================================
ALTER TABLE subscription_plans
  ADD COLUMN IF NOT EXISTS max_carryover INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS token_discount_percent INTEGER DEFAULT 0;

COMMENT ON COLUMN subscription_plans.max_carryover
  IS 'Maximum unused subscription tokens that carry over to next month (0 = no carryover)';
COMMENT ON COLUMN subscription_plans.token_discount_percent
  IS 'Discount percentage (0-100) on additional token package purchases for subscribers of this plan';

-- ============================================================================
-- 2. EXTEND users — split token balances
-- ============================================================================
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS subscription_token_balance INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS purchased_token_balance INTEGER DEFAULT 0;

-- Migrate existing balances: all current tokens → purchased (can't retroactively separate)
UPDATE users
SET purchased_token_balance = token_balance
WHERE token_balance > 0
  AND purchased_token_balance = 0;

COMMENT ON COLUMN users.subscription_token_balance
  IS 'Tokens from current subscription period (subject to carryover limits on renewal)';
COMMENT ON COLUMN users.purchased_token_balance
  IS 'Tokens purchased via token packages or admin credits (no expiry, no carryover limit)';

-- ============================================================================
-- 3. DEACTIVATE OLD PLANS, SEED NEW PLANS
-- ============================================================================
UPDATE subscription_plans SET is_active = false;

INSERT INTO subscription_plans
  (name, description, price_rub, duration_days, tokens_included, is_active, max_carryover, token_discount_percent)
VALUES
  ('Старт', 'Начальный план — 10 токенов/мес', 690.00, 30, 10, true, 3, 0),
  ('Базовый «Сезон рядом»', 'Базовый план — 25 токенов/мес', 1190.00, 30, 25, true, 5, 0),
  ('Расширенный «Уверенный сезон»', 'Расширенный план — 50 токенов/мес', 1990.00, 30, 50, true, 10, 0);

-- ============================================================================
-- 4. DEACTIVATE OLD PACKAGES, SEED NEW PACKAGES
-- ============================================================================
UPDATE token_packages SET is_active = false;

INSERT INTO token_packages (name, description, price_rub, tokens_amount, is_active)
VALUES
  ('10 токенов', 'Дополнительные 10 токенов', 600.00, 10, true),
  ('25 токенов', 'Дополнительные 25 токенов', 1450.00, 25, true),
  ('50 токенов', 'Дополнительные 50 токенов', 2800.00, 50, true);
