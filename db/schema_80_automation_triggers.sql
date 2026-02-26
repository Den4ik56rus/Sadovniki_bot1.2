-- schema_80_automation_triggers.sql
-- Полноценная система автоматических триггеров.
-- Заменяет funnel_stage_triggers + funnel_trigger_log новой универсальной системой.
--
-- 4 типа событий: stage_transition, payment_success, tag_changed, subscription_expiring
-- AND/OR условия, множественные действия, отложенная отправка.

-- ═══════════════════════════════════════════════════════════════════
-- 1. НОВЫЕ ТАБЛИЦЫ
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS automation_triggers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    event_type VARCHAR(30) NOT NULL,
    -- stage_transition | payment_success | tag_changed | subscription_expiring
    event_config JSONB NOT NULL DEFAULT '{}',
    -- Параметры события (зависят от event_type)
    conditions JSONB,
    -- AND/OR дерево условий (null = без условий)
    actions JSONB NOT NULL DEFAULT '[]',
    -- Массив действий (выполняются последовательно)
    delay_minutes INT NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE automation_triggers IS 'Универсальные автоматические триггеры с 4 типами событий';
COMMENT ON COLUMN automation_triggers.event_type IS 'stage_transition | payment_success | tag_changed | subscription_expiring';
COMMENT ON COLUMN automation_triggers.event_config IS 'JSON: stage_transition={funnel_id, stage_key}, payment_success={payment_type, plan_id}, tag_changed={tag_id, action}, subscription_expiring={days_before}';
COMMENT ON COLUMN automation_triggers.conditions IS 'AND/OR дерево: {operator, groups: [{operator, rules: [{type, ...}]}]}';
COMMENT ON COLUMN automation_triggers.actions IS 'Массив: [{type: send_broadcast|move_to_stage|add_tag|remove_tag|set_custom_field|send_payment_offer, ...}]';
COMMENT ON COLUMN automation_triggers.delay_minutes IS 'Задержка выполнения в минутах (0 = немедленно)';

CREATE INDEX IF NOT EXISTS idx_automation_triggers_event_type
    ON automation_triggers(event_type) WHERE is_active = true;


CREATE TABLE IF NOT EXISTS automation_trigger_log (
    id SERIAL PRIMARY KEY,
    trigger_id INT NOT NULL REFERENCES automation_triggers(id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_snapshot JSONB,
    -- Снимок event_data для дедупликации (subscription_expiring: содержит subscription_id)
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending | sent | failed | skipped
    send_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Когда выполнять (для отложенных)
    executed_at TIMESTAMPTZ,
    actions_result JSONB,
    -- Результат каждого действия
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE automation_trigger_log IS 'Лог выполнения автоматических триггеров';
COMMENT ON COLUMN automation_trigger_log.event_snapshot IS 'Снимок event_data для дедупликации (содержит subscription_id для subscription_expiring)';
COMMENT ON COLUMN automation_trigger_log.status IS 'pending = ждёт, sent = выполнен, failed = ошибка, skipped = пропущен';
COMMENT ON COLUMN automation_trigger_log.send_at IS 'Время выполнения (для отложенных — NOW + delay_minutes)';

CREATE INDEX IF NOT EXISTS idx_automation_trigger_log_pending
    ON automation_trigger_log(send_at) WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_automation_trigger_log_trigger
    ON automation_trigger_log(trigger_id);

CREATE INDEX IF NOT EXISTS idx_automation_trigger_log_user
    ON automation_trigger_log(user_id);


-- ═══════════════════════════════════════════════════════════════════
-- 2. МИГРАЦИЯ ДАННЫХ ИЗ funnel_stage_triggers
-- ═══════════════════════════════════════════════════════════════════

-- Мигрируем существующие триггеры этапов в новую таблицу
INSERT INTO automation_triggers (name, event_type, event_config, conditions, actions, delay_minutes, is_active, created_at)
SELECT
    COALESCE(b.title, 'Триггер #' || fst.id) AS name,
    'stage_transition' AS event_type,
    jsonb_build_object('funnel_id', fst.funnel_id, 'stage_key', fst.stage_key) AS event_config,
    NULL AS conditions,
    CASE
        WHEN fst.payment_config IS NOT NULL THEN
            jsonb_build_array(
                jsonb_build_object(
                    'type', 'send_payment_offer',
                    'plan_id', (fst.payment_config->>'plan_id')::int,
                    'custom_price', CASE WHEN fst.payment_config->>'custom_price' IS NOT NULL
                        THEN (fst.payment_config->>'custom_price')::int ELSE NULL END,
                    'bonus_tokens', CASE WHEN fst.payment_config->>'bonus_tokens' IS NOT NULL
                        THEN (fst.payment_config->>'bonus_tokens')::int ELSE NULL END
                )
            )
        ELSE
            jsonb_build_array(
                jsonb_build_object('type', 'send_broadcast', 'broadcast_id', fst.broadcast_id)
            )
    END AS actions,
    fst.delay_minutes,
    fst.is_active,
    fst.created_at
FROM funnel_stage_triggers fst
LEFT JOIN broadcasts b ON b.id = fst.broadcast_id;

-- Мигрируем лог (сопоставляем trigger_id через порядок)
-- Создаём временную маппинг-таблицу
DO $$
DECLARE
    old_rec RECORD;
    new_trigger_id INT;
BEGIN
    FOR old_rec IN
        SELECT DISTINCT ftl.trigger_id AS old_trigger_id, ftl.user_id, ftl.status,
               ftl.error_message, ftl.send_at, ftl.sent_at AS created_at
        FROM funnel_trigger_log ftl
    LOOP
        -- Находим новый trigger_id через event_config
        SELECT at.id INTO new_trigger_id
        FROM automation_triggers at
        JOIN funnel_stage_triggers fst ON
            at.event_config->>'funnel_id' = fst.funnel_id
            AND at.event_config->>'stage_key' = fst.stage_key
            AND at.event_type = 'stage_transition'
        WHERE fst.id = old_rec.old_trigger_id
        LIMIT 1;

        IF new_trigger_id IS NOT NULL THEN
            INSERT INTO automation_trigger_log (trigger_id, user_id, status, error_message, send_at, created_at)
            VALUES (new_trigger_id, old_rec.user_id, old_rec.status, old_rec.error_message,
                    old_rec.send_at, old_rec.created_at);
        END IF;
    END LOOP;
END $$;
