-- schema_73: Добавить этап 'saw_pricing' (Смотрел тарифы) в CRM воронку
-- Между trial_ended (sort_order=2) и paid (sort_order=3→4)

-- Сдвинуть paid на sort_order=4
UPDATE funnel_stages
SET sort_order = 4
WHERE funnel_id = 'crm' AND stage_key = 'paid';

-- Вставить saw_pricing на sort_order=3
INSERT INTO funnel_stages (funnel_id, stage_key, title, color, sort_order, is_system)
VALUES ('crm', 'saw_pricing', 'Смотрел тарифы', '#F97316', 3, true)
ON CONFLICT (funnel_id, stage_key) DO NOTHING;
