"""
test_sets.py — сетовые бонусы:
- set_id назначается предмету при генерации
- бонусы за 2/4/6 предметов набора
- get_set_bonuses возвращает только активные пороги
- DPS/HP/Def учитывают сетовые бонусы
"""
from unittest.mock import MagicMock, patch

from db import Player
from core.loot import generate_item_data, get_set_bonus, get_set_config


def _fake_player(**kw):
    p = MagicMock()
    p.uid = kw.get("uid", 1)
    p.level = kw.get("level", 10)
    p.race = kw.get("race", "")
    p.job = kw.get("job", "")
    p.defense = kw.get("defense", 0)
    for slot in ["weapon", "shield", "helmet", "chest", "gloves", "boots", "ring", "amulet"]:
        setattr(p, slot, kw.get(slot, {"dps": 0, "hp_bonus": 0, "def_bonus": 0, "mp_bonus": 0}))
    p.get_set_pieces = Player.get_set_pieces.__get__(p)
    p.get_set_bonuses = Player.get_set_bonuses.__get__(p)
    p._get_set_sum = Player._get_set_sum.__get__(p)
    p._get_set_stat = Player._get_set_stat.__get__(p)
    p.get_dps = Player.get_dps.__get__(p)
    p.get_max_hp = Player.get_max_hp.__get__(p)
    p.get_max_mp = Player.get_max_mp.__get__(p)
    p.get_defense = Player.get_defense.__get__(p)
    p._get_equip_sum = Player._get_equip_sum.__get__(p)
    return p


def test_get_set_config_exists():
    conf = get_set_config("warrior")
    assert conf is not None
    assert len(conf["items"]) == 6
    assert "2" in conf["bonuses"] and "4" in conf["bonuses"] and "6" in conf["bonuses"]


def test_get_set_bonus_thresholds():
    b2 = get_set_bonus("warrior", 1)
    assert b2 == {}
    b2 = get_set_bonus("warrior", 2)
    assert b2.get("dps_pct", 0) > 0
    b4 = get_set_bonus("warrior", 4)
    assert b4.get("dps_pct", 0) > b2.get("dps_pct", 0)
    b6 = get_set_bonus("warrior", 6)
    assert b6.get("dps_pct", 0) > b4.get("dps_pct", 0)


def test_generate_item_can_have_set():
    with patch("config.SET_AFFIX_CHANCE", 1.0):
        item = generate_item_data("weapon", 10)
    assert item.get("set") is not None


def test_get_set_bonuses_active_only():
    p = _fake_player(
        weapon={"dps": 10, "set": "warrior"},
        helmet={"dps": 10, "set": "warrior"},
        chest={"dps": 10, "set": "warrior"},
        shield={"dps": 10, "set": "warrior"},
    )
    bonuses = p.get_set_bonuses()
    assert "warrior" in bonuses
    assert bonuses["warrior"]["dps_pct"] > 0  # 4-предметный бонус


def test_get_set_bonuses_empty():
    p = _fake_player()
    assert p.get_set_bonuses() == {}


def test_dps_includes_set_bonus():
    p = _fake_player(
        weapon={"dps": 100, "set": "warrior"},
        helmet={"dps": 100, "set": "warrior"},
        chest={"dps": 100, "set": "warrior"},
        shield={"dps": 100, "set": "warrior"},
        gloves={"dps": 100, "set": "warrior"},
        boots={"dps": 100, "set": "warrior"},
    )
    dps_no_set = _fake_player().get_dps()
    dps_with_set = p.get_dps()
    assert dps_with_set > dps_no_set
