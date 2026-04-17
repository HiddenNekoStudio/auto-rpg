"""
health.py — HTTP сервер для Docker Healthcheck
Запускается в том же event loop что и бот
"""
import asyncio
import logging
from aiohttp import web

logger = logging.getLogger(__name__)

# состояние бота
_bot_instance = None
_db_connected = False


async def health(request):
    """Эндпоинт /health — возвращает status ok если бот жив"""
    global _bot_instance, _db_connected
    
    try:
        # Проверяем что бот отвечает
        if _bot_instance:
            try:
                me = await _bot_instance.get_me()
                bot_ok = me is not None
            except Exception as e:
                logger.warning(f"Healthcheck bot error: {e}")
                bot_ok = False
        else:
            bot_ok = False
        
        # Проверяем БД
        from db import database
        db_ok = _db_connected
        
        if bot_ok and db_ok:
            return web.json_response({
                "status": "ok",
                "bot": "alive",
                "database": "connected"
            })
        else:
            return web.json_response({
                "status": "degraded",
                "bot": "alive" if bot_ok else "dead",
                "database": "connected" if db_ok else "disconnected"
            }, status=503)
            
    except Exception as e:
        logger.error(f"Healthcheck error: {e}")
        return web.json_response({"status": "error"}, status=500)


async def ready(request):
    """Эндпоинт /ready — liveness probe"""
    return web.json_response({"ready": True})


async def start_http_server(port: int = 8080, bot=None):
    """Запускает HTTP сервер в том же event loop"""
    global _bot_instance
    
    _bot_instance = bot
    
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/ready", ready)
    app.router.add_get("/", lambda r: web.json_response({"service": "tg-autorpg"}))
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    
    logger.info(f"HTTP server started on port {port}")
    return runner


def set_db_connected(connected: bool):
    """Устанавливает состояние БД"""
    global _db_connected
    _db_connected = connected