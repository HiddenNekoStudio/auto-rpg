"""
config.py - Telegram AutoRPG Configuration
"""
import os

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
    raw = os.getenv("ADMIN_IDS", "")
    if not raw.strip():
        return []
    result = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            result.append(int(part))
        else:
            print(f"Warning: Ignoring non-numeric ADMIN_ID: {part}")
    return result

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
# Интервал автоматической встречи с монстрами (секунды), 3600 = 1 час
MONSTER_INTERVAL = _safe_int(os.getenv("MONSTER_INTERVAL"), 1800)

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
