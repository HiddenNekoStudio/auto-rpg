"""
game/states.py — Паттерн State Machine для FSM игрока
Защищает от зависания в бою после перезагрузки
"""
from enum import Enum
from dataclasses import dataclass
import json
import logging

logger = logging.getLogger(__name__)


class GameState(Enum):
    """Возможные состояния игрока"""
    PEACEFUL = "peaceful"   # В мире
    COMBAT = "combat"        # В бою
    QUEST = "quest"          # На квесте
    TRADE = "trade"         # В магазине


# Переходы между состояниями — кто куда может
TRANSITIONS = {
    GameState.PEACEFUL: {GameState.COMBAT, GameState.QUEST, GameState.TRADE},
    GameState.COMBAT: {GameState.PEACEFUL},     # Только после боя
    GameState.QUEST: {GameState.PEACEFUL, GameState.COMBAT},
    GameState.TRADE: {GameState.PEACEFUL},
}


@dataclass
class StateContext:
    """Контекст состояния — дополнительные данные"""
    monster_id: str = None
    quest_id: str = None
    trade_npc: str = None
    combat_turn: int = 0
    
    def to_json(self) -> str:
        return json.dumps(self.__dict__)
    
    @classmethod
    def from_json(cls, data: str) -> "StateContext":
        if not data:
            return cls()
        try:
            d = json.loads(data)
            return cls(**d)
        except:
            return cls()


class PlayerStateMachine:
    """State Machine для игрока"""
    
    def __init__(self, player):
        self.player = player
    
    @property
    def current_state(self) -> GameState:
        try:
            return GameState(self.player.state)
        except ValueError:
            return GameState.PEACEFUL
    
    @property
    def context(self) -> StateContext:
        return StateContext.from_json(self.player.state_context)
    
    def can_transition(self, new_state: GameState) -> bool:
        """Можно ли перейти в новое состояние"""
        return new_state in TRANSITIONS.get(self.current_state, set())
    
    async def transition(self, new_state: GameState, **context) -> bool:
        """Перейти в новое состояние"""
        if not self.can_transition(new_state):
            logger.warning(
                f"Invalid transition {self.current_state} -> {new_state} for {self.player.name}"
            )
            return False
        
        old_state = self.current_state
        self.player.state = new_state.value
        
        # Сохраняем контекст
        ctx = self.context
        for key, value in context.items():
            setattr(ctx, key, value)
        self.player.state_context = ctx.to_json()
        
        await self.player.update(_columns=["state", "state_context"])
        
        logger.info(f"Player {self.player.name}: {old_state.value} -> {new_state.value}")
        return True
    
    async def resolve_combat(self, won: bool = True):
        """Завершить бой"""
        await self.transition(GameState.PEACEFUL)
    
    async def start_combat(self, monster_id: str):
        """Начать бой"""
        await self.transition(
            GameState.COMBAT,
            monster_id=monster_id,
            combat_turn=1
        )
    
    async def next_turn(self):
        """Следующий ход в бою"""
        ctx = self.context
        ctx.combat_turn += 1
        self.player.state_context = ctx.to_json()
        await self.player.update(_columns=["state_context"])
    
    def is_in_combat(self) -> bool:
        return self.current_state == GameState.COMBAT


class StateManager:
    """Менеджер всех состояний — запускается при старте"""
    
    @staticmethod
    async def resolve_stuck_players():
        """Сбросить застрявших игроков при старте"""
        from db import Player
        
        # Ищем застрявших в бою
        stuck = await Player.objects.filter(state="combat").all()
        
        if stuck:
            logger.warning(f"Found {len(stuck)} stuck players in combat!")
            
            for player in stuck:
                logger.info(f"Resetting stuck player: {player.name}")
                player.state = "peaceful"
                player.state_context = "{}"
                await player.update(_columns=["state", "state_context"])
        
        return len(stuck)
    
    @staticmethod
    async def resolve_all_states():
        """Проверить все состояния"""
        from db import Player
        
        # Статистика
        states = {}
        all_players = await Player.objects.all()
        
        for p in all_players:
            try:
                s = GameState(p.state)
            except ValueError:
                s = GameState.PEACEFUL
            states[s.value] = states.get(s.value, 0) + 1
        
        logger.info(f"State distribution: {states}")
        return states


# === Утилита для использования в handlers ===

async def ensure_peaceful(player) -> bool:
    """Убедиться что игрок в мирном состоянии"""
    sm = PlayerStateMachine(player)
    
    if sm.is_in_combat():
        # Сброс застрявшего
        await sm.transition(GameState.PEACEFUL)
        return False
    
    return True


async def require_peaceful(player) -> bool:
    """Требовать мирное состояние"""
    sm = PlayerStateMachine(player)
    
    if sm.is_in_combat():
        return False  # Занят в бою
    
    return True


async def require_combat(player) -> bool:
    """Требовать состояние боя"""
    sm = PlayerStateMachine(player)
    
    if not sm.is_in_combat():
        return False  # Нет боя
    
    return True