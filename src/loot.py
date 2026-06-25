"""
loot.py - генератор предметов

Теперь использует core/loot.py для чистой логики.
Оставлен для обратной совместимости.
"""

# Алиасы из core/loot для обратной совместимости
from core.loot import (
    CONDITIONS as conditions,
    QUALITIES as qualities,
    PREFIXES as prefixes,
    SUFFIXES as suffixes,
    WEAPONS as weapons,
    SHIELDS as shields,
    HELMETS as helmets,
    CHESTS as chests,
    GLOVES as gloves,
    BOOTS as boots,
    RINGS as rings,
    AMULETS as amulets,
    SLOTS_DATA,
    generate_item_data as _generate_item_data,
    is_item_better,
    get_random_slot,
    is_rare_drop,
)

from db import Player

async def get_item(player: Player) -> tuple[dict, str, bool]:
    """
    Генерирует случайный предмет и экипирует если он лучше текущего.

    Returns:
        tuple[dict, str, bool]: (item_data, slot_name, was_replaced)
    """
    slot_name = get_random_slot()
    item = _generate_item_data(slot_name, player.level)
    
    replaced = False
    current = getattr(player, slot_name)
    if is_item_better(item, current):
        setattr(player, slot_name, item)
        player.sync_max_hp_mp()
        await player.update(_columns=[slot_name, "max_hp", "max_mp"])
        replaced = True
        from plugins.monsters import invalidate_dps_cache as plugin_invalidate
        from game.monsters import invalidate_dps_cache as core_invalidate
        plugin_invalidate(player.uid)
        core_invalidate(player.uid)
    
    if is_rare_drop(item):
        from game.quests import on_rare_drop
        await on_rare_drop(player, item["rank"])
    
    return item, slot_name, replaced