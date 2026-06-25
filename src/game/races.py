import random

RACE_BONUSES = {
    "human": {
        "name_ru": "👤 Человек",
        "name_en": "👤 Human",
        "dps_pct": 0,
        "defense_pct": 0,
        "xp_pct": 0,
        "luck_chance": 0.20,
    },
    "dwarf": {
        "name_ru": "⛏️ Гном",
        "name_en": "⛏️ Dwarf",
        "dps_pct": 15,
        "defense_pct": 15,
        "xp_pct": 0,
        "luck_chance": 0.0,
    },
    "elf": {
        "name_ru": "🌿 Эльф",
        "name_en": "🌿 Elf",
        "dps_pct": 0,
        "defense_pct": 0,
        "xp_pct": 10,
        "luck_chance": 0.0,
    },
}


def get_race_bonus(race: str | None, key: str, default=0) -> float | int:
    if not race:
        return default
    bonuses = RACE_BONUSES.get(race)
    if not bonuses:
        return default
    return bonuses.get(key, default)


def get_race_dps_mult(race: str | None) -> float:
    pct = get_race_bonus(race, "dps_pct")
    return 1.0 + pct / 100 if pct else 1.0


def get_race_defense_mult(race: str | None) -> float:
    pct = get_race_bonus(race, "defense_pct")
    return 1.0 + pct / 100 if pct else 1.0


def get_race_xp_mult(race: str | None) -> float:
    pct = get_race_bonus(race, "xp_pct")
    return 1.0 + pct / 100 if pct else 1.0


def has_race_luck(race: str | None) -> bool:
    return get_race_bonus(race, "luck_chance", 0.0) > 0 and random.random() < get_race_bonus(race, "luck_chance", 0.0)
