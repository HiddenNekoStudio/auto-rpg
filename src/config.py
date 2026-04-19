"""
config.py - Telegram AutoRPG Configuration
"""
import os

# =============================================
# Load .env FIRST - before any config is read
# =============================================
def load_env_file():
    """Load environment variables from .env file."""
    # Try common Docker/local paths
    paths_to_try = [
        "/app/.env",
        "/data/.env", 
        os.path.join(os.path.dirname(__file__), "..", ".env"),
        os.path.join(os.path.dirname(__file__), ".env"),
    ]
    
    for path in paths_to_try:
        print(f"Checking .env at: {path} (exists: {os.path.exists(path)})")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                content = f.read()
                print(f".env content preview: {content[:200]}...")
                f.seek(0)
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        os.environ[key.strip()] = val.strip()
                        print(f"Set env: {key.strip()} = {val.strip()[:20]}...")
            return True
    return False

load_env_file()
print(f"TELEGRAM_TOKEN: {os.environ.get('TELEGRAM_TOKEN', 'NOT SET')[:30] if os.environ.get('TELEGRAM_TOKEN') else 'NOT SET'}")
print(f"ADMIN_IDS: {os.environ.get('ADMIN_IDS', 'NOT SET')}")

# =============================================
#   ОБЯЗАТЕЛЬНЫЕ НАСТРОЙКИ
# =============================================

# Название игры
GAME_NAME = "AutoRPG"
# Версия
VERSION = "1.1.0"
# Описание игры (показывается по /info)
GAME_INFO = f"🎮 AutoRPG (v{VERSION}) — Idle RPG для Telegram"
# Токен Telegram бота (получить у @BotFather)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
# SOCKS5 прокси для Telegram (формат: socks5://user:pass@host:port)
TELEGRAM_PROXY = os.getenv("TELEGRAM_PROXY")
# Telegram ID администраторов (можно узнать у @userinfobot)
# Список ID администраторов через запятую: ADMIN_IDS=123456789,987654321
def _parse_admin_ids():
    admin_ids = []
    raw = os.environ.get("ADMIN_IDS", "")
    if raw:
        for part in raw.split(","):
            part = part.strip()
            if part.isdigit():
                admin_ids.append(int(part))
    return admin_ids

SERVER_ADMINS = _parse_admin_ids()

# =============================================
#   НАСТРОЙКИ БАЗЫ ДАННЫХ
# =============================================
# Тип: sqlite+aiosqlite, mysql+aiomysql, postgresql+asyncpg
DBTYPE = os.getenv("DBTYPE", "sqlite+aiosqlite")
DBNAME = os.getenv("DB_PATH", "autorpg.db")    # для sqlite - путь к файлу (переопределяется через DB_PATH)
DBUSER = os.getenv("DBUSER", "")          # для mysql/postgres
DBPASS = os.getenv("DBPASS", "")
DBHOST = os.getenv("DBHOST", "localhost")

# Безопасное преобразование DBPORT в int
def _safe_int(value, default=3306):
    try:
        return int(value)
    except (ValueError, TypeError):
        print(f"Warning: Invalid integer value: {value}, using default: {default}")
        return default

DBPORT = _safe_int(os.getenv("DBPORT"), 3306)

# =============================================
#   ОПЦИОНАЛЬНЫЕ НАСТРОЙКИ
# =============================================
DEBUG = False
# Через сколько секунд без активности игрок считается оффлайн
# Можно задать через env: OFFLINE_TIMEOUT=300 (в секундах)
# Или в admin_panel командой /admin_timeout <секунды>
OFFLINE_TIMEOUT = _safe_int(os.getenv("OFFLINE_TIMEOUT"), 3600)

# Интервал игрового тика (секунды). Менять осторожно — влияет на скорость прокачки
INTERVAL = _safe_int(os.getenv("GAME_INTERVAL"), 5)
# Базовое время до следующего уровня (секунды), 600 = 10 минут
TIME_BASE = 600
# Экспонента роста времени до следующего уровня
TIME_EXP = 1.16
# Награда за квест: уменьшение времени (0.90 = -10%)
QUEST_REWARD = 0.90
# Штраф за провал квеста: увеличение времени (1.05 = +5%)
QUEST_PENALTY = 1.05
# Размер карты
MAP_SIZE = [1000, 1000]

# ── Кэш для производительности ─────────────────
from functools import lru_cache

@lru_cache(maxsize=1024)
def xp_for_level(level: int) -> int:
    """Кэшированный расчёт XP для уровня. O(1) вместо O(level)."""
    return int(TIME_BASE * (TIME_EXP ** (level + 1)))
# Включить PVP
ENABLE_COMBAT = True
# Интервал автоматической встречи с монстрами (секунды), 300 = 5 минут
MONSTER_INTERVAL = _safe_int(os.getenv("MONSTER_INTERVAL"), 60)  # 1 минута (было 5 минут)

# Расы и их бонусы
RACES = {
    "human": {"ru": "👤 Человек", "en": "👤 Human",   "bonus": "🍀 20% шанс избежать штрафа монстра / 20% chance to avoid monster penalty"},
    "dwarf": {"ru": "⛏️ Гном",    "en": "⛏️ Dwarf",   "bonus": "🛡️ +15% к защите / +15% defense"},
    "elf":   {"ru": "🌿 Эльф",    "en": "🌿 Elf",     "bonus": "🏹 +10% к скорости прокачки / +10% XP speed"},
}

# Минимальный уровень для участия в дуэлях
MIN_CHALLENGE_LEVEL = 10
# Слоты экипировки
WEAPON_SLOTS = ["weapon", "shield", "helmet", "chest", "gloves", "boots", "ring", "amulet"]
# Время для получения лутового токена (секунды), 43200 = 12 часов
TOKEN_TIME = 43200

# Праздники: 0 = обычный, 1 = Рождество, 2 = Хэллоуин
HOLIDAY = 0
HOLIDAY_LIST = ["christmas", "halloween"]

# Эмодзи редкостей
RARITY_EMOJI = {
    "Common":    "⚪",
    "Uncommon":  "🟢",
    "Rare":      "🔵",
    "Epic":      "🟣",
    "Legendary": "🟠",
    "Ascended":  "🔴",
    "Unique":    "🟡",
}

# Подсказки
TIPS = [
    "После 10 уровня можно сменить класс командой /setjob!",
    "Включи упоминания командой /alert, чтобы получать уведомления о событиях!",
    "Добрые игроки получают +10% к силе снаряжения!",
    "Добрые игроки могут использовать Смайт - удваивает шанс победы над монстром!",
    "Злые игроки могут Подло ударить - удваивает шанс победы в дуэлях!",
    "Редкость предмета влияет на его силу в поединках!",
]
