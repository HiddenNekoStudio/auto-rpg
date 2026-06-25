"""
core/__init__.py — Core package

Чистая бизнес-логика без зависимостей от Telegram/БД.
"""
from .loot import (
    CONDITIONS,
    QUALITIES,
    PREFIXES,
    SUFFIXES,
    WEAPONS,
    SHIELDS,
    HELMETS,
    CHESTS,
    GLOVES,
    BOOTS,
    RINGS,
    AMULETS,
    SLOTS_DATA,
    generate_item_data,
    is_item_better,
    get_random_slot,
    is_rare_drop,
)

__all__ = [
    "CONDITIONS",
    "QUALITIES",
    "PREFIXES",
    "SUFFIXES",
    "WEAPONS",
    "SHIELDS",
    "HELMETS",
    "CHESTS",
    "GLOVES",
    "BOOTS",
    "RINGS",
    "AMULETS",
    "SLOTS_DATA",
    "generate_item_data",
    "is_item_better",
    "get_random_slot",
    "is_rare_drop",
]