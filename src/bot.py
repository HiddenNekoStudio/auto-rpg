"""
bot.py - Telegram AutoRPG
Полный порт Discord AutoRPG на python-telegram-bot v20+

Запуск:
    pip install -r requirements.txt
    python bot.py
"""

import logging
import os
import sys
from pathlib import Path

from telegram import Bot
from telegram.ext import Application, ApplicationBuilder

import config as cfg

logger = logging.getLogger(__name__)

# Глобальный экземпляр бота (доступен после старта)
_bot_instance: Bot | None = None

def get_bot() -> Bot | None:
    """Получить экземпляр бота. Возвращает None до старта."""
    return _bot_instance

# ──────────────────────────────────────────────
# Вспомогательные функции (общие для всех модулей)
# ──────────────────────────────────────────────

# Импортируем из services для избежания дублирования
from services import ctime, format_short, item_string


def readfile(e: str) -> list[str]:
    """Читает события/квесты из текстовых файлов."""
    root_dir = Path(__file__).parent
    if cfg.HOLIDAY > 0:
        folder = cfg.HOLIDAY_LIST[cfg.HOLIDAY - 1]
        file = root_dir / "txtfiles" / folder / f"{e}_{folder}.txt"
    else:
        file = root_dir / "txtfiles" / f"{e}.txt"
    with open(file, encoding="utf-8") as f:
        return [i.rstrip() for i in f if i.strip()]


async def send_to_players(bot: Bot, text: str, player_uids: list = None,
                          parse_mode: str = "Markdown", reply_markup=None,
                          force: bool = False) -> None:
    """
    Отправляет сообщение напрямую в личку игрокам.
    Если player_uids не указан — шлёт всем онлайн-игрокам.
    Если указан — только перечисленным uid.
    Автоматически повторяет при сетевых ошибках.
    Отправка конкурентная через asyncio.gather.
    force=True — игнорирует optin игрока (для админ-команд).
    """
    import asyncio
    from telegram.error import NetworkError, RetryAfter, TimedOut
    from db import Player
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

    async def _send_one(uid: int) -> None:
        for attempt in range(3):
            try:
                await bot.send_message(chat_id=uid, text=text, parse_mode=parse_mode, reply_markup=reply_markup)
                return
            except RetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
            except (NetworkError, TimedOut):
                if attempt < 2:
                    await asyncio.sleep(1.5 * (attempt + 1))
            except Exception as e:
                logging.debug("Не удалось отправить игроку %s: %s", uid, e)
                return

    await asyncio.gather(*[_send_one(uid) for uid in uids])


# Алиасы для обратной совместимости
async def send_to_game(bot: Bot, text: str, parse_mode: str = "Markdown") -> None:
    await send_to_players(bot, text, parse_mode=parse_mode)

async def send_to_announce(bot: Bot, text: str, parse_mode: str = "Markdown") -> None:
    await send_to_players(bot, text, parse_mode=parse_mode)


# ──────────────────────────────────────────────
# Импорт модулей после объявления вспомогательных функций
# ──────────────────────────────────────────────

def init_db():
    """Применяет миграции Alembic."""
    from alembic.config import Config
    from alembic import command
    from pathlib import Path

    alembic_cfg_path = Path(__file__).parent.parent / "alembic.ini"
    if not alembic_cfg_path.exists():
        logging.warning("alembic.ini not found, skipping migrations")
        return

    alembic_cfg = Config(str(alembic_cfg_path))

    script_dir = Path(__file__).parent.parent / "alembic"
    alembic_cfg.set_main_option("script_location", str(script_dir))

    command.upgrade(alembic_cfg, "head")
    logging.info("Alembic migrations applied successfully")


async def post_init(app: Application) -> None:
    """Вызывается после старта бота — подключаем БД, задаём команды и запускаем циклы."""
    global _bot_instance
    from db import database
    from health import set_db_connected
    from game.bosses import init_bosses
    from game.states import StateManager
    
    _bot_instance = app.bot
    
    await database.connect()
    set_db_connected(True)
    
    try:
        await init_bosses()
    except Exception as e:
        logger.warning(f"Boss init failed (non-fatal): {e}")
    
    try:
        stuck_count = await StateManager.resolve_stuck_players()
        if stuck_count > 0:
            logger.warning(f"Resolved {stuck_count} stuck players from previous session")
    except Exception as e:
        logger.warning(f"State cleanup failed (non-fatal): {e}")

    # Устанавливаем ТОЛЬКО публичные команды (админ-команды скрыты)
    from telegram import BotCommand
    await app.bot.set_my_commands([
        BotCommand("start",   "Главное меню"),
        BotCommand("profile", "Твой профиль"),
        BotCommand("quest",   "Текущий квест"),
        BotCommand("passives","Пассивные навыки"),
        BotCommand("bosses",  "Список боссов"),
        BotCommand("help",    "Список команд"),
        BotCommand("starshop","Star Магазин"),
    ], language_code="ru")
    await app.bot.set_my_commands([
        BotCommand("start",   "Main menu"),
        BotCommand("profile", "Your profile"),
        BotCommand("quest",   "Current quest"),
        BotCommand("passives","Passive skills"),
        BotCommand("bosses",  "Boss list"),
        BotCommand("help",    "Command list"),
        BotCommand("starshop","Star Shop"),
    ], language_code="en")

    # Запускаем HTTP сервер для healthcheck в том же event loop
    from health import start_http_server
    health_port = int(__import__("os").environ.get("HEALTH_PORT", "8080"))
    await start_http_server(health_port, app.bot)

    # Инициализируем EventBus обработчики
    from services.event_handlers import init_event_handlers
    init_event_handlers(app.bot)

    # Загружаем плагины (импортируем модули для активации декораторов)
    import plugins.monsters
    import plugins.passive_skills
    from plugins.registry import PluginRegistry
    
    await PluginRegistry.load_all()
    logger.info(f"Plugins loaded: {PluginRegistry.list_loaded()}")
    
    # Запускаем игровые циклы
    from loops import start_loops
    await start_loops(app)


async def post_shutdown(app: Application) -> None:
    """Вызывается при завершении — отключаем БД."""
    from health import set_db_connected
    set_db_connected(False)
    from db import database
    await database.disconnect()


def main():
    # Улучшенное логирование с разделением по компонентам
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
        stream=sys.stdout,
    )
    
    # Логи по компонентам
    logging.getLogger("handlers").setLevel(logging.INFO)
    logging.getLogger("game").setLevel(logging.DEBUG)
    logging.getLogger("loops").setLevel(logging.DEBUG)

    config_path = Path(__file__).parent / "config.py"
    if not config_path.exists():
        return logging.error("Файл config.py не найден!")

    if not cfg.TELEGRAM_TOKEN:
        return logging.error("Укажите TELEGRAM_TOKEN в .env файле!")

    # БД создаём синхронно до старта event loop
    init_db()

    from handlers import admin, user, alignment, jobs, listeners, maps
    from core.errors import global_error_handler
    from core.shutdown import GracefulShutdown, HealthChecker

    builder = ApplicationBuilder().token(cfg.TELEGRAM_TOKEN)

    proxy_url = cfg.TELEGRAM_PROXY
    if proxy_url:
        from telegram.request import HTTPXRequest
        builder = builder.request(HTTPXRequest(proxy=proxy_url))
        logging.info("Используется прокси: %s", proxy_url.split("@")[-1] if "@" in proxy_url else "установлен")

    app = (
        builder
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Graceful shutdown
    shutdown = GracefulShutdown(app)
    shutdown.register()
    
    # Healthchecker
    health = HealthChecker(app)

    # Global error handler — бот не падает при ошибках
    app.add_error_handler(global_error_handler)

    # Middleware — о��новляет lastlogin и online=True при любом взаимодействии
    from telegram.ext import TypeHandler
    import datetime as _dt
    from db import Player as _Player

    async def update_activity(update, context):
        u = update.effective_user
        if u:
            p = await _Player.objects.get_or_none(uid=u.id)
            if p:
                p.lastlogin = int(_dt.datetime.today().timestamp())
                p.online = True
                await p.update(_columns=["lastlogin", "online"])

    app.add_handler(TypeHandler(object, update_activity), group=-1)

    # Rate limiting — TTLCache вместо mutable dict
    # ПОЧЕМУ: TTLCache — автоматическая очистка, потокобезопасность
    from core.cache import TTLCache
    
    _user_message_time = TTLCache(ttl=1.0, maxsize=10000)

    async def rate_limit_middleware(update, context):
        if not update.effective_user:
            return
        uid = str(update.effective_user.id)
        
        # Проверяем — если None, можно обрабатывать
        if _user_message_time.get(uid) is not None:
            return  # Rate limited
        
        # Устанавливаем flag
        _user_message_time.set(uid, True)

    app.add_handler(TypeHandler(object, rate_limit_middleware), group=-2)

    user.register(app)
    alignment.register(app)
    jobs.register(app)
    listeners.register(app)
    admin.register(app)
    maps.register_handlers(app)
    import handlers.bosses as bosses
    bosses.register_handlers(app)
    import handlers.quests as quests
    quests.register_handlers(app)
    from plugins.shop import register_shop_handlers
    register_shop_handlers(app)
    from plugins.vip_shop import register_vip_handlers
    register_vip_handlers(app)
    from plugins.stars_shop import register_stars_handlers
    register_stars_handlers(app)
    
    from plugins.passive_skills import register_passive_handlers
    register_passive_handlers(app)
    
    from game.skills.passives import init_passives
    init_passives()
    
    logging.info("Запуск %s v%s", cfg.GAME_NAME, cfg.VERSION)
    # run_polling управляет своим event loop — НЕ оборачиваем в asyncio.run()
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
