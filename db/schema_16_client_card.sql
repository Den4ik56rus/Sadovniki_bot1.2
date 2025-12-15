-- =============================================================================
-- CRM: Расширенная карточка клиента
-- Кастомные поля, теги, задачи, заметки, лента активности
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Расширение таблицы client_funnel_status
-- -----------------------------------------------------------------------------

-- Добавляем приоритет и источник в существующую таблицу
ALTER TABLE client_funnel_status
ADD COLUMN IF NOT EXISTS priority VARCHAR(10) DEFAULT 'normal',
ADD COLUMN IF NOT EXISTS source VARCHAR(255);

COMMENT ON COLUMN client_funnel_status.priority IS 'Приоритет клиента: low, normal, high, vip';
COMMENT ON COLUMN client_funnel_status.source IS 'Источник привлечения клиента';

-- -----------------------------------------------------------------------------
-- 2. Кастомные поля
-- -----------------------------------------------------------------------------

-- Определения кастомных полей (справочник)
CREATE TABLE IF NOT EXISTS client_custom_fields (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    field_type VARCHAR(20) NOT NULL,
    -- Типы: text, number, date, checkbox, select, multiselect
    options JSONB,
    -- Для select/multiselect: ["опция1", "опция2", ...]
    sort_order INTEGER DEFAULT 0,
    is_required BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_custom_fields_sort ON client_custom_fields(sort_order);

COMMENT ON TABLE client_custom_fields IS 'Справочник кастомных полей для карточки клиента';
COMMENT ON COLUMN client_custom_fields.field_type IS 'Тип поля: text, number, date, checkbox, select, multiselect';
COMMENT ON COLUMN client_custom_fields.options IS 'Опции для select/multiselect в формате JSON array';

-- Значения кастомных полей для клиентов
CREATE TABLE IF NOT EXISTS client_custom_field_values (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    field_id INTEGER NOT NULL REFERENCES client_custom_fields(id) ON DELETE CASCADE,
    value_text TEXT,
    value_number DECIMAL,
    value_date DATE,
    value_bool BOOLEAN,
    value_json JSONB,
    -- Для select: "выбранная_опция", для multiselect: ["опция1", "опция2"]
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, field_id)
);

CREATE INDEX IF NOT EXISTS idx_custom_field_values_user ON client_custom_field_values(user_id);
CREATE INDEX IF NOT EXISTS idx_custom_field_values_field ON client_custom_field_values(field_id);

COMMENT ON TABLE client_custom_field_values IS 'Значения кастомных полей для каждого клиента';

-- -----------------------------------------------------------------------------
-- 3. Теги клиентов
-- -----------------------------------------------------------------------------

-- Справочник тегов
CREATE TABLE IF NOT EXISTS client_tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    color VARCHAR(7) DEFAULT '#6B7280',
    -- HEX цвет
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE client_tags IS 'Справочник тегов для клиентов';

-- Связь клиент-тег (many-to-many)
CREATE TABLE IF NOT EXISTS client_tag_links (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES client_tags(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_tag_links_user ON client_tag_links(user_id);
CREATE INDEX IF NOT EXISTS idx_tag_links_tag ON client_tag_links(tag_id);

COMMENT ON TABLE client_tag_links IS 'Связь клиентов с тегами';

-- -----------------------------------------------------------------------------
-- 4. Задачи по клиентам
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS client_tasks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    due_date TIMESTAMPTZ,
    priority VARCHAR(10) DEFAULT 'medium',
    -- low, medium, high
    status VARCHAR(20) DEFAULT 'pending',
    -- pending, completed, cancelled
    assignee VARCHAR(100),
    -- Ответственный (имя/ник)
    reminder_at TIMESTAMPTZ,
    -- Когда напомнить
    repeat_interval VARCHAR(20),
    -- none, daily, weekly, monthly
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tasks_user ON client_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON client_tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON client_tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_reminder ON client_tasks(reminder_at) WHERE reminder_at IS NOT NULL;

COMMENT ON TABLE client_tasks IS 'Задачи по клиентам';
COMMENT ON COLUMN client_tasks.priority IS 'Приоритет: low, medium, high';
COMMENT ON COLUMN client_tasks.status IS 'Статус: pending, completed, cancelled';
COMMENT ON COLUMN client_tasks.repeat_interval IS 'Интервал повторения: none, daily, weekly, monthly';

-- Триггер для обновления updated_at
CREATE OR REPLACE FUNCTION update_client_tasks_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_client_tasks_updated_at ON client_tasks;
CREATE TRIGGER trigger_client_tasks_updated_at
    BEFORE UPDATE ON client_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_client_tasks_updated_at();

-- -----------------------------------------------------------------------------
-- 5. Заметки по клиентам
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS client_notes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notes_user ON client_notes(user_id);
CREATE INDEX IF NOT EXISTS idx_notes_created ON client_notes(created_at DESC);

COMMENT ON TABLE client_notes IS 'Текстовые заметки по клиентам';

-- -----------------------------------------------------------------------------
-- 6. Лента активности
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS client_activity_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_type VARCHAR(30) NOT NULL,
    -- consultation, task_created, task_completed, note, status_change, field_change, tag_change
    event_data JSONB,
    -- Детали события в зависимости от типа
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_activity_user ON client_activity_log(user_id);
CREATE INDEX IF NOT EXISTS idx_activity_type ON client_activity_log(event_type);
CREATE INDEX IF NOT EXISTS idx_activity_created ON client_activity_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_user_created ON client_activity_log(user_id, created_at DESC);

COMMENT ON TABLE client_activity_log IS 'Лента активности по клиенту';
COMMENT ON COLUMN client_activity_log.event_type IS 'Тип события: consultation, task_created, task_completed, note, status_change, field_change, tag_change';
COMMENT ON COLUMN client_activity_log.event_data IS 'JSON с деталями события';

-- -----------------------------------------------------------------------------
-- 7. Триггеры для автоматического логирования
-- -----------------------------------------------------------------------------

-- Логирование изменения статуса воронки
CREATE OR REPLACE FUNCTION log_funnel_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO client_activity_log (user_id, event_type, event_data)
        VALUES (
            NEW.user_id,
            'status_change',
            jsonb_build_object(
                'old_status', OLD.status,
                'new_status', NEW.status
            )
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_log_funnel_status ON client_funnel_status;
CREATE TRIGGER trigger_log_funnel_status
    AFTER UPDATE ON client_funnel_status
    FOR EACH ROW
    EXECUTE FUNCTION log_funnel_status_change();

-- Логирование создания заметки
CREATE OR REPLACE FUNCTION log_note_created()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO client_activity_log (user_id, event_type, event_data)
    VALUES (
        NEW.user_id,
        'note',
        jsonb_build_object(
            'note_id', NEW.id,
            'text_preview', LEFT(NEW.text, 100)
        )
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_log_note ON client_notes;
CREATE TRIGGER trigger_log_note
    AFTER INSERT ON client_notes
    FOR EACH ROW
    EXECUTE FUNCTION log_note_created();

-- Логирование создания задачи
CREATE OR REPLACE FUNCTION log_task_created()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO client_activity_log (user_id, event_type, event_data)
    VALUES (
        NEW.user_id,
        'task_created',
        jsonb_build_object(
            'task_id', NEW.id,
            'title', NEW.title,
            'due_date', NEW.due_date,
            'priority', NEW.priority
        )
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_log_task_created ON client_tasks;
CREATE TRIGGER trigger_log_task_created
    AFTER INSERT ON client_tasks
    FOR EACH ROW
    EXECUTE FUNCTION log_task_created();

-- Логирование завершения задачи
CREATE OR REPLACE FUNCTION log_task_completed()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status != 'completed' AND NEW.status = 'completed' THEN
        INSERT INTO client_activity_log (user_id, event_type, event_data)
        VALUES (
            NEW.user_id,
            'task_completed',
            jsonb_build_object(
                'task_id', NEW.id,
                'title', NEW.title
            )
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_log_task_completed ON client_tasks;
CREATE TRIGGER trigger_log_task_completed
    AFTER UPDATE ON client_tasks
    FOR EACH ROW
    EXECUTE FUNCTION log_task_completed();

-- Логирование изменения тегов
CREATE OR REPLACE FUNCTION log_tag_change()
RETURNS TRIGGER AS $$
DECLARE
    tag_name VARCHAR(50);
BEGIN
    IF TG_OP = 'INSERT' THEN
        SELECT name INTO tag_name FROM client_tags WHERE id = NEW.tag_id;
        INSERT INTO client_activity_log (user_id, event_type, event_data)
        VALUES (
            NEW.user_id,
            'tag_change',
            jsonb_build_object(
                'action', 'added',
                'tag_id', NEW.tag_id,
                'tag_name', tag_name
            )
        );
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        SELECT name INTO tag_name FROM client_tags WHERE id = OLD.tag_id;
        INSERT INTO client_activity_log (user_id, event_type, event_data)
        VALUES (
            OLD.user_id,
            'tag_change',
            jsonb_build_object(
                'action', 'removed',
                'tag_id', OLD.tag_id,
                'tag_name', tag_name
            )
        );
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_log_tag_change ON client_tag_links;
CREATE TRIGGER trigger_log_tag_change
    AFTER INSERT OR DELETE ON client_tag_links
    FOR EACH ROW
    EXECUTE FUNCTION log_tag_change();

-- -----------------------------------------------------------------------------
-- 8. Инициализация
-- -----------------------------------------------------------------------------

-- Создаём несколько тегов по умолчанию
INSERT INTO client_tags (name, color) VALUES
    ('VIP', '#FFD700'),
    ('Оптовик', '#10B981'),
    ('Начинающий', '#3B82F6'),
    ('Профессионал', '#8B5CF6'),
    ('Проблемный', '#EF4444')
ON CONFLICT (name) DO NOTHING;

-- Создаём пару примеров кастомных полей
INSERT INTO client_custom_fields (name, field_type, options, sort_order) VALUES
    ('Площадь участка', 'text', NULL, 1),
    ('Опыт', 'select', '["Начинающий", "Любитель", "Профессионал"]', 2),
    ('Основные культуры', 'multiselect', '["Малина", "Клубника", "Ежевика", "Смородина", "Голубика"]', 3)
ON CONFLICT DO NOTHING;
