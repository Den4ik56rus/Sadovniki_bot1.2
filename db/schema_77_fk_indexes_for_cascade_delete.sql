-- schema_77_fk_indexes_for_cascade_delete.sql
-- Индексы на FK-колонках для ускорения каскадного удаления рассылок.
-- Без этих индексов DELETE FROM broadcasts вызывает full table scan
-- на каждой дочерней таблице, блокируя все параллельные запросы.

CREATE INDEX IF NOT EXISTS idx_broadcast_button_clicks_run_id
    ON broadcast_button_clicks(run_id);

CREATE INDEX IF NOT EXISTS idx_broadcast_poll_answers_run_id
    ON broadcast_poll_answers(run_id);

CREATE INDEX IF NOT EXISTS idx_broadcast_discounts_broadcast_id
    ON broadcast_discounts(broadcast_id);

CREATE INDEX IF NOT EXISTS idx_funnel_stage_triggers_broadcast_id
    ON funnel_stage_triggers(broadcast_id);
