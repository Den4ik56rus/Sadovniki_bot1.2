-- Migration: Admin-editable client billing fields
-- Version: 57
-- Description: Add personal discount columns to users table for admin-side editing
-- Date: 2026-02-20

-- ============================================================================
-- 1. EXTEND users — personal discount
-- ============================================================================
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS personal_discount_percent INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS personal_discount_valid_until TIMESTAMPTZ;

COMMENT ON COLUMN users.personal_discount_percent
  IS 'Admin-set personal discount percentage (0-100) for this user on token purchases';
COMMENT ON COLUMN users.personal_discount_valid_until
  IS 'Expiry timestamp for personal_discount_percent (NULL = no expiry)';
