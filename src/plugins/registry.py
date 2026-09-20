"""
plugins/registry.py — Plugin Registry

Система регистрации и управления плагинами.
"""
import logging
from typing import Any, Optional

from .base import GamePlugin, PluginContext, PluginMetadata

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Реестр плагинов."""
    
    _plugins: dict[str, type[GamePlugin]] = {}
    _loaded_plugins: dict[str, GamePlugin] = {}
    _plugin_contexts: dict[str, PluginContext] = {}
    
    @classmethod
    def register(cls, name: str, description: str = "", author: str = ""):
        """
        Декоратор для регистрации плагина.
        
        Usage:
            @PluginRegistry.register("example", description="Example system")
            class ExamplePlugin(GamePlugin):
                ...
        """
        def decorator(plugin_cls: type[GamePlugin]) -> type[GamePlugin]:
            # Добавляем метаданные
            plugin_cls.metadata = PluginMetadata(
                name=name,
                version=getattr(plugin_cls, 'version', '1.0.0'),
                description=description,
                author=author,
            )
            cls._plugins[name] = plugin_cls
            logger.info(f"Plugin registered: {name}")
            return plugin_cls
        return decorator
    
    @classmethod
    def get(cls, name: str) -> Optional[type[GamePlugin]]:
        """Получить класс плагина по имени."""
        return cls._plugins.get(name)
    
    @classmethod
    def get_loaded(cls, name: str) -> Optional[GamePlugin]:
        """Получить загруженный экземпляр плагина."""
        return cls._loaded_plugins.get(name)
    
    @classmethod
    def list_plugins(cls) -> list[str]:
        """Список всех зарегистрированных плагинов."""
        return list(cls._plugins.keys())
    
    @classmethod
    def list_loaded(cls) -> list[str]:
        """Список загруженных плагинов."""
        return list(cls._loaded_plugins.keys())
    
    @classmethod
    async def load_plugin(cls, name: str) -> bool:
        """Загрузить плагин по имени."""
        if name in cls._loaded_plugins:
            logger.warning(f"Plugin already loaded: {name}")
            return True
        
        plugin_cls = cls._plugins.get(name)
        if not plugin_cls:
            logger.error(f"Plugin not found: {name}")
            return False
        
        try:
            # Создаём контекст плагина
            context = PluginContext(name)
            cls._plugin_contexts[name] = context
            
            # Создаём экземпляр
            plugin = plugin_cls()
            await plugin.on_load()
            
            cls._loaded_plugins[name] = plugin
            logger.info(f"Plugin loaded: {name} v{plugin.metadata.version}")
            return True
        except Exception as e:
            logger.error(f"Failed to load plugin {name}: {e}")
            cls._plugin_contexts.pop(name, None)
            return False
    
    @classmethod
    async def unload_plugin(cls, name: str) -> bool:
        """Выгрузить плагин по имени."""
        plugin = cls._loaded_plugins.get(name)
        if not plugin:
            return False
        
        try:
            await plugin.on_unload()
            cls._loaded_plugins.pop(name, None)
            cls._plugin_contexts.pop(name, None)
            logger.info(f"Plugin unloaded: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to unload plugin {name}: {e}")
            return False
    
    @classmethod
    async def load_all(cls) -> None:
        """Загрузить все зарегистрированные плагины."""
        for name in cls._plugins:
            await cls.load_plugin(name)
    
    @classmethod
    async def unload_all(cls) -> None:
        """Выгрузить все плагины."""
        for name in list(cls._loaded_plugins.keys()):
            await cls.unload_plugin(name)
    
    @classmethod
    def get_context(cls, name: str) -> Optional[PluginContext]:
        """Получить контекст плагина."""
        return cls._plugin_contexts.get(name)
    
    @classmethod
    async def trigger_player_action(
        cls,
        player_uid: int,
        action: str,
        data: dict[str, Any]
    ) -> None:
        """Триггерить событие для всех загруженных плагинов.

        data мутируется плагинами (modified_damage / bonus_gold / bonus_xp) —
        вызывающая сторона читает результат из того же dict.
        """
        for name, plugin in cls._loaded_plugins.items():
            try:
                await plugin.on_player_action(player_uid, action, data)
            except Exception as e:
                logger.error(f"Plugin {name} action error: {e}")


    @classmethod
    async def trigger_game_tick(cls, tick_number: int, bot=None) -> None:
        """Триггерить игровой тик для всех плагинов."""
        for name, plugin in cls._loaded_plugins.items():
            try:
                await plugin.on_game_tick(tick_number, bot)
            except Exception as e:
                logger.error(f"Plugin {name} tick error: {e}")


# Утилита для создания CLI-плагинов
def create_simple_plugin(name: str, version: str = "1.0.0"):
    """Создать простой плагин с базовой функциональностью."""
    def decorator(cls: type[GamePlugin]) -> type[GamePlugin]:
        cls.metadata = PluginMetadata(name=name, version=version)
        return cls
    return decorator