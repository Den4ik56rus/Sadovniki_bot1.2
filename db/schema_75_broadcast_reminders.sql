-- schema_75_broadcast_reminders.sql
-- Напоминалки (reminder broadcasts) — дочерние рассылки, привязанные к родительской.
-- Напоминалка — полноценная строка в broadcasts с parent_broadcast_id.

-- FK на родительскую рассылку
ALTER TABLE broadcasts ADD COLUMN IF NOT EXISTS parent_broadcast_id INT REFERENCES broadcasts(id) ON DELETE CASCADE;

-- Порядок напоминалок внутри родителя
ALTER TABLE broadcasts ADD COLUMN IF NOT EXISTS reminder_sort_order INT DEFAULT 0;

-- За сколько часов (offset)
ALTER TABLE broadcasts ADD COLUMN IF NOT EXISTS reminder_offset_hours NUMERIC;

-- Тип тайминга: 'after_send' | 'before_discount_end'
ALTER TABLE broadcasts ADD COLUMN IF NOT EXISTS reminder_trigger_type VARCHAR(30);

-- Фильтрация аудитории
ALTER TABLE broadcasts ADD COLUMN IF NOT EXISTS reminder_exclude_bought BOOLEAN DEFAULT false;
ALTER TABLE broadcasts ADD COLUMN IF NOT EXISTS reminder_exclude_clicked JSONB;  -- ["opt_0", "opt_1"] или null

-- Расчётное абсолютное время отправки
ALTER TABLE broadcasts ADD COLUMN IF NOT EXISTS reminder_scheduled_at TIMESTAMPTZ;

-- Статус напоминалки: pending → scheduled → sending → sent | cancelled | skipped
ALTER TABLE broadcasts ADD COLUMN IF NOT EXISTS reminder_status VARCHAR(20) DEFAULT 'pending';

-- Индексы
CREATE INDEX IF NOT EXISTS idx_broadcasts_parent ON broadcasts(parent_broadcast_id) WHERE parent_broadcast_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_broadcasts_reminder_schedule ON broadcasts(reminder_scheduled_at)
    WHERE parent_broadcast_id IS NOT NULL AND reminder_status = 'scheduled';
