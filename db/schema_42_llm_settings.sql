-- =============================================================================
-- Schema 42: LLM Model & Temperature Settings
-- Быстрая смена модели и temperature через админ-панель (без рестарта)
-- =============================================================================

-- Модели для каждой группы задач
INSERT INTO admin_settings (key, value, description)
VALUES ('model_consultation', 'gpt-5-mini', 'Модель для консультаций')
ON CONFLICT (key) DO NOTHING;

INSERT INTO admin_settings (key, value, description)
VALUES ('model_classification', 'gpt-4.1-mini', 'Модель для классификации культуры/категории')
ON CONFLICT (key) DO NOTHING;

INSERT INTO admin_settings (key, value, description)
VALUES ('model_article', 'gpt-4.1-mini', 'Модель для генерации статей')
ON CONFLICT (key) DO NOTHING;

INSERT INTO admin_settings (key, value, description)
VALUES ('model_utility', 'gpt-4.1-mini', 'Модель для вспомогательных задач (compose_question и т.д.)')
ON CONFLICT (key) DO NOTHING;

-- Temperature для каждой группы задач (пустая строка = не передавать / отключено)
INSERT INTO admin_settings (key, value, description)
VALUES ('temp_consultation', '', 'Temperature для консультаций (пусто = не передавать, для reasoning моделей)')
ON CONFLICT (key) DO NOTHING;

INSERT INTO admin_settings (key, value, description)
VALUES ('temp_classification', '', 'Temperature для классификации (пусто = не передавать)')
ON CONFLICT (key) DO NOTHING;

INSERT INTO admin_settings (key, value, description)
VALUES ('temp_article', '', 'Temperature для статей (пусто = не передавать)')
ON CONFLICT (key) DO NOTHING;

INSERT INTO admin_settings (key, value, description)
VALUES ('temp_utility', '', 'Temperature для вспомогательных задач (пусто = не передавать)')
ON CONFLICT (key) DO NOTHING;
