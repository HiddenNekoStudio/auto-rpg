import random

RACE_BONUSES = {
    "human": {
        "name_ru": "👤 Человек",
        "name_en": "👤 Human",
        "dps_pct": 0,
        "defense_pct": 0,
        "xp_pct": 0,
        "luck_chance": 0.20,
        "gold_pct": 15,
        "hp_pct": 0,
        "crit_chance": 0.0,
        "desc_ru": "🍀 20% избежать штрафа монстра · 💰 +15% золота",
        "desc_en": "🍀 20% chance to avoid monster penalty · 💰 +15% gold",
    },
    "dwarf": {
        "name_ru": "⛏️ Гном",
        "name_en": "⛏️ Dwarf",
        "dps_pct": 0,
        "defense_pct": 20,
        "xp_pct": 0,
        "luck_chance": 0.0,
        "gold_pct": 0,
        "hp_pct": 10,
        "crit_chance": 0.0,
        "desc_ru": "🛡️ +20% защиты · ❤️ +10% макс. HP",
        "desc_en": "🛡️ +20% defense · ❤️ +10% max HP",
    },
    "elf": {
        "name_ru": "🌿 Эльф",
        "name_en": "🌿 Elf",
        "dps_pct": 0,
        "defense_pct": 0,
        "xp_pct": 10,
        "luck_chance": 0.0,
        "gold_pct": 0,
        "hp_pct": 0,
        "crit_chance": 0.10,
        "desc_ru": "🏹 +10% к опыту · 🎯 +10% шанс крита",
        "desc_en": "🏹 +10% XP · 🎯 +10% crit chance",
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


def get_race_hp_mult(race: str | None) -> float:
    pct = get_race_bonus(race, "hp_pct")
    return 1.0 + pct / 100 if pct else 1.0


def get_race_gold_mult(race: str | None) -> float:
    pct = get_race_bonus(race, "gold_pct")
    return 1.0 + pct / 100 if pct else 1.0


def get_race_crit_chance(race: str | None) -> float:
    return float(get_race_bonus(race, "crit_chance", 0.0))


def has_race_luck(race: str | None) -> bool:
    return get_race_bonus(race, "luck_chance", 0.0) > 0 and random.random() < get_race_bonus(race, "luck_chance", 0.0)


def get_race_desc(race: str | None, lang: str = "ru") -> str:
    if not race:
        return ""
    bonuses = RACE_BONUSES.get(race)
    if not bonuses:
        return ""
    return bonuses.get("desc_en" if lang == "en" else "desc_ru", "")


def _racial_skill_lines(race: str, lang: str) -> list[str]:
    import config as cfg
    lines = []
    passive_id = cfg.RACIAL_PASSIVES.get(race)
    if passive_id:
        from game.skills.passives import init_passives, PassiveRegistry
        init_passives()
        eff = PassiveRegistry.get(passive_id)
        if eff:
            label = "Пассив" if lang != "en" else "Passive"
            desc = eff.get_display_description(1, lang)
            lines.append(f"   🛡️ {label}: {eff.icon} {eff.get_name(lang)} — {desc}")
    active_id = cfg.RACIAL_ACTIVE_SKILLS.get(race)
    if active_id:
        from game.skills.base import SkillRegistry
        sk = SkillRegistry.get(active_id)
        if sk:
            label = "Актив" if lang != "en" else "Active"
            desc = sk.description_en if lang == "en" else sk.description
            cd = int(getattr(sk, "cooldown", 0) or 0)
            mp = int(getattr(sk, "mana_cost", 0) or 0)
            cd_str = f"КД {cd}с" if lang != "en" else f"CD {cd}s"
            lines.append(f"   ⚔️ {label}: {sk.get_display_name(lang)} — {desc} ({cd_str}, {mp} маны)" if lang != "en"
                         else f"   ⚔️ {label}: {sk.get_display_name(lang)} — {desc} ({cd_str}, {mp} MP)")
    return lines


def race_selector_text(lang: str = "ru") -> str:
    sep = "━" * 21
    parts = []
    for race in ("human", "dwarf", "elf"):
        bonuses = RACE_BONUSES[race]
        name = bonuses["name_en"] if lang == "en" else bonuses["name_ru"]
        desc = bonuses["desc_en"] if lang == "en" else bonuses["desc_ru"]
        block = [f"<b>{name}</b>", sep, f"   {desc}"]
        block.extend(_racial_skill_lines(race, lang))
        parts.append("\n".join(block))
    return "\n\n".join(parts)
