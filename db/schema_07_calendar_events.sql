-- schema_07_calendar_events.sql
-- Таблица событий календаря садовых работ

CREATE TABLE IF NOT EXISTS calendar_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Основные поля
    title TEXT NOT NULL,
    start_date_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_date_time TIMESTAMP WITH TIME ZONE,
    all_day BOOLEAN DEFAULT FALSE,

    -- Классификация
    type TEXT NOT NULL CHECK (type IN ('nutrition', 'soil', 'protection', 'harvest', 'planting', 'other')),
    culture_code TEXT,              -- код культуры (клубника_ремонтантная и т.д.)
    plot_id TEXT,                   -- название участка

    -- Статус
    status TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'done', 'skipped')),

    -- Дополнительно
    description TEXT,
    tags TEXT[],                    -- массив тегов
    color TEXT,                     -- hex-цвет для кастомизации

    -- Метаданные
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_calendar_events_user_id ON calendar_events(user_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_start ON calendar_events(start_date_time);
CREATE INDEX IF NOT EXISTS idx_calendar_events_user_start ON calendar_events(user_id, start_date_time);
CREATE INDEX IF NOT EXISTS idx_calendar_events_type ON calendar_events(type);

-- Комментарии
COMMENT ON TABLE calendar_events IS 'События календаря садовых работ';
COMMENT ON COLUMN calendar_events.type IS 'Тип: nutrition, soil, protection, harvest, planting, other';
COMMENT ON COLUMN calendar_events.status IS 'Статус: planned, done, skipped';
