"""
test_hunting_loadout_speed.py — скорость охоты от качества экипировки (PQ3).
Интервал сокращается асимптотически, не быстрее пола и без стака с VIP-бустом.
"""
from unittest.mock import MagicMock, patch

import config as cfg
from game.hunting import hunting_interval, loadout_speed_factor


def _player(dps: int = 0, defense: int = 0):
    p = MagicMock()
    sums = {"dps": dps, "def_bonus": defense}
    p._get_equip_sum.side_effect = lambda key: sums.get(key, 0)
    return p


def test_zero_quality_keeps_base_interval():
    assert loadout_speed_factor(0) == 1.0


def test_factor_decreases_as_quality_grows():
    assert loadout_speed_factor(1000) < loadout_speed_factor(100) < 1.0


def test_factor_never_drops_below_floor():
    assert loadout_speed_factor(10**9) == cfg.HUNTING_LOADOUT_SPEED_FLOOR


def test_negative_quality_is_treated_as_zero():
    assert loadout_speed_factor(-500) == 1.0


def test_interval_scales_base_by_equipment():
    player = _player(dps=4000)
    with patch("plugins.vip_shop.has_active_speed_boost", return_value=False):
        interval = hunting_interval(player, "strong")
    expected = cfg.HUNTING_INTERVAL["strong"] * loadout_speed_factor(4000)
    assert interval == expected


def test_vip_speed_boost_does_not_stack_with_loadout():
    player = _player(dps=10**6)
    with patch("plugins.vip_shop.has_active_speed_boost", return_value=True):
        assert hunting_interval(player, "weak") == cfg.HUNTING_INTERVAL["weak"]


def test_unknown_mode_falls_back_to_default_interval():
    player = _player()
    with patch("plugins.vip_shop.has_active_speed_boost", return_value=False):
        assert hunting_interval(player, "nope") == 240
