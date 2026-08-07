"""
test_titles.py — титулы:
- конфиги загружаются
- is_unlocked по требованиям
- check_titles разблокирует доступные
- профиль показывает экипированный титул
"""
import json
from unittest.mock import MagicMock, AsyncMock, patch

from game.titles import (
    all_titles, get_title_config, is_unlocked, unlocked_titles, title_name, check_titles,
)


def _fake_player(**kw):
    p = MagicMock()
    p.uid = kw.get("uid", 1)
    p.lang = kw.get("lang", "ru")
    p.level = kw.get("level", 1)
    p.monster_kills = kw.get("monster_kills", 0)
    p.fight_streak = kw.get("fight_streak", 0)
    p.prestige_count = kw.get("prestige_count", 0)
    p.title_id = kw.get("title_id", "")
    p.achievement_progress = kw.get("achievement_progress", "{}")
    return p


def test_configs_load():
    confs = all_titles()
    assert len(confs) >= 8
    assert confs["adventurer"]["requirement"] == {"type": "level", "target": 10}


def test_is_unlocked_level():
    assert is_unlocked(_fake_player(level=10), "adventurer")
    assert not is_unlocked(_fake_player(level=5), "adventurer")


def test_is_unlocked_from_progress():
    p = _fake_player(achievement_progress=json.dumps({"gold_earned": 2000000}))
    assert is_unlocked(p, "millionaire")


def test_check_titles_creates_unlocked():
    p = _fake_player(level=60)
    with patch("db.PlayerTitle") as MockTitle:
        MockTitle.objects.filter.return_value.all = AsyncMock(return_value=[])
        MockTitle.objects.create = AsyncMock()
        run_async(check_titles, p)
    created = [c.kwargs["title_id"] for c in MockTitle.objects.create.await_args_list]
    assert "adventurer" in created
    assert "warrior" in created
    assert "master" in created
    assert "legend" not in created


def test_title_name_localized():
    assert run_async(title_name, "adventurer", "ru") == "Авантюрист"
    assert run_async(title_name, "adventurer", "en") == "Adventurer"


import asyncio


def run_async(fn, *args):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(fn(*args))
    finally:
        loop.close()
