"""
game/skills/passives/boss/effects.py — пассивки боссов
"""
import random
from ..base import (
    IPassiveEffect, PassiveTrigger, PassiveType,
    PassiveContext, PassiveResult, PassiveRegistry
)
from config import PASSIVE_MAX_LEVEL


class BossEnrageEffect(IPassiveEffect):
    id = "enrage"
    name_ru = "Ярость"
    name_en = "Enrage"
    description_ru = "При HP < 50% наносит +{value}% урона"
    description_en = "Below 50% HP deals +{value}% damage"
    icon = "🔥"
    trigger = PassiveTrigger.ON_HP_BELOW
    passive_type = PassiveType.BOSS
    base_value = 0.50
    per_level = 0.10
    cooldown = 0
    max_level = 10
    rarity = "Legendary"

    async def on_trigger(self, ctx: PassiveContext, level: int, target=None) -> PassiveResult:
        if ctx.boss_hp_pct < 0.5:
            val = self.get_value(level)
            return PassiveResult(
                triggered=True,
                message=f"{self.icon} ⚡ Boss enters ENRAGE! +{int(val * 100)}% dmg!" if ctx.lang == "en" else f"{self.icon} ⚡ Босс входит в ЯРОСТЬ! +{int(val * 100)}% урон!",
                damage_bonus=val
            )
        return PassiveResult(triggered=False)


class BossPoisonAuraEffect(IPassiveEffect):
    id = "poison_aura"
    name_ru = "Ядовая аура"
    name_en = "Poison Aura"
    description_ru = "Каждый удар наносит {value} урона ядом"
    description_en = "Each attack deals {value} poison damage"
    icon = "☣️"
    trigger = PassiveTrigger.ON_DAMAGE_DEALT
    passive_type = PassiveType.BOSS
    base_value = 10
    per_level = 3
    cooldown = 0
    max_level = PASSIVE_MAX_LEVEL
    rarity = "Epic"

    async def on_trigger(self, ctx: PassiveContext, level: int, target=None) -> PassiveResult:
        val = self.get_value(level)
        return PassiveResult(
            triggered=True,
            message=f"{self.icon} Poison aura: {int(val)} dmg" if ctx.lang == "en" else f"{self.icon} Ядовая аура: {int(val)} урона",
            poison_damage=int(val)
        )


class BossReflectEffect(IPassiveEffect):
    id = "boss_reflect"
    name_ru = "Магическое зеркало"
    name_en = "Magic Mirror"
    description_ru = "Отражает {value}% входящего урона"
    description_en = "Reflect {value}% of incoming damage"
    icon = "🔮"
    trigger = PassiveTrigger.ON_DAMAGE_TAKEN
    passive_type = PassiveType.BOSS
    base_value = 0.20
    per_level = 0.05
    cooldown = 5
    max_level = PASSIVE_MAX_LEVEL
    rarity = "Epic"

    async def on_trigger(self, ctx: PassiveContext, level: int, target=None) -> PassiveResult:
        val = min(0.9, self.get_value(level))
        return PassiveResult(
            triggered=True,
            message=f"{self.icon} Magic mirror: reflect {int(val * 100)}%" if ctx.lang == "en" else f"{self.icon} Магическое зеркало: отражение {int(val * 100)}%",
            damage_reflect=int(ctx.damage_taken * val)
        )


class BossVampirismEffect(IPassiveEffect):
    id = "boss_vampirism"
    name_ru = "Кровавая жатва"
    name_en = "Blood Harvest"
    description_ru = "Лечит {value}% от нанесённого урона"
    description_en = "Heal for {value}% of damage dealt"
    icon = "🩸"
    trigger = PassiveTrigger.ON_DAMAGE_DEALT
    passive_type = PassiveType.BOSS
    base_value = 0.10
    per_level = 0.02
    cooldown = 0
    max_level = PASSIVE_MAX_LEVEL
    rarity = "Legendary"

    async def on_trigger(self, ctx: PassiveContext, level: int, target=None) -> PassiveResult:
        val = self.get_value(level)
        heal = int(ctx.damage_dealt * val)
        return PassiveResult(
            triggered=True,
            message=f"{self.icon} Blood harvest: boss heals {heal} HP" if ctx.lang == "en" else f"{self.icon} Кровавая жатва: босс лечится на {heal} HP",
            healing=heal
        )


class BossCritEffect(IPassiveEffect):
    id = "boss_crit"
    name_ru = "Сокрушительный удар"
    name_en = "Critical Blow"
    description_ru = "{value}% шанс нанести x2 урон"
    description_en = "{value}% chance to deal x2 damage"
    icon = "💥"
    trigger = PassiveTrigger.ON_DAMAGE_DEALT
    passive_type = PassiveType.BOSS
    base_value = 0.15
    per_level = 0.03
    cooldown = 0
    max_level = PASSIVE_MAX_LEVEL
    rarity = "Epic"

    async def on_trigger(self, ctx: PassiveContext, level: int, target=None) -> PassiveResult:
        val = self.get_value(level)
        if random.random() < val:
            return PassiveResult(
                triggered=True,
                message=f"{self.icon} 💥 CRUSHING BLOW!" if ctx.lang == "en" else f"{self.icon} 💥 СОКРУШИТЕЛЬНЫЙ УДАР!",
                is_crit=True,
                damage_bonus=1.0
            )
        return PassiveResult(triggered=False)


class CrushingBlowEffect(IPassiveEffect):
    id = "crushing_blow"
    name_ru = "Дробящий удар"
    name_en = "Crushing Blow"
    description_ru = "{value}% шанс нанести половинный урон"
    description_en = "{value}% chance to deal half damage"
    icon = "⚡"
    trigger = PassiveTrigger.ON_DAMAGE_DEALT
    passive_type = PassiveType.BOSS
    base_value = 0.10
    per_level = 0.02
    cooldown = 10
    max_level = PASSIVE_MAX_LEVEL
    rarity = "Epic"

    async def on_trigger(self, ctx: PassiveContext, level: int, target=None) -> PassiveResult:
        val = self.get_value(level)
        if random.random() < val:
            return PassiveResult(
                triggered=True,
                message=f"{self.icon} CRUSHING BLOW! Boss damage halved!" if ctx.lang == "en" else f"{self.icon} ДРОБЯЩИЙ УДАР! Урон босса уменьшен вдвое!",
                damage_bonus=-0.5
            )
        return PassiveResult(triggered=False)


class BossArmorBoostEffect(IPassiveEffect):
    id = "armor_boost"
    name_ru = "Каменная кожа"
    name_en = "Stone Skin"
    description_ru = "Снижает входящий урон на {value}"
    description_en = "Reduce incoming damage by {value}"
    icon = "🪨"
    trigger = PassiveTrigger.ON_DAMAGE_TAKEN
    passive_type = PassiveType.BOSS
    base_value = 0.10
    per_level = 0.03
    cooldown = 0
    max_level = PASSIVE_MAX_LEVEL
    rarity = "Epic"

    async def on_trigger(self, ctx: PassiveContext, level: int, target=None) -> PassiveResult:
        val = self.get_value(level)
        return PassiveResult(
            triggered=True,
            message=f"{self.icon} Stone skin: -{int(val * 100)}% incoming dmg" if ctx.lang == "en" else f"{self.icon} Каменная кожа: -{int(val * 100)}% входящего урона",
            damage_reduction=val
        )


def register_boss_passives() -> None:
    PassiveRegistry.register(BossEnrageEffect())
    PassiveRegistry.register(BossPoisonAuraEffect())
    PassiveRegistry.register(BossReflectEffect())
    PassiveRegistry.register(BossVampirismEffect())
    PassiveRegistry.register(BossCritEffect())
    PassiveRegistry.register(CrushingBlowEffect())
    PassiveRegistry.register(BossArmorBoostEffect())