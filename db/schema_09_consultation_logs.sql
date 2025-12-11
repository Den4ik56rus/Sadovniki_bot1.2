-- schema_09_consultation_logs.sql
-- Таблица для логирования всех LLM консультаций для мониторинга и отладки

CREATE TABLE IF NOT EXISTS consultation_logs (
    id SERIAL PRIMARY KEY,

    -- Связи с другими таблицами
    topic_id INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL,

    -- Ввод пользователя и ответ бота
    user_message TEXT NOT NULL,
    bot_response TEXT NOT NULL,

    -- Полный системный промпт, отправленный в LLM (может быть очень длинным)
    system_prompt TEXT NOT NULL,

    -- RAG сниппеты как JSON массив
    -- Структура: [{"source_type": "qa"|"document", "priority_level": 1|2,
    --              "content": "...", "distance": 0.35, "category": "...", "subcategory": "..."}]
    rag_snippets JSONB DEFAULT '[]'::jsonb,

    -- Параметры LLM
    -- Структура: {"model": "gpt-4o", "temperature": 0.4, "max_tokens": null}
    llm_params JSONB DEFAULT '{}'::jsonb,

    -- Использование токенов
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER GENERATED ALWAYS AS (prompt_tokens + completion_tokens) STORED,

    -- Стоимость в USD (рассчитывается по ценам OpenAI)
    -- GPT-4o: $5/1M input, $15/1M output
    -- GPT-4o-mini: $0.15/1M input, $0.60/1M output
    cost_usd NUMERIC(10, 6) DEFAULT 0,

    -- Метрики производительности
    latency_ms INTEGER DEFAULT 0,  -- Общее время запроса в миллисекундах

    -- Контекст консультации
    consultation_category TEXT,    -- например: "питание растений"
    culture TEXT,                  -- например: "малина", "голубика"

    -- Временные метки
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для эффективных запросов
CREATE INDEX IF NOT EXISTS idx_consultation_logs_user_id ON consultation_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_consultation_logs_topic_id ON consultation_logs(topic_id);
CREATE INDEX IF NOT EXISTS idx_consultation_logs_created_at ON consultation_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_consultation_logs_category ON consultation_logs(consultation_category);

-- GIN индекс для JSONB запросов
CREATE INDEX IF NOT EXISTS idx_consultation_logs_rag_snippets ON consultation_logs USING GIN (rag_snippets);

-- Комментарии
COMMENT ON TABLE consultation_logs IS 'Полный лог всех LLM консультаций для мониторинга и отладки';
COMMENT ON COLUMN consultation_logs.system_prompt IS 'Полный системный промпт, отправленный в LLM, включая RAG контекст';
COMMENT ON COLUMN consultation_logs.rag_snippets IS 'JSON массив RAG сниппетов, использованных в консультации';
COMMENT ON COLUMN consultation_logs.cost_usd IS 'Расчётная стоимость в USD по ценам OpenAI';
