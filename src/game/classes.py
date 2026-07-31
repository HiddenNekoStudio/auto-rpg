"""game/classes.py — классы персонажей с бонусами"""

CLASSES = {
    "warrior": {
        "name_ru": "Воин",
        "name_en": "Warrior",
        "icon": "⚔️",
        "desc_ru": "+10% к силе атаки",
        "desc_en": "+10% attack power",
        "bonus": {"dps_pct": 10},
    },
    "archer": {
        "name_ru": "Лучник",
        "name_en": "Archer",
        "icon": "🏹",
        "desc_ru": "+10% к шансу крита",
        "desc_en": "+10% crit chance",
        "bonus": {"crit_pct": 10},
    },
    "mage": {
        "name_ru": "Маг",
        "name_en": "Mage",
        "icon": "🔮",
        "desc_ru": "+15% к опыту",
        "desc_en": "+15% XP gain",
        "bonus": {"xp_pct": 15},
    },
    "rogue": {
        "name_ru": "Разбойник",
        "name_en": "Rogue",
        "icon": "🗡️",
        "desc_ru": "+15% к уклонению",
        "desc_en": "+15% dodge chance",
        "bonus": {"dodge_pct": 15},
    },
    "paladin": {
        "name_ru": "Паладин",
        "name_en": "Paladin",
        "icon": "🛡️",
        "desc_ru": "+15% к защите",
        "desc_en": "+15% defense",
        "bonus": {"defense_pct": 15},
    },
}


def get_class_bonus(job: str) -> dict:
    for c in CLASSES.values():
        if c["name_ru"] == job or c["name_en"] == job:
            return c["bonus"]
    return {}


def class_display(job: str, lang: str = "ru") -> str:
    for c in CLASSES.values():
        if c["name_ru"] == job or c["name_en"] == job:
            name = c["name_ru"] if lang == "ru" else c["name_en"]
            return f"{c['icon']} {name}"
    return job


def get_class_desc(job: str, lang: str = "ru") -> str:
    for c in CLASSES.values():
        if c["name_ru"] == job or c["name_en"] == job:
            return c["desc_en"] if lang == "en" else c["desc_ru"]
    return ""


def class_selector_text(lang: str = "ru") -> str:
    sep = "━" * 21
    parts = []
    for c in CLASSES.values():
        name = c["name_ru"] if lang == "ru" else c["name_en"]
        desc = c["desc_ru"] if lang == "ru" else c["desc_en"]
        parts.append(f"<b>{c['icon']} {name}</b>\n{sep}\n   {desc}")
    return "\n\n".join(parts)
