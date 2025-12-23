-- =============================================================================
-- Schema 34: Смородина + Жимолость — структура промтов
-- Новая подгруппа с типами работ + Обрезка
-- =============================================================================

-- 1. Добавить новую подгруппу "Смородина + Жимолость"
INSERT INTO prompt_subgroups (group_id, slug, name, description, sort_order, is_system)
SELECT g.id, 'currant', 'Смородина + Жимолость', 'Промт-документы для смородины и жимолости', 3, TRUE
FROM prompt_groups g WHERE g.slug = 'prompt_docs'
ON CONFLICT (group_id, slug) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description;

-- 2. Добавить промпты для Смородина + Жимолость
-- Структура: Общее + все типы работ (включая Обрезку)

DO $$
DECLARE
    v_group_id INT;
    v_subgroup_id INT;
BEGIN
    SELECT id INTO v_group_id FROM prompt_groups WHERE slug = 'prompt_docs';
    SELECT id INTO v_subgroup_id FROM prompt_subgroups WHERE slug = 'currant' AND group_id = v_group_id;

    -- Общее (general) — все типы работ включая обрезку
    INSERT INTO prompts (group_id, subgroup_id, slug, name, description, content, is_enabled, use_minimal_base, is_system, updated_by)
    VALUES
        (v_group_id, v_subgroup_id, 'general_nutrition', 'общее — Питание растений', 'Промт-документ: Смородина + Жимолость общее / Питание растений', '', TRUE, FALSE, TRUE, 'migration'),
        (v_group_id, v_subgroup_id, 'general_protection', 'общее — Защита растений', 'Промт-документ: Смородина + Жимолость общее / Защита растений', '', TRUE, FALSE, TRUE, 'migration'),
        (v_group_id, v_subgroup_id, 'general_planting', 'общее — Посадка и уход', 'Промт-документ: Смородина + Жимолость общее / Посадка и уход', '', TRUE, FALSE, TRUE, 'migration'),
        (v_group_id, v_subgroup_id, 'general_soil', 'общее — Улучшение почвы', 'Промт-документ: Смородина + Жимолость общее / Улучшение почвы', '', TRUE, FALSE, TRUE, 'migration'),
        (v_group_id, v_subgroup_id, 'general_variety', 'общее — Подбор сорта', 'Промт-документ: Смородина + Жимолость общее / Подбор сорта', '', TRUE, FALSE, TRUE, 'migration'),
        (v_group_id, v_subgroup_id, 'general_pruning', 'общее — Обрезка', 'Промт-документ: Смородина + Жимолость общее / Обрезка', '', TRUE, FALSE, TRUE, 'migration')
    ON CONFLICT (group_id, subgroup_id, slug) DO NOTHING;

END $$;

-- 3. Комментарий
COMMENT ON TABLE prompts IS 'Все промпты системы: базовые, категорийные, промт-документы (Клубника, Малина+Ежевика, Смородина+Жимолость, Кустарники)';
