FROM python:3.12-slim

# =============================================
# Безопасность: не от root
# =============================================
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# =============================================
# Системные зависимости
# =============================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# =============================================
# Оптимизация слоёв
# =============================================
WORKDIR /app

# Сначала зависимости — меняются редко
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Исходники — меняются часто
COPY src/ ./src/

# Entrypoint script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Папка для БД (создаётся в entrypoint с правильными правами)
RUN mkdir -p /data

# =============================================
# ENV — корректный проброс
# =============================================
ENV TELEGRAM_TOKEN="$TELEGRAM_TOKEN"
ENV DB_TYPE="sqlite+aiosqlite"
ENV DB_PATH="/data/autorpg.db"
ENV DBTYPE="${DB_TYPE}"
ENV HEALTH_PORT=8081

# =============================================
# Healthcheck для Docker
# =============================================
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python3 -c "import asyncio; import aiohttp; asyncio.run(aiohttp.ClientSession().get('http://localhost:8080/health'))" || exit 1

# =============================================
# Запуск от не-root с entrypoint
# =============================================
USER appuser
WORKDIR /app/src
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "bot.py"]
