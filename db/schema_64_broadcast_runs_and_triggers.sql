-- schema_64_broadcast_runs_and_triggers.sql
-- Broadcast Runs (повторные запуски рассылок) + Funnel Stage Triggers (триггеры этапов воронки)

-- ═══════════════════════════════════════════════════════════════════════════════
-- 1. BROADCAST RUNS — запуски рассылок (каждая рассылка может быть отправлена несколько раз)
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS broadcast_runs (
    id SERIAL PRIMARY KEY,
    broadcast_id INT NOT NULL REFERENCES broadcasts(id) ON DELETE CASCADE,
    run_number INT NOT NULL DEFAULT 1,
    target_type VARCHAR(20) NOT NULL DEFAULT 'all',
    target_invite_link_id INT,
    target_funnel_id VARCHAR(50),
    target_stage_key VARCHAR(50),
    target_user_ids JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, sending, completed, cancelled, failed
    total_recipients INT DEFAULT 0,
    sent_count INT DEFAULT 0,
    failed_count INT DEFAULT 0,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(broadcast_id, run_number)
);

CREATE INDEX IF NOT EXISTS idx_broadcast_runs_broadcast_id ON broadcast_runs(broadcast_id);
CREATE INDEX IF NOT EXISTS idx_broadcast_runs_status ON broadcast_runs(status);

-- Добавляем run_id в broadcast_recipients
ALTER TABLE broadcast_recipients ADD COLUMN IF NOT EXISTS run_id INT REFERENCES broadcast_runs(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_broadcast_recipients_run_id ON broadcast_recipients(run_id);

-- Пересоздаём unique constraint с учётом run_id (чтобы один и тот же юзер мог быть в разных запусках)
ALTER TABLE broadcast_recipients DROP CONSTRAINT IF EXISTS broadcast_recipients_broadcast_id_user_id_key;
ALTER TABLE broadcast_recipients ADD CONSTRAINT broadcast_recipients_broadcast_run_user_key
    UNIQUE(broadcast_id, run_id, user_id);

-- Добавляем run_id в broadcast_button_clicks
ALTER TABLE broadcast_button_clicks ADD COLUMN IF NOT EXISTS run_id INT REFERENCES broadcast_runs(id) ON DELETE CASCADE;
-- Пересоздаём unique constraint с учётом run_id
ALTER TABLE broadcast_button_clicks DROP CONSTRAINT IF EXISTS broadcast_button_clicks_broadcast_id_user_id_key;
ALTER TABLE broadcast_button_clicks ADD CONSTRAINT broadcast_button_clicks_broadcast_run_user_key
    UNIQUE(broadcast_id, run_id, user_id);

-- Добавляем run_id в broadcast_poll_answers
ALTER TABLE broadcast_poll_answers ADD COLUMN IF NOT EXISTS run_id INT REFERENCES broadcast_runs(id) ON DELETE CASCADE;
ALTER TABLE broadcast_poll_answers DROP CONSTRAINT IF EXISTS broadcast_poll_answers_broadcast_id_telegram_user_id_key;
ALTER TABLE broadcast_poll_answers ADD CONSTRAINT broadcast_poll_answers_broadcast_run_tg_key
    UNIQUE(broadcast_id, run_id, telegram_user_id);

-- Миграция: создать run для уже отправленных рассылок
INSERT INTO broadcast_runs (broadcast_id, run_number, target_type, target_invite_link_id, target_funnel_id, target_stage_key, target_user_ids, status, total_recipients, sent_count, failed_count, started_at, completed_at, created_at)
SELECT id, 1, target_type, target_invite_link_id, target_funnel_id, target_stage_key, target_user_ids,
       status, total_recipients, sent_count, failed_count, started_at, completed_at, created_at
FROM broadcasts
WHERE status IN ('completed', 'failed', 'sending', 'cancelled')
ON CONFLICT DO NOTHING;

-- Привязываем существующие recipients к run
UPDATE broadcast_recipients br
SET run_id = brun.id
FROM broadcast_runs brun
WHERE br.broadcast_id = brun.broadcast_id AND brun.run_number = 1 AND br.run_id IS NULL;

-- Привязываем существующие button clicks к run
UPDATE broadcast_button_clicks bbc
SET run_id = brun.id
FROM broadcast_runs brun
WHERE bbc.broadcast_id = brun.broadcast_id AND brun.run_number = 1 AND bbc.run_id IS NULL;

-- Привязываем существующие poll answers к run
UPDATE broadcast_poll_answers bpa
SET run_id = brun.id
FROM broadcast_runs brun
WHERE bpa.broadcast_id = brun.broadcast_id AND brun.run_number = 1 AND bpa.run_id IS NULL;


-- ═══════════════════════════════════════════════════════════════════════════════
-- 2. FUNNEL STAGE TRIGGERS — автоматическая отправка рассылки при смене этапа
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS funnel_stage_triggers (
    id SERIAL PRIMARY KEY,
    funnel_id VARCHAR(50) NOT NULL,
    stage_key VARCHAR(50) NOT NULL,
    broadcast_id INT NOT NULL REFERENCES broadcasts(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(funnel_id, stage_key, broadcast_id),
    FOREIGN KEY (funnel_id, stage_key) REFERENCES funnel_stages(funnel_id, stage_key) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_funnel_stage_triggers_stage ON funnel_stage_triggers(funnel_id, stage_key);

-- Логирование отправленных триггеров (один триггер на пользователя — не повторяем)
CREATE TABLE IF NOT EXISTS funnel_trigger_log (
    id SERIAL PRIMARY KEY,
    trigger_id INT NOT NULL REFERENCES funnel_stage_triggers(id) ON DELETE CASCADE,
    user_id INT NOT NULL,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'sent',  -- sent, failed
    error_message TEXT,
    UNIQUE(trigger_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_funnel_trigger_log_trigger ON funnel_trigger_log(trigger_id);
CREATE INDEX IF NOT EXISTS idx_funnel_trigger_log_user ON funnel_trigger_log(user_id);
