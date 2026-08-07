"""
test_quest_progress_fix.py — проверка фиксов квест-прогресса (фаза 3 аудита).
- earn_xp капает amount, а не 1 за событие
- win_battle прогресс = max(progress, count)
- on_death сбрасывает survive/win_battle в 0 (а не инкрементит)
- on_win_streak прогрессит и win_battle, и survive
"""
import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

NOW = int(time.time()) + 3600


def _fake_quest(**kw):
    q = MagicMock()
    q.player_uid = kw.get("player_uid", 1)
    q.category = kw["category"]
    q.target_id = kw.get("target_id", "*")
    q.target_count = kw.get("target_count", 5)
    q.progress = kw.get("progress", 0)
    q.status = "active"
    q.expires_at = kw.get("expires_at", NOW)
    q.title = "Test"
    q.quest_type = kw.get("quest_type", "kill")
    q.last_progress_at = 0
    q.update = AsyncMock()
    return q


@pytest.mark.asyncio
@patch("game.quests.complete_quest", new_callable=AsyncMock)
@patch("game.quests.fail_quest", new_callable=AsyncMock)
@patch("game.quests.send_quest_progress_notification", new_callable=AsyncMock)
@patch("game.quests.PlayerQuest")
async def test_earn_xp_progress_by_amount(mock_pq, mock_notify, mock_fail, mock_complete):
    q = _fake_quest(category="earn_xp", target_id="xp", target_count=500)
    mock_pq.objects.filter.return_value.all = AsyncMock(return_value=[q])

    from game.quests import check_quest_progress
    await check_quest_progress(MagicMock(uid=1), "xp_gained", {"target_id": "xp", "amount": 120})

    assert q.progress == 120
    mock_complete.assert_not_awaited()


@pytest.mark.asyncio
@patch("game.quests.complete_quest", new_callable=AsyncMock)
@patch("game.quests.fail_quest", new_callable=AsyncMock)
@patch("game.quests.send_quest_progress_notification", new_callable=AsyncMock)
@patch("game.quests.PlayerQuest")
async def test_win_battle_progress_is_max(mock_pq, mock_notify, mock_fail, mock_complete):
    from game.quests import check_quest_progress
    p = MagicMock(uid=1)

    q = _fake_quest(category="win_battle", target_id="streak", target_count=5, progress=2)
    mock_pq.objects.filter.return_value.all = AsyncMock(return_value=[q])
    await check_quest_progress(p, "win_streak", {"target_id": "streak", "count": 4})
    assert q.progress == 4
    mock_complete.assert_not_awaited()

    q2 = _fake_quest(category="win_battle", target_id="streak", target_count=5, progress=3)
    mock_pq.objects.filter.return_value.all = AsyncMock(return_value=[q2])
    await check_quest_progress(p, "win_streak", {"target_id": "streak", "count": 5})
    assert q2.progress == 5
    mock_complete.assert_awaited_once()


@pytest.mark.asyncio
@patch("game.quests.PlayerQuest")
async def test_on_death_resets_streak_and_survive(mock_pq):
    q1 = _fake_quest(category="survive", target_id="survive", target_count=1, progress=1)
    q2 = _fake_quest(category="win_battle", target_id="streak", target_count=5, progress=3)
    mock_pq.objects.filter.return_value.all = AsyncMock(return_value=[q1, q2])

    from game.quests import on_death
    await on_death(MagicMock(uid=1))

    assert q1.progress == 0
    assert q2.progress == 0
    assert q1.update.await_count == 1
    assert q2.update.await_count == 1


@pytest.mark.asyncio
@patch("game.quests.complete_quest", new_callable=AsyncMock)
@patch("game.quests.fail_quest", new_callable=AsyncMock)
@patch("game.quests.send_quest_progress_notification", new_callable=AsyncMock)
@patch("game.quests.PlayerQuest")
async def test_on_win_streak_progresses_both(mock_pq, mock_notify, mock_fail, mock_complete):
    streak_q = _fake_quest(category="win_battle", target_id="streak", target_count=5)
    survive_q = _fake_quest(category="survive", target_id="survive", target_count=1)
    mock_pq.objects.filter.return_value.all = AsyncMock(side_effect=[[streak_q], [survive_q]])

    from game.quests import on_win_streak
    await on_win_streak(MagicMock(uid=1), 3)

    assert streak_q.progress == 3
    assert survive_q.progress == 1
    mock_complete.assert_awaited_once()
