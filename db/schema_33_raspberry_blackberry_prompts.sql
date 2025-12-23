-- =============================================================================
-- Schema 33: Малина + Ежевика — структура промтов
-- Переименование подгруппы и добавление промптов по аналогии с Клубникой
-- =============================================================================

-- 1. Переименовать подгруппу "Малина" → "Малина + Ежевика"
UPDATE prompt_subgroups
SET name = 'Малина + Ежевика',
    description = 'Промт-документы для малины и ежевики'
WHERE slug = 'raspberry'
  AND group_id = (SELECT id FROM prompt_groups WHERE slug = 'prompt_docs');

-- 2. Добавить промпты для Малина + Ежевика
-- Структура: Ежевика, Летняя, Общее, Рем (по аналогии со скриншотом)

-- Получаем ID группы и подгруппы
DO $$
DECLARE
    v_group_id INT;
    v_subgroup_id INT;
BEGIN
    SELECT id INTO v_group_id FROM prompt_groups WHERE slug = 'prompt_docs';
    SELECT id INTO v_subgroup_id FROM prompt_subgroups WHERE slug = 'raspberry' AND group_id = v_group_id;

    -- Ежевика (blackberry) — все типы работ
    INSERT INTO prompts (group_id, subgroup_id, slug, name, description, content, is_enabled, use_minimal_base, is_system, updated_by)
    VALUES
        (v_group_id, v_subgroup_id, 'blackberry_nutrition', 'ежевика — Питание растений', 'Промт-документ: Малина + Ежевика ежевика / Питание растений', '', TRUE, FALSE, TRUE, 'migration'),
        (v_group_id, v_subgroup_id, 'blackberry_protection', 'ежевика — Защита растений', 'Промт-документ: Малина + Ежевика ежевика / Защита растений', '', TRUE, FALSE, TRUE, 'migration'),
        (v_group_id, v_subgroup_id, 'blackberry_planting', 'ежевика — Посадка и уход', 'Промт-документ: Малина + Ежевика ежевика / Посадка и уход', '', TRUE, FALSE, TRUE, 'migration'),
        (v_group_id, v_subgroup_id, 'blackberry_soil', 'ежевика — Улучшение почвы', 'Промт-документ: Малина + Ежевика ежевика / Улучшение почвы', '', TRUE, FALSE, TRUE, 'migration'),
        (v_group_id, v_subgroup_id, 'blackberry_variety', 'ежевика — Подбор сорта', 'Промт-документ: Малина + Ежевика ежевика / Подбор сорта', '', TRUE, FALSE, TRUE, 'migration')
    ON CONFLICT (group_id, subgroup_id, slug) DO NOTHING;

    -- Летняя (summer) — все типы работ
    INSERT INTO prompts (group_id, subgroup_id, slug, name, description, content, is_enabled, use_minimal_base, is_system, updated_by)
    VALUES
        (v_group_id, v_subgroup_id, 'summer_nutrition', 'летняя — Питание растений', 'Промт-документ: Малина + Ежевика летняя / Питание растений', '', TRUE, FALSE, TRUE, 'migration'),
        (v_group_id, v_subgroup_id, 'summer_protection', 'летняя — Защита растений', 'Промт-документ: Малина + Ежевика летняя / Защита растений', '', TRUE, FALSE, TRUE, 'migration'),
        (v_group_id, v_subgroup_id, 'summer_planting', 'летняя — Посадка и уход', 'Промт-документ: Малина + Ежевика летняя / Посадка и уход', '', TRUE, FALSE, TRUE, 'migration'),
        (v_group_id, v_subgroup_id, 'summer_soil', 'летняя — Улучшение почвы', 'Промт-документ: Малина + Ежевика летняя / Улучшение почвы', '', TRUE, FALSE, TRUE, 'migration'),
        (v_group_id, v_subgroup_id, 'summer_variety', 'летняя — Подбор сорта', 'Промт-документ: Малина + Ежевика летняя / Подбор сорта', '', TRUE, FALSE, TRUE, 'migration')
    ON CONFLICT (group_id, subgroup_id, slug) DO NOTHING;

    -- Общее (general) — все типы работ
    INSERT INTO prompts (group_id, subgroup_id, slug, name, description, content, is_enabled, use_minimal_base, is_system, updated_by)
    VALUES
        (v_group_id, v_subgroup_id, 'general_nutrition', 'общее — Питание растений', 'Промт-документ: Малина + Ежевика общее / Питание растений', '', TRUE, FALSE, TRUE, 'migration'),
        (v_group_id, v_subgroup_id, 'general_protection', 'общее — Защита растений', 'Промт-документ: Малина + Ежевика общее / Защита растений', '', TRUE, FALSE, TRUE, 'migration'),
        (v_group_id, v_subgroup_id, 'general_planting', 'общее — Посадка и уход', 'Промт-документ: Малина + Ежевика общее / Посадка и уход', '', TRUE, FALSE, TRUE, 'migration'),
        (v_group_id, v_subgroup_id, 'general_soil', 'общее — Улучшение почвы', 'Промт-документ: Малина + Ежевика общее / Улучшение почвы', '', TRUE, FALSE, TRUE, 'migration'),
        (v_group_id, v_subgroup_id, 'general_variety', 'общее — Подбор сорта', 'Промт-документ: Малина + Ежевика общее / Подбор сорта', '', TRUE, FALSE, TRUE, 'migration')
    ON CONFLICT (group_id, subgroup_id, slug) DO NOTHING;

    -- Ремонтантная (remontant) — все типы работ
    INSERT INTO prompts (group_id, subgroup_id, slug, name, description, content, is_enabled, use_minimal_base, is_system, updated_by)
    VALUES
        (v_group_id, v_subgroup_id, 'remontant_nutrition', 'ремонтантная — Питание растений', 'Промт-документ: Малина + Ежевика ремонтантная / Питание растений', '', TRUE, FALSE, TRUE, 'migration'),
        (v_group_id, v_subgroup_id, 'remontant_protection', 'ремонтантная — Защита растений', 'Промт-документ: Малина + Ежевика ремонтантная / Защита растений', '', TRUE, FALSE, TRUE, 'migration'),
        (v_group_id, v_subgroup_id, 'remontant_planting', 'ремонтантная — Посадка и уход', 'Промт-документ: Малина + Ежевика ремонтантная / Посадка и уход', '', TRUE, FALSE, TRUE, 'migration'),
        (v_group_id, v_subgroup_id, 'remontant_soil', 'ремонтантная — Улучшение почвы', 'Промт-документ: Малина + Ежевика ремонтантная / Улучшение почвы', '', TRUE, FALSE, TRUE, 'migration'),
        (v_group_id, v_subgroup_id, 'remontant_variety', 'ремонтантная — Подбор сорта', 'Промт-документ: Малина + Ежевика ремонтантная / Подбор сорта', '', TRUE, FALSE, TRUE, 'migration')
    ON CONFLICT (group_id, subgroup_id, slug) DO NOTHING;

END $$;

-- 3. Комментарий
COMMENT ON TABLE prompts IS 'Все промпты системы: базовые, категорийные, промт-документы (Клубника, Малина+Ежевика, Кустарники)';
