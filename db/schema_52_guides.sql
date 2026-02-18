-- Migration: Guide Orders (Готовое решение)
-- Version: 52
-- Description: Таблица заказов на готовые решения (PDF-гайды по культурам)
-- Date: 2026-02-18

CREATE TABLE IF NOT EXISTS guide_orders (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    payment_id INTEGER REFERENCES payments(id),

    -- Параметры гайда
    culture_key VARCHAR(100) NOT NULL,        -- "малина летняя", "клубника ремонтантная"
    culture_display VARCHAR(200) NOT NULL,    -- Отображаемое название

    -- Статус генерации
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    -- pending → payment_pending → generating → completed / failed

    -- Контент от LLM (сохраняем для повторной генерации PDF без повторных LLM-вызовов)
    content_json JSONB,
    total_llm_cost_usd FLOAT DEFAULT 0,
    total_llm_tokens INTEGER DEFAULT 0,

    -- [DEPRECATED] Ранее использовалось для Presenton, оставлено для обратной совместимости
    presenton_presentation_id VARCHAR(255),
    file_path TEXT,                            -- Локальный путь к PDF
    file_format VARCHAR(10) DEFAULT 'pdf',
    file_size_bytes INTEGER,

    -- Доставка в Telegram
    telegram_file_id VARCHAR(255),            -- Для повторной отправки без загрузки файла
    delivered_at TIMESTAMP,

    -- Ошибки
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,

    -- Временные метки
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_guide_orders_user ON guide_orders(user_id);
CREATE INDEX IF NOT EXISTS idx_guide_orders_status ON guide_orders(status);
CREATE INDEX IF NOT EXISTS idx_guide_orders_payment ON guide_orders(payment_id);
CREATE INDEX IF NOT EXISTS idx_guide_orders_culture ON guide_orders(culture_key);

-- Настройки LLM для генерации гайдов
INSERT INTO admin_settings (key, value, description)
VALUES
    ('model_guide', 'gpt-4o', 'Модель для генерации содержимого гайдов'),
    ('temp_guide', '0.3', 'Temperature для генерации гайдов'),
    ('reasoning_guide', '', 'Reasoning effort для генерации гайдов')
ON CONFLICT (key) DO NOTHING;

COMMENT ON TABLE guide_orders IS 'Заказы на готовые решения (PDF-гайды по культурам за 1190₽)';
