-- schema_67: Разрешить повторную отправку триггеров
-- Убираем UNIQUE(trigger_id, user_id) чтобы триггер срабатывал каждый раз при переходе на этап

ALTER TABLE funnel_trigger_log DROP CONSTRAINT IF EXISTS funnel_trigger_log_trigger_id_user_id_key;
