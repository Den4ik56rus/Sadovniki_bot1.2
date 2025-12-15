-- =============================================================================
-- CRM: Funnel Columns Configuration
-- Настройка колонок воронки продаж (Kanban)
-- =============================================================================

-- Таблица конфигурации колонок воронки
CREATE TABLE IF NOT EXISTS crm_funnel_columns (
    id VARCHAR(50) PRIMARY KEY,  -- 'new', 'tried', 'trial_ended', 'paid', 'custom_1', etc.
    title VARCHAR(100) NOT NULL,
    color VARCHAR(20) NOT NULL DEFAULT '#6B7280',
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_system BOOLEAN DEFAULT false,  -- true для стандартных колонок (нельзя удалить)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индекс для сортировки
CREATE INDEX IF NOT EXISTS idx_funnel_columns_sort ON crm_funnel_columns(sort_order);

-- Комментарии
COMMENT ON TABLE crm_funnel_columns IS 'Конфигурация колонок воронки продаж CRM';
COMMENT ON COLUMN crm_funnel_columns.id IS 'Уникальный идентификатор колонки (new, tried, custom_1, etc.)';
COMMENT ON COLUMN crm_funnel_columns.title IS 'Отображаемое название колонки';
COMMENT ON COLUMN crm_funnel_columns.color IS 'Цвет колонки в формате HEX (#RRGGBB)';
COMMENT ON COLUMN crm_funnel_columns.sort_order IS 'Порядок сортировки (0 = первая)';
COMMENT ON COLUMN crm_funnel_columns.is_system IS 'Системная колонка (нельзя удалить)';

-- Функция для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_funnel_column_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Триггер для автоматического обновления updated_at
DROP TRIGGER IF EXISTS trigger_funnel_column_updated_at ON crm_funnel_columns;
CREATE TRIGGER trigger_funnel_column_updated_at
    BEFORE UPDATE ON crm_funnel_columns
    FOR EACH ROW
    EXECUTE FUNCTION update_funnel_column_updated_at();

-- Инициализация стандартных колонок
INSERT INTO crm_funnel_columns (id, title, color, sort_order, is_system)
VALUES
    ('new', 'НЕРАЗОБРАННОЕ', '#3B82F6', 0, true),
    ('tried', 'БИРЖА ЛИДОВ', '#8B5CF6', 1, true),
    ('trial_ended', 'ВЗЯТ В РАБОТУ', '#F59E0B', 2, true),
    ('paid', 'УЗНАЛ ЦЕНУ', '#22C55E', 3, true)
ON CONFLICT (id) DO UPDATE SET
    title = EXCLUDED.title,
    color = EXCLUDED.color,
    sort_order = EXCLUDED.sort_order,
    is_system = EXCLUDED.is_system;

-- Расширяем status в client_funnel_status для поддержки кастомных колонок
-- (status VARCHAR(30) уже достаточно для 'custom_XXX')

-- Добавляем внешний ключ (опционально, для целостности данных)
-- ALTER TABLE client_funnel_status
-- ADD CONSTRAINT fk_funnel_status_column
-- FOREIGN KEY (status) REFERENCES crm_funnel_columns(id);
