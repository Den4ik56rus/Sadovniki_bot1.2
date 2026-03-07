-- schema_96_flagship_purchases.sql
-- Таблицы для флагманского продукта: покупки + кеш file_id

-- Что купил пользователь (бессрочный доступ)
CREATE TABLE IF NOT EXISTS user_purchased_products (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_type VARCHAR(50) NOT NULL,       -- 'seasonal_program'
    product_key VARCHAR(100) NOT NULL,       -- 'strawberry_summer'
    payment_id INTEGER REFERENCES payments(id),
    purchased_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_user_product UNIQUE(user_id, product_type, product_key)
);

CREATE INDEX IF NOT EXISTS idx_upp_user ON user_purchased_products(user_id);

-- Кеш Telegram file_id для PDF и видео (чтобы не заливать 30 MB каждый раз)
CREATE TABLE IF NOT EXISTS flagship_file_cache (
    id SERIAL PRIMARY KEY,
    product_key VARCHAR(100) NOT NULL,
    content_key VARCHAR(200) NOT NULL,      -- 'nutrition:article', 'nutrition:video'
    telegram_file_id TEXT NOT NULL,
    file_type VARCHAR(20) NOT NULL,         -- 'document' | 'video'
    cached_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_file_cache UNIQUE(product_key, content_key)
);
