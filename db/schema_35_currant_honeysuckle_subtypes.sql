-- =============================================================================
-- Schema 35: Смородина + Жимолость — добавление подкатегорий Смородина и Жимолость
-- Каждая с одним промптом "Обрезка"
-- =============================================================================

DO $$
DECLARE
    v_group_id INT;
    v_subgroup_id INT;
BEGIN
    SELECT id INTO v_group_id FROM prompt_groups WHERE slug = 'prompt_docs';
    SELECT id INTO v_subgroup_id FROM prompt_subgroups WHERE slug = 'currant' AND group_id = v_group_id;

    -- Смородина (currant_type) — только Обрезка
    INSERT INTO prompts (group_id, subgroup_id, slug, name, description, content, is_enabled, use_minimal_base, is_system, updated_by)
    VALUES
        (v_group_id, v_subgroup_id, 'currant_pruning', 'смородина — Обрезка', 'Промт-документ: Смородина + Жимолость смородина / Обрезка', '', TRUE, FALSE, TRUE, 'migration')
    ON CONFLICT (group_id, subgroup_id, slug) DO NOTHING;

    -- Жимолость (honeysuckle) — только Обрезка
    INSERT INTO prompts (group_id, subgroup_id, slug, name, description, content, is_enabled, use_minimal_base, is_system, updated_by)
    VALUES
        (v_group_id, v_subgroup_id, 'honeysuckle_pruning', 'жимолость — Обрезка', 'Промт-документ: Смородина + Жимолость жимолость / Обрезка', '', TRUE, FALSE, TRUE, 'migration')
    ON CONFLICT (group_id, subgroup_id, slug) DO NOTHING;

END $$;
