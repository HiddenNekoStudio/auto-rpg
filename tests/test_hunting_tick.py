"""
Регрессионные тесты тика охоты (src/game/hunting.py).

Покрывают исправление инвертированной ветки try/else в process_hunting_tick:
до фикса победа (player_won=True) + успешный on_monster_defeated попадала
в `else` у try — игрок помечался died, получал штраф смерти и охота
досрочно завершалась. Поражение (player_won=False) наоборот пропускало
весь блок и не штрафовалось вообще.

Работают без ormar: игрок — MagicMock (venv несовместим с ormar-записью),
процедурная часть тика проверяется на мутациях data/флагов.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import config as cfg
from game import hunting


def make_hunter(mode="epic", uid=9001):
    """MagicMock-игрок на охоте. last_hunt_tick=0 форсирует бой в этом тике."""
    p = MagicMock()
    p.uid = uid
    p.name = f"Hunter{uid}"
    p.level = 12
    p.job = "warrior"
    p.race = "human"
    p.lang = "ru"
    p.align = 0
    p.nextxp = 1200
    p.currentxp = 200
    p.gold = 10000
    p.hp = 400
    p.max_hp = 400
    p.mp = 200
    p.max_mp = 200
    p.defense = 10
    p.fight_streak = 0
    p.monster_kills = 0
    p.monster_deaths = 0
    p.hunting_expires_at = int(time.time()) + 3600
    p.hunting_data = json.dumps({
        "mode": mode,
        "duration": 3600,
        "kills": 1,
        "escapes": 0,
        "monsters": {},
        "total_xp": 50,
        "total_gold": 100,
        "loot_items": [],
        "died": False,
        "last_hunt_tick": 0,
    }, ensure_ascii=False)
    p.update = AsyncMock()
    p.get_max_hp = MagicMock(return_value=400)
    p.get_max_mp = MagicMock(return_value=200)
    p.get_dps = MagicMock(return_value=300)
    p.sync_max_hp_mp = MagicMock()
    return p


def saved_data(player):
    """data, записанная последним _save (hunting_data — JSON-строка)."""
    return json.loads(player.hunting_data)


def battle_result(won: bool):
    return {
        "player_won": won,
        "hp_left": 200 if won else 0,
        "mp_left": 120 if won else 0,
        "rounds": 3,
        "monster_hp_left": 0 if won else 999,
        "skills_used": [],
    }


@pytest.mark.asyncio
async def test_victory_does_not_trigger_death():
    """Победа + успешный квест-хук НЕ помечает died и не завершает охоту."""
    player = make_hunter(mode="epic", uid=9111)

    with (
        patch.object(hunting, "auto_resolve_hunt_battle", new_callable=AsyncMock) as battle,
        patch.object(hunting, "apply_death_penalty", new_callable=AsyncMock) as penalty,
        patch.object(hunting, "finish_hunt", new_callable=AsyncMock) as finish,
        patch.object(hunting, "_roll_hunt_loot", new_callable=AsyncMock) as loot,
        patch("game.quests.on_monster_defeated", new_callable=AsyncMock) as quest_hook,
    ):
        battle.return_value = battle_result(won=True)
        penalty.return_value = {"gold_lost": 0, "item_slot": None, "update_cols": []}
        loot.return_value = None
        quest_hook.return_value = None

        await hunting.process_hunting_tick(MagicMock(), player)

    # успешный квест-хук — именно он раньше открывал ветку else (смерть)
    quest_hook.assert_awaited_once()
    data = saved_data(player)
    assert data["died"] is False, "победа не должна помечать died=True"
    assert data["kills"] == 2, "победа должна инкрементить kills"
    penalty.assert_not_called()
    finish.assert_not_called()


@pytest.mark.asyncio
async def test_victory_survives_quest_hook_failure():
    """Падение on_monster_defeated не превращает победу в смерть."""
    player = make_hunter(mode="epic", uid=9112)

    async def boom(*_a, **_kw):
        raise RuntimeError("quest boom")

    with (
        patch.object(hunting, "auto_resolve_hunt_battle", new_callable=AsyncMock) as battle,
        patch.object(hunting, "apply_death_penalty", new_callable=AsyncMock) as penalty,
        patch.object(hunting, "finish_hunt", new_callable=AsyncMock) as finish,
        patch.object(hunting, "_roll_hunt_loot", new_callable=AsyncMock) as loot,
        patch("game.quests.on_monster_defeated", side_effect=boom) as quest_hook,
    ):
        battle.return_value = battle_result(won=True)
        penalty.return_value = {"gold_lost": 0, "item_slot": None, "update_cols": []}
        loot.return_value = None

        await hunting.process_hunting_tick(MagicMock(), player)

    data = saved_data(player)
    assert data["died"] is False
    assert data["kills"] == 2
    penalty.assert_not_called()
    finish.assert_not_called()


@pytest.mark.asyncio
async def test_defeat_in_epic_applies_penalty_and_finishes():
    """Поражение в epic: died=True, штраф применён, охота завершена."""
    player = make_hunter(mode="epic", uid=9113)

    with (
        patch.object(hunting, "auto_resolve_hunt_battle", new_callable=AsyncMock) as battle,
        patch.object(hunting, "apply_death_penalty", new_callable=AsyncMock) as penalty,
        patch.object(hunting, "finish_hunt", new_callable=AsyncMock) as finish,
    ):
        battle.return_value = battle_result(won=False)
        penalty.return_value = {"gold_lost": 123, "item_slot": None, "update_cols": []}

        await hunting.process_hunting_tick(MagicMock(), player)

    data = saved_data(player)
    assert data["died"] is True
    assert data["kills"] == 1, "поражение не должно давать kills"
    penalty.assert_called_once()
    finish.assert_called_once()


@pytest.mark.asyncio
async def test_defeat_in_weak_is_escape_without_penalty():
    """Поражение в weak — отступление: escapes++, без died/штрафа/финала."""
    player = make_hunter(mode="weak", uid=9114)

    with (
        patch.object(hunting, "auto_resolve_hunt_battle", new_callable=AsyncMock) as battle,
        patch.object(hunting, "apply_death_penalty", new_callable=AsyncMock) as penalty,
        patch.object(hunting, "finish_hunt", new_callable=AsyncMock) as finish,
    ):
        battle.return_value = battle_result(won=False)

        await hunting.process_hunting_tick(MagicMock(), player)

    data = saved_data(player)
    assert data["died"] is False
    assert data["escapes"] == 1
    penalty.assert_not_called()
    finish.assert_not_called()
