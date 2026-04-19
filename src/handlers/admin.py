"""
handlers/admin.py — скрытые административные команды
"""
import random
import asyncio
from datetime import datetime
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import NetworkError, RetryAfter, TimedOut
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes
from telegram.ext.filters import Command

import config as cfg
from db import Player, Quest, Boss
from loot import get_item
from bot import item_string, ctime, send_to_players
from game import monsters as monster_module


def is_admin(uid):
    # Проверяем только если SERVER_ADMINS не пустой
    if cfg.SERVER_ADMINS:
        return uid in cfg.SERVER_ADMINS
    logging.warning(f"Access denied: no ADMIN_IDS configured")
    return False


async def safe_edit(query, text, keyboard=None, parse_mode="Markdown", retries=3, reply_markup=None):
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
        except Exception as e:
            if "Message is not modified" in str(e):
                return
            logging.warning("safe_edit error: %s", e)
            return


def admin_panel_keyboard():
    mins = cfg.OFFLINE_TIMEOUT // 60
    interval_secs = cfg.INTERVAL
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ Событие всем",    callback_data="adm_event"),
            InlineKeyboardButton("🗺️ Начать квест",    callback_data="adm_quest"),
        ],
        [
            InlineKeyboardButton("❌ Завершить квест",  callback_data="adm_endquest"),
            InlineKeyboardButton("📊 Статистика",       callback_data="adm_stats"),
        ],
        [
            InlineKeyboardButton("👤 Управление игроком", callback_data="adm_player_menu"),
            InlineKeyboardButton("🔧 Настройки сервера", callback_data="adm_settings_menu"),
        ],
        [
            InlineKeyboardButton(
                "⏱️ Таймаут: " + str(mins) + " мин",
                callback_data="adm_timeout_info"
            ),
            InlineKeyboardButton(
                "🎮 Тик: " + str(interval_secs) + " сек",
                callback_data="adm_interval_info"
            ),
        ],
        [
            InlineKeyboardButton("🧟 Монстры",  callback_data="adm_monsters_menu"),
            InlineKeyboardButton("👹 Боссы",   callback_data="adm_bosses_menu"),
        ],
    ])


def player_manage_keyboard(uid):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎖️ +Уровень",    callback_data="adm_addlevel_" + str(uid)),
            InlineKeyboardButton("🎫 +5 Токенов",  callback_data="adm_addtokens_" + str(uid)),
        ],
        [
            InlineKeyboardButton("⏱️ Время онлайна", callback_data="adm_setonline_" + str(uid)),
        ],
        [InlineKeyboardButton("🔙 Панель", callback_data="adm_panel")],
    ])


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    logging.info(f"Admin command from uid: {uid}, SERVER_ADMINS: {cfg.SERVER_ADMINS}")
    if not is_admin(uid):
        await update.message.reply_text("Нет доступа.")
        return
    await update.message.reply_text(
        "*Панель администратора*", parse_mode="Markdown",
        reply_markup=admin_panel_keyboard())


async def callback_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("Нет доступа.", show_alert=True)
        return
    await query.answer()
    action = query.data

    # Статистика
    if action == "adm_stats":
        total    = await Player.objects.count()
        online   = await Player.objects.filter(online=True).count()
        questing = await Player.objects.filter(onquest=True).count()
        quest    = await Quest.objects.get_or_none()
        q_str    = "Активен: " + quest.players if quest else "Нет"
        text = (
            "*Статистика сервера*\n"
            + "━━━━━━━━━━━━━━━━━━\n"
            + "Всего игроков: " + str(total) + "\n"
            + "Онлайн: " + str(online) + "\n"
            + "На квесте: " + str(questing) + "\n"
            + "Квест: " + q_str
        )
        await safe_edit(query, text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Панель", callback_data="adm_panel"),
            ]]))

    # Событие всем онлайн игрокам
    elif action == "adm_event":
        players = await Player.objects.all(online=True)
        if not players:
            await safe_edit(query, "Нет онлайн игроков.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Панель", callback_data="adm_panel"),
                ]]))
            return
        from game.events import randomevent
        count = 0
        for p in players:
            try:
                await randomevent(query.get_bot(), p)
                count += 1
                await asyncio.sleep(0.1)  # 100ms между событиями
            except Exception as e:
                logging.warning("Событие для %s: %s", p.name, e)
        await safe_edit(query,
            "Событие отправлено *" + str(count) + "* игрокам.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Панель", callback_data="adm_panel"),
            ]]))

    # Квест
    elif action == "adm_quest":
        # Запускаем ежедневные квесты для всех игроков (с 1 уровня)
        from loops import generate_daily_quests
        await generate_daily_quests(query.get_bot())
        await safe_edit(query, "Ежедневные квесты обновлены для всех игроков!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Панель", callback_data="adm_panel"),
            ]]))

    elif action == "adm_endquest":
        quest = await Quest.objects.get_or_none()
        if not quest:
            await safe_edit(query, "Нет активного квеста.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Панель", callback_data="adm_panel"),
                ]]))
            return
        await safe_edit(query,
            "Завершить квест *" + quest.players + "*?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Победа",  callback_data="adm_endquest_win"),
                    InlineKeyboardButton("Провал",  callback_data="adm_endquest_fail"),
                ],
                [InlineKeyboardButton("🔙 Панель", callback_data="adm_panel")],
            ]))

    elif action in ("adm_endquest_win", "adm_endquest_fail"):
        quest = await Quest.objects.get_or_none()
        if not quest:
            await safe_edit(query, "Квест уже завершён.")
            return
        from game.quests import endquest
        win = (action == "adm_endquest_win")
        await endquest(query.get_bot(), quest, win=win)
        await safe_edit(query, "Квест завершён: " + ("Победа" if win else "Провал"),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Панель", callback_data="adm_panel"),
            ]]))

    # Управление игроком
    elif action == "adm_player_menu":
        await safe_edit(query,
            "*Управление игроком*\n\n"
            "Найти игрока:\n"
            "/admin\\_find <имя или uid>\n\n"
            "Прямые команды:\n"
            "/admin\\_level <uid> <+N>\n"
            "/admin\\_token <uid> [N]\n"
            "/admin\\_onlinetime <uid> <минуты>",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Панель", callback_data="adm_panel"),
            ]]))

    # +Уровень
    elif action.startswith("adm_addlevel_"):
        uid = int(action.split("_")[-1])
        player = await Player.objects.get_or_none(uid=uid)
        if not player:
            await safe_edit(query, "Игрок не найден.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Панель", callback_data="adm_panel"),
                ]]))
            return
        player.level += 1
        player.currentxp = 0
        player.nextxp = int(cfg.TIME_BASE * (cfg.TIME_EXP ** (player.level + 1)))
        await player.update(_columns=["level", "currentxp", "nextxp"])
        await send_to_players(query.get_bot(),
            "Администратор выдал *+1 уровень*! Теперь ты *" + str(player.level) + " уровня*.",
            player_uids=[player.uid])
        await safe_edit(query,
            "*" + player.name + "* повышен до *" + str(player.level) + "* уровня.",
            parse_mode="Markdown",
            reply_markup=player_manage_keyboard(uid))

    # +Токены
    elif action.startswith("adm_addtokens_"):
        uid = int(action.split("_")[-1])
        player = await Player.objects.get_or_none(uid=uid)
        if not player:
            await safe_edit(query, "Игрок не найден.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Панель", callback_data="adm_panel"),
                ]]))
            return
        player.gold += 5
        await player.update(_columns=["gold"])
        await send_to_players(query.get_bot(),
            "Администратор выдал *5 золота*! Всего: *" + str(player.gold) + "*.",
            player_uids=[player.uid])
        await safe_edit(query,
            "Выдано *5 золота* игроку *" + player.name + "*. Итого: " + str(player.gold),
            parse_mode="Markdown",
            reply_markup=player_manage_keyboard(uid))

    # Инструкция по времени онлайна
    elif action.startswith("adm_setonline_"):
        uid = int(action.split("_")[-1])
        await safe_edit(query,
            "Используй команду:\n/admin\\_onlinetime " + str(uid) + " <минуты>\n\nДиапазон: 1 — 60000 минут",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Панель", callback_data="adm_panel"),
            ]]))

    # Карточка игрока
    elif action.startswith("adm_showplayer_"):
        uid = int(action.split("_")[-1])
        player = await Player.objects.get_or_none(uid=uid)
        if not player:
            await safe_edit(query, "Игрок не найден.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Панель", callback_data="adm_panel"),
                ]]))
            return
        status = "Онлайн" if player.online else "Оффлайн"
        text = (
            "*" + player.name + "* (uid: `" + str(player.uid) + "`)\n"
            + "━━━━━━━━━━━━━━━━━━\n"
            + "Уровень: " + str(player.level) + "\n"
            + "💰 Золото: " + str(player.gold) + "\n"
            + "Время в игре: " + ctime(player.totalxp) + "\n"
            + status
        )
        await safe_edit(query, text, parse_mode="Markdown",
            reply_markup=player_manage_keyboard(player.uid))

    # Таймаут оффлайна — инфо
    elif action == "adm_timeout_info":
        secs = cfg.OFFLINE_TIMEOUT
        mins = secs // 60
        text = (
            "*Таймаут оффлайна*\n\n"
            + "Текущее значение: *" + str(secs) + " сек* (" + str(mins) + " мин)\n\n"
            + "Изменить командой:\n"
            + "/admin\\_timeout <секунды>\n\n"
            + "300=5мин | 600=10мин | 900=15мин | 3600=1ч"
        )
        await safe_edit(query, text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Панель", callback_data="adm_panel"),
            ]]))

    elif action == "adm_panel":
        await safe_edit(query, "*Панель администратора*",
            parse_mode="Markdown",
            reply_markup=admin_panel_keyboard())

    # ── Настройки сервера ────────────────────────
    elif action == "adm_settings_menu":
        await safe_edit(query,
            "*Настройки сервера*\n\n"
            + "⏱️ Таймаут оффлайна: " + str(cfg.OFFLINE_TIMEOUT // 60) + " мин\n"
            + "🎮 Интервал тика: " + str(cfg.INTERVAL) + " сек\n"
            + "📊 TIME_BASE: " + str(cfg.TIME_BASE) + " сек\n"
            + "📈 TIME_EXP: " + str(cfg.TIME_EXP) + "\n\n"
            + "Команды:\n"
            + "/admin\\_timeout <сек>\n"
            + "/admin\\_interval <сек>\n"
            + "/admin\\_timebase <сек>\n"
            + "/admin\\_timeexp <знач>",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Панель", callback_data="adm_panel")],
            ]))

    elif action == "adm_interval_info":
        await safe_edit(query,
            "*Интервал игрового тика*\n\n"
            + "Текущее значение: *" + str(cfg.INTERVAL) + " сек*\n\n"
            + "Изменить:\n"
            + "/admin\\_interval <секунды>\n\n"
            + "1 сек = быстро (для тестов)\n"
            + "5 сек = нормально\n"
            + "10 сек = медленно",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Панель", callback_data="adm_panel")],
            ]))

    # ── Монстры ─────────────────────────────────
    elif action == "adm_monsters_menu":
        await safe_edit(query,
            "*Управление монстрами*\n\n"
            + "Команды:\n"
            + "/admin\\_spawn <uid> — встретить монстра\n"
            + "/admin\\_event <тип> — случайное событие\n\n"
            + "Типы событий: monster, treasure, trap, buff",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Панель", callback_data="adm_panel")],
            ]))

    # ── Боссы ───────────────────────────────────
    elif action == "adm_bosses_menu":
        await safe_edit(query,
            "*Управление боссами*\n\n"
            + "Команды:\n"
            + "/admin\\_spawnboss <uid> — вызвать босса\n"
            + "/admin\\_killboss — убить активного босса",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Панель", callback_data="adm_panel")],
            ]))


# ── Текстовые команды ─────────────────────────

async def cmd_admin_find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_find <имя или uid>"""
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("Использование: /admin\\_find <имя или uid>", parse_mode="Markdown")
        return
    q = " ".join(context.args)
    try:
        player = await Player.objects.get_or_none(uid=int(q))
    except ValueError:
        all_p = await Player.objects.all()
        matches = [p for p in all_p if q.lower() in p.name.lower()]
        player = matches[0] if matches else None
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return
    status = "Онлайн" if player.online else "Оффлайн"
    text = (
        "*" + player.name + "* (uid: `" + str(player.uid) + "`)\n"
        + "Уровень: " + str(player.level) + "\n"
        + "💰 Золото: " + str(player.gold) + "\n"
        + "Время в игре: " + ctime(player.totalxp) + "\n"
        + status
    )
    await update.message.reply_text(text, parse_mode="Markdown",
        reply_markup=player_manage_keyboard(player.uid))


async def cmd_admin_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_level <uid> <+N или N>"""
    if not is_admin(update.effective_user.id): return
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /admin\\_level <uid> <+N>", parse_mode="Markdown")
        return
    try:
        uid   = int(context.args[0])
        delta = int(context.args[1].replace("+", ""))
    except ValueError:
        await update.message.reply_text("Неверные аргументы.")
        return
    player = await Player.objects.get_or_none(uid=uid)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return
    player.level = max(1, player.level + delta)
    player.currentxp = 0
    player.nextxp = int(cfg.TIME_BASE * (cfg.TIME_EXP ** (player.level + 1)))
    await player.update(_columns=["level", "currentxp", "nextxp"])
    await send_to_players(update.get_bot(),
        "Администратор изменил твой уровень! Теперь ты *" + str(player.level) + " уровня*.",
        player_uids=[player.uid])
    await update.message.reply_text(
        "Уровень *" + player.name + "* изменён на *" + str(player.level) + "*.",
        parse_mode="Markdown")


async def cmd_admin_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_token <uid> [N]"""
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("Использование: /admin\\_token <uid> [кол-во]", parse_mode="Markdown")
        return
    try:
        uid    = int(context.args[0])
        amount = int(context.args[1]) if len(context.args) > 1 else 1
    except ValueError:
        await update.message.reply_text("Неверные аргументы.")
        return
    player = await Player.objects.get_or_none(uid=uid)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return
    player.gold += amount
    await player.update(_columns=["gold"])
    await send_to_players(update.get_bot(),
        "Администратор выдал *" + str(amount) + " золота*! Всего: *" + str(player.gold) + "*.",
        player_uids=[player.uid])
    await update.message.reply_text(
        "Выдано *" + str(amount) + "* золота игроку *" + player.name + "*.",
        parse_mode="Markdown")


async def cmd_admin_onlinetime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_onlinetime <uid> <минуты 1-60000>"""
    if not is_admin(update.effective_user.id): return
    if len(context.args) < 2:
        await update.message.reply_text(
            "Использование: /admin\\_onlinetime <uid> <минуты>\nДиапазон: 1 — 60000 (≈1000 часов)",
            parse_mode="Markdown")
        return
    try:
        uid     = int(context.args[0])
        minutes = max(1, min(60000, int(context.args[1])))
    except ValueError:
        await update.message.reply_text("Неверные аргументы.")
        return
    player = await Player.objects.get_or_none(uid=uid)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return
    player.totalxp = minutes * 60
    await player.update(_columns=["totalxp"])
    await update.message.reply_text(
        "Время онлайна *" + player.name + "* установлено: *" + ctime(player.totalxp) + "*.",
        parse_mode="Markdown")


async def cmd_admin_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_timeout <секунды 60-86400>  — таймаут оффлайна"""
    if not is_admin(update.effective_user.id): return
    if not context.args:
        secs = cfg.OFFLINE_TIMEOUT
        mins = secs // 60
        await update.message.reply_text(
            "Текущий таймаут: *" + str(secs) + " сек* (" + str(mins) + " мин)\n\n"
            + "Использование: /admin\\_timeout <секунды>\nМин: 60, макс: 86400",
            parse_mode="Markdown")
        return
    try:
        seconds = max(60, min(86400, int(context.args[0])))
    except ValueError:
        await update.message.reply_text("Неверное значение.")
        return
    cfg.OFFLINE_TIMEOUT = seconds
    await update.message.reply_text(
        "Таймаут оффлайна: *" + str(seconds) + " сек* (" + str(seconds // 60) + " мин)\n\n"
        + "Для постоянного сохранения добавь OFFLINE\\_TIMEOUT=" + str(seconds) + " в .env",
        parse_mode="Markdown")


async def cmd_admin_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_interval <секунды 1-60> — интервал игрового тика"""
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text(
            "Текущий тик: *" + str(cfg.INTERVAL) + " сек*\n\n"
            + "Использование: /admin\\_interval <секунды>\nМин: 1, макс: 60\n\n"
            + "ВНИМАНИЕ: Изменение влияет на скорость прокачки!",
            parse_mode="Markdown")
        return
    try:
        seconds = max(1, min(60, int(context.args[0])))
    except ValueError:
        await update.message.reply_text("Неверное значение.")
        return
    cfg.INTERVAL = seconds
    await update.message.reply_text(
        "Интервал тика: *" + str(seconds) + " сек*\n\n"
        + "Для постоянного сохранения добавь GAME\\_INTERVAL=" + str(seconds) + " в .env",
        parse_mode="Markdown")


async def cmd_admin_timebase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_timebase <секунды> — базовое время до уровня"""
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text(
            "Текущее TIME\\_BASE: *" + str(cfg.TIME_BASE) + " сек* (" + ctime(cfg.TIME_BASE) + ")\n\n"
            + "Использование: /admin\\_timebase <секунды>\n"
            + "По умолчанию: 600 (10 минут)",
            parse_mode="Markdown")
        return
    try:
        seconds = max(60, min(36000, int(context.args[0])))
    except ValueError:
        await update.message.reply_text("Неверное значение.")
        return
    cfg.TIME_BASE = seconds
    await update.message.reply_text(
        "TIME_BASE: *" + str(seconds) + " сек* (" + ctime(seconds) + ")\n\n"
        + "Для постоянного сохранения добавь TIME\\_BASE=" + str(seconds) + " в .env",
        parse_mode="Markdown")


async def cmd_admin_timeexp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_timeexp <значение> — экспонента роста уровней"""
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text(
            "Текущая TIME\\_EXP: *" + str(cfg.TIME_EXP) + "*\n\n"
            + "Использование: /admin\\_timeexp <значение>\n"
            + "По умолчанию: 1.16\nЧем больше — тем медленнее прокачка.",
            parse_mode="Markdown")
        return
    try:
        exp = float(context.args[0])
        if exp < 1.0 or exp > 2.0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("Неверное значение. Диапазон: 1.0 — 2.0")
        return
    cfg.TIME_EXP = exp
    await update.message.reply_text(
        "TIME_EXP: *" + str(exp) + "*\n\n"
        + "Для постоянного сохранения добавь TIME\\_EXP=" + str(exp) + " в .env",
        parse_mode="Markdown")


async def cmd_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_broadcast <текст> — сообщение всем игрокам"""
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text(
            "Использование: /admin\\_broadcast <текст>\n"
            + "Отправляет сообщение всем онлайн-игрокам.",
            parse_mode="Markdown")
        return
    text = " ".join(context.args)
    players = await Player.objects.all(online=True)
    count = 0
    for p in players:
        try:
            await send_to_players(update.get_bot(), text, player_uids=[p.uid])
            count += 1
            await asyncio.sleep(0.1)
        except Exception as e:
            logging.warning("Broadcast to %s: %s", p.name, e)
    await update.message.reply_text(
        "Сообщение отправлено *" + str(count) + "* игрокам.",
        parse_mode="Markdown")


async def cmd_admin_allusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_allusers — сообщение всем игрокам (даже оффлайн)"""
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text(
            "Использование: /admin\\_allusers <текст>",
            parse_mode="Markdown")
        return
    text = " ".join(context.args)
    players = await Player.objects.all()
    count = 0
    for p in players:
        try:
            await send_to_players(update.get_bot(), text, player_uids=[p.uid])
            count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logging.warning("Allusers to %s: %s", p.name, e)
    await update.message.reply_text(
        "Сообщение отправлено *" + str(count) + "* игрокам.",
        parse_mode="Markdown")


async def cmd_admin_kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_kick <uid> — выставить игрока оффлайн"""
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("Использование: /admin\\_kick <uid>", parse_mode="Markdown")
        return
    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Неверный uid.")
        return
    player = await Player.objects.get_or_none(uid=uid)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return
    player.online = False
    await player.update(_columns=["online"])
    await update.message.reply_text(
        "*" + player.name + "* выставлен оффлайн.",
        parse_mode="Markdown")


async def cmd_admin_wipe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_wipe <uid> — сбросить прогресс игрока"""
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text(
            "Использование: /admin\\_wipe <uid>\n"
            + "Сбрасывает уровень, XP, токены, инвентарь...",
            parse_mode="Markdown")
        return
    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Неверный uid.")
        return
    player = await Player.objects.get_or_none(uid=uid)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return
    player.level = 1
    player.currentxp = 0
    player.nextxp = cfg.TIME_BASE * 2
    player.totalxp = 0
    player.gold = 0
    player.online = False
    player.lastlogin = 0
    player.state = "peaceful"
    player.state_context = "{}"
    await player.update(_columns=["level", "currentxp", "nextxp", "totalxp", "gold", "online", "lastlogin", "state", "state_context"])
    await update.message.reply_text(
        "Прогресс *"+player.name+"* сброшен.",
        parse_mode="Markdown")


async def cmd_admin_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_delete <uid> — удалить игрока"""
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("Использование: /admin\\_delete <uid>", parse_mode="Markdown")
        return
    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Неверный uid.")
        return
    player = await Player.objects.get_or_none(uid=uid)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return
    name = player.name
    await player.delete()
    await update.message.reply_text(
        "Игрок *" + name + "* удалён.",
        parse_mode="Markdown")


async def cmd_admin_heal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_heal <uid> — восстановить HP игрока"""
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("Использование: /admin\\_heal <uid>", parse_mode="Markdown")
        return
    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Неверный uid.")
        return
    player = await Player.objects.get_or_none(uid=uid)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return
    player.currenthp = player.maxhp
    await player.update(_columns=["currenthp"])
    await send_to_players(update.get_bot(),
        "Администратор восстановил тебе HP!",
        player_uids=[player.uid])
    await update.message.reply_text(
        "HP игрока *" + player.name + "* восстановлены.",
        parse_mode="Markdown")


async def cmd_admin_gold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_gold <uid> <кол-во> — изменить баланс"""
    if not is_admin(update.effective_user.id): return
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /admin\\_gold <uid> <кол-во>", parse_mode="Markdown")
        return
    try:
        uid = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Неверные аргументы.")
        return
    player = await Player.objects.get_or_none(uid=uid)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return
    player.gold = max(0, player.gold + amount)
    await player.update(_columns=["gold"])
    await send_to_players(update.get_bot(),
        f"Администратор изменил баланс! Теперь у тебя *{player.gold}* золота.",
        player_uids=[player.uid])
    await update.message.reply_text(
        f"Баланс {player.name}: *{player.gold}* золота.",
        parse_mode="Markdown")


async def cmd_admin_race(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_race <uid> <раса> — установить расу"""
    if not is_admin(update.effective_user.id): return
    if len(context.args) < 2:
        races = ", ".join(cfg.RACES.keys())
        await update.message.reply_text(
            "Использование: /admin\\_race <uid> <раса>\n"
            + "Доступные расы: " + races,
            parse_mode="Markdown")
        return
    try:
        uid = int(context.args[0])
        race = context.args[1].lower()
    except (ValueError, IndexError):
        await update.message.reply_text("Неверные аргументы.")
        return
    if race not in cfg.RACES:
        await update.message.reply_text("Неизвестная раса: " + race)
        return
    player = await Player.objects.get_or_none(uid=uid)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return
    player.race = race
    await player.update(_columns=["race"])
    race_name = cfg.RACES[race]["ru"]
    await send_to_players(update.get_bot(),
        f"Администратор изменил тебе расу! Теперь ты *{race_name}*.",
        player_uids=[player.uid])
    await update.message.reply_text(
        f"Раса {player.name} изменена на *{race_name}*.",
        parse_mode="Markdown")


async def cmd_admin_drop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_drop <uid>"""
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("Использование: /admin\\_drop <uid>", parse_mode="Markdown")
        return
    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Неверный uid.")
        return
    player = await Player.objects.get_or_none(uid=uid)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return
    item, slot, replaced = await get_item(player)
    upgrade = " УЛУЧШЕНИЕ!" if replaced else ""
    await update.message.reply_text(
        "Дроп для *" + player.name + "*:\n" + item_string(item) + upgrade,
        parse_mode="Markdown")


async def cmd_admin_setonline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_setonline <uid> <0|1>"""
    if not is_admin(update.effective_user.id): return
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /admin\\_setonline <uid> <0|1>", parse_mode="Markdown")
        return
    try:
        uid    = int(context.args[0])
        status = bool(int(context.args[1]))
    except ValueError:
        await update.message.reply_text("Неверные аргументы.")
        return
    player = await Player.objects.get_or_none(uid=uid)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return
    player.online = status
    if status:
        player.lastlogin = int(datetime.today().timestamp())
    await player.update(_columns=["online", "lastlogin"])
    s = "онлайн" if status else "оффлайн"
    await update.message.reply_text("*" + player.name + "* теперь " + s + ".", parse_mode="Markdown")


async def cmd_admin_spawn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_spawn <uid> — вызвать монстра к игроку"""
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text(
            "Использование: /admin\\_spawn <uid>\n"
            + "Вызывает монстра к указанному игроку.",
            parse_mode="Markdown")
        return
    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Неверный uid.")
        return
    player = await Player.objects.get_or_none(uid=uid)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return
    if not player.online:
        await update.message.reply_text("Игрок не онлайн.")
        return
    from game.factories import create_encounter
    monster, xp = create_encounter(player.level)
    answer = (
        f"🧟 *{monster.name}* атакует!\n"
        f"Уровень угрозы: {monster.threat}\n"
        f"Награда: {xp} XP"
    )
    await send_to_players(update.get_bot(), answer, player_uids=[player.uid])
    await update.message.reply_text(
        "Монстр вызван к *" + player.name + "*.",
        parse_mode="Markdown")


async def cmd_admin_spawnboss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_spawnboss <uid> — вызвать босса к игроку"""
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text(
            "Использование: /admin\\_spawnboss <uid>\n"
            + "Вызывает босса к указанному игроку.",
            parse_mode="Markdown")
        return
    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Неверный uid.")
        return
    player = await Player.objects.get_or_none(uid=uid)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return
    if not player.online:
        await update.message.reply_text("Игрок не онлайн.")
        return
    bosses = await Boss.objects.filter(defeated=False).all()
    if not bosses:
        await update.message.reply_text("Нет доступных боссов (все побеждены).")
        return
    boss = bosses[0]
    await send_to_players(update.get_bot(),
        f"👹 *{boss.title}* появился поблизости!\n"
        f"Уровень: {boss.level}\n"
        f"Локация: {boss.location_name}",
        player_uids=[player.uid])
    await update.message.reply_text(
        f"Босс *{boss.title}* вызван к *{player.name}*!",
        parse_mode="Markdown")


async def cmd_admin_killboss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_killboss — убить активного босса"""
    if not is_admin(update.effective_user.id): return
    boss = await Boss.objects.get_or_none(defeated=False)
    if not boss:
        await update.message.reply_text("Нет активного босса.")
        return
    boss_name = boss.title
    boss.defeated = True
    await boss.update(_columns=["defeated"])
    await update.message.reply_text(
        f"Босс *{boss_name}* побеждён!",
        parse_mode="Markdown")


async def cmd_admin_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_event <тип> — запустить событие"""
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text(
            "Использование: /admin\\_event <тип>\n"
            + "Типы: monster, treasure, trap, buff, boss",
            parse_mode="Markdown")
        return
    event_type = context.args[0].lower()
    allowed = ["monster", "treasure", "trap", "buff", "boss"]
    if event_type not in allowed:
        await update.message.reply_text("Неверный тип: " + ", ".join(allowed))
        return
    players = await Player.objects.all(online=True)
    if not players:
        await update.message.reply_text("Нет онлайн игроков.")
        return
    from game.events import randomevent
    count = 0
    for p in players:
        try:
            await randomevent(update.get_bot(), p, forced_type=event_type)
            count += 1
            await asyncio.sleep(0.1)
        except Exception as e:
            logging.warning("Event %s for %s: %s", event_type, p.name, e)
    await update.message.reply_text(
        f"Событие {event_type} отправлено *{count}* игрокам.",
        parse_mode="Markdown")


async def cmd_admin_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_daily — создать daily квесты для всех онлайн игроков"""
    if not is_admin(update.effective_user.id):
        return
    
    from loops import generate_daily_quests
    bot = context.bot
    
    await update.message.reply_text("🎯 Генерация daily квестов...")
    await generate_daily_quests(bot)
    await update.message.reply_text("✅ Daily квесты созданы для всех онлайн игроков!")


async def cmd_admin_quest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_quest [uid|all] [type] — создать квест игроку или всем"""
    if not is_admin(update.effective_user.id):
        return
    
    args = context.args
    bot = context.bot
    
    if not args or args[0] == "all":
        from loops import generate_daily_quests
        await generate_daily_quests(bot)
        await update.message.reply_text("✅ Квесты созданы для всех онлайн игроков!")
        return
    
    try:
        player_uid = int(args[0])
    except ValueError:
        await update.message.reply_text(
            "Использование:\n"
            + "/admin\\_quest all — всем\n"
            + "/admin\\_quest <uid> [type] — игроку\n"
            + "Типы: daily, location, periodic",
            parse_mode="Markdown")
        return
    
    player = await Player.objects.get_or_none(uid=player_uid)
    if not player:
        await update.message.reply_text("❌ Игрок не найден")
        return
    
    quest_type = args[1] if len(args) > 1 else "daily"
    allowed_types = ["daily", "location", "periodic"]
    if quest_type not in allowed_types:
        await update.message.reply_text(f"Неверный тип. Используйте: {', '.join(allowed_types)}")
        return
    
    from handlers.quests import offer_quest
    await offer_quest(bot, player, quest_type=quest_type)
    await update.message.reply_text(
        f"✅ Квест ({quest_type}) предложен игроку *{player.name}*!",
        parse_mode="Markdown")


def register(app: Application):
    app.add_handler(CommandHandler("admin",            cmd_admin))
    app.add_handler(CommandHandler("admin_find",       cmd_admin_find))
    app.add_handler(CommandHandler("admin_level",      cmd_admin_level))
    app.add_handler(CommandHandler("admin_token",      cmd_admin_token))
    app.add_handler(CommandHandler("admin_onlinetime", cmd_admin_onlinetime))
    app.add_handler(CommandHandler("admin_timeout",    cmd_admin_timeout))
    app.add_handler(CommandHandler("admin_interval",   cmd_admin_interval))
    app.add_handler(CommandHandler("admin_timebase",  cmd_admin_timebase))
    app.add_handler(CommandHandler("admin_timeexp",    cmd_admin_timeexp))
    app.add_handler(CommandHandler("admin_broadcast", cmd_admin_broadcast))
    app.add_handler(CommandHandler("admin_allusers", cmd_admin_allusers))
    app.add_handler(CommandHandler("admin_kick",      cmd_admin_kick))
    app.add_handler(CommandHandler("admin_wipe",     cmd_admin_wipe))
    app.add_handler(CommandHandler("admin_delete",   cmd_admin_delete))
    app.add_handler(CommandHandler("admin_heal",     cmd_admin_heal))
    app.add_handler(CommandHandler("admin_gold",     cmd_admin_gold))
    app.add_handler(CommandHandler("admin_race",       cmd_admin_race))
    app.add_handler(CommandHandler("admin_drop",       cmd_admin_drop))
    app.add_handler(CommandHandler("admin_setonline",  cmd_admin_setonline))
    app.add_handler(CommandHandler("admin_spawn",      cmd_admin_spawn))
    app.add_handler(CommandHandler("admin_spawnboss", cmd_admin_spawnboss))
    app.add_handler(CommandHandler("admin_killboss",  cmd_admin_killboss))
    app.add_handler(CommandHandler("admin_event",    cmd_admin_event))
    app.add_handler(CommandHandler("admin_daily",   cmd_admin_daily))
    app.add_handler(CommandHandler("admin_quest",  cmd_admin_quest))
    app.add_handler(CallbackQueryHandler(callback_admin, pattern="^adm_"))
