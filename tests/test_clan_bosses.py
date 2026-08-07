"""
test_clan_bosses.py — проверка системы клановых боссов:
- расчёт HP по уровню клана
- спавн только кланам нужного уровня без активного босса
- авто-вклад урона онлайн-членами (кулдаун)
- победа и награды вкладчикам + XP клану
- деспаун по времени
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

import config as cfg
from game.clan_bosses import _clan_xp_to_next, _boss_name


def _fake_clan(**kw):
    c = MagicMock()
    c.id = kw.get("id", 1)
    c.level = kw.get("level", 3)
    c.xp = kw.get("xp", 0)
    c.update = AsyncMock()
    return c


def _fake_member(**kw):
    m = MagicMock()
    m.clan_id = kw.get("clan_id", 1)
    m.player_uid = kw.get("player_uid", 10)
    return m


def _fake_player(**kw):
    p = MagicMock()
    p.uid = kw.get("uid", 10)
    p.online = kw.get("online", True)
    p.lang = kw.get("lang", "ru")
    p.tokens = kw.get("tokens", 0)
    p.gold = kw.get("gold", 0)
    p.get_dps = MagicMock(return_value=kw.get("dps", 2000))
    p.update = AsyncMock()
    return p


def _fake_boss(**kw):
    b = MagicMock()
    b.id = kw.get("id", 1)
    b.clan_id = kw.get("clan_id", 1)
    b.level = kw.get("level", 3)
    b.name = kw.get("name", "Boss #3")
    b.hp = kw.get("hp", 10000)
    b.max_hp = kw.get("max_hp", 10000)
    b.despawn_at = kw.get("despawn_at", 0)
    b.status = kw.get("status", "active")
    b.update = AsyncMock()
    return b


def _fake_hit(**kw):
    h = MagicMock()
    h.id = kw.get("id", 1)
    h.clan_boss_id = kw.get("clan_boss_id", 1)
    h.player_uid = kw.get("player_uid", 10)
    h.damage = kw.get("damage", 0)
    h.last_hit_at = kw.get("last_hit_at", 0)
    h.update = AsyncMock()
    return h


def test_xp_to_next():
    assert _clan_xp_to_next(1) == 200
    assert _clan_xp_to_next(2) == 500


def test_boss_name():
    assert _boss_name(1) == "Теневой Титан #1"
    assert _boss_name(1, "en").startswith("Shadow Titan")


@pytest.mark.asyncio
@patch("game.clan_bosses.ClanBoss")
@patch("game.clan_bosses.Clan")
async def test_spawn_for_clans(mock_clan, mock_boss):
    clan_low = _fake_clan(id=1, level=2)
    clan_ok = _fake_clan(id=2, level=5)
    mock_clan.objects.filter.return_value.all = AsyncMock(return_value=[clan_low, clan_ok])
    mock_boss.objects.filter.return_value.get_or_none = AsyncMock(return_value=None)
    mock_boss.objects.create = AsyncMock()
    from game.clan_bosses import spawn_for_clans
    n = await spawn_for_clans()
    assert n == 2
    created = mock_boss.objects.create.await_args.kwargs
    assert created["clan_id"] == 2
    assert created["level"] == 5
    assert created["max_hp"] == cfg.CLAN_BOSS_HP_BASE + 5 * cfg.CLAN_BOSS_HP_PER_LEVEL


@pytest.mark.asyncio
@patch("game.clan_bosses.ClanBoss")
@patch("game.clan_bosses.Clan")
async def test_spawn_skips_clan_with_active_boss(mock_clan, mock_boss):
    clan = _fake_clan(id=2, level=3)
    mock_clan.objects.filter.return_value.all = AsyncMock(return_value=[clan])
    mock_boss.objects.filter.return_value.get_or_none = AsyncMock(return_value=_fake_boss())
    mock_boss.objects.create = AsyncMock()
    from game.clan_bosses import spawn_for_clans
    n = await spawn_for_clans()
    assert n == 0
    mock_boss.objects.create.assert_not_awaited()


@pytest.mark.asyncio
@patch("game.clan_bosses.ClanBossHit")
@patch("game.clan_bosses.ClanMember")
@patch("game.clan_bosses.Player")
async def test_contribute_online_member_deals_dps(mock_player, mock_member, mock_hit):
    member = _fake_member(player_uid=10)
    mock_member.objects.filter.return_value.all = AsyncMock(return_value=[member])
    player = _fake_player(dps=2000)
    mock_player.objects.get_or_none = AsyncMock(return_value=player)
    mock_hit.objects.filter.return_value.get_or_none = AsyncMock(return_value=None)
    mock_hit.objects.create = AsyncMock()
    boss = _fake_boss()
    from game.clan_bosses import _contribute
    await _contribute(boss, 1000)
    assert boss.hp == 8000
    mock_hit.objects.create.assert_awaited_once_with(
        clan_boss_id=1, player_uid=10, damage=2000, last_hit_at=1000)
    boss.update.assert_awaited_once_with(_columns=["hp"])


@pytest.mark.asyncio
@patch("game.clan_bosses.ClanBossHit")
@patch("game.clan_bosses.ClanMember")
@patch("game.clan_bosses.Player")
async def test_contribute_skips_offline_and_cooldown(mock_player, mock_member, mock_hit):
    m_offline = _fake_member(player_uid=11)
    m_cool = _fake_member(player_uid=12)
    mock_member.objects.filter.return_value.all = AsyncMock(return_value=[m_offline, m_cool])
    mock_player.objects.get_or_none = AsyncMock(
        side_effect=[_fake_player(uid=11, online=False), _fake_player(uid=12, dps=100)])
    hit_recent = _fake_hit(player_uid=12, last_hit_at=999)
    mock_hit.objects.filter.return_value.get_or_none = AsyncMock(return_value=hit_recent)
    mock_hit.objects.create = AsyncMock()
    boss = _fake_boss()
    from game.clan_bosses import _contribute
    await _contribute(boss, 1000)
    assert boss.hp == 10000
    mock_hit.objects.create.assert_not_awaited()


@pytest.mark.asyncio
@patch("game.clan_bosses.ClanBossHit")
@patch("game.clan_bosses.Clan")
@patch("game.clan_bosses.Player")
async def test_award_rewards_contributors(mock_player, mock_clan, mock_hit):
    h1 = _fake_hit(player_uid=10, damage=3000)
    h2 = _fake_hit(player_uid=11, damage=1000)
    mock_hit.objects.filter.return_value.all = AsyncMock(return_value=[h1, h2])
    p1 = _fake_player(uid=10, tokens=0, gold=0)
    p2 = _fake_player(uid=11, tokens=0, gold=0)
    mock_player.objects.get_or_none = AsyncMock(side_effect=[p1, p2])
    clan = _fake_clan(xp=0)
    mock_clan.objects.get_or_none = AsyncMock(return_value=clan)
    boss = _fake_boss()
    from game.clan_bosses import _award
    await _award(None, boss)
    assert boss.status == "defeated"
    assert p1.tokens == cfg.CLAN_BOSS_KILL_TOKENS
    assert p1.gold == cfg.CLAN_BOSS_KILL_GOLD_BASE + cfg.CLAN_BOSS_KILL_GOLD * 3 // 4
    assert p2.gold == cfg.CLAN_BOSS_KILL_GOLD_BASE + cfg.CLAN_BOSS_KILL_GOLD * 1 // 4
    assert clan.xp == cfg.CLAN_BOSS_CLAN_XP
    clan.update.assert_awaited_once()


@pytest.mark.asyncio
@patch("game.clan_bosses.ClanBoss")
async def test_tick_despawns_expired_boss(mock_boss):
    boss = _fake_boss(despawn_at=100)
    mock_boss.objects.filter.return_value.all = AsyncMock(return_value=[boss])
    from game.clan_bosses import tick
    await tick(bot=None)
    assert boss.status == "despawned"
