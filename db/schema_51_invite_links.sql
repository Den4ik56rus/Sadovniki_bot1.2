-- schema_51_invite_links.sql
-- Инвайт-ссылки для отслеживания рекламных кампаний

CREATE TABLE IF NOT EXISTS invite_links (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS invite_link_users (
    id SERIAL PRIMARY KEY,
    invite_link_id INTEGER NOT NULL REFERENCES invite_links(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id)
);

CREATE INDEX IF NOT EXISTS idx_invite_links_code ON invite_links(code);
CREATE INDEX IF NOT EXISTS idx_invite_link_users_link ON invite_link_users(invite_link_id);
