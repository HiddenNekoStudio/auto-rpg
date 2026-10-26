"""
test_nemesis.py — досье на виды монстров (PQ3 nemesis).
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from game.nemesis import (
    DOSSIER_ENCOUNTERS,
    dossier_unlocked,
    get_dossiers,
    record_encounter,
    win_rate,
)

UID = 777001


def test_win_rate_is_zero_without_encounters():
    assert win_rate(0, 0) == 0.0


def test_win_rate_is_share_of_wins():
    assert win_rate(3, 4) == pytest.approx(0.75)


def test_win_rate_is_capped_at_one():
    assert win_rate(10, 4) == 1.0


def test_dossier_unlocks_at_threshold():
    assert not dossier_unlocked(DOSSIER_ENCOUNTERS - 1)
    assert dossier_unlocked(DOSSIER_ENCOUNTERS)


async def test_record_encounter_updates_existing_row_atomically():
    with patch("db.database.fetch_val", new=AsyncMock(return_value=1)) as fetch_val, \
         patch("db.PlayerNemesis") as model:
        model.objects.create = AsyncMock()
        await record_encounter(UID, "rat", False)

    params = fetch_val.await_args.args[1]
    assert (params["uid"], params["mid"], params["w"], params["d"]) == (UID, "rat", 0, 1)
    model.objects.create.assert_not_awaited()


async def test_record_encounter_creates_row_on_first_meeting():
    with patch("db.database.fetch_val", new=AsyncMock(return_value=None)), \
         patch("db.PlayerNemesis") as model:
        model.objects.create = AsyncMock()
        await record_encounter(UID, "rat", True)

    kwargs = model.objects.create.await_args.kwargs
    assert (kwargs["encounters"], kwargs["wins"], kwargs["deaths"]) == (1, 1, 0)
    assert kwargs["player_uid"] == UID and kwargs["monster_id"] == "rat"


async def test_record_encounter_ignores_empty_monster_id():
    with patch("db.database.fetch_val", new=AsyncMock()) as fetch_val:
        await record_encounter(UID, "", True)

    fetch_val.assert_not_awaited()


async def test_get_dossiers_filters_by_threshold():
    chain = MagicMock()
    chain.order_by.return_value.limit.return_value.all = AsyncMock(return_value=["row"])
    with patch("db.PlayerNemesis") as model:
        model.objects.filter.return_value = chain
        rows = await get_dossiers(UID)

    assert rows == ["row"]
    assert model.objects.filter.call_args.kwargs["encounters__gte"] == DOSSIER_ENCOUNTERS
