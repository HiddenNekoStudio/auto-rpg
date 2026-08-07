"""
test_duel_fix.py — проверка фикса наград за дуэль (B4/B9).
Победитель получает золото, win_duel — только победителю.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


def _make_player(uid, align=0):
    p = MagicMock()
    p.uid = uid
    p.level = 10
    p.lang = "ru"
    p.name = f"P{uid}"
    p.align = align
    p.race = "human"
    p.job = "warrior"
    p.nextxp = 1000
    p.currentxp = 0
    p.gold = 0
    p.wins = 0
    p.loss = 0
    p.totalxplost = 0
    p.update = AsyncMock()
    for slot in ("weapon", "shield", "helmet", "chest", "gloves", "boots", "ring", "amulet"):
        setattr(p, slot, {"dps": 0})
    return p


@pytest.mark.asyncio
@patch("game.challenge.ctime")
@patch("game.quests.on_duel_win", new_callable=AsyncMock)
@patch("plugins.vip_shop.has_prestige_xp_bonus")
@patch("plugins.vip_shop.has_prestige_gold_bonus")
@patch("plugins.monsters.MonsterEncountersPlugin._add_active_skill_xp", new_callable=AsyncMock)
@patch("plugins.monsters.invalidate_dps_cache")
@patch("game.skills.passives.registry.PassiveSkillRegistry")
@patch("game.challenge.get_total_dps")
@patch("game.challenge.random.randint", side_effect=[10, 5, 5])
@patch("game.challenge.random.random", return_value=0.99)
async def test_duel_winner_gets_gold_and_quest(
    mock_random, mock_randint, mock_dps, mock_registry,
    mock_invalidate, mock_add_skill, mock_prestige_gold, mock_prestige_xp,
    mock_quest_progress, mock_ctime,
):
    from game.challenge import challenge_opp

    mock_ctime.side_effect = lambda v, l: str(v)
    mock_prestige_xp.return_value = False
    mock_prestige_gold.return_value = False
    mock_registry.trigger_on_encounter = AsyncMock(return_value=(False, False, MagicMock(damage_bonus=0)))
    mock_registry.trigger_on_damage_dealt = AsyncMock(return_value=MagicMock(
        is_crit=False, damage_bonus=0, healing=0, poison_damage=0, message=""
    ))
    mock_registry.trigger_on_damage_taken = AsyncMock(return_value=(0, MagicMock(damage_reflect=0, message="")))
    mock_registry.trigger_on_kill = AsyncMock(return_value=(5, 0, MagicMock(triggered=False, message="")))

    player = _make_player(1, align=1)
    opp = _make_player(2, align=0)
    mock_dps.side_effect = lambda p: 100 if p is player else 50

    msg_p, msg_o = await challenge_opp(player, opp)

    nextval = int(5 / 90 * (1000 - 0))
    real_gold = max(1, int(nextval * 0.5))
    assert player.gold == real_gold + 5
    assert opp.gold == 0
    assert player.wins == 1
    assert opp.loss == 1
    assert opp.nextxp == 1000 + nextval
    assert opp.totalxplost == nextval
    assert mock_quest_progress.await_count == 1
    assert mock_quest_progress.await_args.args[0] is player
    assert "Gold" in msg_p
