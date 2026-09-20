"""
plugins/base.py — Base Plugin Class

Базовый класс для игровых плагинов (кланы, рейды и т.д.).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class PluginMetadata:
    """Метаданные плагина."""
    name: str
    version: str
    description: str = ""
    author: str = ""


class GamePlugin(ABC):
    """Базовый класс для игровых плагинов."""
    
    metadata: PluginMetadata
    
    @abstractmethod
    async def on_load(self) -> None:
        """Вызывается при загрузке плагина."""
        pass
    
    @abstractmethod
    async def on_unload(self) -> None:
        """Вызывается при выгрузке плагина."""
        pass
    
    @abstractmethod
    async def on_player_action(
        self, 
        player_uid: int, 
        action: str, 
        data: dict[str, Any]
    ) -> Optional[str]:
        """
        Вызывается при действиях игрока.
        
        Args:
            player_uid: ID игрока
            action: Название действия (level_up, kill_monster, etc.)
            data: Дополнительные данные
            
        Returns:
            Опциональное событие для логирования
        """
        pass
    
    @abstractmethod
    async def on_game_tick(self, tick_number: int, bot=None) -> Optional[str]:
        """
        Вызывается на каждом игровом тике.

        Args:
            tick_number: Номер тика
            bot: Экземпляр Telegram Bot (может быть None вне рантайма)

        Returns:
            Опциональное событие
        """
        pass
    
    def get_handlers(self) -> dict[str, callable]:
        """
        Вернуть словарь обработчиков событий.
        
        Returns:
            {"event_name": async_handler, ...}
        """
        return {}


class PluginState:
    """Состояние плагина — хранится между вызовами."""
    
    def __init__(self):
        self._data: dict[str, Any] = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
    
    def delete(self, key: str) -> None:
        self._data.pop(key, None)
    
    def clear(self) -> None:
        self._data.clear()


class PluginContext:
    """Контекст плагина — доступ к сервисам и данным."""
    
    def __init__(self, plugin_name: str):
        self.plugin_name = plugin_name
        self.state = PluginState()
        self._services: dict[str, Any] = {}
    
    def register_service(self, name: str, service: Any) -> None:
        """Зарегистрировать сервис для плагина."""
        self._services[name] = service
    
    def get_service(self, name: str) -> Any:
        """Получить сервис по имени."""
        return self._services.get(name)
    
    async def get_player(self, uid: int) -> Optional[Any]:
        """Получить игрока по UID."""
        from db import Player
        return await Player.objects.get_or_none(uid=uid)
    
    async def send_message(self, uid: int, text: str, **kwargs) -> None:
        """Отправить сообщение игроку."""
        from services import get_messenger
        messenger = get_messenger()
        if messenger:
            await messenger.send(uid, text, **kwargs)