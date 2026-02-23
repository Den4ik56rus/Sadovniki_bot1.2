-- schema_69: Trigger delay + payment config
-- Добавляем задержку отправки и конфиг платёжной кнопки к триггерам этапов воронки

ALTER TABLE funnel_stage_triggers
  ADD COLUMN IF NOT EXISTS delay_minutes INT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS payment_config JSONB DEFAULT NULL;

-- payment_config shape (если не NULL — вместо рассылки отправляем оффер оплаты):
-- {
--   "plan_id": 1,          -- ID тарифного плана подписки
--   "custom_price": 483,   -- кастомная цена в рублях (null = цена плана)
--   "bonus_tokens": 5      -- доп. токены сверх плана (null = 0)
-- }

COMMENT ON COLUMN funnel_stage_triggers.delay_minutes IS 'Задержка отправки в минутах (0 = немедленно)';
COMMENT ON COLUMN funnel_stage_triggers.payment_config IS 'Если не NULL — отправляем платёжный оффер вместо рассылки';
