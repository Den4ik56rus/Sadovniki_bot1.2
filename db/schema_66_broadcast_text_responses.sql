-- schema_66: Текстовые ответы на кнопки рассылок
-- Пользователь нажимает quick_reply кнопку с ask_for_response=true,
-- бот предлагает написать ответ, ответ сохраняется в эту колонку.

ALTER TABLE broadcast_button_clicks
    ADD COLUMN IF NOT EXISTS text_response TEXT,
    ADD COLUMN IF NOT EXISTS response_at TIMESTAMPTZ;
