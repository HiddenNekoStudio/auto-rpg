"""
core/errors.py — Глобальный обработчик ошибок
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

from core.exceptions import (
    BotException, PlayerNotFound, InsufficientTokens, LevelTooLow,
    AdminOnly, RaceNotSelected, QuestAlreadyActive, QuestNotFound,
    DatabaseError
)

logger = logging.getLogger(__name__)


async def global_error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Глобальный обработчик ошибок — бот не падает при багах"""
    
    if not update:
        logger.warning("Update is None in error handler")
        return
    
    # Получаем язык игрока для ответа
    lang = "ru"
    try:
        from db import Player
        if update.effective_user:
            player = await Player.objects.get_or_none(uid=update.effective_user.id)
            if player and player.lang:
                lang = player.lang
    except Exception:
        pass
    
    if not update.callback_query and not update.message and not update.effective_user:
        logger.warning("Unknown update type in error handler")
        return
    
    try:
        # Пытаемся получить original error из context
        error = context.error
        if not error:
            logger.warning("No error in context")
            return
            
        # Логируем ошибку
        logger.exception(
            f"Unhandled error: {type(error).__name__}: {error}"
        )
        
        # Определяем тип ошибки и ответ
        if isinstance(error, PlayerNotFound):
            reply = error.reply(lang)
        elif isinstance(error, InsufficientTokens):
            reply = error.reply(lang)
        elif isinstance(error, LevelTooLow):
            reply = error.reply(lang)
        elif isinstance(error, AdminOnly):
            reply = error.reply(lang)
        elif isinstance(error, RaceNotSelected):
            reply = error.reply(lang)
        elif isinstance(error, QuestAlreadyActive):
            reply = error.reply(lang)
        elif isinstance(error, QuestNotFound):
            reply = error.reply(lang)
        elif isinstance(error, DatabaseError):
            reply = error.reply(lang)
        else:
            # Неизвестная ошибка — generic ответ
            if lang == "en":
                reply = "An error occurred. Please try again later."
            else:
                reply = "Произошла ошибка. Попробуй позже."
        
        # Отправляем ответ пользователю
        if update.callback_query:
            try:
                await update.callback_query.answer(reply, show_alert=True)
            except Exception:
                pass
        elif update.message:
            try:
                await update.message.reply_text(reply)
            except Exception:
                pass
                
    except Exception as e:
        # Даже в error handler может быть ошибка
        logger.exception(f"Error in error handler: {e}")


# Функция для создания контекстного менеджера error handling
def create_error_wrapper(handler_name: str):
    """Декоратор для оборачивания хендлеров с логированием"""
    def decorator(func):
        async def wrapper(update, context):
            try:
                return await func(update, context)
            except Exception as e:
                logger.exception(f"Error in {handler_name}: {e}")
                # Пробрасываем — global_error_handler поймает
                raise
        return wrapper
    return decorator