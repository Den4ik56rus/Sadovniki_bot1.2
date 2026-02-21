-- schema_62_broadcasts.sql
-- Система рассылок (broadcasts) из админ-панели

CREATE TABLE IF NOT EXISTS broadcasts (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,

    -- Контент
    message_text TEXT,
    photo_path TEXT,
    poll_question VARCHAR(300),
    poll_options JSONB,
    poll_is_anonymous BOOLEAN DEFAULT true,
    poll_allows_multiple BOOLEAN DEFAULT false,

    -- Таргетинг
    target_type VARCHAR(20) NOT NULL,
    target_invite_link_id INT REFERENCES invite_links(id) ON DELETE SET NULL,
    target_funnel_id VARCHAR(50),
    target_stage_key VARCHAR(50),
    target_user_ids JSONB,

    -- Планирование
    scheduled_at TIMESTAMPTZ,

    -- Статус и прогресс
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    total_recipients INT DEFAULT 0,
    sent_count INT DEFAULT 0,
    failed_count INT DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS broadcast_recipients (
    id SERIAL PRIMARY KEY,
    broadcast_id INT NOT NULL REFERENCES broadcasts(id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(id),
    telegram_user_id BIGINT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    error_message TEXT,
    sent_at TIMESTAMPTZ,
    UNIQUE(broadcast_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_broadcast_recipients_broadcast ON broadcast_recipients(broadcast_id);
CREATE INDEX IF NOT EXISTS idx_broadcasts_status ON broadcasts(status);
CREATE INDEX IF NOT EXISTS idx_broadcasts_scheduled ON broadcasts(scheduled_at) WHERE status = 'scheduled';
