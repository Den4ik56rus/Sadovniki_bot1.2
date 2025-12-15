-- =============================================================================
-- CRM: Client Funnel Status
-- Статус клиента в воронке продаж для Kanban-доски
-- =============================================================================

-- Таблица статусов клиентов в воронке
CREATE TABLE IF NOT EXISTS client_funnel_status (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,

    -- Текущий статус (может быть изменён вручную)
    status VARCHAR(30) NOT NULL DEFAULT 'new',
    -- Возможные значения: 'new', 'tried', 'trial_ended', 'paid'

    -- Автоматически вычисленный статус (на основе данных)
    auto_status VARCHAR(30),

    -- Флаг ручного переопределения статуса
    manual_override BOOLEAN DEFAULT false,

    -- Метаданные
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_client_funnel_status ON client_funnel_status(status);
CREATE INDEX IF NOT EXISTS idx_client_funnel_updated ON client_funnel_status(updated_at DESC);

-- Комментарии
COMMENT ON TABLE client_funnel_status IS 'Статус клиента в воронке продаж CRM';
COMMENT ON COLUMN client_funnel_status.status IS 'Текущий статус: new, tried, trial_ended, paid';
COMMENT ON COLUMN client_funnel_status.auto_status IS 'Автоматически вычисленный статус на основе активности';
COMMENT ON COLUMN client_funnel_status.manual_override IS 'true если статус был изменён вручную (drag-and-drop)';

-- Функция для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_client_funnel_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Триггер для автоматического обновления updated_at
DROP TRIGGER IF EXISTS trigger_client_funnel_updated_at ON client_funnel_status;
CREATE TRIGGER trigger_client_funnel_updated_at
    BEFORE UPDATE ON client_funnel_status
    FOR EACH ROW
    EXECUTE FUNCTION update_client_funnel_updated_at();

-- Инициализация: создать записи для всех существующих пользователей
-- Статус определяется по наличию консультаций
INSERT INTO client_funnel_status (user_id, status, auto_status)
SELECT
    u.id,
    CASE
        WHEN EXISTS (SELECT 1 FROM topics t WHERE t.user_id = u.id) THEN 'tried'
        ELSE 'new'
    END,
    CASE
        WHEN EXISTS (SELECT 1 FROM topics t WHERE t.user_id = u.id) THEN 'tried'
        ELSE 'new'
    END
FROM users u
WHERE NOT EXISTS (
    SELECT 1 FROM client_funnel_status cfs WHERE cfs.user_id = u.id
);
