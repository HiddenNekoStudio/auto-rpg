"""
services/telegram_messenger.py — Telegram реализация MessageService

Реализация интерфейса MessageService для Telegram Bot API.
"""
import asyncio
import logging
from typing import Optional

from telegram import Bot
from telegram.error import NetworkError, RetryAfter, TimedOut

from db import Player
from .messenger import MessageService


logger = logging.getLogger(__name__)


class TelegramMessageService(MessageService):
    """Telegram-реализация сервиса сообщений."""
    
    def __init__(self, bot: Bot):
        self._bot = bot
    
    async def send(
        self, 
        user_id: int, 
        text: str, 
        parse_mode: str = "Markdown",
        reply_markup: Optional[object] = None
    ) -> bool:
        """Отправить сообщение пользователю."""
        for attempt in range(3):
            try:
                await self._bot.send_message(
                    chat_id=user_id, 
                    text=text, 
                    parse_mode=parse_mode, 
                    reply_markup=reply_markup
                )
                return True
            except RetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
            except (NetworkError, TimedOut):
                if attempt < 2:
                    await asyncio.sleep(1.5 * (attempt + 1))
            except Exception as e:
                logger.debug("Не удалось отправить игроку %s: %s", user_id, e)
                break
        return False
    
    async def send_to_players(
        self, 
        text: str, 
        player_uids: Optional[list[int]] = None,
        parse_mode: str = "Markdown",
        reply_markup: Optional[object] = None,
        force: bool = False
    ) -> int:
        """Отправить сообщение игрокам."""
        if force:
            if player_uids is None:
                players = await Player.objects.all(online=True)
                uids = [p.uid for p in players]
            else:
                uids = player_uids
        elif player_uids is None:
            players = await Player.objects.filter(online=True, optin=True).all()
            uids = [p.uid for p in players]
        else:
            players = await Player.objects.filter(uid__in=player_uids, optin=True).all()
            uids = [p.uid for p in players]
        
        sent_count = 0
        for uid in uids:
            if await self.send(uid, text, parse_mode, reply_markup):
                sent_count += 1
        return sent_count
    
    async def send_to_all_online(
        self, 
        text: str, 
        parse_mode: str = "Markdown",
        reply_markup: Optional[object] = None
    ) -> int:
        """Отправить всем онлайн игрокам."""
        return await self.send_to_players(text, None, parse_mode, reply_markup)


# Глобальный экземпляр сервиса
_messenger_service: Optional[MessageService] = None


def get_messenger() -> Optional[MessageService]:
    """Получить экземпляр мессенджера."""
    return _messenger_service


def set_messenger(service: MessageService) -> None:
    """Установить экземпляр мессенджера (вызывается при старте бота)."""
    global _messenger_service
    _messenger_service = service