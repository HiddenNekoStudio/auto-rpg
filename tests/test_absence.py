"""
test_absence.py — сводка «пока тебя не было» при возврате из оффлайна.
"""
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from game.absence import DAY_SECONDS, AbsenceDigest, absence_text, build_digest


def _digest(**kw) -> AbsenceDigest:
    base = dict(
        name="Тор", away="5ч 20м", xp="12.3K", levels_gained=0, level=7,
        next_in="40м", hp=80, max_hp=100, mp=30, max_mp=50,
        daily_ready=False, active_quests=0, slow_xp=False,
    )
    base.update(kw)
    return AbsenceDigest(**base)


def test_digest_shows_duration_xp_level_and_resources():
    text = build_digest(_digest(), "ru")
    assert "Тор" in text
    assert "5ч 20м" in text
    assert "+12.3K" in text
    assert "80/100" in text and "30/50" in text
    assert "до следующего" in text


def test_digest_hides_optional_lines_when_nothing_to_report():
    text = build_digest(_digest(), "ru")
    assert "Уровней" not in text
    assert "Что дальше" not in text
    assert "медленнее" not in text


def test_digest_reports_levels_gained():
    assert "+2" in build_digest(_digest(levels_gained=2), "ru")
    assert "Levels: <b>+2</b>" in build_digest(_digest(levels_gained=2), "en")


def test_digest_lists_daily_and_quests_as_next_steps():
    text = build_digest(_digest(daily_ready=True, active_quests=3), "en")
    assert "What's next" in text
    assert "/daily" in text
    assert "Active quests: 3" in text and "/quest" in text


def test_digest_warns_about_slow_xp_after_a_day():
    assert "медленнее" in build_digest(_digest(slow_xp=True), "ru")


def test_digest_never_claims_kills_or_gold():
    text = build_digest(_digest(daily_ready=True, active_quests=1, levels_gained=1), "ru")
    assert "убит" not in text.lower()
    assert "золот" not in text.lower()


def test_digest_escapes_player_name():
    assert "<script>" not in build_digest(_digest(name="<script>"), "ru")


def test_digest_english_has_no_cyrillic():
    text = build_digest(
        _digest(name="Thor", away="5h", next_in="40m", daily_ready=True,
                active_quests=1, levels_gained=1, slow_xp=True),
        "en",
    )
    assert not any("а" <= ch.lower() <= "я" for ch in text)


def _player(last_daily_claim=0):
    return SimpleNamespace(
        uid=5, name="Thor", level=9, currentxp=100, nextxp=1100,
        hp=70, max_hp=120, mp=20, max_mp=60, last_daily_claim=last_daily_claim,
    )


async def _run(player, away, quests=0):
    chain = MagicMock()
    chain.count = AsyncMock(return_value=quests)
    with patch("db.PlayerQuest") as model:
        model.objects.filter.return_value = chain
        text = await absence_text(player, "en", away_seconds=away, xp=5000, levels_gained=1)
    return text, model


async def test_absence_text_marks_daily_ready_when_not_claimed_today():
    text, _ = await _run(_player(last_daily_claim=0), 3600)
    assert "/daily" in text


async def test_absence_text_skips_daily_when_claimed_today():
    text, _ = await _run(_player(last_daily_claim=int(time.time())), 3600)
    assert "/daily" not in text


async def test_absence_text_counts_only_active_quests_of_this_player():
    text, model = await _run(_player(), 3600, quests=2)
    assert model.objects.filter.call_args.kwargs == {"player_uid": 5, "status": "active"}
    assert "Active quests: 2" in text


async def test_absence_text_flags_slow_xp_only_after_a_day():
    short, _ = await _run(_player(), DAY_SECONDS)
    long, _ = await _run(_player(), DAY_SECONDS + 1)
    assert "more slowly" not in short
    assert "more slowly" in long
