"""
game/skills/base.py — Паттерн Команда для скиллов
Позволяет добавлять новые скиллы без изменения handlers
"""
from abc import ABC, abstractmethod
from typing import Optional
import json
from pathlib import Path


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
    async def execute(self, user, target=None) -> SkillResult:
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
    cooldown = 0
    mana_cost = 0
    
    async def execute(self, user, target=None) -> SkillResult:
        if not target:
            return SkillResult(False, "Нет цели!")
        
        damage = user.get_dps()
        target.take_damage(damage)
        return SkillResult(
            True, 
            f"Нанесено {damage} урона!",
            damage=damage
        )


class HealSkill(ISkill):
    """Лечение"""
    
    name = "heal"
    name_ru = "Лечение"
    name_en = "Heal"
    description = "Восстановить 30% HP"
    cooldown = 30
    mana_cost = 10
    
    async def execute(self, user, target=None) -> SkillResult:
        heal = int(user.max_hp * 0.3)
        actual_heal = min(heal, user.max_hp - user.hp)
        user.hp += actual_heal
        
        return SkillResult(
            True,
            f"Восстановлено {actual_heal} HP!",
            healing=actual_heal
        )


class SmiteSkill(ISkill):
    """Смайт — удвоение урона (для добрых)"""
    
    name = "smite"
    name_ru = "Смайт"
    name_en = "Smite"
    description = "Божественный удар (для добрых)"
    cooldown = 60
    mana_cost = 20
    
    async def execute(self, user, target=None) -> SkillResult:
        if user.align != 1:
            return SkillResult(False, "Только добрые могут использовать Смайт!")
        
        if not target:
            return SkillResult(False, "Нет цели!")
        
        damage = user.get_dps() * 2
        target.take_damage(damage)
        
        return SkillResult(
            True,
            f"✨ СМАЙТ! Нанесено {damage} урона!",
            damage=damage,
            effect="smite"
        )


class FireballSkill(ISkill):
    """Огненный шар"""
    
    name = "fireball"
    name_ru = "Огненный шар"
    name_en = "Fireball"
    description = "Атака огнём"
    cooldown = 45
    mana_cost = 15
    
    async def execute(self, user, target=None) -> SkillResult:
        if not target:
            return SkillResult(False, "Нет цели!")
        
        damage = int(user.get_dps() * 1.5)
        target.take_damage(damage)
        
        return SkillResult(
            True,
            f"🔥 Огненный шар наносит {damage} урона!",
            damage=damage,
            effect="fire"
        )


# === Регистрация скиллов ===

def register_default_skills():
    """Зарегистрировать все скиллы при старте"""
    SkillRegistry.register(AttackSkill())
    SkillRegistry.register(HealSkill())
    SkillRegistry.register(SmiteSkill())
    SkillRegistry.register(FireballSkill())


# === Утилита для использования ===

async def use_skill(skill_name: str, user, target=None) -> SkillResult:
    """Использовать скилл — основная точка входа"""
    skill = SkillRegistry.get(skill_name)
    
    if not skill:
        return SkillResult(False, f"Неизвестный скилл: {skill_name}")
    
    if skill_name not in SkillRegistry._enabled:
        return SkillResult(False, "Скилл недоступен")
    
    return await skill.execute(user, target)


# === Пример: добавление нового скилла без изменения handlers ===

# game/skills/custom.py
class PoisonDartSkill(ISkill):
    """Ядовитый дротик — новый скилл"""
    
    name = "poison"
    name_ru = "Ядовитый дротик"
    name_en = "Poison Dart"
    description = "Отравляет врага"
    cooldown = 40
    mana_cost = 12
    
    async def execute(self, user, target=None) -> SkillResult:
        if not target:
            return SkillResult(False, "Нет цели!")
        
        damage = int(user.get_dps() * 0.8)
        target.take_damage(damage)
        # Добавляем эффект яда
        target.apply_effect("poison", 3)  # 3 раунда
        
        return SkillResult(
            True,
            f"☠️ Ядовитый дротик! {damage} урона + отравление",
            damage=damage,
            effect="poison"
        )


# Один раз зарегистрировать — и всё работает!
SkillRegistry.register(PoisonDartSkill())