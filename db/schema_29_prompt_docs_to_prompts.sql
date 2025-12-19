-- =============================================================================
-- Schema 29: Добавление промт-документов в систему промптов
-- Промт-документы теперь редактируются как текст в редакторе промптов
-- =============================================================================

-- 1. Добавляем новую группу для промт-документов
INSERT INTO prompt_groups (slug, name, description, icon, sort_order, is_system)
VALUES (
    'prompt_docs',
    'Промт-документы',
    'Специализированные инструкции по культурам и типам работ',
    '📋',
    5,  -- после references
    TRUE
)
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    icon = EXCLUDED.icon;

-- 2. Добавляем подгруппы для культур
-- Клубника
INSERT INTO prompt_subgroups (group_id, slug, name, description, sort_order, is_system)
SELECT g.id, 'strawberry', 'Клубника', 'Промт-документы для клубники', 0, TRUE
FROM prompt_groups g WHERE g.slug = 'prompt_docs'
ON CONFLICT (group_id, slug) DO NOTHING;

-- Малина
INSERT INTO prompt_subgroups (group_id, slug, name, description, sort_order, is_system)
SELECT g.id, 'raspberry', 'Малина', 'Промт-документы для малины', 1, TRUE
FROM prompt_groups g WHERE g.slug = 'prompt_docs'
ON CONFLICT (group_id, slug) DO NOTHING;

-- Кустарники
INSERT INTO prompt_subgroups (group_id, slug, name, description, sort_order, is_system)
SELECT g.id, 'bushes', 'Кустарники', 'Промт-документы для кустарников (голубика, смородина и др.)', 2, TRUE
FROM prompt_groups g WHERE g.slug = 'prompt_docs'
ON CONFLICT (group_id, slug) DO NOTHING;

-- 3. Миграция существующих промт-документов в таблицу prompts
-- Формат slug: {subculture}_{work_type}
-- Например: strawberry_summer_nutrition, raspberry_remontant_protection

-- Функция для генерации slug
CREATE OR REPLACE FUNCTION generate_prompt_doc_slug(
    culture_name TEXT,
    subculture_name TEXT,
    work_type_name TEXT
) RETURNS TEXT AS $$
DECLARE
    culture_slug TEXT;
    subculture_slug TEXT;
    work_type_slug TEXT;
BEGIN
    -- Маппинг культур
    culture_slug := CASE
        WHEN culture_name = 'Клубника' THEN 'strawberry'
        WHEN culture_name = 'Малина' THEN 'raspberry'
        WHEN culture_name = 'Кустарники' THEN 'bushes'
        ELSE LOWER(REPLACE(culture_name, ' ', '_'))
    END;

    -- Маппинг подкультур
    subculture_slug := CASE
        WHEN subculture_name IS NULL THEN ''
        WHEN subculture_name = 'летняя' THEN 'summer'
        WHEN subculture_name = 'ремонтантная' THEN 'remontant'
        WHEN subculture_name = 'общая' THEN 'general'
        ELSE LOWER(REPLACE(subculture_name, ' ', '_'))
    END;

    -- Маппинг типов работ
    work_type_slug := CASE
        WHEN work_type_name = 'Питание растений' THEN 'nutrition'
        WHEN work_type_name = 'Защита растений' THEN 'protection'
        WHEN work_type_name = 'Посадка и уход' THEN 'planting'
        WHEN work_type_name = 'Улучшение почвы' THEN 'soil'
        WHEN work_type_name = 'Подбор сорта' THEN 'variety'
        ELSE LOWER(REPLACE(work_type_name, ' ', '_'))
    END;

    -- Собираем slug
    IF subculture_slug = '' THEN
        RETURN work_type_slug;
    ELSE
        RETURN subculture_slug || '_' || work_type_slug;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Функция для генерации человекочитаемого имени
CREATE OR REPLACE FUNCTION generate_prompt_doc_name(
    subculture_name TEXT,
    work_type_name TEXT
) RETURNS TEXT AS $$
BEGIN
    IF subculture_name IS NULL OR subculture_name = '' THEN
        RETURN work_type_name;
    ELSE
        RETURN subculture_name || ' — ' || work_type_name;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Миграция данных
INSERT INTO prompts (
    group_id,
    subgroup_id,
    slug,
    name,
    description,
    content,
    is_enabled,
    use_minimal_base,
    is_system,
    updated_by
)
SELECT
    g.id as group_id,
    s.id as subgroup_id,
    generate_prompt_doc_slug(c.name, sc.name, w.name) as slug,
    generate_prompt_doc_name(sc.name, w.name) as name,
    'Промт-документ: ' || c.name || COALESCE(' ' || sc.name, '') || ' / ' || w.name as description,
    COALESCE(d.content_text, '') as content,
    TRUE as is_enabled,
    FALSE as use_minimal_base,
    TRUE as is_system,
    'migration' as updated_by
FROM prompt_documents d
JOIN prompt_cultures c ON c.id = d.culture_id
LEFT JOIN prompt_subcultures sc ON sc.id = d.subculture_id
JOIN prompt_work_types w ON w.id = d.work_type_id
JOIN prompt_groups g ON g.slug = 'prompt_docs'
JOIN prompt_subgroups s ON s.group_id = g.id AND s.slug = CASE
    WHEN c.name = 'Клубника' THEN 'strawberry'
    WHEN c.name = 'Малина' THEN 'raspberry'
    WHEN c.name = 'Кустарники' THEN 'bushes'
END
WHERE d.extraction_status = 'completed' AND d.content_text IS NOT NULL
ON CONFLICT (group_id, slug) WHERE subgroup_id IS NULL DO UPDATE SET
    content = EXCLUDED.content,
    updated_at = NOW(),
    updated_by = 'migration';

-- Для промптов с subgroup_id нужен отдельный ON CONFLICT
-- PostgreSQL не поддерживает условный ON CONFLICT, поэтому используем UPSERT через DO UPDATE
-- Конфликты обрабатываются через unique constraint

-- Очистка временных функций
DROP FUNCTION IF EXISTS generate_prompt_doc_slug(TEXT, TEXT, TEXT);
DROP FUNCTION IF EXISTS generate_prompt_doc_name(TEXT, TEXT);

-- 4. Добавляем комментарий
COMMENT ON TABLE prompts IS 'Все промпты системы, включая базовые, категорийные и промт-документы';
