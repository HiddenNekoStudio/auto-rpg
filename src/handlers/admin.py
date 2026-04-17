"""
handlers/admin.py — скрытые административные команды
"""
import random
import asyncio
from datetime import datetime
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import NetworkError, RetryAfter, TimedOut
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

import config as cfg
from db import Player, Quest
from loot import get_item
from bot import item_string, ctime, send_to_players


def is_admin(uid): return uid in cfg.SERVER_ADMINS


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
        ],
        [
            InlineKeyboardButton(
                "⏱️ Таймаут оффлайна: " + str(mins) + " мин",
                callback_data="adm_timeout_info"
            ),
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
    if not is_admin(update.effective_user.id): return
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
        if await Quest.objects.get_or_none():
            await safe_edit(query, "Квест уже активен!", parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Панель", callback_data="adm_panel"),
                ]]))
            return
        from game.quests import startquest
        await startquest(query.get_bot())
        await safe_edit(query, "Новый квест запущен!",
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
        player.tokens += 5
        await player.update(_columns=["tokens"])
        await send_to_players(query.get_bot(),
            "Администратор выдал *5 токенов лута*! Всего: *" + str(player.tokens) + "*.",
            player_uids=[player.uid])
        await safe_edit(query,
            "Выдано *5 токенов* игроку *" + player.name + "*. Итого: " + str(player.tokens),
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
            + "Токены: " + str(player.tokens) + "\n"
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
        + "Токены: " + str(player.tokens) + "\n"
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
    player.tokens += amount
    await player.update(_columns=["tokens"])
    await send_to_players(update.get_bot(),
        "Администратор выдал *" + str(amount) + " токен(ов)*! Всего: *" + str(player.tokens) + "*.",
        player_uids=[player.uid])
    await update.message.reply_text(
        "Выдано *" + str(amount) + "* токен(ов) игроку *" + player.name + "*.",
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


def register(app: Application):
    app.add_handler(CommandHandler("admin",            cmd_admin))
    app.add_handler(CommandHandler("admin_find",       cmd_admin_find))
    app.add_handler(CommandHandler("admin_level",      cmd_admin_level))
    app.add_handler(CommandHandler("admin_token",      cmd_admin_token))
    app.add_handler(CommandHandler("admin_onlinetime", cmd_admin_onlinetime))
    app.add_handler(CommandHandler("admin_timeout",    cmd_admin_timeout))
    app.add_handler(CommandHandler("admin_drop",       cmd_admin_drop))
    app.add_handler(CommandHandler("admin_setonline",  cmd_admin_setonline))
    app.add_handler(CallbackQueryHandler(callback_admin, pattern="^adm_"))
