-- schema_97_tripwire_followup.sql
-- Воронка дожима для пользователей, не купивших tripwire (99₽ план).
--
-- DB-backed scheduling: фоновый loop каждые 30 сек подбирает
-- записи WHERE status='pending' AND send_at <= NOW().
--
-- 4 этапа:
--   1 — «почему не купил?» (10-15 мин после оффера)
--   2 — ответ на причину (сразу после выбора)
--   3 — универсальный follow-up (2-3 ч)
--   4 — финальное напоминание (24 ч)

CREATE TABLE IF NOT EXISTS tripwire_followup (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    telegram_user_id BIGINT NOT NULL,

    -- Контекст квиза (копия из user_quiz_answers на момент enrollment)
    culture TEXT,          -- "клубники", "малины" (display name)
    problem TEXT,          -- "мелкие ягоды" (display name)
    problem_key TEXT,      -- "straw_s_low_yield"

    -- Этап воронки
    stage SMALLINT NOT NULL,    -- 1, 2, 3, 4
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending | sent | cancelled | failed

    -- Причина отказа (заполняется при ответе на stage 1)
    non_buyer_reason TEXT,
    -- diagnosis_wrong | want_details | not_urgent

    -- Расписание
    send_at TIMESTAMPTZ NOT NULL,
    sent_at TIMESTAMPTZ,

    -- Отслеживание
    offer_shown_at TIMESTAMPTZ NOT NULL,
    support_requested BOOLEAN NOT NULL DEFAULT false,
    error_message TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Основной индекс: pending-записи для отправки (используется scheduler loop)
CREATE INDEX IF NOT EXISTS idx_tripwire_followup_pending
    ON tripwire_followup(send_at) WHERE status = 'pending';

-- Поиск по пользователю (для отмены при оплате, дедупликации)
CREATE INDEX IF NOT EXISTS idx_tripwire_followup_user
    ON tripwire_followup(user_id);

-- Уникальность: один stage на пользователя среди активных записей
CREATE UNIQUE INDEX IF NOT EXISTS idx_tripwire_followup_user_stage
    ON tripwire_followup(user_id, stage) WHERE status IN ('pending', 'sent');
