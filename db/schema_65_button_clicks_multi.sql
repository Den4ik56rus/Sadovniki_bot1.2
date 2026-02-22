-- schema_65: Разрешить несколько кликов по разным кнопкам в одной рассылке
-- Было: UNIQUE (broadcast_id, run_id, user_id) — один клик на рассылку
-- Стало: UNIQUE (broadcast_id, run_id, user_id, option_key) — один клик на каждую кнопку

ALTER TABLE broadcast_button_clicks
  DROP CONSTRAINT IF EXISTS broadcast_button_clicks_broadcast_run_user_key;

ALTER TABLE broadcast_button_clicks
  ADD CONSTRAINT broadcast_button_clicks_broadcast_run_user_option_key
  UNIQUE (broadcast_id, run_id, user_id, option_key);
