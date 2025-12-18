-- schema_23_expenses.sql
-- Таблицы для учёта расходов проекта

-- =============================================================================
-- Категории расходов
-- =============================================================================

CREATE TABLE IF NOT EXISTS expense_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    color VARCHAR(7) DEFAULT '#6B7280',
    is_system BOOLEAN DEFAULT false,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индекс для сортировки
CREATE INDEX IF NOT EXISTS idx_expense_categories_sort ON expense_categories(sort_order);

-- Дефолтные категории
INSERT INTO expense_categories (name, color, is_system, sort_order) VALUES
    ('Реклама', '#F59E0B', true, 0),
    ('Claude code', '#8B5CF6', true, 1),
    ('LLM', '#3B82F6', true, 2),
    ('Server', '#10B981', true, 3)
ON CONFLICT (name) DO NOTHING;


-- =============================================================================
-- Расходы
-- =============================================================================

CREATE TABLE IF NOT EXISTS expenses (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    name VARCHAR(255) NOT NULL,
    category_id INTEGER REFERENCES expense_categories(id) ON DELETE SET NULL,
    amount NUMERIC(12, 2) NOT NULL,
    paid_by VARCHAR(50) NOT NULL CHECK (paid_by IN ('Денис', 'Данил')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы для фильтрации
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date DESC);
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category_id);
CREATE INDEX IF NOT EXISTS idx_expenses_paid_by ON expenses(paid_by);
CREATE INDEX IF NOT EXISTS idx_expenses_created ON expenses(created_at DESC);


-- =============================================================================
-- Триггер для updated_at
-- =============================================================================

CREATE OR REPLACE FUNCTION update_expenses_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_expenses_updated_at ON expenses;
CREATE TRIGGER trigger_expenses_updated_at
    BEFORE UPDATE ON expenses
    FOR EACH ROW
    EXECUTE FUNCTION update_expenses_updated_at();
