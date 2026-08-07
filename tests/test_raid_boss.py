"""
test_raid_boss.py — мировой рейд-босс:
- спавн при отсутствии активного
- уровень растёт от прошлого босса
- авто-вклад урона по кулдауну
- победа и награды вкладчикам
"""
import time
from unittest.mock import MagicMock, AsyncMock, patch

from game import raid_boss as rb


def _fake_boss(**kw):
    b = MagicMock()
    b.id = kw.get("id", 1)
    b.level = kw.get("level", 1)
    b.name = kw.get("name", "Разрушитель Миров #1")
    b.hp = kw.get("hp", 1000)
    b.max_hp = kw.get("max_hp", 1000)
    b.spawned_at = kw.get("spawned_at", 0)
    b.despawn_at = kw.get("despawn_at", int(time.time()) + 3600)
    b.status = kw.get("status", "active")
    b.update = AsyncMock()
    return b


def _fake_player(**kw):
    p = MagicMock()
    p.uid = kw.get("uid", 1)
    p.online = kw.get("online", True)
    p.tokens = kw.get("tokens", 0)
    p.gold = kw.get("gold", 0)
    p.lang = kw.get("lang", "ru")
    p.get_dps = MagicMock(return_value=kw.get("dps", 100))
    p.update = AsyncMock()
    return p


def _fake_hit(**kw):
    h = MagicMock()
    h.raid_boss_id = kw.get("raid_boss_id", 1)
    h.player_uid = kw.get("player_uid", 1)
    h.damage = kw.get("damage", 0)
    h.last_hit_at = kw.get("last_hit_at", 0)
    h.update = AsyncMock()
    return h


def test_spawn_creates_boss():
    with patch("game.raid_boss.RaidBoss") as MockRaid:
        MockRaid.objects.filter.return_value.get_or_none = AsyncMock(return_value=None)
        MockRaid.objects.order_by.return_value.get_or_none = AsyncMock(return_value=None)
        MockRaid.objects.create = AsyncMock(return_value=_fake_boss())
        boss = run_async(rb.spawn)
    assert boss is not None
    assert boss.level == 1


def test_spawn_skips_if_active():
    boss = _fake_boss()
    with patch("game.raid_boss.RaidBoss") as MockRaid:
        MockRaid.objects.filter.return_value.get_or_none = AsyncMock(return_value=boss)
        MockRaid.objects.create = AsyncMock()
        result = run_async(rb.spawn)
    assert result is None
    MockRaid.objects.create.assert_not_awaited()


def test_spawn_increments_level():
    prev = _fake_boss(level=7)
    with patch("game.raid_boss.RaidBoss") as MockRaid:
        MockRaid.objects.filter.return_value.get_or_none = AsyncMock(return_value=None)
        MockRaid.objects.order_by.return_value.get_or_none = AsyncMock(return_value=prev)
        MockRaid.objects.create = AsyncMock(return_value=_fake_boss(level=8))
        boss = run_async(rb.spawn)
    assert boss.level == 8


def test_contribute_applies_damage():
    boss = _fake_boss(hp=1000)
    player = _fake_player(dps=200)
    with patch("game.raid_boss.Player") as MockPlayer, patch("game.raid_boss.RaidBossHit") as MockHit:
        MockPlayer.objects.filter.return_value.all = AsyncMock(return_value=[player])
        MockHit.objects.filter.return_value.get_or_none = AsyncMock(return_value=None)
        MockHit.objects.create = AsyncMock()
        run_async(rb.contribute, boss, int(time.time()))
    assert boss.hp == 800
    MockHit.objects.create.assert_awaited_once()


def test_contribute_cooldown_skips():
    boss = _fake_boss(hp=1000)
    player = _fake_player(dps=200)
    hit = _fake_hit(damage=500, last_hit_at=int(time.time()))
    with patch("game.raid_boss.Player") as MockPlayer, patch("game.raid_boss.RaidBossHit") as MockHit:
        MockPlayer.objects.filter.return_value.all = AsyncMock(return_value=[player])
        MockHit.objects.filter.return_value.get_or_none = AsyncMock(return_value=hit)
        MockHit.objects.create = AsyncMock()
        run_async(rb.contribute, boss, int(time.time()))
    assert boss.hp == 1000
    MockHit.objects.create.assert_not_awaited()


def test_award_rewards_contributors():
    boss = _fake_boss()
    player = _fake_player()
    hit = _fake_hit(player_uid=1, damage=100)
    with patch("game.raid_boss.RaidBossHit") as MockHit, patch("game.raid_boss.Player") as MockPlayer:
        MockHit.objects.filter.return_value.all = AsyncMock(return_value=[hit])
        MockPlayer.objects.get_or_none = AsyncMock(return_value=player)
        run_async(rb.award, None, boss)
    assert boss.status == "defeated"
    assert player.tokens > 0
    assert player.gold > 0


def test_tick_despawns():
    boss = _fake_boss(despawn_at=int(time.time()) - 10)
    with patch("game.raid_boss.RaidBoss") as MockRaid:
        MockRaid.objects.filter.return_value.get_or_none = AsyncMock(return_value=boss)
        n = run_async(rb.tick, None)
    assert boss.status == "despawned"
    assert n == 1


def test_tick_spawns_when_empty():
    with patch("game.raid_boss.RaidBoss") as MockRaid:
        MockRaid.objects.filter.return_value.get_or_none = AsyncMock(return_value=None)
        MockRaid.objects.order_by.return_value.get_or_none = AsyncMock(return_value=None)
        MockRaid.objects.create = AsyncMock(return_value=_fake_boss())
        n = run_async(rb.tick, None)
    assert n == 0
    MockRaid.objects.create.assert_awaited_once()


def test_tick_waits_spawn_interval():
    prev = _fake_boss(level=3, spawned_at=int(time.time()))
    with patch("game.raid_boss.RaidBoss") as MockRaid:
        MockRaid.objects.filter.return_value.get_or_none = AsyncMock(return_value=None)
        MockRaid.objects.order_by.return_value.get_or_none = AsyncMock(return_value=prev)
        MockRaid.objects.create = AsyncMock()
        n = run_async(rb.tick, None)
    assert n == 0
    MockRaid.objects.create.assert_not_awaited()


def test_build_raid_text_no_boss():
    from handlers.raid import build_raid_text
    player = _fake_player()
    with patch("handlers.raid.RaidBoss") as MockRaid:
        MockRaid.objects.filter.return_value.get_or_none = AsyncMock(return_value=None)
        text = run_async(build_raid_text, player, "ru")
    assert "нет активного" in text


def test_build_raid_text_with_boss():
    from handlers.raid import build_raid_text
    player = _fake_player()
    boss = _fake_boss(hp=250, max_hp=1000, name="Разрушитель Миров #1")
    with patch("handlers.raid.RaidBoss") as MockRaid, patch("handlers.raid.RaidBossHit") as MockHit:
        MockRaid.objects.filter.return_value.get_or_none = AsyncMock(return_value=boss)
        MockHit.objects.filter.return_value.get_or_none = AsyncMock(return_value=None)
        text = run_async(build_raid_text, player, "ru")
    assert "25.0%" in text
    assert "Разрушитель Миров #1" in text


def test_battle_hub_has_all_four_entries():
    from handlers.battle import _battle_keyboard
    kb = _battle_keyboard("ru")
    flat = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "menu_hunt" in flat
    assert "menu_dungeons" in flat
    assert "arena_menu" in flat
    assert "raid_menu" in flat


def test_battle_hub_nav_row():
    from handlers.battle import _battle_keyboard
    kb = _battle_keyboard("ru")
    last_row = kb.inline_keyboard[-1]
    cbs = [b.callback_data for b in last_row]
    assert "menu_profile" in cbs
    assert "menu_back" in cbs


import asyncio


def run_async(fn, *args):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(fn(*args))
    finally:
        loop.close()
