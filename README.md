# 🎮 AutoRPG — Telegram Bot

Полный порт Discord AutoRPG на Telegram. Idle RPG — просто будь онлайн и смотри как твой герой приключается!

## 🚀 Быстрый старт

### 1. Установи зависимости
```bash
pip install -r requirements.txt
```

### 2. Настрой конфиг через .env
Скопируй пример конфигурации и отредактируй его:

```bash
cp .env.example .env
nano .env   # отредактировать переменные
```

Пример содержимого `.env`:

```dotenv
# Telegram Bot Token (получить у @BotFather)
TELEGRAM_TOKEN=123456:ABC-...

# Admin Telegram IDs (через запятую, узнать у @userinfobot)
ADMIN_IDS=123456789,987654321

# Путь к файлу базы данных SQLite (по умолчанию autorpg.db в текущей директории)
DB_PATH=autorpg.db

# Опционально: настройки для MySQL (если используешь MySQL вместо SQLite)
# DBUSER=username
# DBPASS=password
# DBHOST=localhost
# DBPORT=3306
# DBNAME=autorpg
```

### 3. Добавь бота в группу
- Добавь бота в группу Telegram
- Выдай боту права **отправлять сообщения**
- Получи ID группы через @getmyid_bot или @username_to_id_bot

### 4. Запусти бота
```bash
cd src
python bot.py
```

---

## 📋 Команды

| Команда | Описание |
|---------|----------|
| `/start` | Регистрация и приветствие |
| `/profile` | Твой профиль и снаряжение |
| `/pull [N]` | Использовать N токенов лута (макс. 10) |
| `/setjob Класс` | Сменить класс (с 10 уровня) |
| `/align` | Выбрать мировоззрение |
| `/quest` | Текущий квест |
| `/alert` | Вкл/выкл упоминания |
| `/info` | Информация о боте |
| `/help` | Список команд |

### 👑 Команды администратора
| Команда | Описание |
|---------|----------|
| `/admin_event` | Случайное событие |
| `/admin_quest` | Запустить квест |
| `/admin_endquest` | Завершить квест |
| `/admin_token <id> [N]` | Выдать токены |
| `/admin_drop <id>` | Дропнуть предмет |
| `/admin_stats` | Статистика сервера |

---

## ⚙️ Как работает

- Каждые **5 секунд** (настраивается в `INTERVAL`) игровой цикл обновляет всех онлайн игроков
- Игроки **автоматически** получают опыт пока открыт Telegram (статус "онлайн" устанавливается при /start)
- Случайные события, монстры и дуэли происходят автоматически
- Токены лута выдаются каждые **12 часов** онлайна

## 🗄️ База данных

По умолчанию используется **SQLite** (файл `autorpg.db`).

Для MySQL измени в `config.py`:
```python
DBTYPE = "mysql+aiomysql"
DBUSER = "user"
DBPASS = "password"
DBHOST = "localhost"
DBPORT = 3306
DBNAME = "autorpg"
```

И раскомментируй MySQL строки в `requirements.txt`.

## 📂 Структура

```
src/
├── bot.py          — главный файл, запуск
├── config.py       — все настройки
├── db.py           — модели базы данных
├── loot.py         — генератор предметов
├── loops.py        — игровые циклы
├── handlers/       — обработчики команд
│   ├── user.py
│   ├── alignment.py
│   ├── jobs.py
│   ├── listeners.py
│   └── admin.py
├── game/           — игровая логика
│   ├── events.py
│   ├── monsters.py
│   ├── challenge.py
│   └── quests.py
└── txtfiles/       — тексты событий и квестов
    ├── gevents.txt
    ├── bevents.txt
    └── quests.txt
```

---

## 🐳 Запуск через Docker

### Быстрый старт

```bash
# 1. Скопируй .env файл и вставь токен
cp .env.example .env
nano .env   # вписать TELEGRAM_TOKEN=...

# 2. Создать папку для базы данных
mkdir -p data

# 3. Собрать и запустить
docker compose up -d --build

# 4. Посмотреть логи
docker compose logs -f
```

### Файлы и папки

```
tg_autorpg/
├── Dockerfile
├── docker-compose.yml
├── .env.example        ← скопируй в .env и заполни
├── .env                ← токен (не коммитить в git!)
├── data/
│   └── autorpg.db      ← база данных (хранится на хосте)
└── src/
```

### Переменные окружения

| Переменная | Описание | По умолчанию |
|---|---|---|
| `TELEGRAM_TOKEN` | Токен бота от @BotFather | — (обязательно) |
| `DB_PATH` | Путь к файлу SQLite внутри контейнера | `/data/autorpg.db` |

### Полезные команды

```bash
# Остановить бота
docker compose down

# Перезапустить после изменений в коде
docker compose up -d --build

# Посмотреть живые логи
docker compose logs -f autorpg

# Зайти внутрь контейнера
docker compose exec autorpg bash

# Резервная копия базы данных
cp data/autorpg.db data/autorpg_backup.db
```

> 💡 База данных `autorpg.db` лежит в папке `./data/` на хосте и **не удаляется** при пересборке контейнера.
