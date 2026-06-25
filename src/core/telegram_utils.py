"""
core/telegram_utils.py — утилиты для работы с Telegram API

Содержит shared функции: safe_edit, rate limiting, клавиатуры.
"""
import asyncio
import logging

from telegram.error import NetworkError, RetryAfter, TimedOut

logger = logging.getLogger(__name__)


async def safe_edit(query, text: str, keyboard=None, parse_mode: str = "Markdown",
                    retries: int = 3, reply_markup=None):
    """Безопасное редактирование сообщения с retry при сетевых ошибках."""
    keyboard = keyboard or reply_markup
    for attempt in range(retries):
        try:
            await query.edit_message_text(text, parse_mode=parse_mode, reply_markup=keyboard)
            return
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except (NetworkError, TimedOut):
            if attempt < retries - 1:
                await asyncio.sleep(1.5 * (attempt + 1))
            else:
                logger.warning("safe_edit: failed after %d attempts", retries)
        except Exception as e:
            if "Message is not modified" in str(e):
                return
            logger.warning("safe_edit error: %s", e)
            return
