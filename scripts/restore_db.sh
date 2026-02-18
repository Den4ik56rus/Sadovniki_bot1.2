#!/bin/bash
# Восстановление базы данных из дампа
# Использование: ./scripts/restore_db.sh backups/garden_bot_XXXX.dump.gz

set -euo pipefail

BACKUP_FILE="${1:?Использование: $0 <файл_бекапа.dump.gz>}"
DB_USER="${DB_USER:-bot_user}"
DB_NAME="${DB_NAME:-garden_bot}"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Ошибка: файл не найден: $BACKUP_FILE"
    exit 1
fi

echo "ВНИМАНИЕ: Это перезапишет базу данных '$DB_NAME'!"
echo "Файл: $BACKUP_FILE"
read -p "Продолжить? (y/N): " confirm
[ "$confirm" = "y" ] || exit 0

echo "Останавливаю бота..."
docker compose stop bot 2>/dev/null || true

echo "Пересоздаю базу данных..."
docker compose exec -T db psql -U "$DB_USER" -d postgres -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();" 2>/dev/null || true
docker compose exec -T db psql -U "$DB_USER" -d postgres -c \
    "DROP DATABASE IF EXISTS $DB_NAME;"
docker compose exec -T db psql -U "$DB_USER" -d postgres -c \
    "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

echo "Включаю pgvector..."
docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME" -c \
    "CREATE EXTENSION IF NOT EXISTS vector;"

echo "Восстанавливаю из дампа..."
gunzip -c "$BACKUP_FILE" | docker compose exec -T db pg_restore \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --no-owner \
    --no-privileges \
    2>&1 | grep -v "WARNING\|NOTICE" || true

echo "База данных восстановлена."
echo "Запускаю бота..."
docker compose up -d bot
