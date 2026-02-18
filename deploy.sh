#!/bin/bash
# Деплой Sadovniki-bot на сервер
# Запускать на VPS после git clone/pull

set -euo pipefail

echo "=== Деплой Sadovniki-bot ==="

# Проверка .env
if [ ! -f .env ]; then
    echo "ОШИБКА: .env файл не найден!"
    echo "Скопируйте .env.production.example в .env и заполните значения:"
    echo "  cp .env.production.example .env"
    echo "  nano .env"
    exit 1
fi

# Создание директорий для данных
mkdir -p data/avatars data/guides data/documents data/prompt_documents backups

# Сборка контейнеров
echo "Собираю контейнеры..."
docker compose build

# Запуск базы данных
echo "Запускаю базу данных..."
docker compose up -d db

echo "Жду готовности БД..."
timeout 30 bash -c 'until docker compose exec -T db pg_isready -U bot_user 2>/dev/null; do sleep 1; done' \
    || { echo "БД не запустилась за 30 секунд"; exit 1; }

echo "База данных готова."

# Запуск всех сервисов
echo "Запускаю все сервисы..."
docker compose up -d

echo ""
echo "=== Деплой завершён ==="
echo ""
docker compose ps
echo ""
echo "Админ-панель: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'SERVER_IP')"
echo ""
echo "Полезные команды:"
echo "  docker compose logs -f bot    # логи бота"
echo "  docker compose logs -f db     # логи БД"
echo "  docker compose logs -f nginx  # логи nginx"
echo "  ./scripts/backup_db.sh        # бекап БД"
