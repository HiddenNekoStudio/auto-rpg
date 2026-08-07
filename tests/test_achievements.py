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
    check_achievements, check_all_achievements, on_gold_changed,
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
    assert len(confs) >= 30
    assert confs["first_kill"]["type"] == "monsters_killed"
    assert get_achievement_config("kills_100")["target"] == 100
    assert get_achievement_config("kills_100")["type"] == "monsters_killed"


def test_all_rewards_one_token():
    """Каждое достижение даёт ровно 1 токен."""
    for aid, conf in all_achievements().items():
        assert conf["reward_tokens"] == 1, f"{aid} reward != 1"


def test_new_achievements_use_known_types():
    """Новые достижения используют типы, которые реально инкрементятся хуками."""
    known = {"monsters_killed", "xp_total", "win_streak", "gold_earned",
             "duel_wins", "bosses_killed", "rare_drops"}
    for aid, conf in all_achievements().items():
        assert conf.get("type") in known, f"{aid} uses unknown type {conf.get('type')}"


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


def test_check_all_unlocks_existing_progress():
    """Ретроспектива: накопленный monster_kills без события разблокирует first_kill."""
    p = _fake_player(monster_kills=1)
    with patch("db.PlayerAchievement") as MockAch:
        MockAch.objects.filter.return_value.all = AsyncMock(return_value=[])
        with patch("db.PlayerAchievement.objects.create", new=AsyncMock()) as create:
            run_async(check_all_achievements, p)
    created_ids = [c.kwargs["achievement_id"] for c in create.await_args_list]
    assert "first_kill" in created_ids


def test_check_all_skips_unrelated_types():
    p = _fake_player(monster_kills=1)
    with patch("db.PlayerAchievement") as MockAch:
        MockAch.objects.filter.return_value.all = AsyncMock(return_value=[])
        with patch("db.PlayerAchievement.objects.create", new=AsyncMock()) as create:
            run_async(check_all_achievements, p)
    created_ids = [c.kwargs["achievement_id"] for c in create.await_args_list]
    assert "xp_10k" not in created_ids  # totalxp=0
    assert "boss_1" not in created_ids   # bosses_killed=0



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
    assert p.tokens == 2  # first_kill + kills_5 по 1 токену


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


def test_gold_earned_uses_accumulated_not_balance():
    """current для gold_earned = max(накопленное, баланс), а не только баланс."""
    p = _fake_player(gold=0, achievement_progress='{"gold_earned": 100000}')
    assert ach_api._current_value(p, "gold_earned") == 100000
    p = _fake_player(gold=100000)
    assert ach_api._current_value(p, "gold_earned") == 100000
    p = _fake_player(gold=500, achievement_progress='{"gold_earned": 300}')
    assert ach_api._current_value(p, "gold_earned") == 500


import asyncio


def run_async(fn, *args):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(fn(*args))
    finally:
        loop.close()
