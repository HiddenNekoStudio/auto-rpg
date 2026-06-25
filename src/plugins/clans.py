"""
plugins/clans.py — Пример плагина: Система кланов

Это пример плагина для демонстрации архитектуры.
Для реального использования нужно добавить в базу данных модели Clan, ClanMember.
"""
import logging
from typing import Any, Optional

from .base import GamePlugin, PluginMetadata
from .registry import PluginRegistry

logger = logging.getLogger(__name__)


@PluginRegistry.register(
    "clans", 
    description="Система кланов — создание кланов, общий банк, клановые квесты",
    author="AutoRPG"
)
class ClansPlugin(GamePlugin):
    """Плагин системы кланов."""
    
    metadata = PluginMetadata(
        name="clans",
        version="1.0.0",
        description="Система кланов",
    )
    
    async def on_load(self) -> None:
        """Инициализация при загрузке."""
        logger.info("ClansPlugin loaded")
        # Здесь можно инициализировать таблицы БД для кланов
    
    async def on_unload(self) -> None:
        """Очистка при выгрузке."""
        logger.info("ClansPlugin unloaded")
    
    async def on_player_action(
        self, 
        player_uid: int, 
        action: str, 
        data: dict[str, Any]
    ) -> Optional[str]:
        """Обработка действий игрока."""
        if action == "level_up":
            level = data.get("level", 1)
            return await self._on_level_up(player_uid, level)
        elif action == "kill_monster":
            return await self._on_kill_monster(player_uid, data)
        elif action == "donate_to_clan":
            return await self._on_donate(player_uid, data)
        return None
    
    async def _on_level_up(self, player_uid: int, level: int) -> Optional[str]:
        """Бонус к уровню для клана."""
        # Логика: каждый N уровень — бонус клану
        if level % 10 == 0:
            # Например, +1 очко клану за каждые 10 уровней
            logger.debug(f"Player {player_uid} reached level {level}, clan bonus triggered")
            return f"level_bonus:{level}"
        return None
    
    async def _on_kill_monster(self, player_uid: int, data: dict[str, Any]) -> Optional[str]:
        """Обработка убийства монстра для клановых квестов."""
        # Логика: квесты "убить N монстров" для клана
        return None
    
    async def _on_donate(self, player_uid: int, data: dict[str, Any]) -> Optional[str]:
        """Обработка пожертвований в клан."""
        amount = data.get("amount", 0)
        logger.debug(f"Player {player_uid} donated {amount} to clan")
        return f"donated:{amount}"
    
    async def on_game_tick(self, tick_number: int) -> Optional[str]:
        """Игровой тик — проверка клановых событий."""
        # Например, каждые 100 тиков — обновление клановых квестов
        if tick_number % 100 == 0:
            logger.debug(f"Tick {tick_number}: checking clan events")
        return None


# ─────────────────────────────────────────────
# Команды для работы с кланами (будут добавлены в handlers)
# ─────────────────────────────────────────────

# class ClanService:
#     """Сервис для работы с кланами."""
    
#     @staticmethod
#     async def create_clan(name: str, founder_uid: int) -> Clan:
#         """Создать клан."""
#         pass
    
#     @staticmethod
#     async def join_clan(clan_id: int, player_uid: int) -> bool:
#         """Вступить в клан."""
#         pass
    
#     @staticmethod
#     async def leave_clan(player_uid: int) -> bool:
#         """Покинуть клан."""
#         pass
    
#     @staticmethod
#     async def donate(clan_id: int, player_uid: int, gold: int) -> bool:
#         """Пожертвовать золото в клан."""
#         pass