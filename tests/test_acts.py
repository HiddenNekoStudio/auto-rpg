"""
test_acts.py — акты по уровню (PQ3 acts): чистая логика и запись через CAS.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from game.acts import (
    ACTS,
    act_for_level,
    act_name,
    check_act_progress,
    claim_new_acts,
    unlocked_acts,
)
from game.progress_blob import load_progress, mutate_progress


def test_acts_are_sorted_by_level_with_unique_numbers():
    levels = [a.min_level for a in ACTS]
    assert levels == sorted(levels)
    assert len({a.number for a in ACTS}) == len(ACTS)


def test_first_act_is_available_from_level_one():
    assert ACTS[0].min_level == 1
    assert act_for_level(1).number == 1


@pytest.mark.parametrize("level,number", [(9, 1), (10, 2), (24, 2), (25, 3), (500, ACTS[-1].number)])
def test_act_for_level_picks_last_reached_threshold(level, number):
    assert act_for_level(level).number == number


def test_unlocked_acts_grow_with_level():
    assert [a.number for a in unlocked_acts(10)] == [1, 2]


def test_act_name_follows_language():
    assert act_name(ACTS[0], "en") == "Prologue"
    assert act_name(ACTS[0], "ru") == "Пролог"


def test_claim_new_acts_returns_only_unclaimed_and_keeps_input():
    original = {"acts_claimed": [1]}
    updated, fresh = claim_new_acts(original, 25)
    assert [a.number for a in fresh] == [2, 3]
    assert updated["acts_claimed"] == [1, 2, 3]
    assert original == {"acts_claimed": [1]}


def test_claim_new_acts_is_idempotent():
    progress, _ = claim_new_acts({}, 25)
    again, fresh = claim_new_acts(progress, 25)
    assert fresh == []
    assert again == progress


def test_load_progress_tolerates_bad_input():
    assert load_progress("not-json") == {}
    assert load_progress(None) == {}
    assert load_progress('{"a": 1}') == {"a": 1}


def _player(level, raw="{}"):
    p = MagicMock()
    p.uid = 42
    p.level = level
    p.tokens = 0
    p.achievement_progress = raw
    return p


async def test_check_act_progress_pays_tokens_once():
    player = _player(25)
    with patch("db.database.fetch_val", new=AsyncMock(return_value=1)), \
         patch("db.database.execute", new=AsyncMock()) as execute:
        fresh = await check_act_progress(player)

    assert [a.number for a in fresh] == [1, 2, 3]
    assert execute.await_args.args[1]["t"] == sum(a.tokens for a in fresh)
    assert player.tokens == sum(a.tokens for a in fresh)


async def test_check_act_progress_skips_payout_when_nothing_new():
    player = _player(1, '{"acts_claimed": [1]}')
    with patch("db.database.fetch_val", new=AsyncMock(return_value=1)), \
         patch("db.database.execute", new=AsyncMock()) as execute:
        fresh = await check_act_progress(player)

    assert fresh == []
    execute.assert_not_awaited()


async def test_mutate_progress_retries_then_gives_up():
    player = _player(1)
    with patch("db.database.fetch_val", new=AsyncMock(return_value=None)):
        result = await mutate_progress(player, lambda p: (p, "ok"))
    assert result is None
