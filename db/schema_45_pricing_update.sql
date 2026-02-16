-- Migration: Pricing Update
-- Version: 45
-- Description: Update seed data for new pricing structure + trial_questions setting
-- Date: 2026-02-13

-- ============================================================================
-- 0. CLEANUP DUPLICATE ROWS (from double seed run)
-- ============================================================================
-- Deactivate duplicate token_packages (can't delete due to FK from payments)
UPDATE token_packages SET is_active = false WHERE id > 1 AND name = (SELECT name FROM token_packages WHERE id = 1);
-- Delete duplicate subscription_plans (safe — no FK references)
DELETE FROM subscription_plans WHERE id > 1 AND name = (SELECT name FROM subscription_plans WHERE id = 1);

-- ============================================================================
-- 1. UPDATE TOKEN PACKAGE: 20 вопросов/200₽ → 10 вопросов/400₽
-- ============================================================================
UPDATE token_packages
SET name = '10 вопросов',
    description = 'Разовая покупка 10 вопросов',
    price_rub = 400.00,
    tokens_amount = 10
WHERE id = 1;

-- ============================================================================
-- 2. UPDATE SUBSCRIPTION PLAN: Стандарт 999 tokens → 20 tokens
-- ============================================================================
UPDATE subscription_plans
SET tokens_included = 20,
    description = 'Месячная подписка — 20 вопросов'
WHERE id = 1;

-- ============================================================================
-- 3. ADD PRO SUBSCRIPTION PLAN
-- ============================================================================
INSERT INTO subscription_plans (name, description, price_rub, duration_days, tokens_included, is_active)
VALUES ('Про', 'Расширенная подписка — 50 вопросов в месяц', 1000.00, 30, 50, true)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 4. TRIAL QUESTIONS SETTING (configurable from admin panel)
-- ============================================================================
INSERT INTO admin_settings (key, value, description)
VALUES ('trial_questions', '3', 'Количество бесплатных вопросов для новых пользователей')
ON CONFLICT (key) DO NOTHING;
