-- schema_94: Атомарный захват pending-триггеров через статус processing
-- Решает race condition: при перезапуске бота pending-запись больше не обрабатывается дважды.
--
-- Изменения:
-- 1. Обновляем комментарий к колонке status
-- 2. Обновляем индекс чтобы покрывал и processing строки

COMMENT ON COLUMN automation_trigger_log.status IS
    'pending = ждёт, processing = захвачен планировщиком (атомарно), sent = выполнен, failed = ошибка, skipped = пропущен';

-- Обновляем индекс: добавляем processing в фильтр
DROP INDEX IF EXISTS idx_automation_trigger_log_pending;
CREATE INDEX IF NOT EXISTS idx_automation_trigger_log_pending
    ON automation_trigger_log(send_at) WHERE status IN ('pending', 'processing');
