"""
test_gems.py — драгоценные камни:
- socket/боnусы применяются к статам игрока
- apply_gem вставляет камень в свободное гнездо
- extract_gem возвращает камень в инвентарь
"""
import json
from unittest.mock import MagicMock, AsyncMock, patch

from db import Player, PlayerGem
from game.gems import get_gem_config, get_socket_bonuses_sync, apply_gem, extract_gem
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


def test_apply_gem_fills_socket():
    p = _fake_player(weapon={
        "dps": 100, "hp_bonus": 0, "def_bonus": 0, "mp_bonus": 0,
        "sockets": 1, "socketed": [None],
    })
    gem = MagicMock()
    gem.gem_id = "ruby"
    gem.equipped = False
    gem.update = AsyncMock()
    with patch("db.PlayerGem") as MockGem:
        MockGem.objects.filter.return_value.order_by.return_value.get_or_none = AsyncMock(return_value=gem)
        ok, status = run_async(apply_gem, p, "weapon")
    assert ok and status == "ok"
    assert json.loads(p.weapon)["socketed"] == ["ruby"]


def test_apply_gem_no_sockets():
    p = _fake_player(weapon={"dps": 100, "sockets": 0})
    ok, status = run_async(apply_gem, p, "weapon")
    assert not ok and status == "no_socket"


def test_extract_gem_returns_to_inventory():
    p = _fake_player(weapon={
        "dps": 100, "hp_bonus": 0, "def_bonus": 0, "mp_bonus": 0,
        "sockets": 1, "socketed": ["ruby"],
    })
    with patch("db.PlayerGem") as MockGem:
        MockGem.objects.create = AsyncMock()
        ok, status = run_async(extract_gem, p, "weapon", 0)
    assert ok and status == "ok"
    assert json.loads(p.weapon)["socketed"] == [None]
    MockGem.objects.create.assert_awaited_once()


import asyncio


def run_async(fn, *args):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(fn(*args))
    finally:
        loop.close()
