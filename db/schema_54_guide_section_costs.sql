-- Migration: Guide Section Costs & Model Tracking
-- Version: 54
-- Description: Per-section LLM cost breakdown + model tracking for guide orders
-- Date: 2026-02-18

-- Per-section cost/token data for analytics
ALTER TABLE guide_orders ADD COLUMN IF NOT EXISTS sections_meta JSONB;

-- Track which LLM model was used for generation
ALTER TABLE guide_orders ADD COLUMN IF NOT EXISTS llm_model VARCHAR(100);

COMMENT ON COLUMN guide_orders.sections_meta IS
  'Per-section cost breakdown: {section_key: {title, prompt_tokens, completion_tokens, cost_usd, model, user_question, rag_snippets_count}}';
COMMENT ON COLUMN guide_orders.llm_model IS 'LLM model used for generation';
