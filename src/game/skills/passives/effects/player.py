"""
game/skills/passives/effects/player.py — все пассивки игрока
"""
from ..base import (
    IPassiveEffect, PassiveTrigger, PassiveType,
    PassiveContext, PassiveResult, PassiveRegistry
)
from config import PASSIVE_MAX_LEVEL


class VampirismEffect(IPassiveEffect):
    id = "vampirism"
    name_ru = "Вампиризм"
    name_en = "Vampirism"
    description_ru = "При нанесении урона лечит {value}% от нанесённого урона"
    description_en = "Heal for {value}% of damage dealt"
    icon = "🩸"
    trigger = PassiveTrigger.ON_DAMAGE_DEALT
    passive_type = PassiveType.PLAYER
    base_value = 0.05
    per_level = 0.01
    cooldown = 0
    max_level = PASSIVE_MAX_LEVEL
    rarity = "Epic"

    async def on_trigger(self, ctx: PassiveContext, level: int) -> PassiveResult:
        val = self.get_value(level)
        heal = int(ctx.damage_dealt * val)
        msg = f"{self.icon} Vampirism: +{heal} HP" if ctx.lang == "en" else f"{self.icon} Вампиризм: +{heal} HP"
        return PassiveResult(
            triggered=True,
            message=msg,
            healing=heal
        )


class ThornsEffect(IPassiveEffect):
    id = "thorns"
    name_ru = "Шипы"
    name_en = "Thorns"
    description_ru = "Отражает {value} ед. урона при получении"
    description_en = "Reflect {value} damage when hit"
    icon = "🌵"
    trigger = PassiveTrigger.ON_DAMAGE_TAKEN
    passive_type = PassiveType.PLAYER
    base_value = 10
    per_level = 2
    cooldown = 5
    max_level = PASSIVE_MAX_LEVEL
    rarity = "Rare"

    async def on_trigger(self, ctx: PassiveContext, level: int) -> PassiveResult:
        val = self.get_value(level)
        msg = f"{self.icon} Thorns: reflected {int(val)} dmg" if ctx.lang == "en" else f"{self.icon} Шипы: отражено {int(val)} урона"
        return PassiveResult(
            triggered=True,
            message=msg,
            damage_reflect=int(val)
        )


class RegenerationEffect(IPassiveEffect):
    id = "regeneration"
    name_ru = "Регенерация"
    name_en = "Regeneration"
    description_ru = "Восстанавливает {value} HP каждый тик"
    description_en = "Restore {value} HP per tick"
    icon = "💚"
    trigger = PassiveTrigger.ON_TICK
    passive_type = PassiveType.PLAYER
    base_value = 5
    per_level = 2
    cooldown = 0
    max_level = PASSIVE_MAX_LEVEL
    rarity = "Epic"

    async def on_trigger(self, ctx: PassiveContext, level: int) -> PassiveResult:
        val = self.get_value(level)
        msg = f"{self.icon} Regeneration: +{int(val)} HP" if ctx.lang == "en" else f"{self.icon} Регенерация: +{int(val)} HP"
        return PassiveResult(
            triggered=True,
            message=msg,
            healing=int(val)
        )


class GoldFinderEffect(IPassiveEffect):
    id = "gold_finder"
    name_ru = "Золотой нюх"
    name_en = "Gold Finder"
    description_ru = "+{value}% золота с монстров"
    description_en = "+{value}% gold from monsters"
    icon = "💰"
    trigger = PassiveTrigger.ON_KILL
    passive_type = PassiveType.PLAYER
    base_value = 0.20
    per_level = 0.05
    cooldown = 0
    max_level = PASSIVE_MAX_LEVEL
    rarity = "Rare"

    async def on_trigger(self, ctx: PassiveContext, level: int) -> PassiveResult:
        val = self.get_value(level)
        msg = f"{self.icon} Gold find: +{int(val * 100)}% gold" if ctx.lang == "en" else f"{self.icon} Золотой нюх: +{int(val * 100)}% золота"
        return PassiveResult(
            triggered=True,
            message=msg,
            gold_bonus=val
        )


class XpBoostEffect(IPassiveEffect):
    id = "xp_boost"
    name_ru = "Мудрец"
    name_en = "Sage"
    description_ru = "+{value}% XP с монстров"
    description_en = "+{value}% XP from monsters"
    icon = "📚"
    trigger = PassiveTrigger.ON_KILL
    passive_type = PassiveType.PLAYER
    base_value = 0.10
    per_level = 0.03
    cooldown = 0
    max_level = PASSIVE_MAX_LEVEL
    rarity = "Epic"

    async def on_trigger(self, ctx: PassiveContext, level: int) -> PassiveResult:
        val = self.get_value(level)
        msg = f"{self.icon} Sage: +{int(val * 100)}% XP" if ctx.lang == "en" else f"{self.icon} Мудрец: +{int(val * 100)}% XP"
        return PassiveResult(
            triggered=True,
            message=msg,
            xp_bonus=val
        )


class CriticalEffect(IPassiveEffect):
    id = "critical"
    name_ru = "Критический удар"
    name_en = "Critical Strike"
    description_ru = "{value}% шанс нанести x2 урон"
    description_en = "{value}% chance to deal x2 damage"
    icon = "⚡"
    trigger = PassiveTrigger.ON_DAMAGE_DEALT
    passive_type = PassiveType.PLAYER
    base_value = 0.10
    per_level = 0.005
    cooldown = 0
    max_level = PASSIVE_MAX_LEVEL
    rarity = "Legendary"

    async def on_trigger(self, ctx: PassiveContext, level: int) -> PassiveResult:
        val = self.get_value(level)
        import random
        if random.random() < val:
            msg = f"{self.icon} ⚡ CRIT!" if ctx.lang == "en" else f"{self.icon} ⚡ КРИТ!"
            return PassiveResult(
                triggered=True,
                message=msg,
                is_crit=True
            )
        return PassiveResult(triggered=False)


class DodgeEffect(IPassiveEffect):
    id = "dodge"
    name_ru = "Тень"
    name_en = "Shadow"
    description_ru = "{value}% шанс уклониться от монстра"
    description_en = "{value}% chance to dodge monster encounter"
    icon = "👤"
    trigger = PassiveTrigger.ON_ENCOUNTER
    passive_type = PassiveType.PLAYER
    base_value = 0.05
    per_level = 0.01
    cooldown = 0
    max_level = PASSIVE_MAX_LEVEL
    rarity = "Rare"

    async def on_trigger(self, ctx: PassiveContext, level: int) -> PassiveResult:
        val = self.get_value(level)
        import random
        if random.random() < min(0.9, val):
            msg = f"{self.icon} You dodged the monster!" if ctx.lang == "en" else f"{self.icon} Ты уклонился от монстра!"
            return PassiveResult(
                triggered=True,
                message=msg,
                is_dodge=True
            )
        return PassiveResult(triggered=False)


class FirstStrikeEffect(IPassiveEffect):
    id = "first_strike"
    name_ru = "Инициатива"
    name_en = "First Strike"
    description_ru = "100% шанс ударить первым (+{value}% урон)"
    description_en = "100% chance to strike first (+{value}% damage)"
    icon = "🎯"
    trigger = PassiveTrigger.ON_ENCOUNTER
    passive_type = PassiveType.PLAYER
    base_value = 0.50
    per_level = 0.10
    cooldown = 0
    max_level = 5
    rarity = "Legendary"

    async def on_trigger(self, ctx: PassiveContext, level: int) -> PassiveResult:
        val = self.get_value(level)
        msg = f"{self.icon} Initiative: +{int(val * 100)}% first strike dmg!" if ctx.lang == "en" else f"{self.icon} Инициатива: +{int(val * 100)}% урон первого удара!"
        return PassiveResult(
            triggered=True,
            message=msg,
            damage_bonus=val
        )


class ShieldWallEffect(IPassiveEffect):
    id = "shield_wall"
    name_ru = "Щит"
    name_en = "Shield Wall"
    description_ru = "Снижает входящий урон на {value}"
    description_en = "Reduce incoming damage by {value}"
    icon = "🛡️"
    trigger = PassiveTrigger.ON_DAMAGE_TAKEN
    passive_type = PassiveType.PLAYER
    base_value = 0.05
    per_level = 0.01
    cooldown = 0
    max_level = PASSIVE_MAX_LEVEL
    rarity = "Epic"

    async def on_trigger(self, ctx: PassiveContext, level: int) -> PassiveResult:
        val = self.get_value(level)
        msg = f"{self.icon} Shield: -{int(val * 100)}% incoming dmg" if ctx.lang == "en" else f"{self.icon} Щит: -{int(val * 100)}% входящего урона"
        return PassiveResult(
            triggered=True,
            message=msg,
            damage_reduction=val
        )


class SlowPoisonEffect(IPassiveEffect):
    id = "slow_poison"
    name_ru = "Замедляющий яд"
    name_en = "Slowing Poison"
    description_ru = "Накладывает яд на {value} урона"
    description_en = "Apply poison for {value} damage"
    icon = "☠️"
    trigger = PassiveTrigger.ON_DAMAGE_DEALT
    passive_type = PassiveType.PLAYER
    base_value = 15
    per_level = 5
    cooldown = 10
    max_level = PASSIVE_MAX_LEVEL
    rarity = "Rare"

    async def on_trigger(self, ctx: PassiveContext, level: int) -> PassiveResult:
        val = self.get_value(level)
        msg = f"{self.icon} Slow poison: {int(val)} dmg" if ctx.lang == "en" else f"{self.icon} Замедляющий яд: {int(val)} урона"
        return PassiveResult(
            triggered=True,
            message=msg,
            poison_damage=int(val)
        )


class FortuneFavorEffect(IPassiveEffect):
    id = "fortune_favor"
    name_ru = "Благосклонность удачи"
    name_en = "Fortune's Favor"
    description_ru = "{value}% шанс полностью избежать входящего урона"
    description_en = "{value}% chance to completely negate incoming damage"
    icon = "🍀"
    trigger = PassiveTrigger.ON_DAMAGE_TAKEN
    passive_type = PassiveType.PLAYER
    base_value = 0.15
    per_level = 0.01
    cooldown = 10
    max_level = PASSIVE_MAX_LEVEL
    rarity = "Unique"

    async def on_trigger(self, ctx: PassiveContext, level: int) -> PassiveResult:
        val = self.get_value(level)
        import random
        if random.random() < val:
            return PassiveResult(
                triggered=True,
                message=f"{self.icon} Fortune's Favor: damage negated!" if ctx.lang == "en" else f"{self.icon} Благосклонность удачи: урон предотвращён!",
                damage_reduction=1.0
            )
        return PassiveResult(triggered=False)


class StoneFortitudeEffect(IPassiveEffect):
    id = "stone_fortitude"
    name_ru = "Каменная стойкость"
    name_en = "Stone Fortitude"
    description_ru = "Снижает входящий урон на {value} ед."
    description_en = "Reduce incoming damage by {value} pts"
    icon = "⛰️"
    trigger = PassiveTrigger.ON_DAMAGE_TAKEN
    passive_type = PassiveType.PLAYER
    base_value = 15
    per_level = 5
    cooldown = 0
    max_level = PASSIVE_MAX_LEVEL
    rarity = "Unique"

    async def on_trigger(self, ctx: PassiveContext, level: int) -> PassiveResult:
        val = self.get_value(level)
        return PassiveResult(
            triggered=True,
            message=f"{self.icon} Stone Fortitude: -{int(val)} incoming dmg" if ctx.lang == "en" else f"{self.icon} Каменная стойкость: -{int(val)} входящего урона",
            damage_reduction=min(0.9, val / max(ctx.damage_taken, 1)) if ctx.damage_taken > 0 else 0
        )


class WindGraceEffect(IPassiveEffect):
    id = "wind_grace"
    name_ru = "Благодать ветра"
    name_en = "Wind Grace"
    description_ru = "+{value}% бонусного урона к каждой атаке"
    description_en = "+{value}% bonus damage on each attack"
    icon = "🌬️"
    trigger = PassiveTrigger.ON_DAMAGE_DEALT
    passive_type = PassiveType.PLAYER
    base_value = 0.15
    per_level = 0.02
    cooldown = 0
    max_level = PASSIVE_MAX_LEVEL
    rarity = "Unique"

    async def on_trigger(self, ctx: PassiveContext, level: int) -> PassiveResult:
        val = self.get_value(level)
        return PassiveResult(
            triggered=True,
            message=f"{self.icon} Wind Grace: +{int(val * 100)}% dmg" if ctx.lang == "en" else f"{self.icon} Благодать ветра: +{int(val * 100)}% урона",
            damage_bonus=val
        )


def register_player_passives() -> None:
    PassiveRegistry.register(VampirismEffect())
    PassiveRegistry.register(ThornsEffect())
    PassiveRegistry.register(RegenerationEffect())
    PassiveRegistry.register(GoldFinderEffect())
    PassiveRegistry.register(XpBoostEffect())
    PassiveRegistry.register(CriticalEffect())
    PassiveRegistry.register(DodgeEffect())
    PassiveRegistry.register(FirstStrikeEffect())
    PassiveRegistry.register(ShieldWallEffect())
    PassiveRegistry.register(SlowPoisonEffect())
    PassiveRegistry.register(FortuneFavorEffect())
    PassiveRegistry.register(StoneFortitudeEffect())
    PassiveRegistry.register(WindGraceEffect())