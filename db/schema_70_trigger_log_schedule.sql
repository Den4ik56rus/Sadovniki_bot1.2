-- schema_70: Trigger log scheduling support
-- Добавляем send_at для отложенных триггеров и статус 'pending'

ALTER TABLE funnel_trigger_log
  ADD COLUMN IF NOT EXISTS send_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- Обновляем комментарий к статусу: теперь допустимы 'pending', 'sent', 'failed'
COMMENT ON COLUMN funnel_trigger_log.status IS 'pending = ждёт отправки, sent = отправлен, failed = ошибка';
COMMENT ON COLUMN funnel_trigger_log.send_at IS 'Время когда нужно отправить (для отложенных триггеров)';

CREATE INDEX IF NOT EXISTS idx_funnel_trigger_log_pending
  ON funnel_trigger_log(send_at)
  WHERE status = 'pending';
