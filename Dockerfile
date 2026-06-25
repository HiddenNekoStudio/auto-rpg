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
    redis-server \
    gosu \
    && apt-get purge -y gcc && apt-get autoremove -y \
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
COPY maps/ ./maps/

# Миграции Alembic
COPY alembic.ini .
COPY alembic/ ./alembic/

# Entrypoint script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Healthcheck script
COPY docker/healthcheck.py /healthcheck.py
RUN chmod +x /healthcheck.py

# Папка для БД (создаётся в entrypoint с правильными правами)
RUN mkdir -p /data

# =============================================
# Healthcheck для Docker
# =============================================
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD ["python3", "/healthcheck.py"]

# =============================================
# Entrypoint от root (чинит права БД) + su-exec для drop привилегий
# =============================================
WORKDIR /app/src
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "bot.py"]

# Папка /data создана; entrypoint чинит права БД через chown
