"""
services/formatter.py — Форматирование текста и чисел

Чистые функции форматирования — не зависят от Telegram.
Используются в core, handlers, game модулях.
"""
import config as cfg

RARITY_EMOJI = cfg.RARITY_EMOJI

# ── Fallback translations for legacy items stored without _en fields ──
ITEM_NAME_EN = {
    "Кулаки": "Fists", "Деревянная доска": "Wooden Board", "Железный шлем": "Iron Helm",
    "Тряпьё": "Rags", "Обмотки": "Hand Wraps", "Деревянные башмаки": "Wooden Clogs",
    "Железное кольцо": "Iron Ring", "Железный амулет": "Iron Amulet",
    "Меч": "Sword", "Молот": "Hammer", "Клеймор": "Claymore", "Длинный меч": "Longsword",
    "Двуручник": "Greatsword", "Палаш": "Broadsword", "Катана": "Katana", "Сабля": "Saber",
    "Топор": "Axe", "Боевой топор": "Battle Axe", "Кинжал": "Dagger", "Стилет": "Stiletto",
    "Копьё": "Spear", "Алебарда": "Halberd", "Коса": "Scythe",
    "Возмездие Закона": "Law's Retribution", "Конец Судьбы": "End of Fate",
    "Экскалибур": "Excalibur", "Мурамаса": "Muramasa",
    "Щит": "Shield", "Нагрудный щит": "Chest Shield", "Баклер": "Buckler",
    "Воинский щит": "War Shield", "Круглый щит": "Round Shield", "Эгида": "Aegis",
    "Шлем": "Helmet", "Котелок": "Pot Helm", "Большой шлем": "Great Helm",
    "Бацинет": "Bascinet", "Крестоносец": "Crusader", "Шлем Ужаса": "Helm of Terror",
    "Нагрудник": "Chestplate", "Гамбезон": "Gambeson", "Латный доспех": "Plate Armor",
    "Кольчуга": "Chainmail", "Кираса": "Cuirass", "Броня Беовульфа": "Beowulf's Armor",
    "Перчатки": "Gloves", "Рукавицы": "Gauntlets", "Наручи": "Bracers",
    "Кастет": "Knuckles", "Когти": "Claws",
    "Сапоги": "Boots", "Ботинки": "Shoes",
    "Кольцо": "Ring", "Перстень": "Signet Ring",
    "Амулет": "Amulet", "Медальон": "Pendant",
}
ITEM_QUALITY_EN = {
    "Базовый": "Basic", "Хлипкий": "Flimsy", "Треснутый": "Cracked",
    "Потрёпанный": "Weathered", "Ржавый": "Rusty", "Укреплённый": "Reinforced",
    "Ветеранский": "Veteran", "Позолоченный": "Gilded", "Безупречный": "Flawless",
    "Аутентичный": "Authentic", "Прославленный": "Glorious", "Вознесённый": "Ascended",
    "Галактический": "Galactic",
}
ITEM_CONDITION_EN = {
    "Жалкий": "Miserable", "Плохой": "Poor", "Потёртый": "Worn",
    "Восстановленный": "Restored", "Пыльный": "Dusty", "Чистый": "Clean",
    "Отполированный": "Polished", "Первозданный": "Pristine",
    "Выставочный": "Display", "Богоданный": "God-given",
}
ITEM_PREFIX_EN = {
    "Горящий ": "Burning ", "Пылающий ": "Flaming ", "Тлеющий ": "Smoldering ",
    "Холодный ": "Cold ", "Охлаждённый ": "Chilled ", "Ледяной ": "Icy ",
    "Ледниковый ": "Glacial ", "Острый ": "Sharp ", "Точный ": "Precise ",
    "Меткий ": "Accurate ", "Смертельный ": "Deadly ", "Роковой ": "Fatal ",
    "Прочный ": "Sturdy ", "Быстрый ": "Swift ", "Стремительный ": "Rapid ",
    "Твёрдый ": "Solid ", "Жёсткий ": "Hard ", "Сосредоточенный ": "Focused ",
    "Святой ": "Holy ", "Светокованый ": "Lightforged ",
}
ITEM_SUFFIX_EN = {
    " Медведя": " of the Bear", " Воина": " of the Warrior",
    " Безумца": " of the Madman", " Проклятых": " of the Cursed",
    " Огня": " of Fire", " Богов": " of the Gods", " Смелого": " of the Brave",
    " Кошмаров": " of Nightmares", " Мечты": " of Dreams",
    " Забытых": " of the Forgotten", " Кунзиле": " of Kunzile",
    " Славы": " of Glory", " Позора": " of Shame", " Греха": " of Sin",
}


def _en_or_fallback(item: dict, field: str, fallback_map: dict, lang: str) -> str:
    """Get EN field with runtime fallback for legacy items."""
    if lang != "en":
        return item[field]
    en_val = item.get(f"{field}_en")
    if en_val is not None:
        return en_val
    return fallback_map.get(item[field], item[field])


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
    quality = _en_or_fallback(item, "quality", ITEM_QUALITY_EN, lang)
    prefix = _en_or_fallback(item, "prefix", ITEM_PREFIX_EN, lang)
    name = _en_or_fallback(item, "name", ITEM_NAME_EN, lang)
    suffix = _en_or_fallback(item, "suffix", ITEM_SUFFIX_EN, lang)
    condition = _en_or_fallback(item, "condition", ITEM_CONDITION_EN, lang)
    if lang == "en":
        flair = item.get("flair_en", item.get("flair"))
    else:
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


def item_string_html(item: dict, lang: str = "ru") -> str:
    """Форматирует предмет в HTML строку для Telegram HTML parse_mode."""
    emoji = RARITY_EMOJI.get(item.get("rank", "Common"), "⚪")
    quality = _en_or_fallback(item, "quality", ITEM_QUALITY_EN, lang)
    prefix = _en_or_fallback(item, "prefix", ITEM_PREFIX_EN, lang)
    name = _en_or_fallback(item, "name", ITEM_NAME_EN, lang)
    suffix = _en_or_fallback(item, "suffix", ITEM_SUFFIX_EN, lang)
    condition = _en_or_fallback(item, "condition", ITEM_CONDITION_EN, lang)
    if lang == "en":
        flair = item.get("flair_en", item.get("flair"))
    else:
        flair = item.get("flair")
    stat_parts = [f"⚔️{item['dps']}"]
    if item.get("hp_bonus"):
        stat_parts.append(f"❤️{item['hp_bonus']}" if lang == "ru" else f"+{item['hp_bonus']} HP")
    if item.get("def_bonus"):
        stat_parts.append(f"🛡️{item['def_bonus']}" if lang == "ru" else f"+{item['def_bonus']} Def")
    if item.get("mp_bonus"):
        stat_parts.append(f"💧{item['mp_bonus']}" if lang == "ru" else f"+{item['mp_bonus']} MP")
    stats = " | ".join(stat_parts)
    name_escaped = f"{prefix}{name}{suffix}".replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    base = f"{emoji} <b>{name_escaped}</b> {{{stats}}}"
    if flair:
        flair_escaped = flair.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        base += f"\n  <i>{flair_escaped}</i>"
    return base