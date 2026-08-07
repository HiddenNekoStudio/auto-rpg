"""
test_achievements.py — достижения:
- конфиги загружаются
- check_achievements разблокирует при достижении цели
- награда токенами выдаётся
- счётчики прогресса (rare_drops, bosses_killed) накапливаются
"""
import json
from unittest.mock import MagicMock, AsyncMock, patch

from db import Player, PlayerAchievement
from game import achievements as ach_api
from game.achievements import (
    all_achievements, get_achievement_config,
    check_achievements, on_gold_changed,
)


def _fake_player(**kw):
    p = MagicMock()
    p.uid = kw.get("uid", 1)
    p.lang = kw.get("lang", "ru")
    p.monster_kills = kw.get("monster_kills", 0)
    p.totalxp = kw.get("totalxp", 0)
    p.fight_streak = kw.get("fight_streak", 0)
    p.gold = kw.get("gold", 0)
    p.tokens = kw.get("tokens", 0)
    p.achievement_progress = kw.get("achievement_progress", "{}")
    p.update = AsyncMock()
    return p


def test_configs_load():
    confs = all_achievements()
    assert len(confs) >= 10
    assert confs["first_kill"]["type"] == "monsters_killed"
    assert get_achievement_config("kills_100")["target"] == 100


def test_check_unlocks_at_target():
    p = _fake_player(monster_kills=150)
    with patch("db.PlayerAchievement") as MockAch:
        MockAch.objects.filter.return_value.all = AsyncMock(return_value=[])
        with patch("db.PlayerAchievement.objects.create", new=AsyncMock()) as create:
            run_async(check_achievements, p, "monsters_killed")
    # first_kill, kills_100 разблокируются, kills_1000 нет
    created_ids = [c.kwargs["achievement_id"] for c in create.await_args_list]
    assert "first_kill" in created_ids
    assert "kills_100" in created_ids
    assert "kills_1000" not in created_ids


def test_check_skips_already_unlocked():
    p = _fake_player(monster_kills=150)
    existing = MagicMock()
    existing.achievement_id = "first_kill"
    with patch("db.PlayerAchievement") as MockAch:
        MockAch.objects.filter.return_value.all = AsyncMock(return_value=[existing])
        with patch("db.PlayerAchievement.objects.create", new=AsyncMock()) as create:
            run_async(check_achievements, p, "monsters_killed")
    created_ids = [c.kwargs["achievement_id"] for c in create.await_args_list]
    assert "first_kill" not in created_ids
    assert "kills_100" in created_ids


def test_rewards_tokens():
    p = _fake_player(monster_kills=5)
    with patch("db.PlayerAchievement") as MockAch:
        MockAch.objects.filter.return_value.all = AsyncMock(return_value=[])
        with patch("db.PlayerAchievement.objects.create", new=AsyncMock()):
            run_async(check_achievements, p, "monsters_killed")
    assert p.tokens == 5  # first_kill reward


def test_gold_accumulates_progress():
    p = _fake_player()
    with patch("db.Player") as MockPlayer, patch("db.PlayerAchievement") as MockAch:
        MockPlayer.objects.get_or_none = AsyncMock(return_value=p)
        MockAch.objects.filter.return_value.all = AsyncMock(return_value=[])
        MockAch.objects.create = AsyncMock()
        run_async(on_gold_changed, 1, 500)
        run_async(on_gold_changed, 1, 50000)
    progress = json.loads(p.achievement_progress)
    assert progress["gold_earned"] >= 50500


import asyncio


def run_async(fn, *args):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(fn(*args))
    finally:
        loop.close()
