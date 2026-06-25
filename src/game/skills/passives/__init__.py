"""
game/skills/passives/__init__.py — публичный API пассивок
"""
from .base import (
    PassiveTrigger, PassiveType, PassiveContext,
    PassiveResult, PassiveRegistry, IPassiveEffect,
    xp_threshold_for_level, progress_percent
)
from .registry import PassiveSkillRegistry, PASSIVES_JSON, calc_upgrade_cost
from .effects.player import register_player_passives
from .boss.effects import register_boss_passives


def init_passives() -> None:
    if PassiveRegistry.is_loaded():
        return
    register_player_passives()
    register_boss_passives()
    PassiveRegistry.load_from_json(PASSIVES_JSON)