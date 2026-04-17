"""
core/shutdown.py — Graceful shutdown для бота
"""
import asyncio
import logging
import signal
import sys

logger = logging.getLogger(__name__)


class GracefulShutdown:
    """Обработка корректного завершения работы"""
    
    def __init__(self, app):
        self._app = app
        self._shutdown = False
        self._tasks = []
    
    def register(self):
        """Регистрирует signal handlers"""
        loop = asyncio.get_event_loop()
        
        # SIGTERM — docker stop
        loop.add_signal_handler(
            signal.SIGTERM,
            lambda: asyncio.create_task(self._shutdown())
        )
        
        # SIGINT — Ctrl+C
        loop.add_signal_handler(
            signal.SIGINT,
            lambda: asyncio.create_task(self._shutdown())
        )
        
        logger.info("Graceful shutdown registered for SIGTERM/SIGINT")
    
    async def _shutdown(self):
        """Выполняет graceful shutdown"""
        if self._shutdown:
            logger.warning("Shutdown already in progress")
            return
            
        self._shutdown = True
        logger.info("Starting graceful shutdown...")
        
        try:
            # 1. Останавливаем Telegram polling
            logger.info("Stopping Telegram bot...")
            self._app.stop()
            
            # 2. Отменяем все активные задачи
            if self._tasks:
                logger.info(f"Cancelling {len(self._tasks)} tasks...")
                for task in self._tasks:
                    if not task.done():
                        task.cancel()
                # Ждём отмены
                await asyncio.gather(*self._tasks, return_exceptions=True)
            
            # 3. Закрываем соединение с БД
            logger.info("Closing database connection...")
            from db import database
            try:
                await database.disconnect()
            except Exception as e:
                logger.warning(f"Database disconnect error: {e}")
            
            logger.info("Graceful shutdown complete")
            
        except Exception as e:
            logger.exception(f"Shutdown error: {e}")
        finally:
            # Принудительный выход
            sys.exit(0)
    
    def register_task(self, task):
        """Регистрирует задачу для отмены при shutdown"""
        self._tasks.append(task)
    
    def unregister_task(self, task):
        """Удаляет задачу из списка"""
        if task in self._tasks:
            self._tasks.remove(task)


class HealthChecker:
    """Проверка здоровья бота"""
    
    def __init__(self, app):
        self._app = app
    
    async def check(self) -> bool:
        """Проверяет что бот жив"""
        try:
            bot = self._app.bot
            me = await bot.get_me()
            return me is not None
        except Exception as e:
            logger.error(f"Healthcheck failed: {e}")
            return False
    
    async def monitor(self, interval: int = 60):
        """Мониторинг в фоне"""
        while True:
            try:
                is_alive = await self.check()
                if is_alive:
                    logger.debug("Healthcheck OK")
                else:
                    logger.error("Healthcheck FAILED - bot not responding")
            except Exception as e:
                logger.exception(f"Healthcheck error: {e}")
            
            await asyncio.sleep(interval)