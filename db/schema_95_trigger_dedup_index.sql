-- schema_95: Уникальный индекс для дедупликации немедленных триггеров
-- Решает race condition в emit_automation_event для немедленных (delay=0) триггеров.
--
-- Проблема: SELECT has_been_triggered() → execute_actions() → INSERT log
-- Если два asyncio.create_task() вызваны почти одновременно — оба пройдут SELECT до INSERT.
--
-- Решение: атомарный INSERT ON CONFLICT DO NOTHING перед выполнением действий.
-- Нужен UNIQUE индекс на (trigger_id, user_id) только для активных (не skipped/failed) записей.
--
-- Для subscription_expiring повторы по разным подпискам остаются возможными —
-- там event_snapshot содержит subscription_id, и уникальность проверяется по нему.

-- Уникальный индекс: только один 'processing' или 'sent'/'pending' на пару (trigger_id, user_id)
-- Partial index — не мешает 'skipped' и 'failed' записям (они не блокируют повтор).
CREATE UNIQUE INDEX IF NOT EXISTS idx_automation_trigger_log_dedup
    ON automation_trigger_log(trigger_id, user_id)
    WHERE status IN ('pending', 'processing', 'sent');
