"""
services/messenger.py — Message Service интерфейс

Абстрактный интерфейс для отправки сообщений.
Позволяет отделить логику боя от Telegram API.
"""
from abc import ABC, abstractmethod
from typing import Optional


class MessageService(ABC):
    """Абстрактный интерфейс сервиса сообщений."""
    
    @abstractmethod
    async def send(
        self, 
        user_id: int, 
        text: str, 
        parse_mode: str = "Markdown",
        reply_markup: Optional[object] = None
    ) -> bool:
        """
        Отправить сообщение пользователю.
        
        Args:
            user_id: Telegram user ID
            text: Текст сообщения
            parse_mode: Режим форматирования (Markdown, HTML)
            reply_markup: Инлайн-клавиатура
            
        Returns:
            True если отправлено успешно
        """
        pass
    
    @abstractmethod
    async def send_to_players(
        self, 
        text: str, 
        player_uids: Optional[list[int]] = None,
        parse_mode: str = "Markdown",
        reply_markup: Optional[object] = None
    ) -> int:
        """
        Отправить сообщение игрокам.
        
        Args:
            text: Текст сообщения
            player_uids: Список UID. Если None — всем онлайн игрокам.
            parse_mode: Режим форматирования
            reply_markup: Инлайн-клавиатура
            
        Returns:
            Количество отправленных сообщений
        """
        pass
    
    @abstractmethod
    async def send_to_all_online(
        self, 
        text: str, 
        parse_mode: str = "Markdown",
        reply_markup: Optional[object] = None
    ) -> int:
        """Отправить всем онлайн игрокам."""
        pass