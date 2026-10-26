"""
test_codex_menu.py — «Дневник героя»: хаб, экраны, подтверждение сброса, регистрация.
"""
from unittest.mock import AsyncMock, MagicMock, patch

from handlers import codex
from handlers.codex import (
    CB_BESTIARY,
    CB_MENU,
    CB_NEMESIS,
    CB_RESPEC_ASK,
    CB_RESPEC_YES,
    CB_SPELLBOOK,
    CB_STATS,
    _respec_screen,
    _screen,
    bestiary_text,
    hub_keyboard,
    spellbook_text,
    stats_text,
)


def _player(**kw):
    p = MagicMock()
    p.uid = 11
    p.level = kw.get("level", 12)
    p.tokens = kw.get("tokens", 10)
    p.achievement_progress = kw.get("progress", "{}")
    for stat in ("str", "con", "dex", "int", "wis", "cha"):
        setattr(p, f"stat_{stat}", kw.get(stat, 10))
    return p


def _callbacks(markup):
    return [b.callback_data for row in markup.inline_keyboard for b in row]


def test_hub_links_journal_sections_and_profile_but_not_stats():
    for lang in ("ru", "en"):
        assert set(_callbacks(hub_keyboard(lang))) == {
            CB_BESTIARY, CB_NEMESIS, CB_SPELLBOOK, "menu_profile",
        }


def test_profile_keyboard_shows_stats_and_journal_buttons():
    from handlers.user import _profile_keyboard
    for lang in ("ru", "en"):
        callbacks = _callbacks(_profile_keyboard(lang))
        assert CB_STATS in callbacks
        assert CB_MENU in callbacks


def test_all_codex_callbacks_match_registered_pattern():
    for cb in (CB_MENU, CB_BESTIARY, CB_NEMESIS, CB_SPELLBOOK, CB_STATS, CB_RESPEC_ASK, CB_RESPEC_YES):
        assert cb.startswith("codex_")


def test_bestiary_empty_and_filled():
    assert "Пока нет" in bestiary_text(_player(), "ru")
    filled = bestiary_text(_player(progress='{"bestiary": {"rat": 12}}'), "en")
    assert "<b>12</b>" in filled and "50" in filled


def test_spellbook_hides_unknown_spells():
    text = spellbook_text(_player(progress='{"spells": ["spark"]}'), "en")
    assert "Spark" in text and "???" in text and "1/" in text


def test_stats_text_shows_bonus_only_for_effective_stats():
    text = stats_text(_player(str=20), "en")
    assert "DPS +3%" in text
    assert "accumulating" in text


async def test_screens_return_back_button_to_hub():
    player = _player()
    with patch("game.nemesis.get_dossiers", new=AsyncMock(return_value=[])):
        for kind in (CB_BESTIARY, CB_NEMESIS, CB_SPELLBOOK):
            _, keyboard = await _screen(player, "ru", kind)
            assert CB_MENU in _callbacks(keyboard)


async def test_stats_screen_offers_respec_and_returns_to_profile():
    _, keyboard = await _screen(_player(), "ru", CB_STATS)
    callbacks = _callbacks(keyboard)
    assert CB_RESPEC_ASK in callbacks
    assert "menu_profile" in callbacks
    assert CB_MENU not in callbacks


async def test_respec_requires_confirmation_before_charging():
    with patch("game.stats.respec", new=AsyncMock()) as respec:
        text, keyboard = await _respec_screen(_player(), "en", confirmed=False)
    respec.assert_not_awaited()
    assert CB_RESPEC_YES in _callbacks(keyboard) and CB_STATS in _callbacks(keyboard)
    assert "10" in text


async def test_respec_confirmed_charges_and_refreshes_caches():
    player = _player()
    with patch("game.stats.respec", new=AsyncMock(return_value=True)) as respec, \
         patch("core.dps.invalidate_dps_cache") as invalidate:
        await _respec_screen(player, "ru", confirmed=True)
        keyboard = (await _respec_screen(player, "ru", confirmed=True))[1]
    assert respec.await_count == 2
    invalidate.assert_called_with(player.uid)
    player.sync_max_hp_mp.assert_called()
    assert CB_RESPEC_ASK in _callbacks(keyboard)


async def test_respec_confirmed_without_tokens_reports_and_stays_in_stats():
    with patch("game.stats.respec", new=AsyncMock(return_value=False)):
        text, keyboard = await _respec_screen(_player(tokens=0), "en", confirmed=True)
    assert "Not enough" in text
    assert "menu_profile" in _callbacks(keyboard)
    assert CB_MENU not in _callbacks(keyboard)


def test_register_adds_commands_and_callback_pattern():
    app = MagicMock()
    codex.register(app)
    handlers = [call.args[0] for call in app.add_handler.call_args_list]
    commands = {c for h in handlers for c in getattr(h, "commands", [])}
    assert commands == {"journal", "bestiary", "nemesis", "spellbook", "mystats", "respec"}
    patterns = [h.pattern.pattern for h in handlers if hasattr(h, "pattern")]
    assert patterns == ["^codex_"]
