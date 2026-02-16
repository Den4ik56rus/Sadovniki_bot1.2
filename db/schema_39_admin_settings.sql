-- =============================================================================
-- Schema 39: Admin Settings — Ключ-значение для глобальных настроек
-- =============================================================================

CREATE TABLE IF NOT EXISTS admin_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Начальная настройка: RAG включён по умолчанию
INSERT INTO admin_settings (key, value, description)
VALUES ('rag_enabled', 'true', 'Глобальный переключатель RAG-системы (true/false)')
ON CONFLICT (key) DO NOTHING;

COMMENT ON TABLE admin_settings IS
'Глобальные настройки административной панели (ключ-значение).';
