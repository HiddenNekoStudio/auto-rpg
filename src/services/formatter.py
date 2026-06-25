"""
services/formatter.py — Форматирование текста и чисел

Чистые функции форматирования — не зависят от Telegram.
Используются в core, handlers, game модулях.
"""
import config as cfg

RARITY_EMOJI = cfg.RARITY_EMOJI


def ctime(seconds: int, lang: str = "ru") -> str:
    """Переводит секунды в читаемый формат."""
    if lang == "ru":
        intervals = [("нед.", 604800), ("дн.", 86400), ("ч.", 3600), ("мин.", 60), ("сек.", 1)]
        zero = "0 сек."
    else:
        intervals = [("w", 604800), ("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]
        zero = "0s"
    result = []
    for name, count in intervals:
        value = seconds // count
        seconds -= value * count
        if value:
            result.append(f"{value} {name}")
    return ", ".join(result) if result else zero


def format_short(n: int) -> str:
    """Сокращает число: 1500 → 1.5K, 1500000 → 1.5M"""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}G"
    elif n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def item_string(item: dict, lang: str = "ru") -> str:
    """Форматирует предмет в строку с эмодзи редкости."""
    emoji = RARITY_EMOJI.get(item.get("rank", "Common"), "⚪")
    if lang == "en":
        quality = item.get("quality_en", item["quality"])
        prefix = item.get("prefix_en", item["prefix"])
        name = item.get("name_en", item["name"])
        suffix = item.get("suffix_en", item["suffix"])
        condition = item.get("condition_en", item["condition"])
        flair = item.get("flair_en", item.get("flair"))
    else:
        quality = item["quality"]
        prefix = item["prefix"]
        name = item["name"]
        suffix = item["suffix"]
        condition = item["condition"]
        flair = item.get("flair")
    stat_parts = [f"⚔️{item['dps']}"]
    if item.get("hp_bonus"):
        stat_parts.append(f"❤️{item['hp_bonus']}" if lang == "ru" else f"+{item['hp_bonus']} HP")
    if item.get("def_bonus"):
        stat_parts.append(f"🛡️{item['def_bonus']}" if lang == "ru" else f"+{item['def_bonus']} Def")
    if item.get("mp_bonus"):
        stat_parts.append(f"💧{item['mp_bonus']}" if lang == "ru" else f"+{item['mp_bonus']} MP")
    base = f"{emoji} {prefix}{name}{suffix} {{ {'|'.join(stat_parts)} }}"
    if flair:
        base += f"\n  _{flair}_"
    return base