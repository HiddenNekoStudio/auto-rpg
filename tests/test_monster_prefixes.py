"""
test_monster_prefixes.py — уровневые префиксы, именные элитки, нормализация
имён монстров для квестов и бестиарий (порт из Progress Quest III).
"""
from unittest.mock import patch

import pytest

from game.bestiary import (
    BESTIARY_MILESTONES,
    apply_kill,
    bestiary_entries,
    milestone_gold,
)
from game.monster_prefixes import (
    LEVEL_PREFIXES,
    NAMED_ELITE_CHANCE,
    generate_name,
    generate_named_monster,
    is_named_elite,
    level_prefix,
)
from game.quests import _normalize_monster_type


@pytest.mark.parametrize("diff,expected", [
    (0, ""),
    (1, "Особый "),
    (2, "Большой "),
    (4, "Большой "),
    (5, "Заоблачный "),
    (9, "Заоблачный "),
    (10, "Мессианский "),
    (100, "Мессианский "),
    (-1, "Больной "),
    (-4, "Больной "),
    (-5, "Молодой "),
    (-100, "Молодой "),
])
def test_level_prefix_ru_covers_every_difference(diff, expected):
    assert level_prefix(diff, "ru") == expected


def test_level_prefix_en_uses_english_names():
    assert level_prefix(3, "en") == "Big "
    assert level_prefix(-2, "en") == "Sick "


def test_level_prefix_ranges_match_exactly_one_entry():
    for diff in range(-30, 31):
        matches = [1 for lo, hi, _, _ in LEVEL_PREFIXES if lo <= diff <= hi]
        assert len(matches) == 1, diff


def test_named_elite_chance_is_one_in_twenty_five():
    assert NAMED_ELITE_CHANCE == pytest.approx(1 / 25)


def test_is_named_elite_follows_random_roll():
    with patch("game.monster_prefixes.random.random", return_value=0.0):
        assert is_named_elite() is True
    with patch("game.monster_prefixes.random.random", return_value=0.99):
        assert is_named_elite() is False


def test_generate_name_is_capitalized():
    name = generate_name("ru")
    assert name[0].isupper()
    assert len(name) >= 4


def test_generate_named_monster_is_not_empty_in_both_languages():
    for lang in ("ru", "en"):
        for _ in range(20):
            assert generate_named_monster(lang).strip()


def test_normalize_monster_type_resolves_json_names_with_decorations():
    assert _normalize_monster_type("⭐Гоблин") == "goblin"
    assert _normalize_monster_type("👑Goblin") == "goblin"
    assert _normalize_monster_type("✨ Грим Мор, Эльф (Гоблин)") == "goblin"


def test_normalize_monster_type_unknown_returns_empty():
    assert _normalize_monster_type("Несуществующий зверь") == ""
    assert _normalize_monster_type("") == ""


def test_apply_kill_counts_and_does_not_mutate_input():
    original = {"bestiary": {"rat": 2}}
    updated, reached = apply_kill(original, "rat")
    assert updated["bestiary"]["rat"] == 3
    assert original == {"bestiary": {"rat": 2}}
    assert reached == []


def test_apply_kill_reports_milestone_once():
    first = BESTIARY_MILESTONES[0]
    progress = {"bestiary": {"rat": first - 1}}
    progress, reached = apply_kill(progress, "rat")
    assert reached == [first]
    progress, reached = apply_kill(progress, "rat")
    assert reached == []


def test_milestone_gold_grows_with_level_and_threshold():
    assert milestone_gold(10, 50) > milestone_gold(10, 10)
    assert milestone_gold(20, 10) > milestone_gold(10, 10)
    assert milestone_gold(0, 10) > 0


def test_bestiary_entries_sorted_by_kills_desc():
    class _P:
        achievement_progress = '{"bestiary": {"rat": 3, "bat": 9}}'

    assert bestiary_entries(_P()) == [("bat", 9), ("rat", 3)]


def test_bestiary_entries_tolerates_broken_json():
    class _P:
        achievement_progress = "not-json"

    assert bestiary_entries(_P()) == []
