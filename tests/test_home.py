"""
test_home.py — главный экран: текст из снимка, клавиатура по ситуации.
"""
from unittest.mock import AsyncMock, MagicMock, patch

from game.home import (
    HomeSnapshot,
    build_home_keyboard,
    build_home_text,
    daily_is_ready,
    home_keyboard_for,
    load_snapshot,
    static_keyboard,
)


def _snap(**kw) -> HomeSnapshot:
    base = dict(
        name="Тор", level=12, xp_pct=40, xp_left="2ч", hp=80, max_hp=100,
        gold="42.5K", tokens=3, active_quests=0, daily_ready=False, hunting_left="",
    )
    base.update(kw)
    return HomeSnapshot(**base)


def _callbacks(markup):
    return [b.callback_data for row in markup.inline_keyboard for b in row]


def test_text_shows_level_xp_resources():
    text = build_home_text(_snap(), "ru")
    assert "Тор" in text and "Ур. <b>12</b>" in text
    assert "40%" in text and "2ч" in text
    assert "80/100" in text and "42.5K" in text and "🪙 <b>3</b>" in text


def test_text_status_lines_only_when_relevant():
    plain = build_home_text(_snap(), "ru")
    assert "готова" not in plain and "охоте" not in plain and "квестов" not in plain
    busy = build_home_text(
        _snap(daily_ready=True, active_quests=2, hunting_left="10м"), "ru"
    )
    assert "готова" in busy and "Активных квестов: <b>2</b>" in busy and "10м" in busy


def test_escapes_player_name():
    assert "<script>" not in build_home_text(_snap(name="<script>"), "ru")


def test_daily_reward_becomes_first_action():
    cbs = _callbacks(build_home_keyboard(_snap(daily_ready=True), "ru"))
    assert cbs[0] == "daily_menu"


def test_hunting_replaces_quest_action_with_status():
    cbs = _callbacks(build_home_keyboard(_snap(hunting_left="5м", active_quests=3), "ru"))
    assert "hunt_status" in cbs
    assert "menu_quest" not in cbs[:2]


def test_quests_action_appears_when_no_hunt_and_active_quests():
    cbs = _callbacks(build_home_keyboard(_snap(active_quests=2), "ru"))
    assert cbs[0] == "menu_quest"


def test_no_action_row_when_nothing_to_do():
    keyboard = build_home_keyboard(_snap(), "ru")
    assert _callbacks(keyboard)[0] == "menu_profile"


def test_hidden_sections_are_not_on_main_screen():
    shown = set(_callbacks(static_keyboard("ru")))
    for hidden in ("menu_quest", "battle_menu", "menu_hunt", "menu_shop",
                   "clan_menu", "codex_menu", "pets_menu"):
        assert hidden not in shown


def test_visible_navigation_stays_on_main_screen():
    shown = set(_callbacks(static_keyboard("ru")))
    for visible in ("menu_profile", "menu_stats", "menu_settings", "menu_info", "menu_back"):
        assert visible in shown


def test_hidden_sections_are_reachable_from_profile():
    from handlers.user import _profile_keyboard
    profile = set(_callbacks(_profile_keyboard("ru")))
    for hidden in ("menu_quest", "battle_menu", "menu_shop", "clan_menu",
                   "codex_menu", "pets_menu"):
        assert hidden in profile


def test_show_all_flag_restores_every_section(monkeypatch):
    import game.home as home
    monkeypatch.setattr(home, "SHOW_ALL_NAV", True)
    shown = set(_callbacks(static_keyboard("ru")))
    for expected in ("menu_quest", "battle_menu", "menu_hunt", "menu_shop",
                     "clan_menu", "codex_menu", "pets_menu"):
        assert expected in shown


def test_every_navigation_callback_has_a_handler():
    """Каждая кнопка навигации должна совпасть хотя бы с одним зарегистрированным паттерном."""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "src"
    patterns = []
    for p in root.rglob("*.py"):
        patterns += re.findall(r'pattern="([^"]+)"', p.read_text(encoding="utf-8"))
        patterns += re.findall(r"pattern='([^']+)'", p.read_text(encoding="utf-8"))
    for row in static_keyboard("ru").inline_keyboard:
        for button in row:
            cb = button.callback_data
            assert any(re.search(pat, cb) for pat in patterns), f"нет обработчика: {cb}"


def test_english_labels_have_no_cyrillic():
    text = build_home_text(
        _snap(name="Thor", xp_left="2h", daily_ready=True, active_quests=1, hunting_left="5m"), "en")
    assert not any("а" <= ch.lower() <= "я" for ch in text)
    for row in build_home_keyboard(_snap(name="Thor", daily_ready=True), "en").inline_keyboard:
        for button in row:
            assert not any("а" <= ch.lower() <= "я" for ch in button.text)


def test_daily_ready_only_on_new_day():
    day = 86400
    assert daily_is_ready(0, 10 * day + 5)
    assert not daily_is_ready(10 * day + 1, 10 * day + 5)
    assert daily_is_ready(9 * day + 1000, 10 * day + 1)


async def test_load_snapshot_counts_only_active_quests_and_hunt_time():
    player = MagicMock()
    player.uid = 7
    player.name = "Тор"
    player.level = 5
    player.currentxp = 300
    player.nextxp = 1000
    player.hp, player.max_hp = 50, 100
    player.gold = 1500
    player.tokens = 2
    player.last_daily_claim = 0
    player.hunting_expires_at = 0
    chain = MagicMock()
    chain.count = AsyncMock(return_value=4)
    with patch("db.PlayerQuest") as model, \
         patch("game.hunting.is_hunting", return_value=False):
        model.objects.filter.return_value = chain
        snap = await load_snapshot(player, "ru")
    assert model.objects.filter.call_args.kwargs == {"player_uid": 7, "status": "active"}
    assert snap.active_quests == 4
    assert snap.xp_pct == 30
    assert snap.daily_ready is True
    assert snap.hunting_left == ""


async def test_home_keyboard_for_returns_markup_for_snapshot():
    player = MagicMock()
    player.uid = 1
    player.name = "x"
    player.level = 1
    player.currentxp = 0
    player.nextxp = 100
    player.hp = player.max_hp = 10
    player.gold = 0
    player.tokens = 0
    player.last_daily_claim = 10**9
    player.hunting_expires_at = 0
    chain = MagicMock()
    chain.count = AsyncMock(return_value=0)
    with patch("db.PlayerQuest") as model, \
         patch("game.hunting.is_hunting", return_value=False):
        model.objects.filter.return_value = chain
        keyboard = await home_keyboard_for(player, "ru")
    assert "menu_profile" in _callbacks(keyboard)
