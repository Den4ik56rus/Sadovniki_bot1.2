-- db/schema_81_activate_funnel_b.sql
-- Активировать воронку Тип Б как активную для A/B теста
-- Все новые пользователи будут попадать в воронку Б

UPDATE bot_settings
SET value = 'B', updated_at = NOW()
WHERE key = 'active_funnel_variant';
