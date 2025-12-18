-- schema_21_admin_articles.sql
-- Таблица для хранения статей, сгенерированных администратором

-- Таблица статей
CREATE TABLE IF NOT EXISTS admin_articles (
    id SERIAL PRIMARY KEY,
    admin_telegram_id BIGINT NOT NULL,           -- ID администратора в Telegram
    topic VARCHAR(500) NOT NULL,                  -- Тема статьи
    article_text TEXT NOT NULL,                   -- Полный текст статьи

    -- Данные о генерации
    rag_snippets_count INTEGER DEFAULT 0,         -- Количество найденных RAG сниппетов
    rag_snippets JSONB,                           -- RAG сниппеты (для просмотра)
    system_prompt TEXT,                           -- Системный промпт

    -- Токены и стоимость
    embedding_tokens INTEGER DEFAULT 0,
    llm_prompt_tokens INTEGER DEFAULT 0,
    llm_completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    cost_usd NUMERIC(12, 8) DEFAULT 0,

    -- Параметры LLM
    llm_model VARCHAR(50),

    -- Метаданные
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_admin_articles_admin ON admin_articles(admin_telegram_id);
CREATE INDEX IF NOT EXISTS idx_admin_articles_created ON admin_articles(created_at DESC);

-- Триггер для логирования в client_activity_log (если нужно показывать в ленте клиента)
-- Пока не добавляем, так как статьи не привязаны к конкретному клиенту

COMMENT ON TABLE admin_articles IS 'Статьи, сгенерированные администратором через режим написания статей';
