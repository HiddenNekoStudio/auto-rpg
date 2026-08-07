"""
test_api.py — HTTP API endpoints for monitor:
- /api/stats содержит новые счётчики (pets, dungeons, arenas, clan bosses)
- /api/arena/top формирует топ по best_wave
- /api/clan_bosses возвращает активных боссов
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp.test_utils import make_mocked_request

from api_handler import handle_stats, handle_arena_top, handle_clan_bosses, handle_raid_boss, handle_api_root


async def _result(handler, **kwargs):
    request = make_mocked_request("GET", "/", **kwargs)
    resp = await handler(request)
    return json.loads(resp.text)


def _query_mock(*results):
    """Fake ormar QuerySet: chainable filter, .all/.count/.get_or_none."""
    q = MagicMock()
    q.filter = MagicMock(return_value=q)
    if results:
        async def _count(*a, **k):
            return results[0]
        q.count = AsyncMock(side_effect=_count)
    else:
        q.count = AsyncMock(return_value=0)
    q.all = AsyncMock(return_value=[])
    q.get_or_none = AsyncMock(return_value=None)
    return q


@pytest.mark.asyncio
@patch("api_handler.ClanBoss")
@patch("api_handler.RaidBoss")
@patch("api_handler.ArenaRun")
@patch("api_handler.DungeonRun")
@patch("api_handler.PlayerPet")
@patch("api_handler.Boss")
@patch("api_handler.Player")
@patch("api_handler.database")
async def test_stats_includes_new_systems(mock_db, mock_player, mock_boss, mock_pet, mock_dg, mock_arena, mock_raid, mock_cb):
    mock_player.objects.count = AsyncMock(return_value=10)
    mock_player.objects.filter = MagicMock(return_value=_query_mock(3))
    mock_boss.objects.filter = MagicMock(return_value=_query_mock(2))
    mock_pet.objects.count = AsyncMock(return_value=5)
    mock_dg.objects.filter = MagicMock(return_value=_query_mock(6))
    mock_arena.objects.filter = MagicMock(return_value=_query_mock(4))
    mock_cb.objects.filter = MagicMock(return_value=_query_mock(1))
    mock_raid.objects.filter = MagicMock(return_value=_query_mock(None))

    agg = {
        "total_xp": 100, "total_gold": 200, "total_tokens": 30,
        "total_quests": 7, "total_monster_kills": 50, "total_deaths": 2,
        "total_online_all": 100, "total_idle_all": 20, "total_offline_all": 30,
        "current_idle_seconds": 5, "current_online_seconds": 10, "total_age": 1000,
    }
    async def _fetch_one(sql, values=None):
        if "pg_database_size" in sql:
            return {"sz": 1234}
        if "FROM users" in sql:
            return agg
        return {"cnt": 1}
    mock_db.fetch_one = AsyncMock(side_effect=_fetch_one)

    data = await _result(handle_stats)
    assert data["total_players"] == 10
    assert data["online_now"] == 3
    assert data["total_pets"] == 5
    assert data["active_dungeons"] == 6
    assert data["active_arenas"] == 4
    assert data["active_clan_bosses"] == 1
    assert data["active_raid_boss"] is None


@pytest.mark.asyncio
@patch("api_handler.database")
async def test_arena_top(mock_db):
    mock_db.fetch_all = AsyncMock(return_value=[
        {"player_uid": 1, "name": "Hero", "level": 20, "best_wave": 12},
        {"player_uid": 2, "name": "Bob", "level": 10, "best_wave": 8},
    ])
    data = await _result(handle_arena_top)
    assert len(data) == 2
    assert data[0]["best_wave"] == 12
    assert data[0]["name"] == "Hero"


@pytest.mark.asyncio
@patch("api_handler.Clan")
@patch("api_handler.ClanBoss")
async def test_clan_bosses(mock_cb, mock_clan):
    clan = MagicMock()
    clan.name = "BadClan"
    clan.tag = "BC"
    mock_clan.objects.get_or_none = AsyncMock(return_value=clan)
    boss = MagicMock()
    boss.id = 1
    boss.clan_id = 5
    boss.level = 2
    boss.name = "Dragon"
    boss.hp = 50
    boss.max_hp = 100
    boss.spawned_at = 0
    boss.despawn_at = 0
    mock_cb.objects.filter = MagicMock()
    mock_cb.objects.filter.return_value.all = AsyncMock(return_value=[boss])
    data = await _result(handle_clan_bosses)
    assert len(data) == 1
    assert data[0]["hp_pct"] == 50.0
    assert "BadClan" in data[0]["clan_name"]


@pytest.mark.asyncio
@patch("api_handler.database")
@patch("api_handler.RaidBoss")
async def test_raid_boss(mock_raid, mock_db):
    boss = MagicMock()
    boss.id = 1
    boss.level = 3
    boss.name = "Worldbreaker #3"
    boss.hp = 250
    boss.max_hp = 1000
    boss.spawned_at = 0
    boss.despawn_at = 0
    mock_raid.objects.filter = MagicMock()
    mock_raid.objects.filter.return_value.get_or_none = AsyncMock(return_value=boss)
    mock_db.fetch_all = AsyncMock(return_value=[
        {"player_uid": 1, "name": "Hero", "level": 20, "damage": 900},
    ])
    data = await _result(handle_raid_boss)
    assert data["active"] is True
    assert data["hp_pct"] == 25.0
    assert data["top_hits"][0]["name"] == "Hero"


@patch("api_handler.database")
@patch("api_handler.RaidBoss")
async def test_raid_boss_none(mock_raid, mock_db):
    mock_raid.objects.filter = MagicMock()
    mock_raid.objects.filter.return_value.get_or_none = AsyncMock(return_value=None)
    data = await _result(handle_raid_boss)
    assert data["active"] is False


def test_api_root_lists_endpoints():
    import asyncio
    data = asyncio.run(_result(handle_api_root))
    assert "/api/clan_bosses" in data["endpoints"]
    assert "/api/raid_boss" in data["endpoints"]
    assert "/api/arena/top" in data["endpoints"]
