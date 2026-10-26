"""
test_spellbook.py — книга заклинаний: чистая коллекция без боевой силы.
"""
import random
from unittest.mock import AsyncMock, MagicMock, patch

from game.spellbook import (
    SPELL_LEARN_CHANCE,
    SPELLS,
    learn_on_levelup,
    learned_ids,
    pick_new_spell,
    spell_name,
)


class _Rng:
    """Детерминированный rng: roll задаёт random(), choice берёт первый элемент."""

    def __init__(self, roll):
        self._roll = roll

    def random(self):
        return self._roll

    def choice(self, seq):
        return seq[0]


def test_spell_ids_are_unique():
    assert len({s.id for s in SPELLS}) == len(SPELLS)


def test_spell_name_follows_language():
    assert spell_name(SPELLS[0], "en") == SPELLS[0].name_en
    assert spell_name(SPELLS[0], "ru") == SPELLS[0].name_ru


def test_pick_new_spell_learns_when_roll_is_below_chance():
    progress, spell = pick_new_spell({}, _Rng(0.0))
    assert spell == SPELLS[0]
    assert progress["spells"] == [SPELLS[0].id]


def test_pick_new_spell_skips_when_roll_is_at_or_above_chance():
    original = {"spells": []}
    progress, spell = pick_new_spell(original, _Rng(SPELL_LEARN_CHANCE))
    assert spell is None
    assert progress is original


def test_pick_new_spell_never_repeats_and_keeps_input():
    original = {"spells": [SPELLS[0].id]}
    progress, spell = pick_new_spell(original, _Rng(0.0))
    assert spell == SPELLS[1]
    assert progress["spells"] == [SPELLS[0].id, SPELLS[1].id]
    assert original == {"spells": [SPELLS[0].id]}


def test_pick_new_spell_returns_none_when_book_is_full():
    full = {"spells": [s.id for s in SPELLS]}
    progress, spell = pick_new_spell(full, _Rng(0.0))
    assert spell is None
    assert progress is full


def test_whole_book_is_collectable_without_duplicates():
    progress, rng = {}, random.Random(1)
    for _ in range(500):
        progress, _ = pick_new_spell(progress, rng)
    assert sorted(progress["spells"]) == sorted(s.id for s in SPELLS)


def test_learned_ids_tolerates_bad_blob():
    assert learned_ids("not-json") == []
    assert learned_ids('{"spells": ["echo"]}') == ["echo"]


async def test_learn_on_levelup_persists_through_cas():
    player = MagicMock()
    player.uid = 7
    player.achievement_progress = "{}"
    with patch("db.database.fetch_val", new=AsyncMock(return_value=1)):
        spell = await learn_on_levelup(player, _Rng(0.0))

    assert spell == SPELLS[0]
    assert SPELLS[0].id in player.achievement_progress
