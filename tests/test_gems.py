"""
test_gems.py — драгоценные камни:
- socket/боnусы применяются к статам игрока
- apply_gem вставляет камень в свободное гнездо
- extract_gem возвращает камень в инвентарь
"""
import json
from unittest.mock import MagicMock, AsyncMock, patch

from db import Player, PlayerGem
from game.gems import (
    GEM_BONUS_CAP, apply_gem, extract_gem, free_sockets, get_gem_config,
    get_socket_bonuses_sync, release_slot_gems, replace_item,
)
from core.loot import generate_item_data


def _fake_player(**kw):
    p = MagicMock()
    p.uid = kw.get("uid", 1)
    p.level = kw.get("level", 10)
    p.race = kw.get("race", "")
    p.job = kw.get("job", "")
    p.defense = kw.get("defense", 0)
    for slot in ["weapon", "shield", "helmet", "chest", "gloves", "boots", "ring", "amulet"]:
        setattr(p, slot, kw.get(slot, {"dps": 0, "hp_bonus": 0, "def_bonus": 0, "mp_bonus": 0, "sockets": 0}))
    p.get_set_pieces = Player.get_set_pieces.__get__(p)
    p.get_set_bonuses = Player.get_set_bonuses.__get__(p)
    p._get_set_sum = Player._get_set_sum.__get__(p)
    p._get_set_stat = Player._get_set_stat.__get__(p)
    p.get_dps = Player.get_dps.__get__(p)
    p.get_max_hp = Player.get_max_hp.__get__(p)
    p.get_max_mp = Player.get_max_mp.__get__(p)
    p.get_defense = Player.get_defense.__get__(p)
    p._get_equip_sum = Player._get_equip_sum.__get__(p)
    p.update = AsyncMock()
    return p


def test_gem_configs_exist():
    for gid in ("ruby", "emerald", "sapphire", "amethyst", "diamond"):
        conf = get_gem_config(gid)
        assert conf is not None
        assert conf.get("drop_weight", 0) > 0


def test_item_can_have_sockets():
    with patch("config.GEM_SOCKET_CHANCE", 1.0), patch("config.SET_AFFIX_CHANCE", 0):
        item = generate_item_data("weapon", 10)
    assert item.get("sockets", 0) >= 1
    assert len(item["socketed"]) == item["sockets"]


def test_socket_bonuses_apply():
    p = _fake_player(weapon={
        "dps": 100, "hp_bonus": 0, "def_bonus": 0, "mp_bonus": 0,
        "sockets": 1, "socketed": ["ruby"],
    })
    bonuses = get_socket_bonuses_sync(p)
    assert bonuses["dps_pct"] == 5
    assert p.get_dps() > 100


def _gem_row(row_id=1, gem_id="ruby"):
    gem = MagicMock()
    gem.id = row_id
    gem.gem_id = gem_id
    return gem


def test_apply_gem_fills_socket_and_stores_dict():
    p = _fake_player(weapon={
        "dps": 100, "hp_bonus": 0, "def_bonus": 0, "mp_bonus": 0,
        "sockets": 1, "socketed": [None],
    })
    with patch("db.PlayerGem") as MockGem, \
         patch("db.database.fetch_val", new=AsyncMock(return_value=1)) as fetch_val, \
         patch("game.gems.list_inventory", new=AsyncMock(return_value=[_gem_row()])), \
         patch("game.gems._refresh_caches") as refresh:
        MockGem.objects.get = AsyncMock(return_value=_gem_row())
        ok, status = run_async(apply_gem, p, "weapon")
    assert ok and status == "ok"
    assert isinstance(p.weapon, dict)           # не строка: нет двойной сериализации
    assert p.weapon["socketed"] == ["ruby"]
    params = fetch_val.await_args.args[1]
    assert (params["slot"], params["idx"], params["id"]) == ("weapon", 0, 1)
    refresh.assert_called_once_with(p)


def test_apply_gem_uses_chosen_gem_not_newest():
    p = _fake_player(weapon={"dps": 1, "sockets": 1, "socketed": [None]})
    with patch("db.PlayerGem") as MockGem, \
         patch("db.database.fetch_val", new=AsyncMock(return_value=1)) as fetch_val, \
         patch("game.gems.list_inventory", new=AsyncMock()) as inventory, \
         patch("game.gems._refresh_caches"):
        MockGem.objects.get = AsyncMock(return_value=_gem_row(7, "emerald"))
        ok, _ = run_async(apply_gem, p, "weapon", 7)
    assert ok and p.weapon["socketed"] == ["emerald"]
    assert fetch_val.await_args.args[1]["id"] == 7
    inventory.assert_not_awaited()


def test_apply_gem_reports_no_gem_when_already_claimed():
    p = _fake_player(weapon={"dps": 1, "sockets": 1, "socketed": [None]})
    with patch("db.PlayerGem"), \
         patch("db.database.fetch_val", new=AsyncMock(return_value=None)):
        ok, status = run_async(apply_gem, p, "weapon", 3)
    assert not ok and status == "no_gem"
    assert p.weapon["socketed"] == [None]       # предмет не тронут


def test_apply_gem_no_sockets():
    p = _fake_player(weapon={"dps": 100, "sockets": 0})
    ok, status = run_async(apply_gem, p, "weapon")
    assert not ok and status == "no_socket"


def test_apply_gem_full_item():
    p = _fake_player(weapon={"dps": 1, "sockets": 1, "socketed": ["ruby"]})
    ok, status = run_async(apply_gem, p, "weapon")
    assert not ok and status == "full"


def test_apply_gem_empty_inventory():
    p = _fake_player(weapon={"dps": 1, "sockets": 1, "socketed": [None]})
    with patch("game.gems.list_inventory", new=AsyncMock(return_value=[])):
        ok, status = run_async(apply_gem, p, "weapon")
    assert not ok and status == "no_gem"


def test_extract_gem_releases_same_row_instead_of_creating_new():
    p = _fake_player(weapon={
        "dps": 100, "hp_bonus": 0, "def_bonus": 0, "mp_bonus": 0,
        "sockets": 1, "socketed": ["ruby"],
    })
    with patch("db.PlayerGem") as MockGem, \
         patch("db.database.fetch_val", new=AsyncMock(return_value=1)) as fetch_val, \
         patch("game.gems._refresh_caches"):
        MockGem.objects.create = AsyncMock()
        ok, status = run_async(extract_gem, p, "weapon", 0)
    assert ok and status == "ok"
    assert p.weapon["socketed"] == [None]
    MockGem.objects.create.assert_not_awaited()  # раньше раздувало таблицу
    assert "equipped = FALSE" in fetch_val.await_args.args[0]


def test_extract_gem_empty_socket():
    p = _fake_player(weapon={"dps": 1, "sockets": 1, "socketed": [None]})
    ok, status = run_async(extract_gem, p, "weapon", 0)
    assert not ok and status == "empty"


def test_extract_gem_repairs_orphan_row():
    p = _fake_player(weapon={"dps": 1, "sockets": 1, "socketed": ["ruby"]})
    with patch("db.database.fetch_val", new=AsyncMock(return_value=None)), \
         patch("game.gems._refresh_caches"):
        ok, status = run_async(extract_gem, p, "weapon", 0)
    assert ok and status == "ok_orphan"
    assert p.weapon["socketed"] == [None]


def test_replace_item_returns_gems_of_old_item():
    p = _fake_player(weapon={"dps": 1, "sockets": 1, "socketed": ["ruby"]})
    new_item = {"dps": 500, "sockets": 0}
    with patch("game.gems.release_slot_gems", new=AsyncMock(return_value=1)) as release:
        returned = run_async(replace_item, p, "weapon", new_item)
    assert returned == 1
    release.assert_awaited_once_with(p.uid, "weapon")
    assert p.weapon is new_item


def test_release_slot_gems_noop_without_gems():
    with patch("db.database.fetch_all", new=AsyncMock(return_value=[])), \
         patch("db.database.execute", new=AsyncMock()) as execute:
        assert run_async(release_slot_gems, 1, "weapon") == 0
    execute.assert_not_awaited()


def test_release_slot_gems_frees_all_gems_of_slot():
    rows = [{"id": 1}, {"id": 2}]
    with patch("db.database.fetch_all", new=AsyncMock(return_value=rows)), \
         patch("db.database.execute", new=AsyncMock()) as execute:
        assert run_async(release_slot_gems, 9, "ring") == 2
    sql, params = execute.await_args.args
    assert "equipped = FALSE" in sql
    assert params == {"uid": 9, "slot": "ring"}


def test_free_sockets_counts_missing_and_empty_cells():
    assert free_sockets({"sockets": 3, "socketed": ["ruby", None]}) == 2
    assert free_sockets({"sockets": 0}) == 0
    assert free_sockets({"sockets": 2, "socketed": ["ruby", "emerald"]}) == 0


def test_socket_bonuses_are_capped():
    many = ["ruby"] * 8   # 8 * 5% = 40% без потолка
    p = _fake_player(weapon={"dps": 1, "sockets": 8, "socketed": many})
    assert get_socket_bonuses_sync(p)["dps_pct"] == GEM_BONUS_CAP["dps_pct"]


def test_socket_bonuses_tolerate_legacy_string_item():
    legacy = json.dumps({"dps": 1, "sockets": 1, "socketed": ["ruby"]})
    p = _fake_player(weapon=legacy)
    assert get_socket_bonuses_sync(p)["dps_pct"] == 5


import asyncio


def run_async(fn, *args):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(fn(*args))
    finally:
        loop.close()
