"""
core/loot.py — Генератор предметов (чистая логика)

Не зависит от Telegram API или базы данных.
Содержит только формулы и логику генерации предметов.
"""
import math
import random
from typing import Optional


# ─────────────────────────────────────────────
# Data tables (все данные предметов)
# ─────────────────────────────────────────────

CONDITIONS = [
    {"name": "Жалкий",      "name_en": "Miserable",      "weight": 0.14, "mdps": 0.6, "mhp": 0.6, "mdef": 0.6, "mmp": 0.6,  "rank": 0},
    {"name": "Плохой",      "name_en": "Poor",           "weight": 0.23, "mdps": 1, "mhp": 1, "mdef": 1, "mmp": 1,    "rank": 0},
    {"name": "Потёртый",    "name_en": "Worn",            "weight": 0.50, "mdps": 1, "mhp": 1, "mdef": 1, "mmp": 1,    "rank": 0},
    {"name": "Восстановленный", "name_en": "Restored",    "weight": 0.45, "mdps": 1.3, "mhp": 1.3, "mdef": 1.3, "mmp": 1.3, "rank": 0},
    {"name": "Пыльный",     "name_en": "Dusty",           "weight": 0.40, "mdps": 1.5, "mhp": 1.5, "mdef": 1.5, "mmp": 1.5,  "rank": 1},
    {"name": "Чистый",      "name_en": "Clean",           "weight": 0.45, "mdps": 2, "mhp": 2, "mdef": 2, "mmp": 2,    "rank": 1},
    {"name": "Отполированный", "name_en": "Polished",     "weight": 0.34, "mdps": 2.5, "mhp": 2.5, "mdef": 2.5, "mmp": 2.5, "rank": 2},
    {"name": "Первозданный", "name_en": "Pristine",       "weight": 0.17, "mdps": 3, "mhp": 3, "mdef": 3, "mmp": 3,   "rank": 3},
    {"name": "Выставочный", "name_en": "Display",         "weight": 0.10, "mdps": 3.5, "mhp": 3.5, "mdef": 3.5, "mmp": 3.5,  "rank": 4},
    {"name": "Богоданный",  "name_en": "God-given",       "weight": 0.03, "mdps": 5, "mhp": 5, "mdef": 5, "mmp": 5,    "rank": 5},
]

QUALITIES = [
    {"name": "Базовый",     "name_en": "Basic",           "weight": 0.85, "mdps": 1, "mhp": 1, "mdef": 1, "mmp": 1,    "rank": 0},
    {"name": "Хлипкий",     "name_en": "Flimsy",          "weight": 0.35, "mdps": 0.6, "mhp": 0.6, "mdef": 0.6, "mmp": 0.6,  "rank": 0},
    {"name": "Треснутый",   "name_en": "Cracked",         "weight": 0.35, "mdps": 0.6, "mhp": 0.6, "mdef": 0.6, "mmp": 0.6,  "rank": 0},
    {"name": "Потрёпанный", "name_en": "Weathered",       "weight": 0.42, "mdps": 1.1, "mhp": 1.1, "mdef": 1.1, "mmp": 1.1,  "rank": 1},
    {"name": "Ржавый",      "name_en": "Rusty",           "weight": 0.31, "mdps": 1.1, "mhp": 1.1, "mdef": 1.1, "mmp": 1.1,  "rank": 0},
    {"name": "Укреплённый", "name_en": "Reinforced",      "weight": 0.27, "mdps": 1.3, "mhp": 1.3, "mdef": 1.3, "mmp": 1.3,  "rank": 1},
    {"name": "Ветеранский", "name_en": "Veteran",         "weight": 0.24, "mdps": 1.7, "mhp": 1.7, "mdef": 1.7, "mmp": 1.7,  "rank": 1},
    {"name": "Позолоченный","name_en": "Gilded",          "weight": 0.18, "mdps": 2.8, "mhp": 2.8, "mdef": 2.8, "mmp": 2.8,  "rank": 2},
    {"name": "Безупречный", "name_en": "Flawless",        "weight": 0.14, "mdps": 3.5, "mhp": 3.5, "mdef": 3.5, "mmp": 3.5,  "rank": 2},
    {"name": "Аутентичный", "name_en": "Authentic",       "weight": 0.10, "mdps": 4, "mhp": 4, "mdef": 4, "mmp": 4,    "rank": 3},
    {"name": "Прославленный","name_en": "Glorious",       "weight": 0.02, "mdps": 7, "mhp": 7, "mdef": 7, "mmp": 7,   "rank": 3},
    {"name": "Вознесённый", "name_en": "Ascended",        "weight": 0.01, "mdps": 10, "mhp": 10, "mdef": 10, "mmp": 10,   "rank": 4},
    {"name": "Галактический","name_en": "Galactic",       "weight": 0.005,"mdps": 12, "mhp": 12, "mdef": 12, "mmp": 12,  "rank": 5},
]

PREFIXES = [
    {"name": "",             "name_en": "",                "weight": 0.9,  "mdps": 1, "mhp": 1, "mdef": 1, "mmp": 1},
    {"name": "Горящий ",     "name_en": "Burning ",        "weight": 0.82, "mdps": 1.15, "mhp": 1.15, "mdef": 1.15, "mmp": 1.15},
    {"name": "Пылающий ",   "name_en": "Flaming ",        "weight": 0.65, "mdps": 1.25, "mhp": 1.25, "mdef": 1.25, "mmp": 1.25},
    {"name": "Тлеющий ",    "name_en": "Smoldering ",     "weight": 0.47, "mdps": 1.35, "mhp": 1.35, "mdef": 1.35, "mmp": 1.35},
    {"name": "Холодный ",   "name_en": "Cold ",           "weight": 0.82, "mdps": 1.15, "mhp": 1.15, "mdef": 1.15, "mmp": 1.15},
    {"name": "Охлаждённый ","name_en": "Chilled ",        "weight": 0.65, "mdps": 1.25, "mhp": 1.25, "mdef": 1.25, "mmp": 1.25},
    {"name": "Ледяной ",    "name_en": "Icy ",            "weight": 0.53, "mdps": 1.25, "mhp": 1.25, "mdef": 1.25, "mmp": 1.25},
    {"name": "Ледниковый ", "name_en": "Glacial ",        "weight": 0.45, "mdps": 1.25, "mhp": 1.25, "mdef": 1.25, "mmp": 1.25},
    {"name": "Острый ",     "name_en": "Sharp ",          "weight": 0.65, "mdps": 1.15, "mhp": 1.15, "mdef": 1.15, "mmp": 1.15},
    {"name": "Точный ",     "name_en": "Precise ",        "weight": 0.64, "mdps": 1.25, "mhp": 1.25, "mdef": 1.25, "mmp": 1.25},
    {"name": "Меткий ",     "name_en": "Accurate ",       "weight": 0.60, "mdps": 1.35, "mhp": 1.35, "mdef": 1.35, "mmp": 1.35},
    {"name": "Смертельный ","name_en": "Deadly ",         "weight": 0.22, "mdps": 1.25, "mhp": 1.25, "mdef": 1.25, "mmp": 1.25},
    {"name": "Роковой ",    "name_en": "Fatal ",          "weight": 0.15, "mdps": 1.25, "mhp": 1.25, "mdef": 1.25, "mmp": 1.25},
    {"name": "Прочный ",    "name_en": "Sturdy ",         "weight": 0.37, "mdps": 1.15, "mhp": 1.15, "mdef": 1.15, "mmp": 1.15},
    {"name": "Быстрый ",    "name_en": "Swift ",          "weight": 0.26, "mdps": 1.25, "mhp": 1.25, "mdef": 1.25, "mmp": 1.25},
    {"name": "Стремительный ","name_en": "Rapid ",        "weight": 0.34,"mdps": 1.35, "mhp": 1.35, "mdef": 1.35, "mmp": 1.35},
    {"name": "Твёрдый ",    "name_en": "Solid ",          "weight": 0.45, "mdps": 1.25, "mhp": 1.25, "mdef": 1.25, "mmp": 1.25},
    {"name": "Жёсткий ",    "name_en": "Hard ",           "weight": 0.62, "mdps": 1.25, "mhp": 1.25, "mdef": 1.25, "mmp": 1.25},
    {"name": "Сосредоточенный ","name_en": "Focused ",    "weight": 0.32,"mdps": 1.15, "mhp": 1.15, "mdef": 1.15, "mmp": 1.15},
    {"name": "Святой ",     "name_en": "Holy ",           "weight": 0.10, "mdps": 2.00, "mhp": 2.00, "mdef": 2.00, "mmp": 2.00},
    {"name": "Светокованый ","name_en": "Lightforged ",   "weight": 0.10,"mdps": 2.00, "mhp": 2.00, "mdef": 2.00, "mmp": 2.00},
]

SUFFIXES = [
    {"name": "",                  "name_en": "",                  "weight": 0.9,  "mdps": 1, "mhp": 1, "mdef": 1, "mmp": 1},
    {"name": " Медведя",          "name_en": " of the Bear",     "weight": 0.10, "mdps": 1.25, "mhp": 1.25, "mdef": 1.25, "mmp": 1.25},
    {"name": " Воина",            "name_en": " of the Warrior",  "weight": 0.10, "mdps": 1.35, "mhp": 1.35, "mdef": 1.35, "mmp": 1.35},
    {"name": " Безумца",          "name_en": " of the Madman",   "weight": 0.10, "mdps": 1.95, "mhp": 1.95, "mdef": 1.95, "mmp": 1.95},
    {"name": " Проклятых",        "name_en": " of the Cursed",   "weight": 0.10, "mdps": 1.30, "mhp": 1.30, "mdef": 1.30, "mmp": 1.30},
    {"name": " Огня",             "name_en": " of Fire",         "weight": 0.10, "mdps": 2.00, "mhp": 2.00, "mdef": 2.00, "mmp": 2.00},
    {"name": " Богов",            "name_en": " of the Gods",     "weight": 0.10, "mdps": 1.95, "mhp": 1.95, "mdef": 1.95, "mmp": 1.95},
    {"name": " Смелого",          "name_en": " of the Brave",    "weight": 0.10, "mdps": 1.20, "mhp": 1.20, "mdef": 1.20, "mmp": 1.20},
    {"name": " Кошмаров",         "name_en": " of Nightmares",   "weight": 0.10, "mdps": 1.50, "mhp": 1.50, "mdef": 1.50, "mmp": 1.50},
    {"name": " Мечты",            "name_en": " of Dreams",       "weight": 0.10, "mdps": 1.50, "mhp": 1.50, "mdef": 1.50, "mmp": 1.50},
    {"name": " Забытых",          "name_en": " of the Forgotten","weight": 0.10, "mdps": 1.60, "mhp": 1.60, "mdef": 1.60, "mmp": 1.60},
    {"name": " Кунзиле",          "name_en": " of Kunzile",      "weight": 0.10, "mdps": 2.50, "mhp": 2.50, "mdef": 2.50, "mmp": 2.50},
    {"name": " Славы",            "name_en": " of Glory",        "weight": 0.10, "mdps": 1.40, "mhp": 1.40, "mdef": 1.40, "mmp": 1.40},
    {"name": " Позора",           "name_en": " of Shame",        "weight": 0.10, "mdps": 1.90, "mhp": 1.90, "mdef": 1.90, "mmp": 1.90},
    {"name": " Греха",            "name_en": " of Sin",          "weight": 0.10, "mdps": 1.80, "mhp": 1.80, "mdef": 1.80, "mmp": 1.80},
]

WEAPONS = [
    {"name": "Меч",               "name_en": "Sword",            "weight": 0.9,  "bdps": 2},
    {"name": "Молот",             "name_en": "Hammer",           "weight": 0.5,  "bdps": 2},
    {"name": "Клеймор",           "name_en": "Claymore",         "weight": 0.5,  "bdps": 2},
    {"name": "Длинный меч",       "name_en": "Longsword",       "weight": 0.5,  "bdps": 2},
    {"name": "Двуручник",         "name_en": "Greatsword",      "weight": 0.2,  "bdps": 2},
    {"name": "Палаш",             "name_en": "Broadsword",       "weight": 0.5,  "bdps": 2},
    {"name": "Катана",            "name_en": "Katana",           "weight": 0.15, "bdps": 2},
    {"name": "Сабля",             "name_en": "Saber",            "weight": 0.4,  "bdps": 2},
    {"name": "Топор",             "name_en": "Axe",              "weight": 0.9,  "bdps": 2},
    {"name": "Боевой топор",      "name_en": "Battle Axe",      "weight": 0.5,  "bdps": 2},
    {"name": "Кинжал",            "name_en": "Dagger",           "weight": 0.9,  "bdps": 2},
    {"name": "Стилет",            "name_en": "Stiletto",         "weight": 0.24, "bdps": 2},
    {"name": "Копьё",             "name_en": "Spear",            "weight": 0.9,  "bdps": 2},
    {"name": "Алебарда",          "name_en": "Halberd",          "weight": 0.24, "bdps": 2},
    {"name": "Коса",              "name_en": "Scythe",           "weight": 0.10, "bdps": 2},
    {"name": "Возмездие Закона",  "name_en": "Law's Retribution","weight": 0.01, "bdps": 4,
     "flair": 'Тяжесть грехов тянет этот кинжал к земле.',
     "flair_en": 'The weight of sins pulls this dagger to the ground.'},
    {"name": "Конец Судьбы",      "name_en": "End of Fate",      "weight": 0.01, "bdps": 4,
     "flair": 'Ты взываешь о пощаде, но ответа нет.',
     "flair_en": 'You beg for mercy, but there is no answer.'},
    {"name": "Экскалибур",        "name_en": "Excalibur",        "weight": 0.01, "bdps": 4,
     "flair": 'Дева озера зовёт этот клинок. Тебе стоит его вернуть.',
     "flair_en": 'The Lady of the Lake calls this blade. You should return it.'},
    {"name": "Мурамаса",          "name_en": "Muramasa",         "weight": 0.01, "bdps": 4,
     "flair": 'Держа это оружие, ты испытываешь желание испытать его остроту на друзьях.',
     "flair_en": 'Holding this weapon, you feel the urge to test its edge on friends.'},
]

SHIELDS = [
    {"name": "Щит",               "name_en": "Shield",           "weight": 0.9,  "bdps": 2},
    {"name": "Нагрудный щит",     "name_en": "Chest Shield",   "weight": 0.6,  "bdps": 2},
    {"name": "Баклер",            "name_en": "Buckler",          "weight": 0.7,  "bdps": 2},
    {"name": "Воинский щит",      "name_en": "War Shield",      "weight": 0.5,  "bdps": 2},
    {"name": "Круглый щит",       "name_en": "Round Shield",    "weight": 0.7,  "bdps": 2},
    {"name": "Эгида",             "name_en": "Aegis",            "weight": 0.01, "bdps": 4,
     "flair": 'Подписан "Афине" и немного обгорел.',
     "flair_en": 'Signed "To Athena" and slightly scorched.'},
]

HELMETS = [
    {"name": "Шлем",              "name_en": "Helmet",           "weight": 0.9,  "bdps": 2},
    {"name": "Котелок",           "name_en": "Pot Helm",        "weight": 0.5,  "bdps": 2},
    {"name": "Большой шлем",      "name_en": "Great Helm",      "weight": 0.6,  "bdps": 2},
    {"name": "Бацинет",           "name_en": "Bascinet",         "weight": 0.5,  "bdps": 2},
    {"name": "Крестоносец",       "name_en": "Crusader",        "weight": 0.7,  "bdps": 2},
    {"name": "Шлем Ужаса",        "name_en": "Helm of Terror",  "weight": 0.01, "bdps": 4,
     "flair": 'Поблёскивающий червь, твоё шипение было велико...',
     "flair_en": 'A glimmering worm, your hissing was great...'},
]

CHESTS = [
    {"name": "Нагрудник",         "name_en": "Chestplate",       "weight": 0.9,  "bdps": 2},
    {"name": "Гамбезон",          "name_en": "Gambeson",         "weight": 0.6,  "bdps": 2},
    {"name": "Латный доспех",     "name_en": "Plate Armor",     "weight": 0.6,  "bdps": 2},
    {"name": "Кольчуга",          "name_en": "Chainmail",        "weight": 0.7,  "bdps": 2},
    {"name": "Кираса",            "name_en": "Cuirass",          "weight": 0.5,  "bdps": 2},
    {"name": "Броня Беовульфа",   "name_en": "Beowulf's Armor", "weight": 0.01, "bdps": 4,
     "flair": 'Если смерть придёт за мной - отошли мою броню Хигелаку.',
     "flair_en": 'If death comes for me - send my armor to Hygelac.'},
]

GLOVES = [
    {"name": "Перчатки",          "name_en": "Gloves",           "weight": 0.8,  "bdps": 2},
    {"name": "Рукавицы",          "name_en": "Gauntlets",        "weight": 0.7,  "bdps": 2},
    {"name": "Наручи",            "name_en": "Bracers",          "weight": 0.6,  "bdps": 2},
    {"name": "Кастет",            "name_en": "Knuckles",        "weight": 0.5,  "bdps": 2},
    {"name": "Когти",             "name_en": "Claws",            "weight": 0.2,  "bdps": 2},
]

BOOTS = [
    {"name": "Сапоги",            "name_en": "Boots",            "weight": 0.9,  "bdps": 2},
    {"name": "Ботинки",           "name_en": "Shoes",           "weight": 0.7,  "bdps": 2},
]

RINGS = [
    {"name": "Кольцо",            "name_en": "Ring",             "weight": 0.9,  "bdps": 2},
    {"name": "Перстень",          "name_en": "Signet Ring",     "weight": 0.6,  "bdps": 2},
]

AMULETS = [
    {"name": "Амулет",            "name_en": "Amulet",           "weight": 0.9,  "bdps": 2},
    {"name": "Медальон",          "name_en": "Pendant",         "weight": 0.6,  "bdps": 2},
]

SLOTS_DATA = {
    "weapon": WEAPONS,
    "shield": SHIELDS,
    "helmet": HELMETS,
    "chest": CHESTS,
    "gloves": GLOVES,
    "boots": BOOTS,
    "ring": RINGS,
    "amulet": AMULETS,
}

SLOT_BASE_STATS = {
    "weapon": {"bhp": 0, "bdef": 0, "bmp": 0},
    "shield": {"bhp": 0, "bdef": 2, "bmp": 0},
    "helmet": {"bhp": 0, "bdef": 1, "bmp": 0},
    "chest":  {"bhp": 3, "bdef": 0, "bmp": 0},
    "gloves": {"bhp": 0, "bdef": 0, "bmp": 0},
    "boots":  {"bhp": 0, "bdef": 0, "bmp": 0},
    "ring":   {"bhp": 0, "bdef": 0, "bmp": 2},
    "amulet": {"bhp": 1, "bdef": 0, "bmp": 1},
}

RARITY_MULT = {
    "Common": 1.0,
    "Uncommon": 1.0,
    "Rare": 1.1,
    "Epic": 1.25,
    "Legendary": 1.5,
    "Ascended": 2.0,
    "Unique": 2.0,
}


# ─────────────────────────────────────────────
# Core функции
# ─────────────────────────────────────────────

def _weighted_choice(items: list, rng: random.Random | None = None) -> dict:
    """Выбрать случайный предмет из списка с учётом весов."""
    rng = rng or random
    names = [item["name"] for item in items]
    weights = [item["weight"] for item in items]
    chosen = rng.choices(names, weights)[0]
    for item in items:
        if item["name"] == chosen:
            return item
    return {}


def _calculate_rank(quality_rank: int, condition_rank: int) -> str:
    """Определить редкость предмета по сумме рангов качества и состояния."""
    rank = quality_rank + condition_rank
    if rank in (1, 2):
        return "Uncommon"
    elif rank in (3, 4):
        return "Rare"
    elif rank in (5, 6):
        return "Epic"
    elif rank in (7, 8):
        return "Legendary"
    elif rank == 9:
        return "Ascended"
    return "Common"


def generate_item_data(
    slot_name: str,
    player_level: int,
    rng: random.Random | None = None,
) -> dict:
    """
    Сгенерировать данные предмета (чистая логика, без побочных эффектов).
    
    Args:
        slot_name: Имя слота (weapon, shield, helmet и т.д.)
        player_level: Уровень игрока для расчёта DPS
        rng: Опциональный Random instance для тестирования
        
    Returns:
        dict с данными предмета
    """
    rng = rng or random
    equip_list = SLOTS_DATA.get(slot_name, WEAPONS)
    
    base = _weighted_choice(equip_list, rng)
    prefix = _weighted_choice(PREFIXES, rng)
    suffix = _weighted_choice(SUFFIXES, rng)
    quality = _weighted_choice(QUALITIES, rng)
    condition = _weighted_choice(CONDITIONS, rng)
    
    quality_rank = quality.get("rank", 0)
    condition_rank = condition.get("rank", 0)
    rankrole = _calculate_rank(quality_rank, condition_rank)
    
    mdps_sum = prefix["mdps"] + suffix["mdps"] + quality["mdps"] + condition["mdps"]
    sqrt_factor = math.sqrt(mdps_sum * 1.2 + 1)
    
    dps = math.floor(
        rng.randrange(base["bdps"] - 1, base["bdps"] + 1)
        * sqrt_factor
        * player_level
    )
    
    slot_stats = SLOT_BASE_STATS.get(slot_name, {"bhp": 0, "bdef": 0, "bmp": 0})
    
    def _calc_bonus(base_val: int, m_sum: float) -> int:
        if base_val <= 0:
            return 0
        return math.floor(
            max(1, rng.randrange(base_val - 1, base_val + 1))
            * math.sqrt(m_sum * 1.2 + 1)
            * player_level
        )
    
    mhp_sum = prefix["mhp"] + suffix["mhp"] + quality["mhp"] + condition["mhp"]
    mdef_sum = prefix["mdef"] + suffix["mdef"] + quality["mdef"] + condition["mdef"]
    mmp_sum = prefix["mmp"] + suffix["mmp"] + quality["mmp"] + condition["mmp"]
    
    hp_bonus = _calc_bonus(slot_stats["bhp"], mhp_sum)
    def_bonus = _calc_bonus(slot_stats["bdef"], mdef_sum)
    mp_bonus = _calc_bonus(slot_stats["bmp"], mmp_sum)
    
    flair = base.get("flair")
    rank = "Unique" if flair else rankrole
    
    mult = RARITY_MULT.get(rank, 1.0)
    if mult != 1.0:
        dps = math.floor(dps * mult)
        hp_bonus = math.floor(hp_bonus * mult)
        def_bonus = math.floor(def_bonus * mult)
        mp_bonus = math.floor(mp_bonus * mult)
    
    return {
        "name": base["name"],
        "quality": quality["name"],
        "condition": condition["name"],
        "prefix": prefix["name"],
        "suffix": suffix["name"],
        "name_en": base.get("name_en", base["name"]),
        "quality_en": quality.get("name_en", quality["name"]),
        "condition_en": condition.get("name_en", condition["name"]),
        "prefix_en": prefix.get("name_en", prefix["name"]),
        "suffix_en": suffix.get("name_en", suffix["name"]),
        "dps": dps,
        "hp_bonus": hp_bonus,
        "def_bonus": def_bonus,
        "mp_bonus": mp_bonus,
        "rank": rank,
        "flair": flair,
        "flair_en": base.get("flair_en", flair),
    }


def is_item_better(new_item: dict, current_item: dict | None) -> bool:
    """Проверить, луч ли новый предмет текущего."""
    if not current_item:
        return True
    return new_item.get("dps", 0) > current_item.get("dps", 0)


def get_random_slot() -> str:
    """Получить случайный слот для предмета."""
    return random.choice(list(SLOTS_DATA.keys()))


def is_rare_drop(item: dict) -> bool:
    """Проверить, является ли предмет редким дропом (триггер квестов)."""
    return item.get("rank") in ("Rare", "Epic", "Legendary", "Ascended")


__all__ = [
    "CONDITIONS",
    "QUALITIES",
    "PREFIXES",
    "SUFFIXES",
    "SLOTS_DATA",
    "SLOT_BASE_STATS",
    "RARITY_MULT",
    "generate_item_data",
    "is_item_better",
    "get_random_slot",
    "is_rare_drop",
]