-- schema_55_server_metrics.sql
-- Таблица для хранения истории метрик сервера (для графиков на дашборде)

CREATE TABLE IF NOT EXISTS server_metrics_history (
    id SERIAL PRIMARY KEY,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cpu_percent REAL NOT NULL DEFAULT 0,
    memory_used_percent REAL NOT NULL DEFAULT 0,
    disk_used_percent REAL NOT NULL DEFAULT 0,
    network_rx_kbps REAL NOT NULL DEFAULT 0,
    network_tx_kbps REAL NOT NULL DEFAULT 0,
    load_1m REAL NOT NULL DEFAULT 0,
    memory_used_mb REAL NOT NULL DEFAULT 0,
    memory_total_mb REAL NOT NULL DEFAULT 0,
    disk_used_gb REAL NOT NULL DEFAULT 0,
    disk_total_gb REAL NOT NULL DEFAULT 0
);

-- Индекс по времени для быстрых запросов по диапазону
CREATE INDEX IF NOT EXISTS idx_server_metrics_recorded_at
    ON server_metrics_history (recorded_at DESC);
