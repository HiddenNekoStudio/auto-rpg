"""
test_gems_menu.py — экран камней: инвентарь, выбор камня и гнезда, извлечение.
"""
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import handlers.gems as hg


def _item(sockets=2, socketed=None, name="Меч"):
    return {"name": name, "name_en": "Sword", "dps": 10,
            "sockets": sockets, "socketed": socketed if socketed is not None else [None] * sockets}


def _player(**slots):
    p = MagicMock(spec=[])
    p.uid = 5
    p.lang = "ru"
    for slot in ("weapon", "shield", "helmet", "chest", "gloves", "boots", "ring", "amulet"):
        setattr(p, slot, slots.get(slot, {"dps": 0, "sockets": 0}))
    return p


def _gem(row_id, gem_id="ruby"):
    return SimpleNamespace(id=row_id, gem_id=gem_id)


def _callbacks(markup):
    return [b.callback_data for row in markup.inline_keyboard for b in row]


def test_menu_text_groups_duplicate_gems_with_count():
    text = hg.menu_text(_player(), [_gem(1), _gem(2), _gem(3, "emerald")], "en")
    assert "×2" in text and "Ruby" in text and "Emerald" in text


def test_menu_text_empty_states():
    text = hg.menu_text(_player(), [], "en")
    assert "nothing yet" in text
    assert "no gear has sockets" in text


def test_menu_text_shows_sockets_and_total_bonus():
    p = _player(weapon=_item(2, ["ruby", None]))
    text = hg.menu_text(p, [], "ru")
    assert "Рубин" in text and "▫️" in text
    assert "Итого от камней" in text and "DPS +5%" in text


def test_menu_keyboard_offers_one_button_per_gem_type_and_pull_buttons():
    p = _player(weapon=_item(2, ["ruby", None]))
    callbacks = _callbacks(hg.menu_keyboard(p, [_gem(1), _gem(2)], "ru"))
    assert callbacks.count("gem_pick_1") == 1 and "gem_pick_2" not in callbacks
    assert "gem_pull_weapon_0" in callbacks
    assert "menu_profile" in callbacks


def test_pick_screen_lists_only_gear_with_free_sockets():
    p = _player(weapon=_item(1, ["ruby"]), ring=_item(2, [None, None], "Кольцо"))
    _, keyboard = hg.pick_screen(p, _gem(9), "ru")
    callbacks = _callbacks(keyboard)
    assert "gem_put_9_ring" in callbacks
    assert "gem_put_9_weapon" not in callbacks
    assert hg.CB_MENU in callbacks


def test_pick_screen_explains_when_nothing_fits():
    text, keyboard = hg.pick_screen(_player(), _gem(9), "en")
    assert "No gear with a free socket" in text
    assert _callbacks(keyboard) == [hg.CB_MENU]


def test_status_messages_are_localized_with_fallback():
    assert hg.status_message("full", "ru") == "Гнёзда заняты"
    assert hg.status_message("full", "en") == "Sockets full"
    assert hg.status_message("weird", "en") == "weird"


def _query(data):
    q = MagicMock()
    q.data = data
    q.from_user.id = 5
    q.answer = AsyncMock()
    return q


async def _dispatch(data, player, apply=None, extract=None, inventory=None):
    query = _query(data)
    update = SimpleNamespace(callback_query=query)
    with patch("handlers.gems.Player") as model, \
         patch("handlers.gems.safe_edit", new=AsyncMock()) as edit, \
         patch.object(hg.gems_api, "apply_gem", new=apply or AsyncMock(return_value=(True, "ok"))), \
         patch.object(hg.gems_api, "extract_gem", new=extract or AsyncMock(return_value=(True, "ok"))), \
         patch.object(hg.gems_api, "list_inventory", new=AsyncMock(return_value=inventory or [])):
        model.objects.get_or_none = AsyncMock(return_value=player)
        await hg.callback_gems(update, MagicMock())
    return query, edit


async def test_put_passes_chosen_gem_and_slot_and_answers_once():
    apply = AsyncMock(return_value=(True, "ok"))
    query, _ = await _dispatch("gem_put_7_ring", _player(), apply=apply)
    apply.assert_awaited_once()
    assert apply.await_args.args[1:] == ("ring", 7)
    assert query.answer.await_count == 1


async def test_put_failure_alerts_with_reason():
    apply = AsyncMock(return_value=(False, "no_gem"))
    query, _ = await _dispatch("gem_put_7_ring", _player(), apply=apply)
    assert query.answer.await_args.kwargs.get("show_alert") is True
    assert query.answer.await_count == 1


async def test_pull_parses_slot_and_index():
    extract = AsyncMock(return_value=(True, "ok"))
    query, _ = await _dispatch("gem_pull_weapon_1", _player(), extract=extract)
    assert extract.await_args.args[1:] == ("weapon", 1)
    assert query.answer.await_count == 1


async def test_pick_unknown_gem_alerts_and_redraws_menu():
    query, edit = await _dispatch("gem_pick_99", _player(), inventory=[_gem(1)])
    assert query.answer.await_count == 1
    assert query.answer.await_args.kwargs.get("show_alert") is True
    edit.assert_awaited()


async def test_pick_known_gem_shows_slot_choice_and_answers_once():
    p = _player(ring=_item(1, [None]))
    query, edit = await _dispatch("gem_pick_1", p, inventory=[_gem(1)])
    assert query.answer.await_count == 1
    assert "gem_put_1_ring" in _callbacks(edit.await_args.kwargs["reply_markup"])


def test_register_pattern_matches_every_gem_callback():
    app = MagicMock()
    hg.register(app)
    pattern = next(c.args[0].pattern.pattern for c in app.add_handler.call_args_list
                   if hasattr(c.args[0], "pattern"))
    for data in ("gems_menu", "gem_pick_1", "gem_put_1_ring", "gem_pull_ring_0"):
        assert re.search(pattern, data)
