"""
game/combat.py — боевая логика (HP, MP, Defense, раунды)
Используется в encounter с монстрами, боссами и PVP
"""
import random
import time
from dataclasses import dataclass, field
from typing import Optional

import config as cfg
from db import Player


@dataclass
class CombatUnit:
    """Боевая единица (игрок или босс)"""
    name: str
    uid: int = 0
    hp: int = 100
    max_hp: int = 100
    mp: int = 50
    max_mp: int = 50
    dps: int = 50
    defense: int = 0
    is_player: bool = True

    def get_defense_reduction(self) -> float:
        return min(0.75, self.defense / (self.defense + 200))

    @property
    def hp_pct(self) -> float:
        return self.hp / self.max_hp if self.max_hp > 0 else 1.0

    @property
    def mp_pct(self) -> float:
        return self.mp / self.max_mp if self.max_mp > 0 else 1.0

    def is_alive(self) -> bool:
        return self.hp > 0

    def can_use_skill(self, mp_cost: int) -> bool:
        return self.mp >= mp_cost


@dataclass
class RoundResult:
    """Результат одного раунда"""
    round_num: int
    attacker_name: str
    defender_name: str

    damage_dealt: int = 0
    skill_used: Optional[str] = None
    skill_mp_cost: int = 0

    # Пассивки
    is_crit: bool = False
    crit_bonus: float = 0.0
    heal_amount: int = 0
    poison_damage: int = 0
    reflect_damage: int = 0
    damage_reduction: float = 0.0
    dodge: bool = False
    stun: bool = False
    extra_messages: list = field(default_factory=list)

    # Defender результат
    defender_hp_before: int = 0
    defender_hp_after: int = 0


def create_combat_unit_from_player(player: Player, dps: int) -> CombatUnit:
    """Создать CombatUnit из Player"""
    return CombatUnit(
        name=player.name,
        uid=player.uid,
        hp=player.hp or 100,
        max_hp=player.max_hp or 100,
        mp=player.mp or 50,
        max_mp=player.max_mp or 50,
        dps=dps,
        defense=player.defense or 0,
        is_player=True,
    )


async def process_player_heal_skill(
    player: CombatUnit,
    skill_id: str,
    player_db: Optional[Player] = None,
) -> tuple[bool, str]:
    """Обработать лечебный навык игрока"""
    skill = cfg.PLAYER_HEAL_SKILLS.get(skill_id)
    if not skill:
        return False, "Навык не найден"

    if not player.can_use_skill(skill["mp_cost"]):
        return False, "Недостаточно MP"

    player.mp -= skill["mp_cost"]
    heal_amount = int(player.max_hp * skill["heal_pct"])
    player.hp = min(player.max_hp, player.hp + heal_amount)

    lang = player_db.lang or "ru" if player_db else "ru"
    name = skill["name_ru"] if lang == "ru" else skill["name_en"]
    return True, f"✨ {name}: +{heal_amount} HP"


def format_hp_bar(current: int, maximum: int, length: int = 12) -> str:
    """Форматировать HP bar"""
    pct = current / maximum if maximum > 0 else 0
    filled = int(pct * length)
    bar = "█" * min(filled, length) + "░" * (length - min(filled, length))
    return f"[{bar}] {current}/{maximum} ({int(pct * 100)}%)"


def format_mp_bar(current: int, maximum: int, length: int = 12) -> str:
    """Форматировать MP bar"""
    pct = current / maximum if maximum > 0 else 0
    filled = int(pct * length)
    bar = "▓" * min(filled, length) + "░" * (length - min(filled, length))
    return f"[{bar}] {current}/{maximum} ({int(pct * 100)}%)"


def format_combat_status(unit: CombatUnit, is_player: bool = True) -> str:
    """Форматировать статус бойца"""
    hp_bar = format_hp_bar(unit.hp, unit.max_hp)
    mp_bar = format_mp_bar(unit.mp, unit.max_mp)
    defense = unit.get_defense_reduction()
    reduction_pct = int(defense * 100)

    if is_player:
        return f"📊 {hp_bar}\n💧 {mp_bar}\n🛡️ Защита: {unit.defense} ({reduction_pct}%)"
    else:
        return f"👹 {hp_bar}\n💧 {mp_bar}\n🛡️ Защита: {unit.defense}"