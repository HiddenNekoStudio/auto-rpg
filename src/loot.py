"""
loot.py - генератор предметов
"""

import math
import random
from enum import Enum

from db import Player

conditions = [
    {"name": "Жалкий",      "weight": 0.14, "mdps": 0.6,  "rank": 0},
    {"name": "Плохой",      "weight": 0.23, "mdps": 1,    "rank": 0},
    {"name": "Потёртый",    "weight": 0.50, "mdps": 1,    "rank": 0},
    {"name": "Восстановленный", "weight": 0.45, "mdps": 1.3, "rank": 0},
    {"name": "Пыльный",     "weight": 0.40, "mdps": 1.5,  "rank": 1},
    {"name": "Чистый",      "weight": 0.45, "mdps": 2,    "rank": 1},
    {"name": "Отполированный", "weight": 0.34, "mdps": 2.5, "rank": 2},
    {"name": "Первозданный", "weight": 0.17, "mdps": 3,   "rank": 3},
    {"name": "Выставочный", "weight": 0.10, "mdps": 3.5,  "rank": 4},
    {"name": "Богоданный",  "weight": 0.03, "mdps": 5,    "rank": 5},
]
qualities = [
    {"name": "Базовый",     "weight": 0.85, "mdps": 1,    "rank": 0},
    {"name": "Хлипкий",     "weight": 0.35, "mdps": 0.6,  "rank": 0},
    {"name": "Треснутый",   "weight": 0.35, "mdps": 0.6,  "rank": 0},
    {"name": "Weathered",   "weight": 0.42, "mdps": 1.1,  "rank": 1},
    {"name": "Ржавый",      "weight": 0.31, "mdps": 1.1,  "rank": 0},
    {"name": "Укреплённый", "weight": 0.27, "mdps": 1.3,  "rank": 1},
    {"name": "Ветеранский", "weight": 0.24, "mdps": 1.7,  "rank": 1},
    {"name": "Позолоченный","weight": 0.18, "mdps": 2.8,  "rank": 2},
    {"name": "Безупречный", "weight": 0.14, "mdps": 3.5,  "rank": 2},
    {"name": "Аутентичный", "weight": 0.10, "mdps": 4,    "rank": 3},
    {"name": "Прославленный","weight": 0.02, "mdps": 7,   "rank": 3},
    {"name": "Вознесённый", "weight": 0.01, "mdps": 10,   "rank": 4},
    {"name": "Галактический","weight": 0.005,"mdps": 12,  "rank": 5},
]
prefixes = [
    {"name": "",             "weight": 0.9,  "mdps": 1},
    {"name": "Горящий ",     "weight": 0.82, "mdps": 1.15},
    {"name": "Пылающий ",   "weight": 0.65, "mdps": 1.25},
    {"name": "Тлеющий ",    "weight": 0.47, "mdps": 1.35},
    {"name": "Холодный ",   "weight": 0.82, "mdps": 1.15},
    {"name": "Охлаждённый ","weight": 0.65, "mdps": 1.25},
    {"name": "Ледяной ",    "weight": 0.53, "mdps": 1.25},
    {"name": "Ледниковый ", "weight": 0.45, "mdps": 1.25},
    {"name": "Острый ",     "weight": 0.65, "mdps": 1.15},
    {"name": "Точный ",     "weight": 0.64, "mdps": 1.25},
    {"name": "Меткий ",     "weight": 0.60, "mdps": 1.35},
    {"name": "Смертельный ","weight": 0.22, "mdps": 1.25},
    {"name": "Роковой ",    "weight": 0.15, "mdps": 1.25},
    {"name": "Прочный ",    "weight": 0.37, "mdps": 1.15},
    {"name": "Быстрый ",    "weight": 0.26, "mdps": 1.25},
    {"name": "Стремительный ","weight": 0.34,"mdps": 1.35},
    {"name": "Твёрдый ",    "weight": 0.45, "mdps": 1.25},
    {"name": "Жёсткий ",    "weight": 0.62, "mdps": 1.25},
    {"name": "Сосредоточенный ","weight": 0.32,"mdps": 1.15},
    {"name": "Святой ",     "weight": 0.10, "mdps": 2.00},
    {"name": "Светокованый ","weight": 0.10,"mdps": 2.00},
]
suffixes = [
    {"name": "",                  "weight": 0.9,  "mdps": 1},
    {"name": " Медведя",          "weight": 0.10, "mdps": 1.25},
    {"name": " Воина",            "weight": 0.10, "mdps": 1.35},
    {"name": " Безумца",          "weight": 0.10, "mdps": 1.95},
    {"name": " Проклятых",        "weight": 0.10, "mdps": 1.30},
    {"name": " Огня",             "weight": 0.10, "mdps": 2.00},
    {"name": " Богов",            "weight": 0.10, "mdps": 1.95},
    {"name": " Смелого",          "weight": 0.10, "mdps": 1.20},
    {"name": " Кошмаров",         "weight": 0.10, "mdps": 1.50},
    {"name": " Мечты",            "weight": 0.10, "mdps": 1.50},
    {"name": " Забытых",          "weight": 0.10, "mdps": 1.60},
    {"name": " Кунзиле",          "weight": 0.10, "mdps": 2.50},
    {"name": " Славы",            "weight": 0.10, "mdps": 1.40},
    {"name": " Позора",           "weight": 0.10, "mdps": 1.90},
    {"name": " Греха",            "weight": 0.10, "mdps": 1.80},
]
shields = [
    {"name": "Щит",               "weight": 0.9,  "bdps": 2},
    {"name": "Нагрудный щит",     "weight": 0.6,  "bdps": 2},
    {"name": "Баклер",            "weight": 0.7,  "bdps": 2},
    {"name": "Воинский щит",      "weight": 0.5,  "bdps": 2},
    {"name": "Круглый щит",       "weight": 0.7,  "bdps": 2},
    {"name": "Эгида",             "weight": 0.01, "bdps": 4,
     "flair": 'Подписан "Афине" и немного обгорел.'},
]
helmets = [
    {"name": "Шлем",              "weight": 0.9,  "bdps": 2},
    {"name": "Котелок",           "weight": 0.5,  "bdps": 2},
    {"name": "Большой шлем",      "weight": 0.6,  "bdps": 2},
    {"name": "Бацинет",           "weight": 0.5,  "bdps": 2},
    {"name": "Крестоносец",       "weight": 0.7,  "bdps": 2},
    {"name": "Шлем Ужаса",        "weight": 0.01, "bdps": 4,
     "flair": 'Поблёскивающий червь, твоё шипение было велико...'},
]
chests = [
    {"name": "Нагрудник",         "weight": 0.9,  "bdps": 2},
    {"name": "Гамбезон",          "weight": 0.6,  "bdps": 2},
    {"name": "Латный доспех",     "weight": 0.6,  "bdps": 2},
    {"name": "Кольчуга",          "weight": 0.7,  "bdps": 2},
    {"name": "Кираса",            "weight": 0.5,  "bdps": 2},
    {"name": "Броня Беовульфа",   "weight": 0.01, "bdps": 4,
     "flair": 'Если смерть придёт за мной - отошли мою броню Хигелаку.'},
]
gloves = [
    {"name": "Перчатки",          "weight": 0.8,  "bdps": 2},
    {"name": "Рукавицы",          "weight": 0.7,  "bdps": 2},
    {"name": "Наручи",            "weight": 0.6,  "bdps": 2},
    {"name": "Кастет",            "weight": 0.5,  "bdps": 2},
    {"name": "Когти",             "weight": 0.2,  "bdps": 2},
]
boots = [
    {"name": "Сапоги",            "weight": 0.9,  "bdps": 2},
    {"name": "Ботинки",           "weight": 0.7,  "bdps": 2},
]
rings = [
    {"name": "Кольцо",            "weight": 0.9,  "bdps": 2},
    {"name": "Перстень",          "weight": 0.6,  "bdps": 2},
]
amulets = [
    {"name": "Амулет",            "weight": 0.9,  "bdps": 2},
    {"name": "Медальон",          "weight": 0.6,  "bdps": 2},
]
weapons = [
    {"name": "Меч",               "weight": 0.9,  "bdps": 2},
    {"name": "Молот",             "weight": 0.5,  "bdps": 2},
    {"name": "Клеймор",           "weight": 0.5,  "bdps": 2},
    {"name": "Длинный меч",       "weight": 0.5,  "bdps": 2},
    {"name": "Двуручник",         "weight": 0.2,  "bdps": 2},
    {"name": "Палаш",             "weight": 0.5,  "bdps": 2},
    {"name": "Катана",            "weight": 0.15, "bdps": 2},
    {"name": "Сабля",             "weight": 0.4,  "bdps": 2},
    {"name": "Топор",             "weight": 0.9,  "bdps": 2},
    {"name": "Боевой топор",      "weight": 0.5,  "bdps": 2},
    {"name": "Кинжал",            "weight": 0.9,  "bdps": 2},
    {"name": "Стилет",            "weight": 0.24, "bdps": 2},
    {"name": "Копьё",             "weight": 0.9,  "bdps": 2},
    {"name": "Алебарда",          "weight": 0.24, "bdps": 2},
    {"name": "Коса",              "weight": 0.10, "bdps": 2},
    {"name": "Возмездие Закона",  "weight": 0.01, "bdps": 4,
     "flair": 'Тяжесть грехов тянет этот кинжал к земле.'},
    {"name": "Конец Судьбы",      "weight": 0.01, "bdps": 4,
     "flair": 'Ты взываешь о пощаде, но ответа нет.'},
    {"name": "Экскалибур",        "weight": 0.01, "bdps": 4,
     "flair": 'Дева озера зовёт этот клинок. Тебе стоит его вернуть.'},
    {"name": "Мурамаса",          "weight": 0.01, "bdps": 4,
     "flair": 'Держа это оружие, ты испытываешь желание испытать его остроту на друзьях.'},
]


class Slots(Enum):
    weapon = weapons
    shield = shields
    helmet = helmets
    chest  = chests
    gloves = gloves
    boots  = boots
    ring   = rings
    amulet = amulets


async def weighted_choice(items: list) -> dict:
    names   = [item["name"]   for item in items]
    weights = [item["weight"] for item in items]
    chosen  = random.choices(names, weights)[0]
    for item in items:
        if item["name"] == chosen:
            return item
    return {}


async def get_item(player: Player):
    """Генерирует случайный предмет и экипирует если он лучше текущего"""

    async def generate_item(equip_list):
        base      = await weighted_choice(equip_list)
        prefix    = await weighted_choice(prefixes)
        suffix    = await weighted_choice(suffixes)
        quality   = await weighted_choice(qualities)
        condition = await weighted_choice(conditions)
        rank = quality["rank"] + condition["rank"]
        match rank:
            case 1 | 2: rankrole = "Uncommon"
            case 3 | 4: rankrole = "Rare"
            case 5 | 6: rankrole = "Epic"
            case 7 | 8: rankrole = "Legendary"
            case 9:     rankrole = "Ascended"
            case _:     rankrole = "Common"
        dps = math.floor(
            random.randrange(base["bdps"] - 1, base["bdps"] + 1)
            * math.sqrt(
                (prefix["mdps"] + suffix["mdps"] + quality["mdps"] + condition["mdps"])
                * 1.2 + 1
            )
            * player.level
        )
        flair = base.get("flair")
        return {
            "name":      base["name"],
            "quality":   quality["name"],
            "condition": condition["name"],
            "prefix":    prefix["name"],
            "suffix":    suffix["name"],
            "dps":       dps,
            "rank":      "Unique" if flair else rankrole,
            "flair":     flair,
        }

    slot = random.choice(list(Slots))
    item = await generate_item(slot.value)
    replaced = False
    current  = getattr(player, slot.name)
    if not current or item["dps"] > current["dps"]:
        setattr(player, slot.name, item)
        await player.update(_columns=[slot.name])
        replaced = True
        # Инвалидируем кэш DPS
        from game.monsters import invalidate_dps_cache
        invalidate_dps_cache(player.uid)
    
    # Триггер для квестов редкого дропа
    if item.get("rank") in ("Rare", "Epic", "Legendary", "Ascended"):
        from game.quests import on_rare_drop
        await on_rare_drop(player, item["rank"])
    
    return item, slot.name, replaced
