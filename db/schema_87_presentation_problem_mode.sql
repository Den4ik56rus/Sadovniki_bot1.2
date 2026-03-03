-- schema_87: Режим «По проблеме» для презентаций
-- Добавляет поля для генерации презентаций из проблем Funnel B

-- Режим генерации: 'article' (вручную текст) | 'problem' (авто из проблемы)
ALTER TABLE presentations ADD COLUMN IF NOT EXISTS generation_mode TEXT NOT NULL DEFAULT 'article';

-- Ключи выбранной проблемы/культуры/сорта из Funnel B
ALTER TABLE presentations ADD COLUMN IF NOT EXISTS problem_key TEXT;
ALTER TABLE presentations ADD COLUMN IF NOT EXISTS culture_key TEXT;
ALTER TABLE presentations ADD COLUMN IF NOT EXISTS variety_key TEXT;

-- Отдельный трекинг стоимости генерации статьи (до разбивки на слайды)
ALTER TABLE presentations ADD COLUMN IF NOT EXISTS article_cost_usd NUMERIC(10,6) DEFAULT 0;
ALTER TABLE presentations ADD COLUMN IF NOT EXISTS article_prompt_tokens INTEGER DEFAULT 0;
ALTER TABLE presentations ADD COLUMN IF NOT EXISTS article_completion_tokens INTEGER DEFAULT 0;

-- source_text может быть пустым в problem mode (заполняется после генерации статьи)
ALTER TABLE presentations ALTER COLUMN source_text DROP NOT NULL;
ALTER TABLE presentations ALTER COLUMN source_text SET DEFAULT '';
