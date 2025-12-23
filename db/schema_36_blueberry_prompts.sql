-- =============================================================================
-- Schema 36: Голубика — структура промтов
-- Добавляем промпты: защита, питание, обрезка, посадка
-- =============================================================================

-- 1. Добавить новую подгруппу "Голубика"
INSERT INTO prompt_subgroups (group_id, slug, name, description, sort_order, is_system)
SELECT g.id, 'blueberry', 'Голубика', 'Промт-документы для голубики', 4, TRUE
FROM prompt_groups g WHERE g.slug = 'prompt_docs'
ON CONFLICT (group_id, slug) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description;

-- 2. Добавить промпты для Голубики
DO $$
DECLARE
    v_group_id INT;
    v_subgroup_id INT;
BEGIN
    SELECT id INTO v_group_id FROM prompt_groups WHERE slug = 'prompt_docs';
    SELECT id INTO v_subgroup_id FROM prompt_subgroups WHERE slug = 'blueberry' AND group_id = v_group_id;

    -- Общее (general) — защита, питание, обрезка, посадка
    INSERT INTO prompts (group_id, subgroup_id, slug, name, description, content, is_enabled, use_minimal_base, is_system, updated_by)
    VALUES
        (v_group_id, v_subgroup_id, 'general_protection', 'общее — Защита растений', 'Промт-документ: Голубика / Защита растений', '', TRUE, FALSE, TRUE, 'migration'),
        (v_group_id, v_subgroup_id, 'general_nutrition', 'общее — Питание растений', 'Промт-документ: Голубика / Питание растений', '', TRUE, FALSE, TRUE, 'migration'),
        (v_group_id, v_subgroup_id, 'general_pruning', 'общее — Обрезка', 'Промт-документ: Голубика / Обрезка', '', TRUE, FALSE, TRUE, 'migration'),
        (v_group_id, v_subgroup_id, 'general_planting', 'общее — Посадка и уход', 'Промт-документ: Голубика / Посадка и уход', '', TRUE, FALSE, TRUE, 'migration')
    ON CONFLICT (group_id, subgroup_id, slug) DO NOTHING;

END $$;
