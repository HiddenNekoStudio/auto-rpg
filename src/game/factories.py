"""
game/factories.py — Паттерн Фабрика для создания мобов
Позволяет добавлять новых монстров без изменения основного кода
"""
import random
import json
from pathlib import Path
from abc import ABC, abstractmethod


class IMonster(ABC):
    """Интерфейс монстра"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @property
    @abstractmethod
    def name_en(self) -> str:
        pass
    
    @property
    @abstractmethod
    def level(self) -> int:
        pass
    
    @property
    @abstractmethod
    def dps(self) -> int:
        pass
    
    @property
    @abstractmethod
    def xp_reward(self) -> int:
        pass
    
    @property
    @abstractmethod
    def rank(self) -> str:
        pass
    
    def get_display_name(self, lang: str = "ru") -> str:
        return self.name_en if lang == "en" else self.name


class MonsterConfig:
    """Загрузка конфигурации монстров из JSON"""
    
    def __init__(self):
        self._data = []
        self._load()
    
    def _load(self):
        config_path = Path(__file__).parent / "data" / "monsters.json"
        if config_path.exists():
            with open(config_path) as f:
                self._data = json.load(f)
        else:
            # Дефолтные данные
            self._data = self._default_monsters()
    
    def _default_monsters(self) -> list[dict]:
        return [
            {"id": "goblin", "name_ru": "Больной Гоблин", "name_en": "Sick Goblin", 
             "level_mult": 1.0, "dps_mult": 1.0, "xp_mult": 1.0, "rank": "Common"},
            {"id": "rat", "name_ru": "Бешеная Крыса", "name_en": "Mad Rat",
             "level_mult": 0.5, "dps_mult": 0.5, "xp_mult": 0.5, "rank": "Common"},
            {"id": "dragon", "name_ru": "Позолоченный Дракон", "name_en": "Gilded Dragon",
             "level_mult": 3.0, "dps_mult": 5.0, "xp_mult": 5.0, "rank": "Legendary"},
        ]
    
    def get_random(self) -> dict:
        """Случайный монстр из конфига"""
        weights = [m.get("weight", 1.0) for m in self._data]
        chosen = random.choices(self._data, weights)[0]
        return chosen
    
    def get_by_id(self, monster_id: str) -> dict:
        """Получить монстра по ID"""
        for m in self._data:
            if m.get("id") == monster_id:
                return m
        return self._data[0]
    
    def all_ids(self) -> list[str]:
        """Все ID монстров"""
        return [m.get("id") for m in self._data]


class MonsterFactory:
    """Фабрика монстров — создаёт экземпляры по ID"""
    
    _config = None
    _custom_classes: dict[str, type] = {}
    
    @classmethod
    def get_config(cls) -> MonsterConfig:
        if cls._config is None:
            cls._config = MonsterConfig()
        return cls._config
    
    @classmethod
    def register_custom(cls, monster_id: str, monster_class: type):
        """Зарегистрировать кастомный класс монстра"""
        cls._custom_classes[monster_id] = monster_class
    
    @classmethod
    def create(cls, monster_id: str, player_level: int = 1) -> IMonster:
        """Создать монстра по ID"""
        # Проверяем кастомный класс
        if monster_id in cls._custom_classes:
            return cls._custom_classes[monster_id](player_level)
        
        # Используем конфиг
        config = cls.get_config()
        data = config.get_by_id(monster_id)
        
        return Monster(
            monster_id=monster_id,
            player_level=player_level,
            name_ru=data["name_ru"],
            name_en=data["name_en"],
            level_mult=data["level_mult"],
            dps_mult=data["dps_mult"],
            xp_mult=data["xp_mult"],
            rank=data["rank"],
        )
    
    @classmethod
    def create_random(cls, player_level: int = 1) -> IMonster:
        """Создать случайного монстра"""
        config = cls.get_config()
        data = config.get_random()
        return cls.create(data["id"], player_level)


class Monster(IMonster):
    """Реализация монстра из конфига"""
    __slots__ = ('_id', '_level', '_name_ru', '_name_en', '_dps', '_xp', '_rank')
    
    def __init__(self, monster_id: str, player_level: int, 
                 name_ru: str, name_en: str,
                 level_mult: float, dps_mult: float, 
                 xp_mult: float, rank: str):
        self._id = monster_id
        self._level = int(player_level * level_mult)
        self._name_ru = name_ru
        self._name_en = name_en
        self._dps = int(player_level * 10 * dps_mult)
        self._xp = int(player_level * 5 * xp_mult)
        self._rank = rank
    
    @property
    def name(self) -> str:
        return self._name_ru
    
    @property
    def name_en(self) -> str:
        return self._name_en
    
    @property
    def level(self) -> int:
        return self._level
    
    @property
    def dps(self) -> int:
        return self._dps
    
    @property
    def xp_reward(self) -> int:
        return self._xp
    
    @property
    def rank(self) -> str:
        return self._rank


# === Пример кастомного монстра ===

class BossDragon(IMonster):
    """Босс Дракон — переопределяет логику"""
    __slots__ = ('_level', '_name_ru', '_name_en', '_dps', '_xp', '_rank')
    
    def __init__(self, player_level: int):
        self._level = player_level * 3
        self._name_ru = "Древний Дракон"
        self._name_en = "Ancient Dragon"
        self._dps = player_level * 50
        self._xp = player_level * 20
        self._rank = "Legendary"
    
    @property
    def rank(self) -> str:
        return "Legendary"
    
    @property
    def dps(self) -> int:
        return self._dps


# === Утилита для Battle ===
def create_encounter(player_level: int) -> tuple[IMonster, int]:
    """Создать encounter для игрока — основная точка входа"""
    monster = MonsterFactory.create_random(player_level)
    return monster, monster.xp_reward