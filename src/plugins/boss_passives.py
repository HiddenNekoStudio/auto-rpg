"""
plugins/boss_passives.py — пассивные навыки боссов

Босс получает случайные пассивки при каждой встрече.
Интеграция: resolve_battle() в game/bosses.py.
"""
import logging
import random
import time
from typing import Optional, Any
from dataclasses import dataclass

from plugins.base import GamePlugin, PluginMetadata
from plugins.registry import PluginRegistry

logger = logging.getLogger(__name__)

METADATA = PluginMetadata(
    name="boss_passives",
    version="1.0.0",
    description="Пассивные навыки боссов — рандомные эффекты при встрече",
    author="AutoRPG",
)

BOSS_PASSIVE_RARITIES = ["Epic", "Legendary"]


@dataclass
class BossActivePassive:
    passive_id: str
    level: int = 1
    cooldown_until: int = 0
    last_triggered_at: int = 0


class BossPassiveManager:
    """Управление активными пассивками босса."""
    
    _cache: dict[str, list[BossActivePassive]] = {}
    _cooldown_cache: dict[str, int] = {}
    
    COOLDOWN = 7200
    
    @classmethod
    def clear_boss_passives(cls, boss_id: str) -> None:
        cls._cache.pop(boss_id, None)
        cls._cooldown_cache.pop(boss_id, None)
    
    @classmethod
    def assign_passives(cls, boss_id: str, boss_level: int) -> list[BossActivePassive]:
        """Выдать случайные пассивки боссу при встрече."""
        from game.skills.passives.base import PassiveRegistry, PassiveType
        
        cached = cls._cache.get(boss_id, None)
        if cached:
            return cached
        
        last_assigned = cls._cooldown_cache.get(boss_id, 0)
        now = int(time.time())
        if now - last_assigned < cls.COOLDOWN:
            return []
        
        boss_passives = PassiveRegistry.by_type(PassiveType.BOSS)
        
        pool = {
            pid: eff for pid, eff in boss_passives.items()
            if eff.rarity in BOSS_PASSIVE_RARITIES
        }
        
        if not pool:
            pool = boss_passives
        
        count = random.randint(1, 2)
        selected = random.sample(list(pool.keys()), min(count, len(pool)))
        
        active_passives = []
        for pid in selected:
            level = max(1, min(boss_level // 10 + 1, 10))
            active_passives.append(BossActivePassive(
                passive_id=pid,
                level=level
            ))
        
        cls._cache[boss_id] = active_passives
        cls._cooldown_cache[boss_id] = now
        
        logger.info(f"Boss {boss_id} assigned passives: {[p.passive_id for p in active_passives]}")
        return active_passives
    
    @classmethod
    def get_passives(cls, boss_id: str) -> list[BossActivePassive]:
        return cls._cache.get(boss_id, [])
    
    @classmethod
    async def trigger_boss_passive_on_dealt(
        cls,
        boss_id: str,
        damage: int,
        boss_hp_pct: float = 1.0,
        lang: str = "ru"
    ) -> tuple[int, float, str, bool, int, int]:
        """
        Триггер боссовых пассивок при нанесении урона.
        Возвращает (бонус_урон, снижение_урона, сообщение, крит?, хиление, яд_урон)
        """
        from game.skills.passives.base import PassiveRegistry, PassiveTrigger, PassiveContext
        
        active_passives = cls.get_passives(boss_id)
        if not active_passives:
            return 0, 0.0, "", False, 0, 0
        
        ctx = PassiveContext(
            trigger=PassiveTrigger.ON_DAMAGE_DEALT,
            boss_id=boss_id,
            damage_dealt=damage,
            boss_hp_pct=boss_hp_pct,
            lang=lang,
        )
        
        bonus_mult = 0.0
        reflect_damage = 0
        messages = []
        is_crit = False
        stun = False
        healing = 0
        poison_damage = 0
        
        now = int(time.time())
        
        for ap in active_passives:
            effect = PassiveRegistry.get(ap.passive_id)
            if not effect:
                continue
            
            if ap.cooldown_until > now:
                continue
            
            if effect.trigger not in (PassiveTrigger.ON_DAMAGE_DEALT, PassiveTrigger.ON_HP_BELOW):
                continue
            
            if effect.trigger == PassiveTrigger.ON_HP_BELOW:
                ctx.trigger = PassiveTrigger.ON_HP_BELOW
            
            res = await effect.on_trigger(ctx, ap.level)
            if res.triggered:
                ap.cooldown_until = now + effect.cooldown
                ap.last_triggered_at = now
                
                if res.damage_bonus:
                    bonus_mult = (1 + bonus_mult) * (1 + res.damage_bonus) - 1
                if res.damage_reflect:
                    reflect_damage += res.damage_reflect
                if res.healing:
                    healing += res.healing
                if res.poison_damage:
                    poison_damage += res.poison_damage
                if res.message:
                    messages.append(res.message)
                if res.is_crit:
                    is_crit = True
                if res.stun:
                    stun = True
        
        msg = " ".join(messages)
        return bonus_mult, reflect_damage, msg, is_crit or stun, healing, poison_damage
    
    @classmethod
    async def trigger_boss_passive_on_taken(
        cls,
        boss_id: str,
        damage: int,
        lang: str = "ru"
    ) -> tuple[int, float, str]:
        """
        Триггер боссовых пассивок при получении урона.
        Возвращает (отражённый_урон, снижение_урона, сообщение)
        """
        from game.skills.passives.base import PassiveRegistry, PassiveTrigger, PassiveContext
        
        active_passives = cls.get_passives(boss_id)
        if not active_passives:
            return 0, 0.0, ""
        
        ctx = PassiveContext(
            trigger=PassiveTrigger.ON_DAMAGE_TAKEN,
            boss_id=boss_id,
            damage_taken=damage,
            lang=lang,
        )
        
        reflect = 0
        reduction = 0.0
        messages = []
        
        now = int(time.time())
        
        for ap in active_passives:
            effect = PassiveRegistry.get(ap.passive_id)
            if not effect:
                continue
            
            if ap.cooldown_until > now:
                continue
            
            if effect.trigger != PassiveTrigger.ON_DAMAGE_TAKEN:
                continue
            
            res = await effect.on_trigger(ctx, ap.level)
            if res.triggered:
                ap.cooldown_until = now + effect.cooldown
                ap.last_triggered_at = now
                
                if res.damage_reflect:
                    reflect += res.damage_reflect
                if res.damage_reduction:
                    reduction += res.damage_reduction
                if res.message:
                    messages.append(res.message)
        
        msg = " ".join(messages)
        return reflect, reduction, msg
    
    @classmethod
    async def get_boss_passive_descriptions(cls, boss_id: str, lang: str = "ru") -> str:
        """Получить описание всех активных пассивок босса."""
        from game.skills.passives.base import PassiveRegistry
        
        active_passives = cls.get_passives(boss_id)
        if not active_passives:
            return ""
        
        lines = []
        for ap in active_passives:
            effect = PassiveRegistry.get(ap.passive_id)
            if not effect:
                continue
            
            icon = effect.icon
            name = effect.get_name(lang)
            level = ap.level
            val = effect.get_value(level)
            
            if val < 1:
                val_str = f"{int(val * 100)}%"
            else:
                val_str = f"{int(val)}"
            
            lines.append(f"{icon} {name} Lv.{level} ({val_str})")
        
        return " | ".join(lines)


@PluginRegistry.register(
    "boss_passives",
    description="Пассивные навыки боссов — рандомные эффекты при встрече",
    author="AutoRPG",
)
class BossPassivesPlugin(GamePlugin):
    metadata = METADATA

    async def on_load(self) -> None:
        logger.info("Boss passives plugin loaded")
    
    async def on_unload(self) -> None:
        BossPassiveManager._cache.clear()
        BossPassiveManager._cooldown_cache.clear()
        logger.info("Boss passives plugin unloaded")
    
    async def on_player_action(
        self,
        player_uid: int,
        action: str,
        data: dict[str, Any]
    ) -> Optional[str]:
        return None
    
    async def on_game_tick(self, tick_number: int, bot=None) -> Optional[str]:
        return None


def assign_boss_passives_on_encounter(boss_id: str, boss_level: int) -> list[BossActivePassive]:
    return BossPassiveManager.assign_passives(boss_id, boss_level)


async def get_boss_passive_display(boss_id: str, lang: str = "ru") -> str:
    return await BossPassiveManager.get_boss_passive_descriptions(boss_id, lang)