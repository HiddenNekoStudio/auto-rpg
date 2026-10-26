"""
game/spellbook.py — Книга заклинаний (PQ3 spell collection).

На каждом уровне героя есть шанс выучить новое заклинание. Это чистая
коллекция: боевой силы, DPS, HP и MP заклинания не дают, поэтому баланс
боя не меняется. Выученные id лежат в achievement_progress["spells"].
"""
import random
from typing import NamedTuple, Optional

from game.progress_blob import load_progress, mutate_progress

_KEY_SPELLS = "spells"

# Шанс выучить заклинание при повышении уровня
SPELL_LEARN_CHANCE = 0.5


class Spell(NamedTuple):
    id: str
    name_ru: str
    name_en: str


SPELLS: tuple[Spell, ...] = (
    Spell("spark", "Искра", "Spark"),
    Spell("frost_touch", "Ледяное касание", "Frost Touch"),
    Spell("ember", "Уголёк", "Ember"),
    Spell("gust", "Порыв ветра", "Gust"),
    Spell("stone_skin", "Каменная кожа", "Stone Skin"),
    Spell("moon_veil", "Лунная вуаль", "Moon Veil"),
    Spell("echo", "Эхо", "Echo"),
    Spell("whisper", "Шёпот теней", "Whisper of Shadows"),
    Spell("dawn_light", "Свет зари", "Dawn Light"),
    Spell("void_step", "Шаг в пустоту", "Void Step"),
    Spell("star_fall", "Звездопад", "Star Fall"),
    Spell("time_slip", "Складка времени", "Time Slip"),
)


def spell_name(spell: Spell, lang: str = "ru") -> str:
    return spell.name_en if lang == "en" else spell.name_ru


def learned_ids(raw) -> list[str]:
    return list(load_progress(raw).get(_KEY_SPELLS, []))


def pick_new_spell(progress: dict, rng: random.Random) -> tuple[dict, Optional[Spell]]:
    """Чистая функция: выбрать невыученное заклинание или вернуть None."""
    known = list(progress.get(_KEY_SPELLS, []))
    pool = [s for s in SPELLS if s.id not in known]
    if not pool or rng.random() >= SPELL_LEARN_CHANCE:
        return progress, None
    spell = rng.choice(pool)
    return {**progress, _KEY_SPELLS: [*known, spell.id]}, spell


async def learn_on_levelup(player, rng: Optional[random.Random] = None) -> Optional[Spell]:
    """Попытаться выучить заклинание при повышении уровня."""
    generator = rng or random.Random()
    return await mutate_progress(
        player, lambda progress: pick_new_spell(progress, generator)
    )
