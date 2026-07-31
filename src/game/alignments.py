"""game/alignments.py — бонусы мировоззрения и селектор."""

ALIGNMENTS = {
    1: {
        "name_ru": "😇 Добрый",
        "name_en": "😇 Good",
        "desc_ru": "✨ Смайт: 2× урона · +10% к силе в дуэлях",
        "desc_en": "✨ Smite: 2× damage · +10% power in duels",
    },
    0: {
        "name_ru": "😐 Нейтральный",
        "name_en": "😐 Neutral",
        "desc_ru": "Без бонусов",
        "desc_en": "No bonuses",
    },
    2: {
        "name_ru": "😈 Злой",
        "name_en": "😈 Evil",
        "desc_ru": "🔪 Подлый удар: 21% шанс 2× урона · 🎒 Кража предмета: 15%",
        "desc_en": "🔪 Backstab: 21% chance 2× damage · 🎒 Steal item: 15%",
    },
}


def get_align_desc(align: int, lang: str = "ru") -> str:
    a = ALIGNMENTS.get(align)
    if not a:
        return ""
    return a["desc_en"] if lang == "en" else a["desc_ru"]


def alignment_selector_text(lang: str = "ru") -> str:
    sep = "━" * 21
    parts = []
    for align in (1, 0, 2):
        a = ALIGNMENTS[align]
        name = a["name_en"] if lang == "en" else a["name_ru"]
        desc = a["desc_en"] if lang == "en" else a["desc_ru"]
        parts.append(f"<b>{name}</b>\n{sep}\n   {desc}")
    return "\n\n".join(parts)
