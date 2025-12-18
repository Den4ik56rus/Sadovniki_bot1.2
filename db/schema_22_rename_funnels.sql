-- Переименование воронок
-- Воронка CRM → Пробный период
-- Покупатели → Подписка

UPDATE funnels
SET title = 'Пробный период'
WHERE id = 'crm';

UPDATE funnels
SET title = 'Подписка'
WHERE id = 'buyers';
