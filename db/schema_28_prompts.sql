-- Schema 28: Prompt Editor System
-- Система редактирования промптов через админку

-- Группы промптов (верхний уровень)
CREATE TABLE IF NOT EXISTS prompt_groups (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(50) NOT NULL UNIQUE,          -- 'base', 'categories', 'references', 'article'
    name VARCHAR(100) NOT NULL,                -- 'Базовые секции', 'Категории', etc.
    description TEXT,
    icon VARCHAR(10),                          -- emoji для UI
    sort_order INTEGER DEFAULT 0,
    is_system BOOLEAN DEFAULT FALSE,           -- нельзя удалить
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Подгруппы (вложенные папки)
CREATE TABLE IF NOT EXISTS prompt_subgroups (
    id SERIAL PRIMARY KEY,
    group_id INTEGER NOT NULL REFERENCES prompt_groups(id) ON DELETE CASCADE,
    slug VARCHAR(50) NOT NULL,                 -- 'nutrition', 'diseases_pests', etc.
    name VARCHAR(100) NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    is_system BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(group_id, slug)
);

-- Промпты (редактируемые тексты)
CREATE TABLE IF NOT EXISTS prompts (
    id SERIAL PRIMARY KEY,
    group_id INTEGER NOT NULL REFERENCES prompt_groups(id) ON DELETE CASCADE,
    subgroup_id INTEGER REFERENCES prompt_subgroups(id) ON DELETE SET NULL,

    slug VARCHAR(100) NOT NULL,                -- 'role', 'strawberry', etc.
    name VARCHAR(200) NOT NULL,                -- 'Роль агронома', 'Клубника (питание)'
    description TEXT,                          -- Краткое описание назначения

    content TEXT NOT NULL,                     -- Текст промпта

    -- Метаданные
    is_enabled BOOLEAN DEFAULT TRUE,           -- ВКЛ/ВЫКЛ промпт
    use_minimal_base BOOLEAN DEFAULT FALSE,    -- Использовать минимальный базовый промпт
    is_system BOOLEAN DEFAULT FALSE,           -- Системный (нельзя удалить)

    -- Версионирование
    version INTEGER DEFAULT 1,
    updated_by VARCHAR(100),                   -- Кто обновил

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(group_id, subgroup_id, slug)
);

-- История изменений промптов
CREATE TABLE IF NOT EXISTS prompt_history (
    id SERIAL PRIMARY KEY,
    prompt_id INTEGER NOT NULL REFERENCES prompts(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    changed_by VARCHAR(100),
    change_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_prompts_group ON prompts(group_id);
CREATE INDEX IF NOT EXISTS idx_prompts_subgroup ON prompts(subgroup_id);
CREATE INDEX IF NOT EXISTS idx_prompts_slug ON prompts(slug);
CREATE INDEX IF NOT EXISTS idx_prompts_enabled ON prompts(is_enabled);
CREATE INDEX IF NOT EXISTS idx_prompt_history_prompt ON prompt_history(prompt_id);
CREATE INDEX IF NOT EXISTS idx_prompt_groups_slug ON prompt_groups(slug);
CREATE INDEX IF NOT EXISTS idx_prompt_subgroups_slug ON prompt_subgroups(group_id, slug);

-- Триггер для updated_at и version
CREATE OR REPLACE FUNCTION update_prompts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    IF OLD.content IS DISTINCT FROM NEW.content THEN
        NEW.version = OLD.version + 1;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_prompts_updated_at ON prompts;
CREATE TRIGGER trigger_prompts_updated_at
    BEFORE UPDATE ON prompts
    FOR EACH ROW
    EXECUTE FUNCTION update_prompts_updated_at();

-- Триггер для сохранения истории при изменении content
CREATE OR REPLACE FUNCTION save_prompt_history()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.content IS DISTINCT FROM NEW.content THEN
        INSERT INTO prompt_history (prompt_id, version, content, changed_by)
        VALUES (OLD.id, OLD.version, OLD.content, NEW.updated_by);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_save_prompt_history ON prompts;
CREATE TRIGGER trigger_save_prompt_history
    BEFORE UPDATE ON prompts
    FOR EACH ROW
    EXECUTE FUNCTION save_prompt_history();

-- ============================================================================
-- Начальные данные: группы и подгруппы
-- ============================================================================

-- Группы
INSERT INTO prompt_groups (slug, name, description, icon, sort_order, is_system) VALUES
    ('base', 'Базовые секции', 'Основные части системного промпта', '📋', 1, TRUE),
    ('categories', 'Категории консультаций', 'Промпты для разных типов консультаций', '📁', 2, TRUE),
    ('references', 'Справочники', 'Справочные материалы (удобрения, СЗР, сорта)', '📚', 3, TRUE),
    ('article', 'Режим статей', 'Промпты для генерации статей', '📝', 4, TRUE),
    ('other', 'Прочее', 'Дополнительные промпты', '📄', 5, FALSE)
ON CONFLICT (slug) DO NOTHING;

-- Подгруппы для категорий
INSERT INTO prompt_subgroups (group_id, slug, name, description, sort_order, is_system)
SELECT g.id, s.slug, s.name, s.description, s.sort_order, TRUE
FROM prompt_groups g,
(VALUES
    ('nutrition', 'Питание растений', 'Схемы подкормок и удобрений', 1),
    ('diseases_pests', 'Защита растений', 'Болезни и вредители', 2),
    ('planting_care', 'Посадка и уход', 'Посадка, обрезка, полив', 3),
    ('soil_improvement', 'Улучшение почвы', 'Подготовка и улучшение почвы', 4),
    ('variety_selection', 'Подбор сортов', 'Рекомендации по сортам', 5)
) AS s(slug, name, description, sort_order)
WHERE g.slug = 'categories'
ON CONFLICT (group_id, slug) DO NOTHING;
