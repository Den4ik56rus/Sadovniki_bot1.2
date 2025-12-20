-- Migration: YooKassa Payment Integration
-- Version: 30
-- Description: Tables for subscriptions, token packages, payments, and user subscriptions
-- Date: 2025-12-20

-- ============================================================================
-- 1. SUBSCRIPTION PLANS
-- ============================================================================
CREATE TABLE IF NOT EXISTS subscription_plans (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price_rub DECIMAL(10,2) NOT NULL,
    duration_days INTEGER NOT NULL,
    tokens_included INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT true,
    yookassa_product_id VARCHAR(255),
    trial_days INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Initial data: Standard subscription
INSERT INTO subscription_plans (name, description, price_rub, duration_days, tokens_included, is_active)
VALUES ('Стандарт', 'Месячная подписка с безлимитными вопросами', 500.00, 30, 999, true)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 2. TOKEN PACKAGES
-- ============================================================================
CREATE TABLE IF NOT EXISTS token_packages (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price_rub DECIMAL(10,2) NOT NULL,
    tokens_amount INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Initial data: 20 questions package
INSERT INTO token_packages (name, description, price_rub, tokens_amount, is_active)
VALUES ('20 вопросов', 'Разовая покупка 20 вопросов', 200.00, 20, true)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 3. PAYMENTS
-- ============================================================================
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    yookassa_payment_id VARCHAR(100) UNIQUE NOT NULL,
    idempotency_key VARCHAR(255) NOT NULL,

    -- Payment type
    payment_type VARCHAR(50) NOT NULL,
    subscription_plan_id INTEGER REFERENCES subscription_plans(id),
    token_package_id INTEGER REFERENCES token_packages(id),

    -- Financial data
    amount_rub DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'RUB',

    -- YooKassa status
    status VARCHAR(50) NOT NULL,
    paid BOOLEAN DEFAULT false,

    -- Metadata
    description TEXT,
    metadata JSONB,
    yookassa_payment_object JSONB,

    -- Receipt (54-FZ)
    receipt_registration VARCHAR(50),
    fiscal_document_number VARCHAR(100),

    -- Refunds
    refund_id VARCHAR(255),
    refund_status VARCHAR(50),

    -- Security
    webhook_verified BOOLEAN DEFAULT false,
    client_ip VARCHAR(45),

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    paid_at TIMESTAMP,
    canceled_at TIMESTAMP,
    expires_at TIMESTAMP,

    -- Webhook data
    confirmation_url TEXT,
    last_webhook_at TIMESTAMP,

    -- Prevent duplicates
    CONSTRAINT unique_payment_idempotency UNIQUE(yookassa_payment_id, idempotency_key)
);

-- Indexes for payments
CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS idx_payments_yookassa_id ON payments(yookassa_payment_id);
CREATE INDEX IF NOT EXISTS idx_payments_status_created ON payments(status, created_at);
CREATE INDEX IF NOT EXISTS idx_payments_idempotency ON payments(idempotency_key) WHERE idempotency_key IS NOT NULL;

-- ============================================================================
-- 4. USER SUBSCRIPTIONS
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    subscription_plan_id INTEGER NOT NULL REFERENCES subscription_plans(id),
    payment_id INTEGER NOT NULL REFERENCES payments(id),

    -- Period
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    next_billing_date TIMESTAMP,

    -- Status
    status VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT true,

    -- Tokens
    tokens_granted INTEGER NOT NULL,

    -- Auto-renewal
    auto_renew BOOLEAN DEFAULT false,
    payment_method_id VARCHAR(255),
    cancellation_reason TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for subscriptions
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user ON user_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_status ON user_subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_expires ON user_subscriptions(expires_at) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_next_billing ON user_subscriptions(next_billing_date) WHERE auto_renew = true;

-- Trigger to auto-expire subscriptions
CREATE OR REPLACE FUNCTION check_subscription_expiration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.expires_at <= NOW() AND NEW.status = 'active' THEN
        NEW.status = 'expired';
        NEW.is_active = false;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS subscription_expiration_check ON user_subscriptions;
CREATE TRIGGER subscription_expiration_check
BEFORE UPDATE ON user_subscriptions
FOR EACH ROW
EXECUTE FUNCTION check_subscription_expiration();

-- ============================================================================
-- 5. PAYMENT ERRORS
-- ============================================================================
CREATE TABLE IF NOT EXISTS payment_errors (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    payment_id VARCHAR(255),
    error_code VARCHAR(50) NOT NULL,
    error_message TEXT,
    yookassa_error_data JSONB,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for payment errors
CREATE INDEX IF NOT EXISTS idx_payment_errors_user ON payment_errors(user_id);
CREATE INDEX IF NOT EXISTS idx_payment_errors_created ON payment_errors(created_at);

-- ============================================================================
-- 6. EXTEND USERS TABLE
-- ============================================================================
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(50) DEFAULT 'none';
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_expires_at TIMESTAMP;

-- ============================================================================
-- COMMENTS
-- ============================================================================
COMMENT ON TABLE subscription_plans IS 'Subscription plans (e.g., Standard, Premium)';
COMMENT ON TABLE token_packages IS 'One-time token purchase packages';
COMMENT ON TABLE payments IS 'Payment transactions via YooKassa';
COMMENT ON TABLE user_subscriptions IS 'Active and historical user subscriptions';
COMMENT ON TABLE payment_errors IS 'Payment error log for debugging and retry logic';
