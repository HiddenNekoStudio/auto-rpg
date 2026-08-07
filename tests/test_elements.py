"""
test_elements.py — элементы и DoT:
- элемент монстра определяется по типу
- weakness_mult: ×1.5 по слабости, ×1.0 иначе
- элемент-аффикс выдаётся оружию при генерации лута
- hunting-монстр несёт element и type
"""
import config as cfg
from game import combat
from core import loot
from game.hunting import generate_hunt_monster


class _Monster:
    def __init__(self, mid, mtype):
        self.id = mid
        self._type = mtype


def test_monster_element_by_type():
    assert combat.monster_element(_Monster("skeleton", "undead")) == "dark"
    assert combat.monster_element(_Monster("dragon", "dragon")) == "fire"
    assert combat.monster_element(_Monster("golem", "construct")) == "earth"


def test_weakness_mult_fire_vs_undead():
    m = _Monster("vampire", "undead")
    assert combat.weakness_mult("fire", m) == cfg.ELEMENT_WEAK_MULT


def test_weakness_mult_no_match():
    m = _Monster("dragon", "dragon")
    assert combat.weakness_mult("nature", m) == 1.0


def test_weakness_mult_empty_weapon():
    m = _Monster("dragon", "dragon")
    assert combat.weakness_mult("", m) == 1.0


def test_weakness_mult_dict_with_type():
    m = {"id": "x", "type": "undead"}
    assert combat.weakness_mult("holy", m) == cfg.ELEMENT_WEAK_MULT


def test_loot_weapon_may_carry_element():
    rng = loot.random.Random(42)
    got_any = False
    for _ in range(200):
        item = loot.generate_item_data("weapon", 10, rng=rng)
        if item.get("element"):
            assert item["element"] in cfg.ELEMENT_NAMES_RU
            got_any = True
    assert got_any, "no weapon got an element affix in 200 rolls"


def test_loot_shield_never_element():
    rng = loot.random.Random(1)
    for _ in range(200):
        item = loot.generate_item_data("shield", 10, rng=rng)
        assert item.get("element") is None


def test_hunt_monster_has_element_and_type():
    for _ in range(100):
        m = generate_hunt_monster(_FakePlayer(), "weak")
        assert m["element"] in cfg.ELEMENT_NAMES_RU
        assert m["type"] in cfg.MONSTER_TYPE_ELEMENT


class _FakePlayer:
    uid = 1
    level = 10
    fight_streak = 0
    hp = 100
    lang = "ru"
    race = "human"
    job = "warrior"
    align = 0
    defense = 10

    def get_max_hp(self):
        return 100

    def get_dps(self):
        return 1000
