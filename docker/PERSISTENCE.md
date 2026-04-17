# Telegram AutoRPG Docker Persistence Guide

## Проблема

После `docker compose up -d` данные теряются и игра начинается с нуля.

## Причины

1. **Директория `./data` не существует** — Docker создаёт её с root-владельцем
2. **Пользователь `appuser` не может писать** в директорию с root-правами
3. **Несоответствие путей** — `DB_PATH` и `DBNAME` путаются

## Решение

### Шаг 1: Создай директорию с правильными правами

```bash
# Создаём директорию
mkdir -p data

# Даём права на запись
chmod 777 data

# Проверяем
ls -la data/
```

### Шаг 2: Пересобери и запусти

```bash
# Останови и удали старый контейнер
docker compose down

# Пересобери образ
docker compose build --no-cache

# Запусти заново
docker compose up -d

# Проверь логи
docker compose logs -f
```

### Шаг 3: Проверь что БД сохранилась

```bash
# После перезапуска проверь размер файла
ls -la data/autorpg.db
```

## Варианты Persistence

### Вариант A: Хост-директория (текущий)

```yaml
volumes:
  - ./data:/data
```

**Плюсы:** Файл БД доступен на хосте
**Минусы:** Права могут слететь

### Вариант B: Docker Named Volume (рекомендуется)

```yaml
volumes:
  - autorpg_data:/data

volumes:
  autorpg_data:
```

**Плюсы:** Docker управляет правами автоматически
**Минусы:** Файл не доступен напрямую на хосте

Для просмотра данных:
```bash
docker compose exec autorpg ls -la /data/
docker compose exec autorpg cat /data/autorpg.db > backup.db
```

### Вариант C: PostgreSQL/MySQL (продакшн)

```yaml
services:
  autorpg:
    environment:
      - DBTYPE=postgresql+asyncpg
      - DBHOST=postgres
      - DBNAME=autorpg
      - DBUSER=postgres
      - DBPASS=${DBPASS}

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: autorpg
      POSTGRES_PASSWORD: ${DBPASS}
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

## Проверка Connection String

Внутри контейнера:
```
sqlite+aiosqlite:///data/autorpg.db
```

Проверь что `DB_PATH` установлен в `/data/autorpg.db`:
```bash
docker compose exec autorpg env | grep DB
```

## Troubleshooting

### Ошибка "Permission denied"

```bash
# Исправь права
sudo chown -R $(id -u):$(id -g) data
```

### База создаётся заново

Проверь что volume монтируется правильно:
```bash
docker compose exec autorpg ls -la /data/
```

### Данные всё равно теряются

Используй PostgreSQL — он надёжнее для persistence:
```bash
DBTYPE=postgresql+asyncpg docker compose up -d
```
