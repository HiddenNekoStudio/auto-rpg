"""
game/monster_prefixes.py — Уровневые префиксы и именные элитные монстры.

Логика портирована из Progress Quest III (MIT):
- Префикс монстра зависит от разницы уровней монстра и игрока:
  sick/young — слабее игрока, big/special — сильнее, notional/messianic —
  далеко за пределами (≥10 уровней разницы).
- С вероятностью 1/25 монстр становится именной элиткой с уникальным именем
  вида "<Раса> <Класс>" или "<Титул> <Имя> the <Раса>".
"""

import random

# Префиксы по разнице уровней (monster_level - player_level).
# Порядок важен: первая подходящая граница выигрывает.
LEVEL_PREFIXES: list[tuple[int, int, str, str]] = [
    # (min_diff, max_diff, ru, en)
    (10, 10**6,  "Мессианский ", "Messianic "),   # сильно выше игрока
    (5, 9,       "Заоблачный ", "Notional "),      # заметно выше
    (2, 4,       "Большой ", "Big "),              # сильнее
    (1, 1,       "Особый ", "Special "),           # чуть сильнее
    (0, 0,       "", ""),                          # равный уровень — без префикса
    (-4, -1,     "Больной ", "Sick "),             # слабее
    (-10**6, -5, "Молодой ", "Young "),            # сильно слабее
]


def level_prefix(level_diff: int, lang: str = "ru") -> str:
    """Префикс по разнице уровней (пустая строка если префикс не нужен)."""
    for lo, hi, ru, en in LEVEL_PREFIXES:
        if lo <= level_diff <= hi:
            return ru if lang != "en" else en
    return ""


# --- Именные элитки ---

NAMED_ELITE_CHANCE = 1 / 25  # PQ3: 1 in 25 kills is a named monster

_NAME_PARTS_RU = ("Брок", "Нар", "Грим", "Тор", "Фен", "Драк", "Мор", "Зул", "Кар", "Гал")
_NAME_PARTS_EN = ("Brog", "nar", "Grim", "thor", "Fen", "drak", "Mor", "zul", "Kar", "gal")

_RACES_RU = ("Человек", "Гном", "Эльф", "Полуорк", "Дварф")
_RACES_EN = ("Human", "Dwarf", "Elf", "Half-Orc", "Gnome")

_CLASSES_RU = ("Воин", "Маг", "Разбойник", "Паладин", "Лучник", "Жрец")
_CLASSES_EN = ("Warrior", "Mage", "Rogue", "Paladin", "Archer", "Priest")

_TITLES_RU = ("Грозный", "Тень", "Разоритель", "Повелитель", "Вечный", "Безымянный")
_TITLES_EN = ("Dread", "Shadow", "Destroyer", "Overlord", "Eternal", "Nameless")


def generate_name(lang: str = "ru") -> str:
    """Слоговый генератор имён (PQ3 generateName): две части, «Brog»+«nar»."""
    parts = _NAME_PARTS_EN if lang == "en" else _NAME_PARTS_RU
    return random.choice(parts) + random.choice(parts).lower()


def generate_named_monster(lang: str = "ru") -> str:
    """Уникальное имя элитного монстра: «<Раса> <Класс>» или «<Титул> <Имя> the <Раса>»."""
    name = generate_name(lang)
    if random.random() < 0.5:
        race = random.choice(_RACES_EN if lang == "en" else _RACES_RU)
        klass = random.choice(_CLASSES_EN if lang == "en" else _CLASSES_RU)
        return f"{race} {klass} {name}"
    title = random.choice(_TITLES_EN if lang == "en" else _TITLES_RU)
    race = random.choice(_RACES_EN if lang == "en" else _RACES_RU)
    if lang == "en":
        return f"{title} {name} the {race}"
    return f"{title} {name}, {race}"


def is_named_elite() -> bool:
    """Шанс 1/25, что монстр — именная элитка."""
    return random.random() < NAMED_ELITE_CHANCE
