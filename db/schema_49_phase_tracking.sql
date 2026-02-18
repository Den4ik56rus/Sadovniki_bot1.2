-- schema_49_phase_tracking.sql
-- Отслеживание фазового режима в логах консультаций

ALTER TABLE consultation_logs
ADD COLUMN IF NOT EXISTS phase_mode VARCHAR(20),
ADD COLUMN IF NOT EXISTS phase_key VARCHAR(50),
ADD COLUMN IF NOT EXISTS phase_number INTEGER DEFAULT 0;

COMMENT ON COLUMN consultation_logs.phase_mode IS 'Режим фазы: single_phase | seasonal_phase | NULL (обычный)';
COMMENT ON COLUMN consultation_logs.phase_key IS 'Ключ фазы: весна-цветение | цветение-плодоношение | плодоношение-зима';
COMMENT ON COLUMN consultation_logs.phase_number IS 'Номер фазы в последовательности (1, 2, 3) для Тип C';
