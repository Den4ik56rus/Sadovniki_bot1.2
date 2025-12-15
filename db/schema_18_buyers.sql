-- Schema 18: Buyers section (customers who paid)
-- Покупатели - клиенты, которые оплатили подписку

-- Таблица статусов покупателей
CREATE TABLE IF NOT EXISTS buyer_status (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'pending_payment',
    manual_override BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индекс по статусу для группировки
CREATE INDEX IF NOT EXISTS idx_buyer_status_status ON buyer_status(status);

-- Триггер для updated_at
CREATE OR REPLACE FUNCTION update_buyer_status_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_buyer_status_updated_at ON buyer_status;
CREATE TRIGGER trigger_buyer_status_updated_at
    BEFORE UPDATE ON buyer_status
    FOR EACH ROW
    EXECUTE FUNCTION update_buyer_status_updated_at();

-- Колонки канбана покупателей
CREATE TABLE IF NOT EXISTS buyer_funnel_columns (
    id VARCHAR(50) PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    color VARCHAR(20) DEFAULT '#6B7280',
    sort_order INTEGER DEFAULT 0,
    is_system BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Триггер для updated_at колонок
DROP TRIGGER IF EXISTS trigger_buyer_funnel_columns_updated_at ON buyer_funnel_columns;
CREATE TRIGGER trigger_buyer_funnel_columns_updated_at
    BEFORE UPDATE ON buyer_funnel_columns
    FOR EACH ROW
    EXECUTE FUNCTION update_buyer_status_updated_at();

-- Seed системные колонки
INSERT INTO buyer_funnel_columns (id, title, color, sort_order, is_system) VALUES
    ('pending_payment', 'Ожидает оплаты', '#F59E0B', 0, true),
    ('paid', 'Оплачено', '#22C55E', 1, true),
    ('active', 'Активна', '#3B82F6', 2, true),
    ('expired', 'Истекла', '#EF4444', 3, true)
ON CONFLICT (id) DO NOTHING;

-- Логирование активности покупателей (используем общую таблицу client_activity_log)
-- Добавляем триггер для логирования изменений статуса покупателя
CREATE OR REPLACE FUNCTION log_buyer_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO client_activity_log (user_id, event_type, event_data)
        VALUES (
            NEW.user_id,
            'buyer_status_change',
            jsonb_build_object(
                'old_status', OLD.status,
                'new_status', NEW.status,
                'manual_override', NEW.manual_override
            )
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_log_buyer_status_change ON buyer_status;
CREATE TRIGGER trigger_log_buyer_status_change
    AFTER UPDATE ON buyer_status
    FOR EACH ROW
    EXECUTE FUNCTION log_buyer_status_change();
