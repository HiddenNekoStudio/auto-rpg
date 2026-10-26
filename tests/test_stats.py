"""
test_stats.py — основные характеристики STR/CON/DEX/INT/WIS/CHA (PQ3 prime stats).
"""
import random
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from game.stats import (
    BASE_STAT,
    PRIME_STATS,
    RESPEC_TOKEN_COST,
    STAT_BONUS_CAP,
    default_stats,
    dps_mult,
    grant_level_point,
    hp_mult,
    mp_mult,
    pick_stat,
    read_stats,
    respec,
    stat_bonus,
)


def _player(level=1, tokens=0, **stats):
    p = MagicMock(spec=[])
    p.uid = 99
    p.level = level
    p.tokens = tokens
    for s in PRIME_STATS:
        setattr(p, f"stat_{s}", stats.get(s, BASE_STAT))
    return p


def test_stat_bonus_is_zero_at_base_and_below():
    assert stat_bonus(BASE_STAT) == 0
    assert stat_bonus(0) == 0


def test_stat_bonus_grows_per_point_and_is_capped():
    assert stat_bonus(BASE_STAT + 10) == pytest.approx(0.03)
    assert stat_bonus(10_000) == STAT_BONUS_CAP


def test_multipliers_map_stats_to_dps_hp_mp():
    p = _player(str=BASE_STAT + 10, con=BASE_STAT + 20, int=BASE_STAT + 30)
    assert dps_mult(p) == pytest.approx(1.03)
    assert hp_mult(p) == pytest.approx(1.06)
    assert mp_mult(p) == pytest.approx(1.09)


def test_read_stats_defaults_missing_columns_to_base():
    p = MagicMock(spec=[])
    assert read_stats(p) == {s: BASE_STAT for s in PRIME_STATS}


def test_default_stats_spread_levels_evenly():
    assert default_stats(1) == {s: BASE_STAT for s in PRIME_STATS}
    assert default_stats(13) == {s: BASE_STAT + 2 for s in PRIME_STATS}


def test_default_stats_never_exceeds_points_earned():
    for level in range(1, 200):
        gained = sum(v - BASE_STAT for v in default_stats(level).values())
        assert gained <= level - 1


def test_pick_stat_weights_by_square():
    stats = {s: 1 for s in PRIME_STATS}
    stats["str"] = 100
    rng = random.Random(0)
    picks = [pick_stat(stats, rng) for _ in range(200)]
    assert picks.count("str") > 190


def test_pick_stat_returns_known_stat():
    rng = random.Random(3)
    for _ in range(50):
        assert pick_stat({}, rng) in PRIME_STATS


async def test_grant_level_point_increments_chosen_column():
    p = _player()
    with patch("db.database.execute", new=AsyncMock()) as execute, \
         patch("game.stats.pick_stat", return_value="dex"):
        stat = await grant_level_point(p)

    assert stat == "dex"
    assert "stat_dex = stat_dex + 1" in execute.await_args.args[0]
    assert p.stat_dex == BASE_STAT + 1


async def test_respec_charges_tokens_and_resets_to_default_layout():
    p = _player(level=13, tokens=RESPEC_TOKEN_COST + 2, str=40)
    with patch("db.database.fetch_val", new=AsyncMock(return_value=1)) as fetch_val:
        assert await respec(p) is True

    params = fetch_val.await_args.args[1]
    assert params["cost"] == RESPEC_TOKEN_COST
    assert p.tokens == 2
    assert p.stat_str == BASE_STAT + 2


async def test_respec_refused_when_not_enough_tokens():
    p = _player(level=13, tokens=0, str=40)
    with patch("db.database.fetch_val", new=AsyncMock(return_value=None)):
        assert await respec(p) is False

    assert p.tokens == 0
    assert p.stat_str == 40
