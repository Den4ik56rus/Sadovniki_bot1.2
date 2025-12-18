-- schema_20_remove_crm_paid.sql
-- Удаление этапа "Оплатил" из CRM и очистка дубликатов

-- ═══════════════════════════════════════════════════════════════════════════════
-- 1. ОЧИСТКА ДУБЛИКАТОВ
-- Если пользователь есть в обоих воронках (CRM и Buyers), оставляем в CRM
-- ═══════════════════════════════════════════════════════════════════════════════

-- Удалить из Покупателей тех, кто есть в CRM (оставляем в CRM)
DELETE FROM client_funnel_position
WHERE funnel_id = 'buyers'
AND user_id IN (
    SELECT user_id FROM client_funnel_position WHERE funnel_id = 'crm'
);

-- Также очистить legacy buyer_status для тех кто в CRM
DELETE FROM buyer_status
WHERE user_id IN (
    SELECT user_id FROM client_funnel_position WHERE funnel_id = 'crm'
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- 2. ПЕРЕНОС КЛИЕНТОВ СО СТАТУСА 'paid' В 'trial_ended'
-- ═══════════════════════════════════════════════════════════════════════════════

UPDATE client_funnel_position
SET stage_key = 'trial_ended', updated_at = NOW()
WHERE funnel_id = 'crm' AND stage_key = 'paid';

-- ═══════════════════════════════════════════════════════════════════════════════
-- 3. УДАЛЕНИЕ ЭТАПА 'paid' ИЗ CRM
-- ═══════════════════════════════════════════════════════════════════════════════

-- Из новой таблицы
DELETE FROM funnel_stages
WHERE funnel_id = 'crm' AND stage_key = 'paid';

-- Из legacy таблицы (для обратной совместимости)
DELETE FROM crm_funnel_columns
WHERE id = 'paid';

-- Также перенести клиентов в legacy таблице
UPDATE client_funnel_status
SET status = 'trial_ended', updated_at = NOW()
WHERE status = 'paid';
