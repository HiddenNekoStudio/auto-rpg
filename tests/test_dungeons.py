"""
test_dungeons.py — проверка системы подземелий:
- загрузка конфигурации подземелий
- старт забега (проверки уровня/дубля)
- монстр комнаты масштабируется (босс на последнем этаже)
- бой: победа -> следующий этаж, босс-этаж -> победа подземелья
- смерть -> провал забега
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

import config as cfg
from game.dungeons import load_dungeons, get_dungeon, _room_monster


def _fake_player(**kw):
    p = MagicMock()
    p.uid = kw.get("uid", 1)
    p.level = kw.get("level", 20)
    p.lang = kw.get("lang", "ru")
    p.hp = kw.get("hp", 1000)
    p.mp = kw.get("mp", 500)
    p.gold = kw.get("gold", 100)
    p.tokens = kw.get("tokens", 0)
    p.nextxp = kw.get("nextxp", 1000)
    p.currentxp = kw.get("currentxp", 0)
    p.monster_kills = kw.get("monster_kills", 0)
    p.update = AsyncMock()
    p.sync_max_hp_mp = MagicMock()
    p.get_max_hp = MagicMock(return_value=kw.get("max_hp", 1000))
    return p


def _fake_run(**kw):
    r = MagicMock()
    r.id = kw.get("id", 1)
    r.player_uid = kw.get("player_uid", 1)
    r.dungeon_id = kw.get("dungeon_id", "crypt")
    r.floor = kw.get("floor", 1)
    r.max_floor = kw.get("max_floor", 5)
    r.status = kw.get("status", "active")
    r.data = kw.get("data", "{}")
    r.started_at = kw.get("started_at", 0)
    r.last_tick_at = kw.get("last_tick_at", 0)
    r.update = AsyncMock()
    return r


def test_load_dungeons():
    d = load_dungeons()
    assert "crypt" in d and "abyss" in d
    assert get_dungeon("crypt")["min_level"] == 5


@pytest.mark.asyncio
@patch("game.dungeons.DungeonRun")
async def test_start_run(mock_run):
    mock_run.objects.filter.return_value.get_or_none = AsyncMock(return_value=None)
    mock_run.objects.create = AsyncMock()
    from game.dungeons import start_run
    p = _fake_player(level=20)
    ok, name = await start_run(p, "crypt")
    assert ok and name == "Забытый склеп"
    created = mock_run.objects.create.await_args.kwargs
    assert created["player_uid"] == 1
    assert created["max_floor"] == 5


@pytest.mark.asyncio
@patch("game.dungeons.DungeonRun")
async def test_start_run_low_level(mock_run):
    mock_run.objects.filter.return_value.get_or_none = AsyncMock(return_value=None)
    from game.dungeons import start_run
    p = _fake_player(level=2)
    ok, name = await start_run(p, "crypt")
    assert ok is False and name == "level"


@pytest.mark.asyncio
@patch("game.dungeons.DungeonRun")
async def test_start_run_already_active(mock_run):
    mock_run.objects.filter.return_value.get_or_none = AsyncMock(return_value=_fake_run())
    from game.dungeons import start_run
    p = _fake_player(level=20)
    ok, name = await start_run(p, "crypt")
    assert ok is False and name == "already"


@patch("game.dungeons.generate_hunt_monster")
def test_room_monster_scales(mock_gen):
    def _monster(player, mode, wave_bonus=0):
        return {"name": "X", "name_en": "X", "level": 5, "max_hp": 1000, "dps": 100}
    mock_gen.side_effect = _monster
    dungeon = get_dungeon("crypt")
    p = _fake_player(level=20)
    m1 = _room_monster(p, dungeon, 1)
    m2 = _room_monster(p, dungeon, 2)
    assert m2["max_hp"] > m1["max_hp"]
    assert m2["dps"] > m1["dps"]
    boss = _room_monster(p, dungeon, dungeon["rooms"])
    assert boss["is_miniboss"]
    assert boss["max_hp"] > m2["max_hp"]


@pytest.mark.asyncio
@patch("game.dungeons.auto_resolve_hunt_battle")
@patch("game.dungeons.Player")
@patch("game.dungeons.DungeonRun")
async def test_process_tick_wins_room(mock_run, mock_player, mock_battle):
    from game.dungeons import process_dungeon_tick
    run = _fake_run(floor=1, last_tick_at=0)
    mock_run.objects.filter.return_value.get_or_none = AsyncMock(return_value=run)
    mock_battle.return_value = {"player_won": True, "hp_left": 900, "mp_left": 400}
    player = _fake_player()
    with patch("game.quests.on_monster_defeated", AsyncMock()):
        await process_dungeon_tick(None, player, run)
    assert run.floor == 2
    assert run.status == "active"
    assert run.update.await_count >= 1


@pytest.mark.asyncio
@patch("game.dungeons.auto_resolve_hunt_battle")
@patch("game.dungeons._notify", new_callable=AsyncMock)
@patch("game.dungeons.Player")
@patch("game.dungeons.DungeonRun")
async def test_process_tick_wins_boss_floor(mock_run, mock_player, mock_notify, mock_battle):
    from game.dungeons import process_dungeon_tick
    run = _fake_run(floor=5, last_tick_at=0)
    mock_run.objects.filter.return_value.get_or_none = AsyncMock(return_value=run)
    mock_battle.return_value = {"player_won": True, "hp_left": 900, "mp_left": 400}
    player = _fake_player(tokens=0)
    with patch("game.quests.on_monster_defeated", AsyncMock()):
        await process_dungeon_tick(None, player, run)
    assert run.status == "won"
    assert player.tokens == cfg.DUNGEON_TOKEN_REWARD
    mock_notify.assert_awaited_once()


@pytest.mark.asyncio
@patch("game.dungeons.auto_resolve_hunt_battle")
@patch("game.dungeons._notify", new_callable=AsyncMock)
@patch("game.dungeons.Player")
@patch("game.dungeons.DungeonRun")
async def test_process_tick_loses(mock_run, mock_player, mock_notify, mock_battle):
    from game.dungeons import process_dungeon_tick
    run = _fake_run(floor=1, last_tick_at=0)
    mock_run.objects.filter.return_value.get_or_none = AsyncMock(return_value=run)
    mock_battle.return_value = {"player_won": False, "hp_left": 0, "mp_left": 0}
    player = _fake_player()
    await process_dungeon_tick(None, player, run)
    assert run.status == "failed"
    mock_notify.assert_awaited_once()


@pytest.mark.asyncio
@patch("game.dungeons.DungeonRun")
async def test_process_tick_skips_if_soon(mock_run):
    import time
    from game.dungeons import process_dungeon_tick
    run = _fake_run(floor=1, last_tick_at=int(time.time()))
    mock_run.objects.filter.return_value.get_or_none = AsyncMock(return_value=run)
    player = _fake_player()
    await process_dungeon_tick(None, player, run)
    assert run.status == "active"
    assert run.update.await_count == 0
