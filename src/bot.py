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
import sqlalchemy
from db import database, engine, metadata

# ──────────────────────────────────────────────
# Вспомогательные функции (общие для всех модулей)
# ──────────────────────────────────────────────

def ctime(seconds: int) -> str:
    """Переводит секунды в читаемый формат."""
    intervals = [
        ("нед.", 604800),
        ("дн.",  86400),
        ("ч.",   3600),
        ("мин.", 60),
        ("сек.", 1),
    ]
    result = []
    for name, count in intervals:
        value = seconds // count
        seconds -= value * count
        if value:
            result.append(f"{value} {name}")
    return ", ".join(result) if result else "0 сек."


def item_string(item: dict) -> str:
    """Форматирует предмет в строку с эмодзи редкости."""
    emoji = cfg.RARITY_EMOJI.get(item.get("rank", "Common"), "⚪")
    base = f"{emoji} {item['quality']} {item['prefix']}{item['name']}{item['suffix']} ({item['condition']}) [⚔️{item['dps']}]"
    if item.get("flair"):
        base += f"\n  _{item['flair']}_"
    return base


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
                          parse_mode: str = "Markdown") -> None:
    """
    Отправляет сообщение напрямую в личку игрокам.
    Если player_uids не указан — шлёт всем онлайн-игрокам.
    Если указан — только перечисленным uid.
    Автоматически повторяет при сетевых ошибках.
    """
    import asyncio
    from telegram.error import NetworkError, RetryAfter, TimedOut
    from db import Player
    if player_uids is None:
        players = await Player.objects.all(online=True)
        uids = [p.uid for p in players]
    else:
        uids = player_uids
    for uid in uids:
        for attempt in range(3):
            try:
                await bot.send_message(chat_id=uid, text=text, parse_mode=parse_mode)
                break
            except RetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
            except (NetworkError, TimedOut):
                if attempt < 2:
                    await asyncio.sleep(1.5 * (attempt + 1))
            except Exception as e:
                logging.debug("Не удалось отправить игроку %s: %s", uid, e)
                break


# Алиасы для обратной совместимости
async def send_to_game(bot: Bot, text: str, parse_mode: str = "Markdown") -> None:
    await send_to_players(bot, text, parse_mode=parse_mode)

async def send_to_announce(bot: Bot, text: str, parse_mode: str = "Markdown") -> None:
    await send_to_players(bot, text, parse_mode=parse_mode)


# ──────────────────────────────────────────────
# Импорт модулей после объявления вспомогательных функций
# ──────────────────────────────────────────────

def init_db():
    """Создаёт таблицы в БД если их нет + применяет миграции для новых колонок."""
    metadata.create_all(engine)

    # Миграции — добавляем новые колонки если их нет (безопасно для существующей БД)
    migrations = [
        "ALTER TABLE users ADD COLUMN lang VARCHAR(5) NOT NULL DEFAULT ''",
        "ALTER TABLE users ADD COLUMN race VARCHAR(20) NOT NULL DEFAULT ''",  # расы
        "ALTER TABLE users ADD COLUMN state VARCHAR(20) NOT NULL DEFAULT 'peaceful'",
        "ALTER TABLE users ADD COLUMN state_context TEXT NOT NULL DEFAULT '{}'",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(sqlalchemy.text(sql))
                conn.commit()
                col = sql.split("ADD COLUMN")[1].strip().split()[0]
                logging.info("Миграция применена: добавлена колонка %s", col)
            except Exception:
                pass  # Колонка уже существует — пропускаем

    logging.info("База данных инициализирована")


async def post_init(app: Application) -> None:
    """Вызывается после старта бота — подключаем БД, задаём команды и запускаем циклы."""
    await database.connect()
    
    # Устанавливаем состояние БД для healthcheck
    from health import set_db_connected
    set_db_connected(True)

    # Сбрасываем застрявших игроков (FSM protection)
    from game.states import StateManager
    stuck_count = await StateManager.resolve_stuck_players()
    if stuck_count > 0:
        logger.warning(f"Resolved {stuck_count} stuck players from previous session")

    # Устанавливаем ТОЛЬКО публичные команды (админ-команды скрыты)
    from telegram import BotCommand
    await app.bot.set_my_commands([
        BotCommand("start",   "Главное меню"),
        BotCommand("profile", "Твой профиль и снаряжение"),
        BotCommand("pull",    "Использовать токен лута"),
        BotCommand("setjob",  "Сменить класс (с 10 уровня)"),
        BotCommand("align",   "Выбрать мировоззрение"),
        BotCommand("quest",   "Текущий квест"),
        BotCommand("top",     "Топ 10 игроков"),
        BotCommand("online",  "Кто сейчас онлайн"),
        BotCommand("help",    "Список команд"),
    ])

    # Запускаем HTTP сервер для healthcheck в том же event loop
    from health import start_http_server
    health_port = int(__import__("os").environ.get("HEALTH_PORT", "8080"))
    await start_http_server(health_port, app.bot)
    
    # Запускаем игровые циклы
    from loops import start_loops
    await start_loops(app)


async def post_shutdown(app: Application) -> None:
    """Вызывается при завершении — отключаем БД."""
    from health import set_db_connected
    set_db_connected(False)
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

    from handlers import admin, user, alignment, jobs, listeners
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

    # Rate limiting — 1 сообщение в секунду
    _user_message_time = {}

    async def rate_limit_middleware(update, context):
        if not update.effective_user:
            return
        uid = update.effective_user.id
        now = _dt.datetime.now().timestamp()
        last_time = _user_message_time.get(uid, 0)
        if now - last_time < 1.0:
            return  # Rate limited
        _user_message_time[uid] = now

    app.add_handler(TypeHandler(object, rate_limit_middleware), group=-2)

    user.register(app)
    alignment.register(app)
    jobs.register(app)
    listeners.register(app)
    admin.register(app)

    logging.info("Запуск %s v%s", cfg.GAME_NAME, cfg.VERSION)
    # run_polling управляет своим event loop — НЕ оборачиваем в asyncio.run()
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
