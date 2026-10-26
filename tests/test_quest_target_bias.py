"""
test_quest_target_bias.py — квесты на конкретный вид монстра: генерация, спавн и прогресс ×2.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import config as cfg
from data.quests import (
    _RANK_ORDER,
    generate_quest,
    generate_quest_text,
    monster_label,
    pick_kill_target,
)
from game.factories import MonsterFactory
from game.quests import check_quest_progress
from plugins.monsters import _create_quest_target

KNOWN_IDS = {m["id"] for m in MonsterFactory.get_config()._data}


def _quest(**kw):
    q = MagicMock()
    q.category = kw.get("category", "kill_monster")
    q.target_id = kw.get("target_id", "rat")
    q.target_count = kw.get("target_count", 10)
    q.progress = kw.get("progress", 0)
    q.status = "active"
    q.update = AsyncMock()
    return q


async def _run(quest, target_id):
    chain = MagicMock()
    chain.all = AsyncMock(return_value=[quest])
    with patch("game.quests.PlayerQuest") as pq, \
         patch("game.quests.is_expired", return_value=False), \
         patch("game.quests.send_quest_progress_notification", new=AsyncMock()), \
         patch("game.quests.complete_quest", new=AsyncMock()):
        pq.objects.filter.return_value = chain
        await check_quest_progress(MagicMock(uid=1), "monster_defeated", {"target_id": target_id})


def test_pick_kill_target_returns_known_monster():
    for _ in range(30):
        assert pick_kill_target(10) in KNOWN_IDS


def test_pick_kill_target_respects_rank_cap_for_low_levels():
    cap = next(r for lvl, r in cfg.LEVEL_RANK_CAP if 1 <= lvl)
    by_id = {m["id"]: m for m in MonsterFactory.get_config()._data}
    for _ in range(50):
        picked = by_id[pick_kill_target(1)]
        assert _RANK_ORDER.index(picked["rank"]) <= _RANK_ORDER.index(cap)


def test_generate_kill_quest_can_target_a_species():
    player = MagicMock(level=10)
    with patch("data.quests.random.random", return_value=0.0):
        quest = generate_quest(player, "kill", None, "ru")
    assert quest["target_id"] in KNOWN_IDS
    assert quest["category"] == "kill_monster"


def test_generate_kill_quest_stays_generic_otherwise():
    player = MagicMock(level=10)
    with patch("data.quests.random.random", return_value=0.99):
        quest = generate_quest(player, "kill", None, "ru")
    assert quest["target_id"] == "*"


def test_quest_text_names_the_species():
    title, _ = generate_quest_text("kill_monster", "rat", 7, None, "en")
    assert monster_label("rat", "en") in title
    generic, _ = generate_quest_text("kill_monster", "*", 7, None, "en")
    assert "monsters" in generic


def test_monster_label_falls_back_to_id():
    assert monster_label("no_such_monster", "ru") == "no_such_monster"


def test_create_quest_target_builds_matching_species():
    rat = next(m for m in MonsterFactory.get_config()._data if m["id"] == "rat")
    monster = _create_quest_target("rat", 10, [rat["type"]], "Legendary", None)
    assert monster is not None and monster._id == "rat"


def test_create_quest_target_rejects_wrong_biome():
    assert _create_quest_target("rat", 10, ["dragon"], "Legendary", None) is None


def test_create_quest_target_rejects_rank_above_cap():
    dragon = next(m for m in MonsterFactory.get_config()._data if m["rank"] != "Common")
    assert _create_quest_target(dragon["id"], 10, None, "Common", None) is None


def test_create_quest_target_unknown_species_is_none():
    assert _create_quest_target("ghost_of_tests", 10, None, "Legendary", None) is None


async def test_target_species_kill_counts_double():
    quest = _quest(target_id="rat", progress=0)
    await _run(quest, "rat")
    assert quest.progress == cfg.QUEST_TARGET_PROGRESS_MULT


async def test_generic_quest_kill_counts_once():
    quest = _quest(target_id="*", progress=0)
    await _run(quest, "rat")
    assert quest.progress == 1


async def test_other_species_does_not_progress_targeted_quest():
    quest = _quest(target_id="rat", progress=0)
    await _run(quest, "bat")
    assert quest.progress == 0
