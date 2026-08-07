"""
test_arena.py — проверка арены волн:
- старт забега (проверки уровня/дубля)
- монстр волны масштабируется (босс каждые N волн)
- бой: победа -> следующая волна + награды
- смерть -> провал забега + рекорд
"""
import time

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

import config as cfg
from game.arena import _wave_monster


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
    r.wave = kw.get("wave", 1)
    r.best_wave = kw.get("best_wave", 0)
    r.status = kw.get("status", "active")
    r.data = kw.get("data", "{}")
    r.started_at = kw.get("started_at", 0)
    r.last_tick_at = kw.get("last_tick_at", 0)
    r.update = AsyncMock()
    return r


@pytest.mark.asyncio
@patch("game.arena.ArenaRun")
async def test_start_run(mock_run):
    mock_run.objects.filter.return_value.get_or_none = AsyncMock(return_value=None)
    mock_run.objects.filter.return_value.order_by.return_value.limit.return_value.get_or_none = AsyncMock(return_value=None)
    mock_run.objects.create = AsyncMock()
    from game.arena import start_run
    p = _fake_player(level=20)
    ok, reason = await start_run(p)
    assert ok
    created = mock_run.objects.create.await_args.kwargs
    assert created["player_uid"] == 1
    assert created["wave"] == 1


@pytest.mark.asyncio
@patch("game.arena.ArenaRun")
async def test_start_run_low_level(mock_run):
    mock_run.objects.filter.return_value.get_or_none = AsyncMock(return_value=None)
    from game.arena import start_run
    p = _fake_player(level=2)
    ok, reason = await start_run(p)
    assert ok is False and reason == "level"


@pytest.mark.asyncio
@patch("game.arena.ArenaRun")
async def test_start_run_already_active(mock_run):
    mock_run.objects.filter.return_value.get_or_none = AsyncMock(return_value=_fake_run())
    from game.arena import start_run
    p = _fake_player(level=20)
    ok, reason = await start_run(p)
    assert ok is False and reason == "already"


@patch("game.arena.generate_hunt_monster")
def test_wave_monster_scales(mock_gen):
    def _monster(player, mode, wave_bonus=0):
        return {"name": "X", "name_en": "X", "level": 5, "max_hp": 1000, "dps": 100}
    mock_gen.side_effect = _monster
    p = _fake_player(level=20)
    m1 = _wave_monster(p, 1)
    m2 = _wave_monster(p, 2)
    assert m2["max_hp"] > m1["max_hp"]
    assert m2["dps"] > m1["dps"]
    boss = _wave_monster(p, cfg.ARENA_BOSS_EVERY)
    assert boss["is_arena_boss"]
    assert boss["max_hp"] > m2["max_hp"]


@pytest.mark.asyncio
@patch("game.arena.auto_resolve_hunt_battle")
@patch("game.arena.Player")
@patch("game.arena.ArenaRun")
async def test_process_tick_wins_wave(mock_run, mock_player, mock_battle):
    from game.arena import process_arena_tick
    run = _fake_run(wave=1, last_tick_at=0)
    mock_battle.return_value = {"player_won": True, "hp_left": 900, "mp_left": 400}
    player = _fake_player()
    with patch("game.quests.on_monster_defeated", AsyncMock()):
        await process_arena_tick(None, player, run)
    assert run.wave == 2
    assert run.status == "active"
    assert run.best_wave == 1
    assert player.tokens == cfg.ARENA_TOKEN_PER_WAVE
    assert run.update.await_count >= 1


@pytest.mark.asyncio
@patch("game.arena.auto_resolve_hunt_battle")
@patch("game.arena._notify", new_callable=AsyncMock)
@patch("game.arena.Player")
@patch("game.arena.ArenaRun")
async def test_process_tick_loses(mock_run, mock_player, mock_notify, mock_battle):
    from game.arena import process_arena_tick
    run = _fake_run(wave=3, last_tick_at=0)
    mock_battle.return_value = {"player_won": False, "hp_left": 0, "mp_left": 0}
    player = _fake_player()
    await process_arena_tick(None, player, run)
    assert run.status == "failed"
    assert run.best_wave == 2
    mock_notify.assert_awaited_once()


@pytest.mark.asyncio
@patch("game.arena.ArenaRun")
async def test_process_tick_skips_if_soon(mock_run):
    from game.arena import process_arena_tick
    run = _fake_run(wave=1, last_tick_at=int(time.time()))
    mock_run.objects.filter.return_value.get_or_none = AsyncMock(return_value=run)
    player = _fake_player()
    await process_arena_tick(None, player, run)
    assert run.update.await_count == 0
