"""
game/skills/passives/registry.py — регистрация и управление пассивками игроков
"""
import json
import time
import random
from pathlib import Path
from typing import Optional

import config as cfg
from db import PlayerPassive, Player

from .base import (
    PassiveRegistry, PassiveTrigger, PassiveType,
    PassiveContext, PassiveResult, xp_threshold_for_level
)

PASSIVES_JSON = Path(__file__).parent.parent.parent.parent / "data" / "passives.json"


def _load_passives_config() -> dict:
    if PASSIVES_JSON.exists():
        return json.loads(PASSIVES_JSON.read_text())
    return {}


def calc_upgrade_cost(level: int) -> int:
    """Стоимость апгрейда пассивки с level до level+1."""
    base = getattr(cfg, 'PASSIVE_UPGRADE_BASE', 100)
    scale = getattr(cfg, 'PASSIVE_UPGRADE_SCALE', 1.15)
    return int(base * (scale ** level))


async def _get_price(passive_id: str, player_uid: int) -> int:
    """Цена пассивки: базовая × прогрессия от числа купленных."""
    prices = getattr(cfg, 'PASSIVE_SKILL_PRICES', {})
    base = prices.get(passive_id, 500)
    owned = await PlayerPassive.objects.filter(player_uid=player_uid).count()
    factor = getattr(cfg, 'PASSIVE_PRICE_GROWTH_FACTOR', 1.5) ** owned
    return int(base * factor)


class PassiveSkillRegistry:
    
    @classmethod
    async def buy_passive(cls, player: Player, passive_id: str) -> tuple[bool, str]:
        """Купить пассивку за золото."""
        lang = player.lang or "ru"
        
        effect = PassiveRegistry.get(passive_id)
        if not effect:
            return False, "Пассивка не найдена" if lang != "en" else "Passive not found"
        
        existing = await PlayerPassive.objects.filter(
            player_uid=player.uid,
            passive_id=passive_id
        ).get_or_none()
        if existing:
            return False, "Уже куплено" if lang != "en" else "Already owned"
        
        level_reqs = getattr(cfg, 'PASSIVE_LEVEL_REQUIREMENTS', {})
        req_level = level_reqs.get(effect.rarity, 0)
        if player.level < req_level:
            return False, (
                f"Нужен {req_level} уровень (текущий: {player.level})"
                if lang != "en"
                else f"Requires level {req_level} (current: {player.level})"
            )
        
        price = await _get_price(passive_id, player.uid)
        if player.gold < price:
            return False, f"Нужно {price} золота, у тебя {player.gold}" if lang != "en" else f"Need {price} gold, you have {player.gold}"
        
        player.gold -= price
        await player.update(_columns=["gold"])
        
        new_passive = PlayerPassive(
            player_uid=player.uid,
            passive_id=passive_id,
            level=1,
            xp_progress=0,
            equipped=False,
            acquired_at=int(time.time()),
        )
        await new_passive.save()
        
        name = effect.get_name(lang)
        return True, f"✨ Куплено: {effect.icon} {name}!" if lang != "en" else f"✨ Purchased: {effect.icon} {name}!"
    
    @classmethod
    async def upgrade_passive(cls, player: Player, passive_id: str) -> tuple[bool, str]:
        """Прокачать пассивку на +1 уровень за золото."""
        lang = player.lang or "ru"

        effect = PassiveRegistry.get(passive_id)
        if not effect:
            return False, "Пассивка не найдена" if lang != "en" else "Passive not found"

        passive = await PlayerPassive.objects.filter(
            player_uid=player.uid,
            passive_id=passive_id
        ).get_or_none()
        if not passive:
            return False, "Сначала купи пассивку" if lang != "en" else "Buy the passive first"

        if passive.level >= getattr(cfg, 'PASSIVE_MAX_LEVEL', 100):
            return False, "Максимальный уровень!" if lang != "en" else "Max level already!"

        threshold = xp_threshold_for_level(passive.level)
        if passive.xp_progress < threshold:
            return False, (
                f"Сначала полностью изучи текущий уровень! (XP: {passive.xp_progress}/{threshold})"
                if lang != "en"
                else f"Fully master the current level first! (XP: {passive.xp_progress}/{threshold})"
            )

        cost = calc_upgrade_cost(passive.level)
        if player.gold < cost:
            return False, (
                f"Нужно {cost}💰, у тебя {player.gold}💰"
                if lang != "en"
                else f"Need {cost}💰, you have {player.gold}💰"
            )

        player.gold -= cost
        passive.level += 1
        passive.xp_progress = 0

        await player.update(_columns=["gold"])
        await passive.update(_columns=["level", "xp_progress"])

        name = effect.get_name(lang)
        return True, (
            f"⬆ {effect.icon} {name} Lv.{passive.level}!"
            if lang != "en"
            else f"⬆ {effect.icon} {name} Lv.{passive.level}!"
        )

    @classmethod
    async def equip_passive(cls, player: Player, passive_id: str) -> tuple[bool, str]:
        """Экипировать пассивку (макс 5 слотов)."""
        lang = player.lang or "ru"
        
        passive = await PlayerPassive.objects.filter(
            player_uid=player.uid,
            passive_id=passive_id
        ).get_or_none()
        if not passive:
            return False, "Нет такой пассивки" if lang != "en" else "Passive not found"
        
        if passive.equipped:
            return False, "Уже экипировано" if lang != "en" else "Already equipped"
        
        equipped = await PlayerPassive.objects.filter(
            player_uid=player.uid,
            equipped=True
        ).all()
        
        max_slots = getattr(cfg, 'PASSIVE_MAX_SLOTS', 5)
        if len(equipped) >= max_slots:
            return False, f"Слоты заполнены ({max_slots}/" + str(max_slots) + ")" if lang != "en" else f"Slots full ({max_slots}/{max_slots})"
        
        passive.equipped = True
        await passive.update(_columns=["equipped"])
        
        effect = PassiveRegistry.get(passive_id)
        name = effect.get_name(lang) if effect else passive_id
        return True, f"⚔️ Экипировано: {effect.icon if effect else '✨'} {name}"
    
    @classmethod
    async def unequip_passive(cls, player: Player, passive_id: str) -> tuple[bool, str]:
        """Снять пассивку. Расовые пассивки снять нельзя."""
        lang = player.lang or "ru"
        
        import config as cfg
        if passive_id in cfg.RACIAL_PASSIVES.values():
            return False, "Нельзя снять расовый навык!" if lang != "en" else "Cannot unequip racial skill!"
        
        passive = await PlayerPassive.objects.filter(
            player_uid=player.uid,
            passive_id=passive_id
        ).get_or_none()
        if not passive:
            return False, "Нет такой пассивки" if lang != "en" else "Passive not found"
        
        passive.equipped = False
        await passive.update(_columns=["equipped"])
        
        effect = PassiveRegistry.get(passive_id)
        name = effect.get_name(lang) if effect else passive_id
        return True, f"📦 Снято: {effect.icon if effect else '✨'} {name}"
    
    @classmethod
    async def get_equipped_passives(cls, player_uid: int) -> list[PlayerPassive]:
        """Все экипированные пассивки игрока."""
        return await PlayerPassive.objects.filter(
            player_uid=player_uid,
            equipped=True
        ).all()
    
    @classmethod
    async def get_all_passives(cls, player_uid: int) -> list[PlayerPassive]:
        """Все купленные пассивки игрока."""
        return await PlayerPassive.objects.filter(
            player_uid=player_uid
        ).order_by("-acquired_at").all()
    
    @classmethod
    async def add_xp_and_check_levelup(
        cls,
        passive: PlayerPassive
    ) -> tuple[int, int, int]:
        """
        Добавить очки опыта и проверить level up.
        Возвращает (new_xp, new_level, levels_gained).
        """
        old_level = passive.level
        passive.xp_progress += getattr(cfg, 'PASSIVE_XP_PER_TRIGGER', 1)
        
        levels_gained = 0
        max_lv = getattr(cfg, 'PASSIVE_MAX_LEVEL', 100)
        while passive.xp_progress >= xp_threshold_for_level(passive.level):
            threshold = xp_threshold_for_level(passive.level)
            passive.xp_progress -= threshold
            passive.level += 1
            levels_gained += 1
            if passive.level >= max_lv:
                passive.level = max_lv
                passive.xp_progress = xp_threshold_for_level(max_lv) - 1
                break
        
        await passive.update(_columns=["level", "xp_progress"])
        return passive.xp_progress, passive.level, levels_gained
    
    @classmethod
    async def trigger_on_damage_dealt(
        cls,
        player: Player,
        damage: int,
        is_crit: bool = False,
        target_hp_pct: float = 1.0,
        target_is_boss: bool = False
    ) -> PassiveResult:
        """Триггер ON_DAMAGE_DEALT для всех экипированных пассивок."""
        equipped = await cls.get_equipped_passives(player.uid)
        ctx = PassiveContext(
            trigger=PassiveTrigger.ON_DAMAGE_DEALT,
            player_uid=player.uid,
            damage_dealt=damage,
            is_crit=is_crit,
            player_hp_pct=player.hp / player.max_hp if player.max_hp > 0 else 1.0,
            boss_hp_pct=target_hp_pct,
            lang=player.lang or "ru",
        )
        ctx.extra["is_boss"] = target_is_boss
        
        total_heal = 0
        total_damage_bonus = 0.0
        total_poison = 0
        result = PassiveResult()
        
        for ep in equipped:
            effect = PassiveRegistry.get(ep.passive_id)
            if not effect or effect.trigger != PassiveTrigger.ON_DAMAGE_DEALT:
                continue
            if effect.passive_type != PassiveType.PLAYER:
                continue
            
            now = int(time.time())
            if ep.cooldown_until > now:
                continue
            
            res = await effect.on_trigger(ctx, ep.level)
            if res.triggered:
                ep.cooldown_until = now + effect.cooldown
                ep.last_triggered_at = now
                await ep.update(_columns=["cooldown_until", "last_triggered_at"])
                
                if res.healing:
                    total_heal += res.healing
                    result.healing += res.healing
                if res.damage_bonus:
                    total_damage_bonus += res.damage_bonus
                    result.damage_bonus += res.damage_bonus
                if res.poison_damage:
                    total_poison += res.poison_damage
                    result.poison_damage += res.poison_damage
                if res.message:
                    result.message += f"\n{res.message}"
                if res.is_crit:
                    result.is_crit = True
                
                if ep.level < getattr(cfg, 'PASSIVE_MAX_LEVEL', 100):
                    await cls.add_xp_and_check_levelup(ep)
        
        if total_heal > 0:
            player.hp = min(player.hp + total_heal, player.max_hp)
            await player.update(_columns=["hp"])
        
        result.triggered = total_heal > 0 or total_damage_bonus > 0 or total_poison > 0 or result.is_crit
        return result
    
    @classmethod
    async def trigger_on_damage_taken(
        cls,
        player: Player,
        damage: int,
        is_from_boss: bool = False
    ) -> tuple[int, PassiveResult]:
        """Триггер ON_DAMAGE_TAKEN. Возвращает (модифицированный_урон, результат)."""
        equipped = await cls.get_equipped_passives(player.uid)
        ctx = PassiveContext(
            trigger=PassiveTrigger.ON_DAMAGE_TAKEN,
            player_uid=player.uid,
            damage_taken=damage,
            lang=player.lang or "ru",
        )
        ctx.extra["is_from_boss"] = is_from_boss
        
        reflect_total = 0
        reduction_total = 0.0
        result = PassiveResult()
        
        for ep in equipped:
            effect = PassiveRegistry.get(ep.passive_id)
            if not effect or effect.trigger != PassiveTrigger.ON_DAMAGE_TAKEN:
                continue
            if effect.passive_type != PassiveType.PLAYER:
                continue
            
            now = int(time.time())
            if ep.cooldown_until > now:
                continue
            
            res = await effect.on_trigger(ctx, ep.level)
            if res.triggered:
                ep.cooldown_until = now + effect.cooldown
                ep.last_triggered_at = now
                await ep.update(_columns=["cooldown_until", "last_triggered_at"])
                
                if res.damage_reflect:
                    reflect_total += res.damage_reflect
                    result.damage_reflect += res.damage_reflect
                if res.damage_reduction:
                    reduction_total += res.damage_reduction
                    result.damage_reduction += res.damage_reduction
                if res.message:
                    result.message += f"\n{res.message}"
                
                if ep.level < getattr(cfg, 'PASSIVE_MAX_LEVEL', 100):
                    await cls.add_xp_and_check_levelup(ep)
        
        modified_damage = int(damage * (1.0 - min(1.0, reduction_total)))
        result.triggered = reflect_total > 0 or reduction_total > 0
        return modified_damage, result
    
    @classmethod
    async def trigger_on_kill(
        cls,
        player: Player,
        monster_level: int,
        base_gold: int,
        base_xp: int
    ) -> tuple[int, int, PassiveResult]:
        """Триггер ON_KILL. Возвращает (бонус_золото, бонус_xp, результат)."""
        equipped = await cls.get_equipped_passives(player.uid)
        ctx = PassiveContext(
            trigger=PassiveTrigger.ON_KILL,
            player_uid=player.uid,
            is_kill=True,
            damage_dealt=base_gold,
            extra={"monster_level": monster_level, "base_gold": base_gold, "base_xp": base_xp},
            lang=player.lang or "ru",
        )
        
        gold_bonus_mult = 1.0
        xp_bonus_mult = 1.0
        result = PassiveResult()
        
        for ep in equipped:
            effect = PassiveRegistry.get(ep.passive_id)
            if not effect or effect.trigger != PassiveTrigger.ON_KILL:
                continue
            if effect.passive_type != PassiveType.PLAYER:
                continue
            
            res = await effect.on_trigger(ctx, ep.level)
            if res.triggered:
                if res.gold_bonus:
                    gold_bonus_mult += res.gold_bonus
                    result.gold_bonus += res.gold_bonus
                if res.xp_bonus:
                    xp_bonus_mult += res.xp_bonus
                    result.xp_bonus += res.xp_bonus
                if res.message:
                    result.message += f"\n{res.message}"
                
                now = int(time.time())
                ep.cooldown_until = now + effect.cooldown
                ep.last_triggered_at = now
                await ep.update(_columns=["cooldown_until", "last_triggered_at"])
                
                if ep.level < getattr(cfg, 'PASSIVE_MAX_LEVEL', 100):
                    await cls.add_xp_and_check_levelup(ep)
        
        bonus_gold = int(base_gold * (gold_bonus_mult - 1.0))
        bonus_xp = int(base_xp * (xp_bonus_mult - 1.0))
        result.triggered = gold_bonus_mult > 1.0 or xp_bonus_mult > 1.0
        return bonus_gold, bonus_xp, result
    
    @classmethod
    async def trigger_on_tick(cls, player: Player, tick: int) -> PassiveResult:
        """Триггер ON_TICK (регенерация и т.д.)."""
        equipped = await cls.get_equipped_passives(player.uid)
        ctx = PassiveContext(
            trigger=PassiveTrigger.ON_TICK,
            player_uid=player.uid,
            tick_number=tick,
            lang=player.lang or "ru",
        )
        
        total_heal = 0
        result = PassiveResult()
        
        for ep in equipped:
            effect = PassiveRegistry.get(ep.passive_id)
            if not effect or effect.trigger != PassiveTrigger.ON_TICK:
                continue
            if effect.passive_type != PassiveType.PLAYER:
                continue
            
            res = await effect.on_trigger(ctx, ep.level)
            if res.triggered:
                if res.healing:
                    total_heal += res.healing
                    result.healing += res.healing
                if res.message:
                    result.message += f"\n{res.message}"
                
                now = int(time.time())
                ep.cooldown_until = now + effect.cooldown
                ep.last_triggered_at = now
                await ep.update(_columns=["cooldown_until", "last_triggered_at"])
                
                if ep.level < getattr(cfg, 'PASSIVE_MAX_LEVEL', 100):
                    await cls.add_xp_and_check_levelup(ep)
        
        if total_heal > 0:
            player.hp = min(player.hp + total_heal, player.max_hp)
            await player.update(_columns=["hp"])
        
        result.triggered = total_heal > 0
        return result
    
    @classmethod
    async def trigger_on_encounter(cls, player: Player) -> tuple[bool, bool, PassiveResult]:
        """Триггер ON_ENCOUNTER. Возвращает (dodge_success, first_strike_active, result)."""
        equipped = await cls.get_equipped_passives(player.uid)
        ctx = PassiveContext(
            trigger=PassiveTrigger.ON_ENCOUNTER,
            player_uid=player.uid,
            lang=player.lang or "ru",
        )
        
        dodge_success = False
        first_strike = False
        result = PassiveResult()
        
        for ep in equipped:
            effect = PassiveRegistry.get(ep.passive_id)
            if not effect or effect.trigger != PassiveTrigger.ON_ENCOUNTER:
                continue
            if effect.passive_type != PassiveType.PLAYER:
                continue
            
            res = await effect.on_trigger(ctx, ep.level)
            if res.triggered:
                if res.is_dodge:
                    dodge_success = True
                    result.is_dodge = True
                if res.damage_bonus > 0:
                    first_strike = True
                    result.damage_bonus = res.damage_bonus
                if res.message:
                    result.message += f"\n{res.message}"
                
                now = int(time.time())
                ep.cooldown_until = now + effect.cooldown
                ep.last_triggered_at = now
                await ep.update(_columns=["cooldown_until", "last_triggered_at"])
                
                if ep.level < getattr(cfg, 'PASSIVE_MAX_LEVEL', 100):
                    await cls.add_xp_and_check_levelup(ep)
        
        result.triggered = dodge_success or first_strike
        return dodge_success, first_strike, result
    
    @classmethod
    async def get_passive_info(cls, player: Player, passive_id: str) -> Optional[PlayerPassive]:
        return await PlayerPassive.objects.filter(
            player_uid=player.uid,
            passive_id=passive_id
        ).get_or_none()
    
    @classmethod
    async def format_passives_list(cls, player: Player, equipped_only: bool = False) -> str:
        """Форматирует список пассивок игрока."""
        lang = player.lang or "ru"
        
        if equipped_only:
            passives = await cls.get_equipped_passives(player.uid)
        else:
            passives = await cls.get_all_passives(player.uid)
        
        if not passives:
            return "📭 Нет пассивок" if lang != "en" else "📭 No passives"
        
        lines = []
        now = int(time.time())
        for p in passives:
            effect = PassiveRegistry.get(p.passive_id)
            if not effect:
                continue
            
            icon = effect.icon
            name = effect.get_name(lang)
            level = p.level
            threshold = xp_threshold_for_level(level)
            xp = p.xp_progress
            
            bar_len = 10
            filled = min(bar_len, int((xp / threshold) * bar_len) if threshold > 0 else 0)
            bar = "█" * filled + "░" * (bar_len - filled)
            
            cooldown_tag = ""
            if p.cooldown_until > now:
                cooldown_tag = " ⏳"
            
            eq_mark = "⚔️" if p.equipped else "📦"
            lines.append(f"{icon} {eq_mark} {name} Lv.{level}{cooldown_tag} [{bar}] {xp}/{threshold}")
        
        return "\n".join(lines)
    
    @classmethod
    def init_passives_from_json(cls) -> None:
        """Инициализировать пассивки из JSON при старте."""
        if PassiveRegistry.is_loaded():
            return
        PassiveRegistry.load_from_json(PASSIVES_JSON)