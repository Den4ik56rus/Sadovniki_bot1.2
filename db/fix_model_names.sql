-- =============================================================================
-- Исправление некорректных названий моделей OpenAI в admin_settings
--
-- Было: gpt-5-mini, gpt-4.1-mini (несуществующие модели)
-- Стало: gpt-4o-mini (корректное название)
-- =============================================================================

-- Обновить модель для консультаций
UPDATE admin_settings
SET value = 'gpt-4o-mini'
WHERE key = 'model_consultation'
AND value IN ('gpt-5-mini', 'gpt-4.1-mini', 'gpt-55');

-- Обновить модель для классификации
UPDATE admin_settings
SET value = 'gpt-4o-mini'
WHERE key = 'model_classification'
AND value IN ('gpt-5-mini', 'gpt-4.1-mini', 'gpt-55');

-- Обновить модель для статей
UPDATE admin_settings
SET value = 'gpt-4o-mini'
WHERE key = 'model_article'
AND value IN ('gpt-5-mini', 'gpt-4.1-mini', 'gpt-55');

-- Обновить модель для вспомогательных задач
UPDATE admin_settings
SET value = 'gpt-4o-mini'
WHERE key = 'model_utility'
AND value IN ('gpt-5-mini', 'gpt-4.1-mini', 'gpt-55');

-- Проверить результаты
SELECT key, value, description
FROM admin_settings
WHERE key LIKE 'model_%'
ORDER BY key;
