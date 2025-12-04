-- "01;8F0 topics 4;O E@0=5=8O 480;>3>2
CREATE TABLE IF NOT EXISTS topics (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    status TEXT DEFAULT 'open',
    culture TEXT,  -- C;LBC@0, 2K1@0==0O ?>;L7>20B5;5<
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_topics_user_status ON topics(user_id, status);
