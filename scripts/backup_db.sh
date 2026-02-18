#!/bin/bash
# Бекап базы данных
# Использование: ./scripts/backup_db.sh

set -euo pipefail

BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y-%m-%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/garden_bot_${TIMESTAMP}.dump.gz"

mkdir -p "$BACKUP_DIR"

echo "Создаю бекап базы данных..."
docker compose exec -T db pg_dump \
    -U "${DB_USER:-bot_user}" \
    -d "${DB_NAME:-garden_bot}" \
    --no-owner \
    --no-privileges \
    --format=custom \
    | gzip > "$BACKUP_FILE"

echo "Бекап сохранён: $BACKUP_FILE"
echo "Размер: $(du -h "$BACKUP_FILE" | cut -f1)"

# Оставляем только последние 7 бекапов
ls -t "$BACKUP_DIR"/garden_bot_*.dump.gz 2>/dev/null | tail -n +8 | xargs -r rm
echo "Старые бекапы очищены (хранятся последние 7)"
