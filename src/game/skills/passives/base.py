"""
game/skills/passives/base.py — система пассивных навыков

Архитектура:
- IPassiveEffect — интерфейс пассивки
- PassiveTrigger — enum триггеров
- PassiveContext — контекст при срабатывании
- PassiveResult — результат срабатывания
- PassiveRegistry — реестр всех пассивок
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import json
from pathlib import Path


class PassiveTrigger(Enum):
    ON_DAMAGE_DEALT  = "on_damage_dealt"
    ON_DAMAGE_TAKEN  = "on_damage_taken"
    ON_KILL          = "on_kill"
    ON_TICK           = "on_tick"
    ON_ENCOUNTER      = "on_encounter"
    ON_HP_BELOW       = "on_hp_below"
    ON_LEVEL_UP       = "on_level_up"


class PassiveType(Enum):
    PLAYER = "player"
    BOSS   = "boss"


@dataclass
class PassiveContext:
    """Контекст при срабатывании пассивки."""
    trigger: PassiveTrigger
    
    player_uid: int = 0
    boss_id: str = ""
    
    damage_dealt: int = 0
    damage_taken: int = 0
    
    is_kill: bool = False
    is_crit: bool = False
    is_dodge: bool = False
    
    tick_number: int = 0
    
    player_hp_pct: float = 1.0
    boss_hp_pct: float = 1.0
    
    lang: str = "ru"

    extra: dict = field(default_factory=dict)


@dataclass
class PassiveResult:
    """Результат срабатывания пассивки."""
    triggered: bool = False
    message: str = ""
    healing: int = 0
    damage_bonus: float = 0.0
    damage_reflect: int = 0
    damage_reduction: float = 0.0
    gold_bonus: float = 0.0
    xp_bonus: float = 0.0
    is_crit: bool = False
    poison_damage: int = 0
    stun: bool = False
    extra: dict = field(default_factory=dict)


class IPassiveEffect(ABC):
    """Интерфейс пассивного эффекта."""
    
    id: str = ""
    name_ru: str = ""
    name_en: str = ""
    description_ru: str = ""
    description_en: str = ""
    icon: str = "✨"
    
    trigger: PassiveTrigger = PassiveTrigger.ON_DAMAGE_DEALT
    passive_type: PassiveType = PassiveType.PLAYER
    
    base_value: float = 0.0
    per_level: float = 0.0
    cooldown: int = 0
    max_level: int = 100
    rarity: str = "Common"
    
    _config: dict = None
    
    def configure(self, config: dict) -> None:
        """Загрузить конфиг из passives.json."""
        self._config = config
        self.base_value = config.get("base_value", self.base_value)
        self.per_level = config.get("per_level", self.per_level)
        self.cooldown = config.get("cooldown", self.cooldown)
        self.max_level = config.get("max_level", self.max_level)
        self.rarity = config.get("rarity", self.rarity)
        if config.get("name_ru"):
            self.name_ru = config["name_ru"]
        if config.get("name_en"):
            self.name_en = config["name_en"]
        if config.get("description_ru"):
            self.description_ru = config["description_ru"]
        if config.get("description_en"):
            self.description_en = config["description_en"]
        if config.get("icon"):
            self.icon = config["icon"]
    
    def get_value(self, level: int) -> float:
        """Расчёт значения эффекта на данном уровне."""
        return self.base_value + (level - 1) * self.per_level
    
    def get_formatted_value(self, level: int) -> str:
        """Форматированное значение для отображения."""
        val = self.get_value(level)
        if self.base_value < 1:
            return f"{int(val * 100)}%"
        return f"{val:.1f}"
    
    def get_display_description(self, level: int, lang: str = "ru") -> str:
        """Описание с подставленными значениями."""
        desc = self.description_ru if lang == "ru" else self.description_en
        val = self.get_value(level)
        if self.base_value < 1:
            val_str = f"{int(val * 100)}%"
        else:
            val_str = f"{val:.0f}" if val == int(val) else f"{val:.1f}"
        return desc.replace("{value}", val_str)
    
    def get_name(self, lang: str = "ru") -> str:
        return self.name_ru if lang == "ru" else self.name_en
    
    async def on_trigger(self, ctx: PassiveContext, level: int) -> PassiveResult:
        """Вызывается при срабатывании. Переопределить в подклассах."""
        return PassiveResult(triggered=False)


class PassiveRegistry:
    """Реестр всех пассивных эффектов."""
    
    _passives: dict[str, IPassiveEffect] = {}
    _loaded: bool = False
    
    @classmethod
    def register(cls, effect: IPassiveEffect) -> None:
        cls._passives[effect.id] = effect
    
    @classmethod
    def get(cls, passive_id: str) -> Optional[IPassiveEffect]:
        return cls._passives.get(passive_id)
    
    @classmethod
    def all(cls) -> dict[str, IPassiveEffect]:
        return cls._passives.copy()
    
    @classmethod
    def by_type(cls, ptype: PassiveType) -> dict[str, IPassiveEffect]:
        return {
            pid: p for pid, p in cls._passives.items()
            if p.passive_type == ptype
        }
    
    @classmethod
    def by_trigger(cls, trigger: PassiveTrigger) -> dict[str, IPassiveEffect]:
        return {
            pid: p for pid, p in cls._passives.items()
            if p.trigger == trigger
        }
    
    @classmethod
    def by_rarity(cls, rarity: str) -> dict[str, IPassiveEffect]:
        return {
            pid: p for pid, p in cls._passives.items()
            if p.rarity == rarity
        }
    
    @classmethod
    def load_from_json(cls, json_path: Path) -> None:
        """Загрузить конфиг из JSON."""
        if not json_path.exists():
            return
        data = json.loads(json_path.read_text())
        
        all_passives = {}
        all_passives.update(data.get("passives", {}))
        all_passives.update(data.get("boss_passives", {}))
        
        for pid, cfg_data in all_passives.items():
            effect = cls.get(pid)
            if effect:
                effect.configure(cfg_data)
        
        cls._loaded = True
    
    @classmethod
    def is_loaded(cls) -> bool:
        return cls._loaded


def xp_threshold_for_level(level: int) -> int:
    """Порог очков для перехода на следующий уровень. Lv1→2=100, Lv2→3=200..."""
    from config import PASSIVE_LEVEL_UP_XP_BASE
    return PASSIVE_LEVEL_UP_XP_BASE * level


def progress_percent(xp: int, level: int) -> float:
    """Процент прогресса к следующему уровню."""
    threshold = xp_threshold_for_level(level)
    if threshold == 0:
        return 0.0
    return min(1.0, xp / threshold)