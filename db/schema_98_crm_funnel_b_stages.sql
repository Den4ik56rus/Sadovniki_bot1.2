-- schema_98: Новые этапы CRM-воронки для Funnel B
-- Этапы: quiz_done (прошёл опрос), bought_plan (купил презентацию), bought_product (купил продукт)

-- Добавить 3 новых системных этапа в CRM-воронку
INSERT INTO funnel_stages (funnel_id, stage_key, title, color, sort_order, is_system)
VALUES
    ('crm', 'quiz_done',       'Прошёл опрос',      '#A855F7', 4, true),
    ('crm', 'bought_plan',     'Купил презентацию',  '#F97316', 5, true),
    ('crm', 'bought_product',  'Купил',              '#10B981', 6, true)
ON CONFLICT (funnel_id, stage_key) DO NOTHING;

-- Если кто-то остался на 'paid' в CRM — переносим на 'bought_product'
UPDATE client_funnel_position
SET stage_key = 'bought_product', updated_at = NOW()
WHERE funnel_id = 'crm' AND stage_key = 'paid';
