-- schema_24_category_icons.sql
-- Добавление иконок к категориям расходов

-- Добавляем колонку icon
ALTER TABLE expense_categories ADD COLUMN IF NOT EXISTS icon VARCHAR(50) DEFAULT 'default';

-- Обновляем системные категории с иконками
UPDATE expense_categories SET icon = 'megaphone' WHERE name = 'Реклама';
UPDATE expense_categories SET icon = 'brain' WHERE name = 'Claude code';
UPDATE expense_categories SET icon = 'cpu' WHERE name = 'LLM';
UPDATE expense_categories SET icon = 'server' WHERE name = 'Server';
