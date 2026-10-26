"""
game/autosell.py — Автопродажа выброшенного лута (PQ3 auto-sell).

Предмет, который слабее надетого, не пропадает, а продаётся за золото.
Контроль инфляции: цена привязана к уровню и редкости (не к DPS), берётся
налог рынка, а продаются только предметы, не попавшие в слот.
"""
import math

# Базовая цена за уровень предмета и множители редкости
AUTOSELL_GOLD_PER_LEVEL = 3
AUTOSELL_RARITY_MULT = {
    "Common": 1.0,
    "Uncommon": 1.5,
    "Rare": 2.5,
    "Epic": 4.0,
    "Legendary": 7.0,
    "Ascended": 10.0,
    "Unique": 10.0,
}

# Налог рынка: доля цены, которую забирает торговец
AUTOSELL_TAX = 0.30


def sale_value(item: dict, player_level: int) -> int:
    """Золото за продажу предмета после налога (минимум 1)."""
    rarity = AUTOSELL_RARITY_MULT.get(item.get("rank", "Common"), 1.0)
    gross = max(1, player_level) * AUTOSELL_GOLD_PER_LEVEL * rarity
    return max(1, math.floor(gross * (1 - AUTOSELL_TAX)))


async def sell_item(player, item: dict) -> int:
    """Начислить золото за предмет атомарным UPDATE. Возвращает сумму."""
    from db import database

    gold = sale_value(item, player.level)
    await database.execute(
        "UPDATE users SET gold = gold + :g WHERE uid = :uid",
        {"g": gold, "uid": player.uid},
    )
    player.gold = (player.gold or 0) + gold
    return gold
