-- schema_19_unified_funnels.sql
-- Универсальная система воронок
-- Объединяет CRM и Buyers в единую архитектуру

-- ═══════════════════════════════════════════════════════════════════════════════
-- 1. ТАБЛИЦА ВОРОНОК (реестр всех воронок)
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS funnels (
    id VARCHAR(50) PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    description TEXT,
    icon VARCHAR(50) DEFAULT 'deals',
    sort_order INTEGER DEFAULT 0,
    is_system BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индекс для сортировки
CREATE INDEX IF NOT EXISTS idx_funnels_sort_order ON funnels(sort_order);

-- ═══════════════════════════════════════════════════════════════════════════════
-- 2. ТАБЛИЦА ЭТАПОВ ВОРОНОК (колонки Kanban)
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS funnel_stages (
    id SERIAL PRIMARY KEY,
    funnel_id VARCHAR(50) NOT NULL REFERENCES funnels(id) ON DELETE CASCADE,
    stage_key VARCHAR(50) NOT NULL,
    title VARCHAR(100) NOT NULL,
    color VARCHAR(20) DEFAULT '#6B7280',
    sort_order INTEGER DEFAULT 0,
    is_system BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(funnel_id, stage_key)
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_funnel_stages_funnel ON funnel_stages(funnel_id);
CREATE INDEX IF NOT EXISTS idx_funnel_stages_sort ON funnel_stages(funnel_id, sort_order);

-- ═══════════════════════════════════════════════════════════════════════════════
-- 3. ПОЗИЦИЯ КЛИЕНТА В ВОРОНКЕ
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS client_funnel_position (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    funnel_id VARCHAR(50) NOT NULL REFERENCES funnels(id) ON DELETE CASCADE,
    stage_key VARCHAR(50) NOT NULL,
    manual_override BOOLEAN DEFAULT false,
    entered_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, funnel_id)
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_client_funnel_position_funnel ON client_funnel_position(funnel_id);
CREATE INDEX IF NOT EXISTS idx_client_funnel_position_stage ON client_funnel_position(funnel_id, stage_key);

-- ═══════════════════════════════════════════════════════════════════════════════
-- 4. ТРИГГЕР ДЛЯ ОБНОВЛЕНИЯ updated_at
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION update_funnel_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Триггеры
DROP TRIGGER IF EXISTS trigger_funnels_updated_at ON funnels;
CREATE TRIGGER trigger_funnels_updated_at
    BEFORE UPDATE ON funnels
    FOR EACH ROW EXECUTE FUNCTION update_funnel_updated_at();

DROP TRIGGER IF EXISTS trigger_funnel_stages_updated_at ON funnel_stages;
CREATE TRIGGER trigger_funnel_stages_updated_at
    BEFORE UPDATE ON funnel_stages
    FOR EACH ROW EXECUTE FUNCTION update_funnel_updated_at();

DROP TRIGGER IF EXISTS trigger_client_funnel_position_updated_at ON client_funnel_position;
CREATE TRIGGER trigger_client_funnel_position_updated_at
    BEFORE UPDATE ON client_funnel_position
    FOR EACH ROW EXECUTE FUNCTION update_funnel_updated_at();

-- ═══════════════════════════════════════════════════════════════════════════════
-- 5. НАЧАЛЬНЫЕ ДАННЫЕ: СИСТЕМНЫЕ ВОРОНКИ
-- ═══════════════════════════════════════════════════════════════════════════════

-- Воронка CRM (Сделки)
INSERT INTO funnels (id, title, description, icon, sort_order, is_system)
VALUES ('crm', 'Воронка CRM', 'Основная воронка продаж', 'deals', 0, true)
ON CONFLICT (id) DO NOTHING;

-- Воронка Покупатели
INSERT INTO funnels (id, title, description, icon, sort_order, is_system)
VALUES ('buyers', 'Покупатели', 'Клиенты с активной подпиской', 'buyers', 1, true)
ON CONFLICT (id) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════════
-- 6. НАЧАЛЬНЫЕ ЭТАПЫ ДЛЯ CRM
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO funnel_stages (funnel_id, stage_key, title, color, sort_order, is_system) VALUES
    ('crm', 'new', 'Новый пользователь', '#3B82F6', 0, true),
    ('crm', 'tried', 'Получил консультацию', '#8B5CF6', 1, true),
    ('crm', 'trial_ended', 'Закончился пробный', '#F59E0B', 2, true),
    ('crm', 'paid', 'Оплатил', '#22C55E', 3, true)
ON CONFLICT (funnel_id, stage_key) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════════
-- 7. НАЧАЛЬНЫЕ ЭТАПЫ ДЛЯ BUYERS
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO funnel_stages (funnel_id, stage_key, title, color, sort_order, is_system) VALUES
    ('buyers', 'pending_payment', 'Активная подписка', '#F59E0B', 0, true),
    ('buyers', 'paid', 'подходит к концу', '#22C55E', 1, true),
    ('buyers', 'active', 'Активна', '#3B82F6', 2, true),
    ('buyers', 'expired', 'Истекла', '#EF4444', 3, true)
ON CONFLICT (funnel_id, stage_key) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════════
-- 8. МИГРАЦИЯ ДАННЫХ ИЗ СТАРЫХ ТАБЛИЦ
-- ═══════════════════════════════════════════════════════════════════════════════

-- Миграция из client_funnel_status в client_funnel_position
INSERT INTO client_funnel_position (user_id, funnel_id, stage_key, manual_override, entered_at, updated_at)
SELECT
    user_id,
    'crm' as funnel_id,
    COALESCE(status, 'new') as stage_key,
    COALESCE(manual_override, false),
    COALESCE(created_at, NOW()) as entered_at,
    COALESCE(updated_at, NOW()) as updated_at
FROM client_funnel_status
WHERE EXISTS (SELECT 1 FROM users WHERE users.id = client_funnel_status.user_id)
ON CONFLICT (user_id, funnel_id) DO NOTHING;

-- Миграция из buyer_status в client_funnel_position
INSERT INTO client_funnel_position (user_id, funnel_id, stage_key, manual_override, entered_at, updated_at)
SELECT
    user_id,
    'buyers' as funnel_id,
    COALESCE(status, 'pending_payment') as stage_key,
    COALESCE(manual_override, false),
    COALESCE(created_at, NOW()) as entered_at,
    COALESCE(updated_at, NOW()) as updated_at
FROM buyer_status
WHERE EXISTS (SELECT 1 FROM users WHERE users.id = buyer_status.user_id)
ON CONFLICT (user_id, funnel_id) DO NOTHING;

-- Миграция кастомных колонок из crm_funnel_columns
INSERT INTO funnel_stages (funnel_id, stage_key, title, color, sort_order, is_system)
SELECT
    'crm',
    id,
    title,
    color,
    sort_order,
    is_system
FROM crm_funnel_columns
WHERE id NOT IN ('new', 'tried', 'trial_ended', 'paid')
ON CONFLICT (funnel_id, stage_key) DO UPDATE SET
    title = EXCLUDED.title,
    color = EXCLUDED.color,
    sort_order = EXCLUDED.sort_order;

-- Миграция кастомных колонок из buyer_funnel_columns
INSERT INTO funnel_stages (funnel_id, stage_key, title, color, sort_order, is_system)
SELECT
    'buyers',
    id,
    title,
    color,
    sort_order,
    is_system
FROM buyer_funnel_columns
WHERE id NOT IN ('pending_payment', 'paid', 'active', 'expired')
ON CONFLICT (funnel_id, stage_key) DO UPDATE SET
    title = EXCLUDED.title,
    color = EXCLUDED.color,
    sort_order = EXCLUDED.sort_order;

-- ═══════════════════════════════════════════════════════════════════════════════
-- 9. ЛОГИРОВАНИЕ ПЕРЕМЕЩЕНИЙ МЕЖДУ ВОРОНКАМИ
-- ═══════════════════════════════════════════════════════════════════════════════

-- Добавляем новый тип события в client_activity_log
-- (таблица уже существует, просто будем использовать event_type = 'funnel_transfer')

-- ═══════════════════════════════════════════════════════════════════════════════
-- ПРИМЕЧАНИЕ: Старые таблицы НЕ удаляются для обратной совместимости
-- client_funnel_status, buyer_status, crm_funnel_columns, buyer_funnel_columns
-- можно удалить после полного перехода на новую систему
-- ═══════════════════════════════════════════════════════════════════════════════
