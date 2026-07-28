"""
core/telegram_utils.py — утилиты для работы с Telegram API

Содержит shared функции: safe_edit, rate limiting, клавиатуры.
"""
import asyncio
import logging

from telegram.error import NetworkError, RetryAfter, TimedOut

logger = logging.getLogger(__name__)


async def safe_edit(query, text: str, keyboard=None, parse_mode: str = "HTML",
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


async def safe_edit_html(query, text: str, keyboard=None,
                         retries: int = 3, reply_markup=None):
    """Безопасное редактирование сообщения с HTML parse_mode."""
    return await safe_edit(query, text, keyboard=keyboard,
                           parse_mode="HTML", retries=retries, reply_markup=reply_markup)


async def send_photo_safe(chat_id, photo, caption: str = "", parse_mode: str = "HTML",
                          retries: int = 3, reply_markup=None):
    """Отправка фото с caption в HTML и retry."""
    from telegram import Bot
    for attempt in range(retries):
        try:
            await Bot.get_instance().send_photo(
                chat_id=chat_id, photo=photo, caption=caption,
                parse_mode=parse_mode, reply_markup=reply_markup,
            )
            return
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except (NetworkError, TimedOut):
            if attempt < retries - 1:
                await asyncio.sleep(1.5 * (attempt + 1))
            else:
                logger.warning("send_photo_safe: failed after %d attempts", retries)
        except Exception as e:
            logger.warning("send_photo_safe error: %s", e)
            return
