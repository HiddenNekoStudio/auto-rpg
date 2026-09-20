"""
test_retention.py — проверка ретеншн-механик (P1-P4):
- ежедневная награда: стрик, сброс, 7-дневный цикл, оффлайн-бонус
- бонусный квест с токенами
- кланы: вместимость, опыт/уровень, перк ежедневки
"""
import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from handlers.daily import _next_reward, _offline_seconds, DAY_SECONDS
from handlers.clans import _member_cap, _clan_xp_to_next, _daily_bonus

NOW = int(time.time())
TODAY = NOW // DAY_SECONDS


def _fake_player(**kw):
    p = MagicMock()
    p.uid = kw.get("uid", 1)
    p.gold = kw.get("gold", 10000)
    p.level = kw.get("level", 10)
    p.last_daily_claim = kw.get("last_daily_claim", 0)
    p.daily_streak = kw.get("daily_streak", 0)
    p.tokens = kw.get("tokens", 0)
    p.online = kw.get("online", False)
    p.last_idle_at = kw.get("last_idle_at", 0)
    p.last_online_at = kw.get("last_online_at", 0)
    p.update = AsyncMock()
    return p


@pytest.mark.asyncio
@patch("handlers.daily.database", new_callable=AsyncMock)
@patch("handlers.daily.time.time", return_value=float(NOW))
async def test_claim_first_time(mock_time, mock_db):
    mock_db.fetch_val = AsyncMock(return_value=1)
    from handlers.daily import _claim
    p = _fake_player()
    msg, credited = await _claim(p, "ru")
    assert credited is True
    assert p.daily_streak == 1
    assert p.tokens == 1
    mock_db.fetch_val.assert_awaited_once()


@pytest.mark.asyncio
@patch("handlers.daily.database", new_callable=AsyncMock)
@patch("handlers.daily.time.time", return_value=float(NOW))
async def test_claim_streak_continues(mock_time, mock_db):
    mock_db.fetch_val = AsyncMock(return_value=1)
    from handlers.daily import _claim
    p = _fake_player(last_daily_claim=(TODAY - 1) * DAY_SECONDS, daily_streak=2)
    msg, credited = await _claim(p, "ru")
    assert credited is True
    assert p.daily_streak == 3
    assert p.tokens == 2  # cycle[2] == 2


@pytest.mark.asyncio
@patch("handlers.daily.time.time", return_value=float(NOW))
async def test_claim_same_day_blocked(mock_time):
    from handlers.daily import _claim
    p = _fake_player(last_daily_claim=TODAY * DAY_SECONDS, daily_streak=5)
    msg, credited = await _claim(p, "ru")
    assert credited is False
    assert p.daily_streak == 5
    p.update.assert_not_awaited()


@pytest.mark.asyncio
@patch("handlers.daily.database", new_callable=AsyncMock)
@patch("handlers.daily.time.time", return_value=float(NOW))
async def test_claim_streak_resets_after_gap(mock_time, mock_db):
    mock_db.fetch_val = AsyncMock(return_value=1)
    from handlers.daily import _claim
    p = _fake_player(last_daily_claim=(TODAY - 3) * DAY_SECONDS, daily_streak=7)
    msg, credited = await _claim(p, "ru")
    assert credited is True
    assert p.daily_streak == 1  # пропуск — стрик сброшен
    assert p.tokens == 1  # cycle[0]


def test_reward_cycle_repeats():
    # 7-дневный цикл: 1,1,2,2,3,3,5
    assert [_next_reward(i) for i in range(7)] == [1, 1, 2, 2, 3, 3, 5]
    assert _next_reward(7) == 1  # замыкание
    assert _next_reward(8) == 1


@pytest.mark.asyncio
@patch("handlers.daily.database", new_callable=AsyncMock)
@patch("handlers.daily.time.time", return_value=float(NOW))
async def test_offline_bonus_granted(mock_time, mock_db):
    mock_db.fetch_val = AsyncMock(return_value=1)
    from handlers.daily import _claim
    hours = 7  # >= OFFLINE_BONUS_HOURS (6)
    p = _fake_player(last_idle_at=NOW - hours * 3600)
    msg, credited = await _claim(p, "ru")
    assert credited is True
    assert p.tokens == 2  # 1 + 1 оффлайн-бонус


@pytest.mark.asyncio
@patch("handlers.daily.database", new_callable=AsyncMock)
@patch("handlers.daily.time.time", return_value=float(NOW))
async def test_offline_bonus_denied_under_threshold(mock_time, mock_db):
    mock_db.fetch_val = AsyncMock(return_value=1)
    from handlers.daily import _claim
    hours = 3  # < OFFLINE_BONUS_HOURS
    p = _fake_player(last_idle_at=NOW - hours * 3600)
    msg, credited = await _claim(p, "ru")
    assert credited is True
    assert p.tokens == 1  # без бонуса


def test_offline_seconds_online_zero():
    p = _fake_player(online=True)
    assert _offline_seconds(p) == 0


def test_offline_seconds_offline():
    p = _fake_player(online=False, last_idle_at=NOW - 7200)
    assert _offline_seconds(p) >= 7200


def test_clan_formulas():
    assert _member_cap(1) == 10
    assert _member_cap(5) == 18
    assert _clan_xp_to_next(1) == 200
    assert _clan_xp_to_next(2) == 500
    assert _daily_bonus(1) == 0
    assert _daily_bonus(3) == 1
    assert _daily_bonus(7) == 2


@pytest.mark.asyncio
@patch("handlers.clans.database", new_callable=AsyncMock)
async def test_clan_levelup_on_donate(mock_db):
    """Донат капает опыт; при превышении порога — уровень растёт."""
    mock_db.fetch_val = AsyncMock(return_value=1)
    from handlers.clans import _donate

    player = _fake_player(gold=5000)
    player.update = AsyncMock()

    member = MagicMock()
    member.total_donated = 0
    member.last_donated = 0
    member.update = AsyncMock()

    clan = MagicMock()
    clan.bank_gold = 0
    clan.xp = 190  # вплотную к порогу уровня 1 (200)
    clan.level = 1
    clan.update = AsyncMock()

    async def fake_membership(uid):
        return member, clan
    with patch("handlers.clans.get_membership", side_effect=fake_membership):
        await _donate(MagicMock(), player, "ru", "1000")

    assert player.gold == 4000
    assert clan.bank_gold == 1000
    assert clan.xp == 90  # 190 + 100 - 200
    assert clan.level == 2  # левел-ап произошёл
    assert member.total_donated == 1000
    clan.update.assert_awaited()
