#!/bin/bash
set -e

# Signal handling for clean shutdown
cleanup() {
    echo "Shutting down..."
    if [ -n "$REDIS_PID" ]; then
        kill "$REDIS_PID" 2>/dev/null || true
        wait "$REDIS_PID" 2>/dev/null || true
    fi
    exit 0
}
trap cleanup SIGTERM SIGINT

if [ "${USE_REDIS}" = "true" ]; then
    echo "Starting Redis server..."
    redis-server --bind 127.0.0.1 --port 6379 &
    REDIS_PID=$!
    for i in {1..10}; do
        if redis-cli -p 6379 ping 2>/dev/null; then
            echo "Redis started"
            break
        fi
        sleep 1
    done
fi

echo "Starting Telegram AutoRPG..."
echo "DB Type: ${DBTYPE:-postgresql+asyncpg}"
echo "Redis: ${USE_REDIS:-false}"

# Fix permissions for /data if running as root
if [ "$(id -u)" = "0" ]; then
    chown -R appuser:appuser /data 2>/dev/null || true
    # Drop privileges for bot, run override commands directly
    if [ "$1" = "python3" ] || [ "$1" = "alembic" ] || [ "$1" = "bash" ] || [ "$1" = "sh" ]; then
        exec gosu appuser "$@"
    elif [ "$1" = "pip" ]; then
        exec "$@"
    else
        exec gosu appuser python3 bot.py "$@"
    fi
fi

if [ "$1" = "python3" ] || [ "$1" = "alembic" ] || [ "$1" = "bash" ] || [ "$1" = "sh" ]; then
    exec "$@"
else
    exec python3 bot.py "$@"
fi
