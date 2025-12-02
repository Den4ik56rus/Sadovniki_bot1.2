-- Словарь терминов и фраз для LLM
CREATE TABLE IF NOT EXISTS terminology (
    id SERIAL PRIMARY KEY,
    term VARCHAR(255) NOT NULL,
    preferred_phrase TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Индекс для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_terminology_term ON terminology(term);

-- Примеры начальных данных
INSERT INTO terminology (term, preferred_phrase, description) VALUES
('навоз', 'удобрения естественного происхождения', 'Вместо слова "навоз" использовать формулировку "удобрения естественного происхождения"'),
('помёт', 'органические азотные удобрения', 'Вместо "помёт" использовать "органические азотные удобрения"')
ON CONFLICT DO NOTHING;
