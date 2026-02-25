-- schema_74: Одноразовая рассортировка клиентов CRM по правильным этапам
-- Выполнять ПОСЛЕ schema_73 (saw_pricing)
-- Безопасно запускать повторно (идемпотентно)

-- 1. new → tried: у кого есть хотя бы 1 запись в consultation_logs
UPDATE client_funnel_position cfp
SET stage_key = 'tried', updated_at = NOW()
WHERE cfp.funnel_id = 'crm'
  AND cfp.stage_key = 'new'
  AND cfp.manual_override = false
  AND EXISTS (SELECT 1 FROM consultation_logs cl WHERE cl.user_id = cfp.user_id);

-- 2. new → trial_ended: нет консультаций, но токены = 0
UPDATE client_funnel_position cfp
SET stage_key = 'trial_ended', updated_at = NOW()
WHERE cfp.funnel_id = 'crm'
  AND cfp.stage_key = 'new'
  AND cfp.manual_override = false
  AND EXISTS (SELECT 1 FROM users u WHERE u.id = cfp.user_id AND COALESCE(u.token_balance, 0) = 0);

-- 3. tried → trial_ended: получили консультацию, но токены кончились
UPDATE client_funnel_position cfp
SET stage_key = 'trial_ended', updated_at = NOW()
WHERE cfp.funnel_id = 'crm'
  AND cfp.stage_key = 'tried'
  AND cfp.manual_override = false
  AND EXISTS (SELECT 1 FROM users u WHERE u.id = cfp.user_id AND COALESCE(u.token_balance, 0) = 0);
