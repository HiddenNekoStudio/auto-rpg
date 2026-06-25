"""
core/event_bus.py — Event Bus для decoupling игровой логики от Telegram

Позволяет game модулям публиковать события, а обработчики
подписываются на них без прямой зависимости.
"""
import asyncio
import logging
from typing import Callable, Awaitable, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Типы игровых событий."""
    PLAYER_LEVEL_UP = "player_level_up"
    PLAYER_IDLE_ENTER = "player_idle_enter"
    PLAYER_IDLE_EXIT = "player_idle_exit"
    PLAYER_ITEM_GAINED = "player_item_gained"
    PLAYER_MONSTER_DEFEATED = "player_monster_defeated"
    PLAYER_BOSS_DEFEATED = "player_boss_defeated"
    PLAYER_QUESTS_COMPLETED = "player_quests_completed"
    PLAYER_DUEL_WON = "player_duel_won"
    PLAYER_DUEL_LOST = "player_duel_lost"
    GLOBAL_EVENT = "global_event"
    PLAYER_GOLD_CHANGED = "player_gold_changed"
    PLAYER_XP_CHANGED = "player_xp_changed"


@dataclass
class GameEvent:
    """Событие игры."""
    event_type: EventType
    player_uid: int
    data: dict
    timestamp: int = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = int(datetime.now().timestamp())


EventHandler = Callable[[GameEvent], Awaitable[Any]]


class EventBus:
    """
    Event Bus для pub/sub коммуникации между game и handlers.
    """

    _instance = None
    _subscribers: dict[EventType, list[EventHandler]] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._subscribers = {}
        return cls._instance

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Подписаться на тип события."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)
            logger.debug(f"Subscribed {handler.__name__} to {event_type.value}")

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Отписаться от события."""
        if event_type in self._subscribers:
            if handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)

    async def publish(self, event: GameEvent) -> None:
        """Публиковать событие всем подписчикам."""
        handlers = self._subscribers.get(event.event_type, [])
        if not handlers:
            return

        logger.debug(f"Publishing {event.event_type.value} to {len(handlers)} handlers")

        tasks = []
        for handler in handlers:
            try:
                task = asyncio.create_task(handler(event))
                tasks.append(task)
            except Exception as e:
                logger.error(f"Failed to schedule handler {handler.__name__}: {e}")

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def publish_sync(self, event: GameEvent) -> None:
        """Синхронная публикация (для использования вне async контекста)."""
        handlers = self._subscribers.get(event.event_type, [])
        for handler in handlers:
            try:
                asyncio.create_task(handler(event))
            except Exception as e:
                logger.error(f"Failed to schedule handler {handler.__name__}: {e}")


# Глобальный экземпляр
event_bus = EventBus()


# Удобные функции для создания событий
async def emit_level_up(player_uid: int, new_level: int, reward_item: dict = None):
    """Emit level up event."""
    await event_bus.publish(GameEvent(
        event_type=EventType.PLAYER_LEVEL_UP,
        player_uid=player_uid,
        data={"new_level": new_level, "reward_item": reward_item}
    ))


async def emit_idle_enter(player_uid: int, idle_since: int):
    """Emit player enters idle mode."""
    await event_bus.publish(GameEvent(
        event_type=EventType.PLAYER_IDLE_ENTER,
        player_uid=player_uid,
        data={"idle_since": idle_since}
    ))


async def emit_idle_exit(player_uid: int, xp_gained: int):
    """Emit player exits idle mode."""
    await event_bus.publish(GameEvent(
        event_type=EventType.PLAYER_IDLE_EXIT,
        player_uid=player_uid,
        data={"xp_gained": xp_gained}
    ))


async def emit_item_gained(player_uid: int, item: dict, slot: str, replaced: bool):
    """Emit player got new item."""
    await event_bus.publish(GameEvent(
        event_type=EventType.PLAYER_ITEM_GAINED,
        player_uid=player_uid,
        data={"item": item, "slot": slot, "replaced": replaced}
    ))


async def emit_monster_defeated(player_uid: int, xp_gained: int, gold_gained: int, monster_level: int):
    """Emit monster defeated."""
    await event_bus.publish(GameEvent(
        event_type=EventType.PLAYER_MONSTER_DEFEATED,
        player_uid=player_uid,
        data={"xp_gained": xp_gained, "gold_gained": gold_gained, "monster_level": monster_level}
    ))


async def emit_gold_changed(player_uid: int, amount: int, reason: str):
    """Emit gold changed."""
    await event_bus.publish(GameEvent(
        event_type=EventType.PLAYER_GOLD_CHANGED,
        player_uid=player_uid,
        data={"amount": amount, "reason": reason}
    ))


async def emit_xp_changed(player_uid: int, amount: int, reason: str):
    """Emit XP changed."""
    await event_bus.publish(GameEvent(
        event_type=EventType.PLAYER_XP_CHANGED,
        player_uid=player_uid,
        data={"amount": amount, "reason": reason}
    ))


async def emit_global_event(event_type: str, message: str, affected_uids: list = None):
    """Emit global event."""
    await event_bus.publish(GameEvent(
        event_type=EventType.GLOBAL_EVENT,
        player_uid=0,
        data={"event_type": event_type, "message": message, "affected_uids": affected_uids or []}
    ))