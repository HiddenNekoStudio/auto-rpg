#!/bin/bash
set -e

# Создаём директорию для БД (volume монтируется с хоста, права уже заданы)
mkdir -p /data

# Проверяем что файл БД существует и доступен
if [ -f "/data/autorpg.db" ]; then
    DB_SIZE=$(stat -c%s "/data/autorpg.db" 2>/dev/null || echo "0")
    echo "Found existing database: /data/autorpg.db (${DB_SIZE} bytes)"
else
    echo "No existing database found, will create new one"
fi

echo "Starting Telegram AutoRPG..."
echo "DB Path: ${DB_PATH:-/data/autorpg.db}"
echo "DB Type: ${DBTYPE:-sqlite+aiosqlite}"

# Запускаем бота
exec python3 bot.py "$@"
