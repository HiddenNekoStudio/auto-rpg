"""
game/skills/base.py — Паттерн Команда для скиллов
Позволяет добавлять новые скиллы без изменения handlers
"""
from abc import ABC, abstractmethod
from typing import Optional
import json
from pathlib import Path


def active_skill_xp_threshold(level: int) -> int:
    """Порог XP для следующего уровня активного скилла."""
    import config as _cfg
    return _cfg.ACTIVE_SKILL_LEVEL_UP_XP_BASE * level


class SkillResult:
    """Результат выполнения скилла"""
    __slots__ = ('success', 'message', 'damage', 'healing', 'effect')
    
    def __init__(self, success: bool, message: str, damage: int = 0, 
                 healing: int = 0, effect: str = None):
        self.success = success
        self.message = message
        self.damage = damage
        self.healing = healing
        self.effect = effect


class ISkill(ABC):
    """Интерфейс скилла"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """ID скилла"""
        pass
    
    @property
    @abstractmethod
    def name_ru(self) -> str:
        """Название на русском"""
        pass
    
    @property
    @abstractmethod
    def name_en(self) -> str:
        """Название на английском"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Описание"""
        pass
    
    @property
    @abstractmethod
    def cooldown(self) -> int:
        """Кулдаун в секундах"""
        pass
    
    @property
    @abstractmethod
    def mana_cost(self) -> int:
        """Мана (если есть)"""
        pass
    
    @abstractmethod
    async def execute(self, user, target=None, lang: str = "ru") -> SkillResult:
        """Выполнить скилл"""
        pass
    
    def get_display_name(self, lang: str = "ru") -> str:
        return self.name_en if lang == "en" else self.name_ru


class SkillRegistry:
    """Реестр всех скиллов"""
    
    _skills: dict[str, ISkill] = {}
    _enabled: set[str] = set()
    
    @classmethod
    def register(cls, skill: ISkill):
        """Зарегистрировать скилл"""
        cls._skills[skill.name] = skill
        cls._enabled.add(skill.name)
    
    @classmethod
    def unregister(cls, skill_name: str):
        """Убрать скилл"""
        if skill_name in cls._skills:
            del cls._skills[skill_name]
        cls._enabled.discard(skill_name)
    
    @classmethod
    def get(cls, skill_name: str) -> Optional[ISkill]:
        """Получить скилл по имени"""
        return cls._skills.get(skill_name)
    
    @classmethod
    def all(cls) -> dict[str, ISkill]:
        """Все доступные скиллы"""
        return {k: v for k, v in cls._skills.items() if k in cls._enabled}
    
    @classmethod
    def list_names(cls) -> list[str]:
        """Список имён скиллов"""
        return list(cls.all().keys())
    
    @classmethod
    def set_enabled(cls, skill_name: str, enabled: bool):
        """Включить/выключить скилл"""
        if enabled:
            cls._enabled.add(skill_name)
        else:
            cls._enabled.discard(skill_name)


# === Базовые скиллы ===

class AttackSkill(ISkill):
    """Атака — базовый скилл"""
    
    name = "attack"
    name_ru = "Атака"
    name_en = "Attack"
    description = "Атаковать врага"
    description_en = "Attack the enemy"
    cooldown = 0
    mana_cost = 0
    
    async def execute(self, user, target=None, lang: str = "ru") -> SkillResult:
        if not target:
            return SkillResult(False, "No target!" if lang == "en" else "Нет цели!")
        
        damage = user.get_dps()
        target.take_damage(damage)
        return SkillResult(
            True, 
            f"Dealt {damage} damage!" if lang == "en" else f"Нанесено {damage} урона!",
            damage=damage
        )


class HealSkill(ISkill):
    """Лечение"""
    
    name = "heal"
    name_ru = "Лечение"
    name_en = "Heal"
    description = "Восстановить 30% HP"
    description_en = "Restore 30% HP"
    cooldown = 30
    mana_cost = 10
    
    async def execute(self, user, target=None, lang: str = "ru") -> SkillResult:
        heal = int(user.max_hp * 0.3)
        actual_heal = min(heal, user.max_hp - user.hp)
        user.hp += actual_heal
        
        return SkillResult(
            True,
            f"Restored {actual_heal} HP!" if lang == "en" else f"Восстановлено {actual_heal} HP!",
            healing=actual_heal
        )


class SmiteSkill(ISkill):
    """Смайт — удвоение урона (для добрых)"""
    
    name = "smite"
    name_ru = "Смайт"
    name_en = "Smite"
    description = "Божественный удар (для добрых)"
    description_en = "Divine strike (for good characters)"
    cooldown = 60
    mana_cost = 20
    
    async def execute(self, user, target=None, lang: str = "ru") -> SkillResult:
        if user.align != 1:
            return SkillResult(False, "Only good characters can use Smite!" if lang == "en" else "Только добрые могут использовать Смайт!")
        
        if not target:
            return SkillResult(False, "No target!" if lang == "en" else "Нет цели!")
        
        damage = user.get_dps() * 2
        target.take_damage(damage)
        
        return SkillResult(
            True,
            f"✨ SMITE! Dealt {damage} damage!" if lang == "en" else f"✨ СМАЙТ! Нанесено {damage} урона!",
            damage=damage,
            effect="smite"
        )


class FireballSkill(ISkill):
    """Огненный шар"""
    
    name = "fireball"
    name_ru = "Огненный шар"
    name_en = "Fireball"
    description = "Атака огнём"
    description_en = "Fire attack"
    cooldown = 45
    mana_cost = 15
    
    async def execute(self, user, target=None, lang: str = "ru") -> SkillResult:
        if not target:
            return SkillResult(False, "No target!" if lang == "en" else "Нет цели!")
        
        damage = int(user.get_dps() * 1.5)
        target.take_damage(damage)
        
        return SkillResult(
            True,
            f"🔥 Fireball deals {damage} damage!" if lang == "en" else f"🔥 Огненный шар наносит {damage} урона!",
            damage=damage,
            effect="fire"
        )


# === Регистрация скиллов (авто при импорте) ===

SkillRegistry.register(AttackSkill())
SkillRegistry.register(HealSkill())
SkillRegistry.register(SmiteSkill())
SkillRegistry.register(FireballSkill())


# === Утилита для использования ===

async def use_skill(skill_name: str, user, target=None, lang: str = "ru") -> SkillResult:
    """Использовать скилл — основная точка входа"""
    skill = SkillRegistry.get(skill_name)
    
    if not skill:
        return SkillResult(False, f"Unknown skill: {skill_name}" if lang == "en" else f"Неизвестный скилл: {skill_name}")
    
    if skill_name not in SkillRegistry._enabled:
        return SkillResult(False, "Skill not available" if lang == "en" else "Скилл недоступен")
    
    return await skill.execute(user, target, lang=lang)


class PoisonDartSkill(ISkill):
    """Ядовитый дротик — новый скилл"""
    
    name = "poison"
    name_ru = "Ядовитый дротик"
    name_en = "Poison Dart"
    description = "Отравляет врага"
    description_en = "Poisons the enemy"
    cooldown = 40
    mana_cost = 12
    
    async def execute(self, user, target=None, lang: str = "ru") -> SkillResult:
        if not target:
            return SkillResult(False, "No target!" if lang == "en" else "Нет цели!")
        
        damage = int(user.get_dps() * 0.8)
        target.take_damage(damage)
        
        return SkillResult(
            True,
            f"☠️ Poison Dart! {damage} damage + poison" if lang == "en" else f"☠️ Ядовитый дротик! {damage} урона + отравление",
            damage=damage,
            effect="poison"
        )


class PurifyingLightSkill(ISkill):
    """Очищающий свет — навык расы Human"""
    name = "purifying_light"
    name_ru = "Очищающий свет"
    name_en = "Purifying Light"
    description = "Лечение HP"
    description_en = "Heal HP"
    cooldown = 90
    mana_cost = 20

    @staticmethod
    def get_heal_pct(level: int) -> float:
        return min(0.50, 0.25 + (level - 1) * 0.01)

    async def execute(self, user, target=None, lang: str = "ru") -> SkillResult:
        lvl = 1
        try:
            from db import PlayerActiveSkill
            rec = await PlayerActiveSkill.objects.filter(
                player_uid=user.uid, skill_id=self.name
            ).get_or_none()
            if rec:
                lvl = rec.level
        except Exception:
            pass
        pct = self.get_heal_pct(lvl)
        heal = int(user.max_hp * pct)
        actual_heal = min(heal, user.max_hp - user.hp)
        user.hp += actual_heal
        return SkillResult(
            True,
            f"✨ Purifying Light Lv.{lvl}: +{actual_heal} HP!"
            if lang == "en"
            else f"✨ Очищающий свет Lv.{lvl}: +{actual_heal} HP!",
            healing=actual_heal
        )


class SeismicSlamSkill(ISkill):
    """Сейсмический удар — навык расы Dwarf"""
    name = "seismic_slam"
    name_ru = "Сейсмический удар"
    name_en = "Seismic Slam"
    description = "Мощный удар"
    description_en = "Powerful strike"
    cooldown = 60
    mana_cost = 25

    @staticmethod
    def get_damage_mult(level: int) -> float:
        return min(4.0, 2.0 + (level - 1) * 0.1)

    async def execute(self, user, target=None, lang: str = "ru") -> SkillResult:
        if not target:
            return SkillResult(False, "No target!" if lang == "en" else "Нет цели!")
        lvl = 1
        try:
            from db import PlayerActiveSkill
            rec = await PlayerActiveSkill.objects.filter(
                player_uid=user.uid, skill_id=self.name
            ).get_or_none()
            if rec:
                lvl = rec.level
        except Exception:
            pass
        mult = self.get_damage_mult(lvl)
        damage = int(user.get_dps() * mult)
        target.take_damage(damage)
        return SkillResult(
            True,
            f"💥 Seismic Slam Lv.{lvl}: {damage} dmg (x{mult})!"
            if lang == "en"
            else f"💥 Сейсмический удар Lv.{lvl}: {damage} урона (x{mult})!",
            damage=damage,
            effect="stun"
        )


class QuickVolleySkill(ISkill):
    """Быстрый залп — навык расы Elf"""
    name = "quick_volley"
    name_ru = "Быстрый залп"
    name_en = "Quick Volley"
    description = "3 быстрых атаки"
    description_en = "3 quick attacks"
    cooldown = 45
    mana_cost = 15

    @staticmethod
    def get_hit_mult(level: int) -> float:
        return min(1.0, 0.6 + (level - 1) * 0.02)

    async def execute(self, user, target=None, lang: str = "ru") -> SkillResult:
        if not target:
            return SkillResult(False, "No target!" if lang == "en" else "Нет цели!")
        lvl = 1
        try:
            from db import PlayerActiveSkill
            rec = await PlayerActiveSkill.objects.filter(
                player_uid=user.uid, skill_id=self.name
            ).get_or_none()
            if rec:
                lvl = rec.level
        except Exception:
            pass
        mult = self.get_hit_mult(lvl)
        base_dmg = user.get_dps()
        total_dmg = 0
        for i in range(3):
            hit = int(base_dmg * mult)
            target.take_damage(hit)
            total_dmg += hit
        return SkillResult(
            True,
            f"🏹 Quick Volley Lv.{lvl}: 3×{mult:.1f} = {total_dmg} dmg!"
            if lang == "en"
            else f"🏹 Быстрый залп Lv.{lvl}: 3×{mult:.1f} = {total_dmg} урона!",
            damage=total_dmg,
            effect="multi_strike"
        )


# PoisonDartSkill — авторегистрация
SkillRegistry.register(PoisonDartSkill())
SkillRegistry.register(PurifyingLightSkill())
SkillRegistry.register(SeismicSlamSkill())
SkillRegistry.register(QuickVolleySkill())