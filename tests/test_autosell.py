"""
test_autosell.py — автопродажа выброшенного лута: цена по уровню и редкости, налог.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from game.autosell import (
    AUTOSELL_GOLD_PER_LEVEL,
    AUTOSELL_RARITY_MULT,
    AUTOSELL_TAX,
    sale_value,
    sell_item,
)


def test_sale_value_applies_tax_to_level_price():
    gross = 10 * AUTOSELL_GOLD_PER_LEVEL
    assert sale_value({"rank": "Common"}, 10) == int(gross * (1 - AUTOSELL_TAX))


def test_sale_value_grows_with_rarity():
    values = [sale_value({"rank": r}, 20) for r in ("Common", "Rare", "Legendary")]
    assert values == sorted(values) and len(set(values)) == 3


def test_sale_value_ignores_item_dps():
    weak = {"rank": "Rare", "dps": 1}
    strong = {"rank": "Rare", "dps": 10**6}
    assert sale_value(weak, 15) == sale_value(strong, 15)


def test_sale_value_has_minimum_of_one_gold():
    assert sale_value({"rank": "Common"}, 0) >= 1
    assert sale_value({}, 1) >= 1


def test_unknown_rank_is_priced_as_common():
    assert sale_value({"rank": "Mythic"}, 10) == sale_value({"rank": "Common"}, 10)


def test_tax_is_a_real_fraction():
    assert 0 < AUTOSELL_TAX < 1
    assert all(m > 0 for m in AUTOSELL_RARITY_MULT.values())


async def test_sell_item_credits_gold_atomically():
    player = MagicMock()
    player.uid = 5
    player.level = 10
    player.gold = 100
    with patch("db.database.execute", new=AsyncMock()) as execute:
        gold = await sell_item(player, {"rank": "Common"})

    assert gold == sale_value({"rank": "Common"}, 10)
    sql, params = execute.await_args.args
    assert "gold = gold + :g" in sql
    assert params == {"g": gold, "uid": 5}
    assert player.gold == 100 + gold
