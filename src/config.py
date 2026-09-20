"""
config.py - Telegram AutoRPG Configuration
"""
import logging
import os

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def load_env_file():
    """Load environment variables from .env file."""
    paths_to_try = [
        "/app/.env",
        "/data/.env",
        os.path.join(os.path.dirname(__file__), "..", ".env"),
        os.path.join(os.path.dirname(__file__), ".env"),
    ]
    
    for path in paths_to_try:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        val = val.strip()
                        # Снять кавычки, если значение закавычено.
                        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                            val = val[1:-1]
                        else:
                            # Обрезать inline-комментарий: `KEY=3600  # comment`.
                            # Только при пробеле перед '#', чтобы не ломать
                            # значения с '#' внутри (пароли, токены).
                            for sep in (" #", "\t#"):
                                if sep in val:
                                    val = val.split(sep, 1)[0].rstrip()
                        os.environ.setdefault(key.strip(), val)
            logger.info(f".env loaded from: {path}")
            return True
    
    logger.warning("No .env file found, using environment variables only")
    return False

load_env_file()

# =============================================
#   ОБЯЗАТЕЛЬНЫЕ НАСТРОЙКИ
# =============================================

# Название игры
GAME_NAME = "AutoRPG"
# Версия
VERSION = "2.1.0-beta1"
# Описание игры (показывается по /info)
GAME_INFO = f"🎮 AutoRPG (v{VERSION}) — Idle RPG Telegram"
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

# ── Idle Mode ─────────────────────────────────────────────
# Скорость накопления XP в idle режиме (% от normal rate, первые 24ч)
IDLE_XP_RATE = 0.10          # 10%
# Скорость после 24ч без cap
IDLE_XP_RATE_EXTENDED = 0.05  # 5%

# =============================================
#   НАСТРОЙКИ БАЗЫ ДАННЫХ
# =============================================
# Тип: sqlite+aiosqlite, mysql+aiomysql, postgresql+asyncpg
DBTYPE = os.getenv("DBTYPE", "postgresql+asyncpg")
DBNAME = os.getenv("DBNAME", "autorpg")
# Путь к файлу SQLite (только для DBTYPE=sqlite+aiosqlite)
DB_PATH = os.getenv("DB_PATH", "data/autorpg.db")
DBUSER = os.getenv("DBUSER", "autorpg")
DBPASS = os.getenv("DBPASS", "autorpg_pass")
DBHOST = os.getenv("DBHOST", "localhost")

def _safe_int(value, default=5432):
    try:
        return int(value)
    except (ValueError, TypeError):
        logger.warning(f"Invalid integer value: {value}, using default: {default}")
        return default

DBPORT = _safe_int(os.getenv("DBPORT"), 5432)

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
MONSTER_INTERVAL = 900  # 15 минут

# Конфигурация встреч с монстрами
MONSTER_LEVEL_MIN_OFFSET = -4
MONSTER_LEVEL_MAX_OFFSET = 6

# Максимальный ранг монстра по уровню игрока
LEVEL_RANK_CAP = [
    (10,  "Common"),
    (25,  "Uncommon"),
    (40,  "Rare"),
    (60,  "Epic"),
    (999, "Legendary"),
]

# Минимальный ранг монстра по streak побед
STREAK_RANK_FLOOR = [
    (3, "Uncommon"),   # streak 3+ → убираем Common
    (5, "Rare"),       # streak 5+ → только Rare+
]

# Биомы → типы монстров
BIOME_MONSTERS = {
    "forest":   ["animal"],
    "swamp":    ["ooze", "animal"],
    "mountain": ["giant", "elemental"],
    "dungeon":  ["undead", "demon"],
    "ruins":    ["undead", "construct"],
    "desert":   ["animal", "giant"],
    "mine":     ["construct", "humanoid"],
    "castle":   ["humanoid", "mythical"],
    "lair":     ["dragon", "mythical", "demon"],
    "cemetery": ["undead"],
    "temple":   ["elemental", "mythical"],
    "city":     ["humanoid"],
    "village":  ["animal", "humanoid"],
    "meadow":    ["animal"],
    "lake":      ["animal", "elemental"],
    "capital":   ["humanoid", "mythical"],
    "port":      ["humanoid"],
    "farm":      ["animal", "humanoid"],
    "tavern":    ["humanoid"],
    "hut":       ["humanoid", "animal"],
    "gate":      ["humanoid", "construct"],
    "bridge":    ["humanoid", "construct"],
    "river":     ["animal", "elemental"],
    "outpost":   ["humanoid"],
    "shrine":    ["elemental", "mythical"],
    "default":   ["animal", "humanoid"],
}

# Шансы вариантов монстра (normal/elite/boss)
VARIANT_CHANCES = {
    "boss":  0.05,     # 5%
    "elite": 0.15,     # 15%
}
# Множители для вариантов
VARIANT_MULT = {
    "boss":  {"hp": 3.0, "xp": 5.0, "gold": 5.0, "dps": 1.5, "loot_guaranteed": True,  "prefix_ru": "👑", "prefix_en": "👑"},
    "elite": {"hp": 2.0, "xp": 3.0, "gold": 3.0, "dps": 1.3, "loot_guaranteed": False, "prefix_ru": "⭐", "prefix_en": "⭐"},
}

# Шанс выпадения лута с монстра (0.12 = 12%)
LOOT_CHANCE = 0.08
# Шанс появления группового монстра (0.03 = 3%)
PARTY_CHANCE = 0.03
# Максимум последовательных боёв до штрафа стамины
STAMINA_MAX = 2
# Интервал снятия 1 очка стамины (сек)
STREAK_DECAY_INTERVAL = 300

# Комбо-стрик: +% DPS за каждую победу серии (до порога STAMINA_MAX, дальше — усталость)
COMBO_STREAK_BONUS_PER_WIN = 0.01   # +1% DPS за победу в серии
COMBO_STREAK_MAX_MULT = 0.25        # потолок бонуса (25%)

# Вампиризм монстров: % урона, возвращаемый монстру как HP (по id монстра)
MONSTER_LIFESTEAL = {
    "vampire": 0.15,
    "wraith": 0.10,
    "demon": 0.08,
}
# Шанс «кровожадного» монстра в охоте по режимам
HUNTING_LIFESTEAL_CHANCE = {"weak": 0.05, "strong": 0.10, "epic": 0.15}

# ── Элементы (урон ×1.5 по слабости) ────────────────
# Элемент монстра определяется по его типу из data/monsters.json
MONSTER_TYPE_ELEMENT = {
    "animal": "nature", "humanoid": "nature", "ooze": "nature",
    "undead": "dark", "demon": "fire", "dragon": "fire",
    "elemental": "lightning", "mythical": "lightning",
    "giant": "earth", "construct": "earth",
}
# Слабости: элемент оружия → типы монстров, по которым бьёт ×1.5
ELEMENT_WEAKNESS = {
    "fire": ["animal", "undead", "ooze"],
    "ice": ["dragon", "demon", "elemental"],
    "lightning": ["construct", "giant", "mythical"],
    "nature": ["giant", "construct", "earth"],
    "dark": ["humanoid", "mythical", "nature"],
    "holy": ["undead", "demon", "dark"],
}
ELEMENT_WEAK_MULT = 1.5      # множитель урона по слабости
ELEMENT_AFFIX_CHANCE = 0.30  # шанс оружия получить элемент при генерации лута
SET_AFFIX_CHANCE = 0.12      # шанс предмета получить сетовый аффикс при генерации

# =============================================
#   ДРАГОЦЕННЫЕ КАМНИ (гнёзда в экипировке)
# =============================================
GEM_SOCKET_CHANCE = 0.25        # шанс предмета иметь хотя бы одно гнездо
GEM_MAX_SOCKETS = 2             # макс. гнёзд на предмете
GEM_DROP_CHANCE = 0.08          # шанс дропа камня с редкого лута/босса
ELEMENT_NAMES_RU = {"fire": "Огненный", "ice": "Ледяной", "lightning": "Грозовой",
                    "nature": "Природный", "dark": "Тёмный", "holy": "Святой"}
ELEMENT_NAMES_EN = {"fire": "Fiery", "ice": "Icy", "lightning": "Storm",
                    "nature": "Nature", "dark": "Dark", "holy": "Holy"}

# ── DoT-статусы (burn/freeze/stun) ──────────────────
DOT_BURN_CHANCE = 0.25      # шанс огненного удара поджечь монстра
DOT_BURN_TICKS = 2          # тиков горения
DOT_BURN_DMG_PCT = 0.08     # урон горения = 8% от урона игрока за тик
FREEZE_SKIP_CHANCE = 0.25   # шанс ледяного удара пропустить ход монстра

# ── Фьюри-ульт (шкала ярости) ────────────────────────
# Ярость накапливается в бою, при 100% следующий удар — ульт ×FURY_ULT_MULT
FURY_GAIN_ON_HIT = 8       # ярость за нанесённый удар
FURY_GAIN_ON_TAKEN = 5     # ярость за полученный удар
FURY_ULT_MULT = 2.5        # множитель урона ульта
FURY_RESET_LOSS = 50       # % ярости, теряемый при смерти

# Интервал спавна одного монстра (сек, для разнесённого спавна)
SPAWN_MIN_INTERVAL = 60     # мин 1 минута
SPAWN_MAX_INTERVAL = 300    # макс 5 минут

# Региональные бонусы (множители XP/Gold за тип локации)
REGION_BONUSES = {
    "dungeon": 1.5,
    "lair": 1.5,
    "castle": 1.3,
    "ruins": 1.25,
    "tower": 1.2,
    "temple": 1.2,
    "cemetery": 1.15,
    "swamp": 1.15,
    "mountain": 1.1,
    "desert": 1.1,
    "forest": 1.05,
    "mine": 1.05,
}

# Бонус XP/Gold за королевство (множитель)
KINGDOM_BONUSES = {
    "K1": 1.0,
    "K2": 1.2,
    "K3": 1.3,
}

# Расы и их бонусы
RACES = {
    "human": {"ru": "👤 Человек", "en": "👤 Human",   "bonus": "🍀 20% избежать штрафа монстра · 💰 +15% золота / 20% avoid monster penalty · +15% gold"},
    "dwarf": {"ru": "⛏️ Гном",    "en": "⛏️ Dwarf",   "bonus": "🛡️ +20% защиты · ❤️ +10% макс. HP / +20% defense · +10% max HP"},
    "elf":   {"ru": "🌿 Эльф",    "en": "🌿 Elf",     "bonus": "🏹 +10% к опыту · 🎯 +10% шанс крита / +10% XP · +10% crit chance"},
}

# Стоимость смены расы (в токенах). Первый выбор при онбординге — бесплатный.
RACE_CHANGE_COST = 5

# Расовые навыки (выдаются при выборе расы)
RACIAL_PASSIVES = {
    "human": "fortune_favor",
    "dwarf": "stone_fortitude",
    "elf":   "wind_grace",
}
RACIAL_ACTIVE_SKILLS = {
    "human": "purifying_light",
    "dwarf": "seismic_slam",
    "elf":   "quick_volley",
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

# =============================================
#   НАСТРОЙКИ МАГАЗИНА (сундуки)
# =============================================
# Цены и количество предметов в каждом сундуке
# Можно изменять в любое время через admin_panel
SHOP_CHESTS = {
    "small": {"price": 100, "items": 1, "emoji": "🎒"},
    "medium": {"price": 500, "items": 3, "emoji": "📦"},
    "big": {"price": 1000, "items": 5, "emoji": "🏴"},
    "legendary": {"price": 5000, "items": 3, "emoji": "✨", "guaranteed_rare": True},
}

# =============================================
# VIP МАГАЗИН (токены)
# =============================================
VIP_SHOP_ITEMS = {
    "xp_boost": {"price": 1, "duration": 3600, "emoji": "⚡"},
    "speed_boost": {"price": 1, "duration": 1800, "emoji": "🏃"},
    "protect": {"price": 2, "duration": 3600, "emoji": "🛡️"},
    "prestige": {"price": 5, "emoji": "✨"},
    "auto_quest": {"price": 5, "emoji": "🤖", "name": "Auto Quests"},
}

# =============================================
# PRESTIGE НАСТРОЙКИ
# =============================================
PRESTIGE_BONUS_PER_LEVEL = 2  # % бонуса за каждый уровень prestige
PRESTIGE_MAX_BONUS = 150      # максимум % бонуса (×2.5 от базы — защита кривой TIME_EXP)

# =============================================
#   НАСТРОЙКИ БОССОВ (гибкая система)
# =============================================
# Радиусы зон боссов
BOSS_RADIUS_AUTO = 10          # автобой в радиусе 10px
BOSS_RADIUS_CHOICE = 100        # выбор боя в радиусе 100px
BOSS_RESPAWN_DAYS = 1            # дни до респауна босса

# Анти-спам: персональный cooldown для игрока
BOSS_PLAYER_COOLDOWN = 3600     # 1 час между алертами от ОДНОГО босса
BOSS_ENCOUNTER_COOLDOWN = 7200    # 2 часа после боя (победа/поражение)
BOSS_MIN_DISTANCE = 50          # минимум 50px движения для повторного алерта

# Фильтрация по уровню
BOSS_LEVEL_TOLERANCE = 15       # показывать боссов +/- N уровней от игрока
BOSS_SHOW_ALL_FOR_VIP = True    # VIP видят всех боссов независимо от уровня

# XP бонусы и штрафы
BOSS_XP_BONUS = 2.0             # множитель XP за победу
BOSS_PENALTY_MULT = 3.0        # множитель штрафа за поражение

# =============================================
#   БОЕВАЯ СИСТЕМА (HP/MP/DEFENSE)
# =============================================
BOSS_SKILL_CHANCE = 0.20        # 20% шанс босса использовать навык
BOSS_SKILL_COOLDOWN = 2         # min раундов между навыками босса

# Регенерация (процент от max за тик 5с)
HP_REGEN_PCT = 0.005            # 0.5% max_hp за тик (~16 мин полный)
HP_REGEN_IDLE_PCT = 0.001       # 0.1% max_hp за тик для офлайн
MP_REGEN_PCT = 0.003            # 0.3% max_mp за тик (~28 мин полный)
MP_REGEN_IDLE_PCT = 0.001       # 0.1% max_mp за тик для офлайн
BOSS_REGEN_PCT = 0.01           # 1% HP в минуту регенерация босса

# Защита
DEFENSE_SOFT_CAP = 800          # Софт кап defense
DEFENSE_MAX_REDUCTION = 0.75     # Макс 75% снижения урона

# Навыки игроков (лечение за MP)
PLAYER_HEAL_SKILLS = {
    "quick_heal": {"mp_cost": 15, "heal_pct": 0.20, "name_ru": "Быстрое лечение", "name_en": "Quick Heal"},
    "regeneration": {"mp_cost": 25, "heal_pct": 0.35, "name_ru": "Регенерация", "name_en": "Regeneration"},
    "divine_shield": {"mp_cost": 30, "heal_pct": 0.50, "name_ru": "Божественный щит", "name_en": "Divine Shield"},
}

# Навыки боссов
BOSS_SKILLS = {
    "fireball": {"mp_cost": 25, "damage_mult": 1.5, "name_ru": "Огненный шар", "name_en": "Fireball", "chance": 0.20},
    "heal": {"mp_cost": 30, "heal_pct": 0.30, "name_ru": "Лечение", "name_en": "Heal", "chance": 0.15},
    "dark_burst": {"mp_cost": 45, "damage_mult": 2.0, "name_ru": "Тёмная вспышка", "name_en": "Dark Burst", "chance": 0.10},
    "stun": {"mp_cost": 20, "damage_mult": 0.8, "name_ru": "Оглушение", "name_en": "Stun", "chance": 0.15, "stun": True},
}

# =============================================
#   ПАССИВНЫЕ НАВЫКИ
# =============================================
PASSIVE_MAX_SLOTS = 5
PASSIVE_MAX_LEVEL = 100
PASSIVE_XP_PER_TRIGGER = 1
PASSIVE_LEVEL_UP_XP_BASE = 500
PASSIVE_REGEN_TICK_INTERVAL = 12

PASSIVE_SKILL_PRICES = {
    "vampirism": 2000,
    "thorns": 600,
    "regeneration": 800,
    "gold_finder": 500,
    "xp_boost": 700,
    "critical": 2000,
    "dodge": 600,
    "first_strike": 1600,
    "shield_wall": 900,
    "slow_poison": 700,
}

PASSIVE_PRICE_GROWTH_FACTOR = 1.5

PASSIVE_LEVEL_REQUIREMENTS = {
    "Rare": 5,
    "Epic": 15,
    "Legendary": 30,
    "Unique": 45,
}

PASSIVE_UPGRADE_BASE = 100
PASSIVE_UPGRADE_SCALE = 1.15

# Активные навыки — XP за использование
ACTIVE_SKILL_XP_PER_USE = 10
ACTIVE_SKILL_LEVEL_UP_XP_BASE = 500

# =============================================
#   TELEGRAM STARS МАГАЗИН
# =============================================
# 1 токен = 50 Stars
STARS_SHOP_RATE = 50
# Максимум токенов за одну покупку
STARS_SHOP_MAX_PER_PURCHASE = 10

# =============================================
#   СИСТЕМА ОХОТЫ
# =============================================
# Интервал боя (секунды) по режимам
HUNTING_INTERVAL = {
    "weak": 120,      # каждые 2 мин
    "strong": 240,    # каждые 4 мин
    "epic": 300,      # каждые 5 мин
}
# Длительности охоты: {секунды: бонус завершения}
HUNTING_DURATIONS = {
    3600: 1.0,   # 1ч
    7200: 1.5,   # 2ч
    14400: 2.5,  # 4ч
    18000: 3.0,  # 5ч
}
# Режимы охоты: уровни монстров, множители наград, риски
HUNTING_MODES = {
    "weak": {
        "name_ru": "Слабый", "name_en": "Weak", "icon": "🟢",
        "level_offset": (-2, 0),
        "xp_mult": 0.5, "gold_mult": 0.5,
        "loot_chance": 0.04,
        "retreat_hp_pct": 0.30,     # отступление при HP < 30% (боя нет)
        "survive_bonus": 1.0,
        "death_gold_penalty": 0.0,
        "death_item_chance": 0.0,
    },
    "strong": {
        "name_ru": "Сильный", "name_en": "Strong", "icon": "🟡",
        "level_offset": (0, 2),
        "xp_mult": 1.0, "gold_mult": 1.0,
        "loot_chance": 0.08,
        "retreat_hp_pct": 0.0,
        "survive_bonus": 1.5,
        "death_gold_penalty": 0.10,
        "death_item_chance": 0.0,
    },
    "epic": {
        "name_ru": "Эпический", "name_en": "Epic", "icon": "🔴",
        "level_offset": (2, 5),
        "xp_mult": 2.0, "gold_mult": 2.0,
        "loot_chance": 0.15,
        "retreat_hp_pct": 0.0,
        "survive_bonus": 3.0,
        "death_gold_penalty": 0.20,
        "death_item_chance": 0.30,
    },
}
# Волны: каждые N убийств +1 уровень монстра (макс бонус)
HUNTING_WAVE_KILLS = 5
HUNTING_WAVE_MAX_BONUS = 3
# Статы монстра масштабируются от DPS игрока (самобаланс под экипировку)
HUNTING_MONSTER_HP_FACTOR = {"weak": 1.8, "strong": 2.6, "epic": 3.6}
HUNTING_MONSTER_DPS_FACTOR = {"weak": 0.10, "strong": 0.18, "epic": 0.28}
# Прирост статов монстра за волну
HUNTING_WAVE_MULT = 0.15
# Эпический мини-босс: шанс на финальном бое
HUNTING_MINIBOSS_CHANCE = 0.5
# Множители статов мини-босса
HUNTING_MINIBOSS_HP_MULT = 2.5
HUNTING_MINIBOSS_DPS_MULT = 1.5
# Множитель наград мини-босса
HUNTING_MINIBOSS_REWARD_MULT = 3.0
# Раунд боя охоты = N секунд
HUNTING_ROUND_SECONDS = 5
# Максимум раундов в одном бою охоты (предохранитель)
HUNTING_MAX_ROUNDS = 20

# =============================================
#   ЕЖЕДНЕВНЫЕ НАГРАДЫ
# =============================================
# Награды за ежедневный вход по дням 7-дневного цикла (токены)
DAILY_REWARD_CYCLE = [1, 1, 2, 2, 3, 3, 5]
# Оффлайн-бонус: часов оффлайна для бонусного токена
OFFLINE_BONUS_HOURS = 6

# Токены за выполнение ежедневного бонусного квеста (из /daily)
DAILY_QUEST_TOKEN_REWARD = 2

# =============================================
#   БОССЫ — ОКНО УБИЙСТВА
# =============================================
# Часов после респауна, в течение которых босс должен быть убит
BOSS_KILL_WINDOW_HOURS = 2

# =============================================
#   ПИТОМЦЫ
# =============================================
# Опыт питомца за игровой тик (экипированному) каждые PET_XP_INTERVAL секунд
PET_XP_PER_TICK = 1
PET_XP_INTERVAL = 300
# Опыт за убийства (второй источник прокачки)
PET_XP_PER_KILL = 1
PET_XP_PER_BOSS = 3
PET_MAX_LEVEL = 50
PET_XP_THRESHOLD_BASE = 100  # порог до след. уровня = PET_XP_THRESHOLD_BASE * level
PET_LEVEL_GROWTH = 0.10      # +10% к бонусам за каждый уровень сверх 1-го
PET_EVOLVE_LEVEL = 30        # уровень для эволюции
PET_EVOLVE_TOKENS = 25       # стоимость эволюции в токенах

# =============================================
#   КЛАНОВЫЕ БОССЫ
# =============================================
# Как часто проверяем спавн боссов кланам без активного (сек)
CLAN_BOSS_SPAWN_INTERVAL = 6 * 3600
# Время жизни босса до деспауна (сек)
CLAN_BOSS_DURATION = 6 * 3600
# Минимальный уровень клана для появления босса
CLAN_BOSS_MIN_CLAN_LEVEL = 2
# HP босса = CLAN_BOSS_HP_BASE + clan.level * CLAN_BOSS_HP_PER_LEVEL
CLAN_BOSS_HP_BASE = 50000
CLAN_BOSS_HP_PER_LEVEL = 50000
# Вклад урона членом клана = DPS игрока * CLAN_BOSS_DPS_MULT каждые CLAN_BOSS_HIT_COOLDOWN сек
CLAN_BOSS_DPS_MULT = 1.0
CLAN_BOSS_HIT_COOLDOWN = 300
# Награды за победу
CLAN_BOSS_KILL_TOKENS = 5      # токенов каждому вкладчику
CLAN_BOSS_KILL_GOLD_BASE = 500  # база золота вкладчику + доля от урона
CLAN_BOSS_KILL_GOLD = 2000     # пул золота, делится пропорционально урону
CLAN_BOSS_CLAN_XP = 500        # опыт клану за победу

# =============================================
#   МИРОВОЙ РЕЙД-БОСС
# =============================================
RAID_BOSS_SPAWN_INTERVAL = 8 * 3600   # переспавн после победы/деспауна
RAID_BOSS_DURATION = 8 * 3600         # время жизни до деспауна
# HP босса = RAID_BOSS_HP_BASE + level * RAID_BOSS_HP_PER_LEVEL
RAID_BOSS_HP_BASE = 500000
RAID_BOSS_HP_PER_LEVEL = 250000
# Вклад игрока = DPS * RAID_BOSS_DPS_MULT каждые RAID_BOSS_HIT_COOLDOWN сек
RAID_BOSS_DPS_MULT = 1.0
RAID_BOSS_HIT_COOLDOWN = 120
# Награды за победу (всем вкладчикам)
RAID_BOSS_KILL_TOKENS = 10
RAID_BOSS_KILL_GOLD_BASE = 2000
RAID_BOSS_KILL_GOLD = 10000

# =============================================
#   ПОДЗЕМЕЛЬЯ
# =============================================
# Как часто бой за комнату (сек)
DUNGEON_INTERVAL = 300
# Монстр комнаты генерируется движком охоты (режим strong) и масштабируется:
# hp = hp * (1 + (floor-1) * DUNGEON_ROOM_GROWTH) * dungeon.hp_mult
DUNGEON_ROOM_GROWTH = 0.25
# Токены за полное прохождение
DUNGEON_TOKEN_REWARD = 5

# =============================================
#   АРЕНА ВОЛН
# =============================================
# Как часто бой за волну (сек)
ARENA_INTERVAL = 240
# Минимальный уровень для входа на арену
ARENA_MIN_LEVEL = 3
# Рост статов монстра за волну (как у подземелий)
ARENA_WAVE_GROWTH = 0.12
# Каждая N-я волна — мини-босс
ARENA_BOSS_EVERY = 5
# Токены за каждую пройденную волну
ARENA_TOKEN_PER_WAVE = 1

