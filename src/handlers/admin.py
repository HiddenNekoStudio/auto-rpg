"""
handlers/admin.py — скрытые административные команды

Содержит админ-панель, управление игроками (уровень, токены, XP, раса),
управление монстрами и боссами, настройки сервера (таймаут, интервал тика),
а также массовую рассылку сообщений.
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


def validate_admin_args(uid_str: str, amount_str: str = None,
                         min_val: int = None, max_val: int = None,
                         uid_required: bool = True) -> tuple:
    """
    Валидация аргументов для admin команд.
    Возвращает: (uid, amount, error_message)
    """
    try:
        uid = int(uid_str) if uid_str else 0
        amount = int(amount_str) if amount_str else 0

        if uid_required and (uid <= 0 or uid > 10**12):
            return None, None, "Invalid user ID"

        if amount_str is not None:
            if min_val is not None and amount < min_val:
                return None, None, f"Amount must be >= {min_val}"
            if max_val is not None and amount > max_val:
                return None, None, f"Amount must be <= {max_val}"

        return uid, amount, None
    except (ValueError, IndexError):
        return None, None, "Invalid arguments"


def is_admin(uid: int) -> bool:
    """
    Проверяет, является ли пользователь администратором.
    
    ПОЧЕМУ: логирование отказов — для аудита безопасности
    ПОЧЕМУ: возвращает bool — вызывающий код решает что делать
    """
    if not cfg.SERVER_ADMINS:
        logger.warning(f"Access denied: no ADMIN_IDS configured (uid={uid})")
        return False
    
    is_admin = uid in cfg.SERVER_ADMINS
    
    if not is_admin:
        logger.warning(f"Non-admin access attempt: uid={uid}")
    
    return is_admin


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


def admin_panel_keyboard(lang: str = "ru"):
    mins = cfg.OFFLINE_TIMEOUT // 60
    interval_secs = cfg.INTERVAL
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ Событие всем" if lang != "en" else "⚡ Event all",    callback_data="adm_event"),
            InlineKeyboardButton("🗺️ Начать квест" if lang != "en" else "🗺️ Start quest",    callback_data="adm_quest"),
        ],
        [
            InlineKeyboardButton("❌ Завершить квест" if lang != "en" else "❌ End quest",  callback_data="adm_endquest"),
            InlineKeyboardButton("📊 Статистика" if lang != "en" else "📊 Statistics",       callback_data="adm_stats"),
        ],
        [
            InlineKeyboardButton("👤 Управление игроком" if lang != "en" else "👤 Player mgmt", callback_data="adm_player_menu"),
            InlineKeyboardButton("🔧 Настройки сервера" if lang != "en" else "🔧 Server settings", callback_data="adm_settings_menu"),
        ],
        [
            InlineKeyboardButton(
                ("⏱️ Таймаут: " if lang != "en" else "⏱️ Timeout: ") + str(mins) + (" мин" if lang != "en" else " min"),
                callback_data="adm_timeout_info"
            ),
            InlineKeyboardButton(
                ("🎮 Тик: " if lang != "en" else "🎮 Tick: ") + str(interval_secs) + (" сек" if lang != "en" else " sec"),
                callback_data="adm_interval_info"
            ),
        ],
        [
            InlineKeyboardButton("🧟 Монстры" if lang != "en" else "🧟 Monsters",  callback_data="adm_monsters_menu"),
            InlineKeyboardButton("👹 Боссы" if lang != "en" else "👹 Bosses",   callback_data="adm_bosses_menu"),
        ],
    ])


def player_manage_keyboard(uid, lang: str = "ru"):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎖️ +Уровень" if lang != "en" else "🎖️ +Level",    callback_data="adm_addlevel_" + str(uid)),
            InlineKeyboardButton("🎫 +5 Токенов" if lang != "en" else "🎫 +5 Tokens",  callback_data="adm_addtokens_" + str(uid)),
        ],
        [
            InlineKeyboardButton("⏱️ Время онлайна" if lang != "en" else "⏱️ Online time", callback_data="adm_setonline_" + str(uid)),
        ],
        [InlineKeyboardButton("🔙 Панель" if lang != "en" else "🔙 Panel", callback_data="adm_panel")],
    ])


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Панель администратора (/admin)."""
    uid = update.effective_user.id
    if not is_admin(uid):
        logging.info(f"Non-admin /admin attempt: uid={uid}")
        await update.message.reply_text("Нет доступа.")
        return
    logging.info(f"Admin command from uid: {uid}")
    await update.message.reply_text(
        "*Панель администратора*", parse_mode="Markdown",
        reply_markup=admin_panel_keyboard())


async def callback_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок админ-панели."""
    query = update.callback_query
    if not is_admin(query.from_user.id):
        adm_lang = "en" if query.from_user.language_code == "en" else "ru"
        msg = "No access." if adm_lang == "en" else "Нет доступа."
        await query.answer(msg, show_alert=True)
        return
    await query.answer()
    action = query.data
    admin_pl = await Player.objects.get_or_none(uid=query.from_user.id)
    lang = admin_pl.lang or "ru" if admin_pl else "ru"
    _back = "🔙 Панель" if lang != "en" else "🔙 Panel"
    _panel = "*Панель администратора*" if lang != "en" else "*Admin Panel*"

    # Статистика
    if action == "adm_stats":
        total    = await Player.objects.count()
        online   = await Player.objects.filter(online=True).count()
        questing = await Player.objects.filter(onquest=True).count()
        quest    = await Quest.objects.get_or_none()
        if quest:
            q_str = ("Активен: " if lang != "en" else "Active: ") + quest.players
        else:
            q_str = "Нет" if lang != "en" else "None"
        text = (
            ("*Статистика сервера*\n" if lang != "en" else "*Server Statistics*\n")
            + "━━━━━━━━━━━━━━━━━━\n"
            + ("Всего игроков: " if lang != "en" else "Total players: ") + str(total) + "\n"
            + ("Онлайн: " if lang != "en" else "Online: ") + str(online) + "\n"
            + ("На квесте: " if lang != "en" else "On quest: ") + str(questing) + "\n"
            + ("Квест: " if lang != "en" else "Quest: ") + q_str
        )
        await safe_edit(query, text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(_back, callback_data="adm_panel"),
            ]]))

    # Событие всем онлайн игрокам
    elif action == "adm_event":
        players = await Player.objects.all(online=True)
        if not players:
            _no_online = "Нет онлайн игроков." if lang != "en" else "No online players."
            await safe_edit(query, _no_online,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(_back, callback_data="adm_panel"),
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
        _sent = ("Событие отправлено " if lang != "en" else "Event sent to ") + "*" + str(count) + "* " + ("игрокам." if lang != "en" else "players.")
        await safe_edit(query,
            _sent,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(_back, callback_data="adm_panel"),
            ]]))

    # Квест
    elif action == "adm_quest":
        from loops import generate_daily_quests
        await generate_daily_quests(query.get_bot())
        _quest_updated = "Ежедневные квесты обновлены для всех игроков!" if lang != "en" else "Daily quests updated for all players!"
        await safe_edit(query, _quest_updated,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(_back, callback_data="adm_panel"),
            ]]))

    elif action == "adm_endquest":
        quest = await Quest.objects.get_or_none()
        if not quest:
            _no_quest = "Нет активного квеста." if lang != "en" else "No active quest."
            await safe_edit(query, _no_quest,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(_back, callback_data="adm_panel"),
                ]]))
            return
        _end_quest = "Завершить квест " if lang != "en" else "End quest "
        _win = "Победа" if lang != "en" else "Victory"
        _fail = "Провал" if lang != "en" else "Fail"
        await safe_edit(query,
            _end_quest + "*" + quest.players + "*?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(_win,  callback_data="adm_endquest_win"),
                    InlineKeyboardButton(_fail,  callback_data="adm_endquest_fail"),
                ],
                [InlineKeyboardButton(_back, callback_data="adm_panel")],
            ]))

    elif action in ("adm_endquest_win", "adm_endquest_fail"):
        quest = await Quest.objects.get_or_none()
        if not quest:
            _already = "Квест уже завершён." if lang != "en" else "Quest already finished."
            await safe_edit(query, _already)
            return
        from game.quests import endquest
        win = (action == "adm_endquest_win")
        await endquest(query.get_bot(), quest, win=win)
        _victory = "Победа" if lang != "en" else "Victory"
        _result = _victory if win else ("Провал" if lang != "en" else "Fail")
        await safe_edit(query, ("Квест завершён: " if lang != "en" else "Quest finished: ") + _result,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(_back, callback_data="adm_panel"),
            ]]))

    # Управление игроком
    elif action == "adm_player_menu":
        _player_mgmt = "*Управление игроком*\n\n" if lang != "en" else "*Player Management*\n\n"
        _find = "Найти игрока:\n" if lang != "en" else "Find player:\n"
        _name_or_uid = "<имя или uid>\n\n" if lang != "en" else "<name or uid>\n\n"
        _direct_cmds = "Прямые команды:\n" if lang != "en" else "Direct commands:\n"
        _minutes = "<минуты>" if lang != "en" else "<minutes>"
        await safe_edit(query,
            _player_mgmt
            + _find
            + "/admin\\_find " + _name_or_uid
            + _direct_cmds
            + "/admin\\_level <uid> <+N>\n"
            + "/admin\\_token <uid> [N]\n"
            + "/admin\\_onlinetime <uid> " + _minutes,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(_back, callback_data="adm_panel"),
            ]]))

    # +Уровень
    elif action.startswith("adm_addlevel_"):
        uid = int(action.split("_")[-1])
        player = await Player.objects.get_or_none(uid=uid)
        if not player:
            _not_found = "Игрок не найден." if lang != "en" else "Player not found."
            await safe_edit(query, _not_found,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(_back, callback_data="adm_panel"),
                ]]))
            return
        player.level += 1
        player.currentxp = 0
        player.nextxp = int(cfg.TIME_BASE * (cfg.TIME_EXP ** (player.level + 1)))
        await player.update(_columns=["level", "currentxp", "nextxp"])
        _pl_lang = player.lang or "ru"
        _lvl_msg = (
            "Администратор выдал *+1 уровень*! Теперь ты *" + str(player.level) + " уровня*."
            if _pl_lang != "en" else
            "Admin gave *+1 level*! You are now level *" + str(player.level) + "*."
        )
        await send_to_players(query.get_bot(), _lvl_msg, player_uids=[player.uid], force=True)
        _lvl_up = (
            "*" + player.name + "* повышен до *" + str(player.level) + "* уровня."
            if lang != "en" else
            "*" + player.name + "* upgraded to level *" + str(player.level) + "*."
        )
        await safe_edit(query, _lvl_up,
            parse_mode="Markdown",
            reply_markup=player_manage_keyboard(uid, lang))

    # +Токены
    elif action.startswith("adm_addtokens_"):
        uid = int(action.split("_")[-1])
        player = await Player.objects.get_or_none(uid=uid)
        if not player:
            _not_found = "Игрок не найден." if lang != "en" else "Player not found."
            await safe_edit(query, _not_found,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(_back, callback_data="adm_panel"),
                ]]))
            return
        player.tokens += 5
        await player.update(_columns=["tokens"])
        _pl_lang = player.lang or "ru"
        _token_msg = (
            "Администратор выдал *5 токенов*! Всего: *" + str(player.tokens) + "*."
            if _pl_lang != "en" else
            "Admin gave *5 tokens*! Total: *" + str(player.tokens) + "*."
        )
        await send_to_players(query.get_bot(), _token_msg, player_uids=[player.uid], force=True)
        _given = (
            "Выдано *5 токенов* игроку *" + player.name + "*. Итого: " + str(player.tokens)
            if lang != "en" else
            "Gave *5 tokens* to *" + player.name + "*. Total: " + str(player.tokens)
        )
        await safe_edit(query, _given,
            parse_mode="Markdown",
            reply_markup=player_manage_keyboard(uid, lang))

    # Инструкция по времени онлайна
    elif action.startswith("adm_setonline_"):
        uid = int(action.split("_")[-1])
        _online_help = (
            "Используй команду:\n/admin\\_onlinetime " + str(uid) + " <минуты>\n\nДиапазон: 1 — 60000 минут"
            if lang != "en" else
            "Use command:\n/admin\\_onlinetime " + str(uid) + " <minutes>\n\nRange: 1 — 60000 minutes"
        )
        await safe_edit(query, _online_help,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(_back, callback_data="adm_panel"),
            ]]))

    # Карточка игрока
    elif action.startswith("adm_showplayer_"):
        uid = int(action.split("_")[-1])
        player = await Player.objects.get_or_none(uid=uid)
        if not player:
            _not_found = "Игрок не найден." if lang != "en" else "Player not found."
            await safe_edit(query, _not_found,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(_back, callback_data="adm_panel"),
                ]]))
            return
        _online = "Онлайн" if lang != "en" else "Online"
        _offline = "Оффлайн" if lang != "en" else "Offline"
        status = _online if player.online else _offline
        _level = "Уровень" if lang != "en" else "Level"
        _gold = "💰 Золото" if lang != "en" else "💰 Gold"
        _playtime = "Время в игре" if lang != "en" else "Playtime"
        text = (
            "*" + player.name + "* (uid: `" + str(player.uid) + "`)\n"
            + "━━━━━━━━━━━━━━━━━━\n"
            + _level + ": " + str(player.level) + "\n"
            + _gold + ": " + str(player.gold) + "\n"
            + _playtime + ": " + ctime(player.totalxp, lang) + "\n"
            + status
        )
        await safe_edit(query, text, parse_mode="Markdown",
            reply_markup=player_manage_keyboard(player.uid, lang))

    # Таймаут оффлайна — инфо
    elif action == "adm_timeout_info":
        secs = cfg.OFFLINE_TIMEOUT
        mins = secs // 60
        _timeout_title = "*Таймаут оффлайна*\n\n" if lang != "en" else "*Offline Timeout*\n\n"
        _current_val = "Текущее значение: " if lang != "en" else "Current value: "
        _sec = " сек" if lang != "en" else " sec"
        _min = " мин" if lang != "en" else " min"
        _change_cmd = "Изменить командой:\n" if lang != "en" else "Change with command:\n"
        _seconds = "<секунды>" if lang != "en" else "<seconds>"
        text = (
            _timeout_title
            + _current_val + "*" + str(secs) + _sec + "* (" + str(mins) + _min + ")\n\n"
            + _change_cmd
            + "/admin\\_timeout " + _seconds + "\n\n"
            + "300=5" + _min + " | 600=10" + _min + " | 900=15" + _min + " | 3600=1" + ("ч" if lang != "en" else "h")
        )
        await safe_edit(query, text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(_back, callback_data="adm_panel"),
            ]]))

    elif action == "adm_panel":
        await safe_edit(query, _panel,
            parse_mode="Markdown",
            reply_markup=admin_panel_keyboard(lang))

    # ── Настройки сервера ────────────────────────
    elif action == "adm_settings_menu":
        _settings_title = "*Настройки сервера*\n\n" if lang != "en" else "*Server Settings*\n\n"
        _timeout_label = "⏱️ Таймаут оффлайна: " if lang != "en" else "⏱️ Offline timeout: "
        _interval_label = "🎮 Интервал тика: " if lang != "en" else "🎮 Tick interval: "
        _min = " мин" if lang != "en" else " min"
        _sec = " сек" if lang != "en" else " sec"
        _commands = "Команды:\n" if lang != "en" else "Commands:\n"
        _sec_short = "<сек>" if lang != "en" else "<sec>"
        _value = "<знач>" if lang != "en" else "<val>"
        await safe_edit(query,
            _settings_title
            + _timeout_label + str(cfg.OFFLINE_TIMEOUT // 60) + _min + "\n"
            + _interval_label + str(cfg.INTERVAL) + _sec + "\n"
            + "📊 TIME_BASE: " + str(cfg.TIME_BASE) + _sec + "\n"
            + "📈 TIME_EXP: " + str(cfg.TIME_EXP) + "\n\n"
            + _commands
            + "/admin\\_timeout " + _sec_short + "\n"
            + "/admin\\_interval " + _sec_short + "\n"
            + "/admin\\_timebase " + _sec_short + "\n"
            + "/admin\\_timeexp " + _value,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(_back, callback_data="adm_panel")],
            ]))

    elif action == "adm_interval_info":
        _interval_title = "*Интервал игрового тика*\n\n" if lang != "en" else "*Tick Interval*\n\n"
        _current = "Текущее значение: " if lang != "en" else "Current value: "
        _sec = " сек" if lang != "en" else " sec"
        _change = "Изменить:\n" if lang != "en" else "Change:\n"
        _seconds = "<секунды>" if lang != "en" else "<seconds>"
        _fast = "быстро (для тестов)" if lang != "en" else "fast (for testing)"
        _normal = "нормально" if lang != "en" else "normal"
        _slow = "медленно" if lang != "en" else "slow"
        await safe_edit(query,
            _interval_title
            + _current + "*" + str(cfg.INTERVAL) + _sec + "*\n\n"
            + _change
            + "/admin\\_interval " + _seconds + "\n\n"
            + "1" + _sec + " = " + _fast + "\n"
            + "5" + _sec + " = " + _normal + "\n"
            + "10" + _sec + " = " + _slow,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(_back, callback_data="adm_panel")],
            ]))

    # ── Монстры ─────────────────────────────────
    elif action == "adm_monsters_menu":
        _monster_title = "*Управление монстрами*\n\n" if lang != "en" else "*Monster Control*\n\n"
        _commands = "Команды:\n" if lang != "en" else "Commands:\n"
        _spawn_label = " — встретить монстра" if lang != "en" else " — encounter monster"
        _event_label = " — случайное событие" if lang != "en" else " — random event"
        _event_cmd = "/admin\\_event <тип>" if lang != "en" else "/admin\\_event <type>"
        _event_types = "Типы событий: " if lang != "en" else "Event types: "
        await safe_edit(query,
            _monster_title
            + _commands
            + "/admin\\_spawn <uid>" + _spawn_label + "\n"
            + _event_cmd + _event_label + "\n\n"
            + _event_types + "monster, treasure, trap, buff",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(_back, callback_data="adm_panel")],
            ]))

    # ── Боссы ───────────────────────────────────
    elif action == "adm_bosses_menu":
        _boss_title = "*Управление боссами*\n\n" if lang != "en" else "*Boss Control*\n\n"
        _commands = "Команды:\n" if lang != "en" else "Commands:\n"
        _spawnboss_label = " — вызвать босса" if lang != "en" else " — summon boss"
        _killboss_label = " — убить активного босса" if lang != "en" else " — kill active boss"
        await safe_edit(query,
            _boss_title
            + _commands
            + "/admin\\_spawnboss <uid>" + _spawnboss_label + "\n"
            + "/admin\\_killboss" + _killboss_label,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(_back, callback_data="adm_panel")],
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
        players = await Player.objects.filter(name__icontains=q).limit(20).all()
        if players:
            player = players[0]
        else:
            player = None
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return
    lang = player.lang or "ru"
    status = "Онлайн" if player.online else "Оффлайн"
    text = (
        "*" + player.name + "* (uid: `" + str(player.uid) + "`)\n"
        + "Уровень: " + str(player.level) + "\n"
        + "💰 Золото: " + str(player.gold) + "\n"
        + "Время в игре: " + ctime(player.totalxp, lang) + "\n"
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

    uid, delta, error = validate_admin_args(
        context.args[0],
        context.args[1].replace("+", ""),
        min_val=-100, max_val=100
    )
    if error:
        await update.message.reply_text(f"Ошибка: {error}")
        return

    player = await Player.objects.get_or_none(uid=uid)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return

    player.level = max(1, player.level + delta)
    player.currentxp = 0
    player.nextxp = int(cfg.TIME_BASE * (cfg.TIME_EXP ** (player.level + 1)))
    await player.update(_columns=["level", "currentxp", "nextxp"])
    _pl_lang = player.lang or "ru"
    _lvl_msg = (
        "Администратор изменил твой уровень! Теперь ты *" + str(player.level) + " уровня*."
        if _pl_lang != "en" else
        "Admin changed your level! You are now level *" + str(player.level) + "*."
    )
    await send_to_players(update.get_bot(), _lvl_msg, player_uids=[player.uid], force=True)
    admin_pl = await Player.objects.get_or_none(uid=update.effective_user.id)
    alang = admin_pl.lang or "ru" if admin_pl else "ru"
    await update.message.reply_text(
        ("Уровень " if alang != "en" else "Level ") + "*" + player.name + "* " + ("изменён на " if alang != "en" else "changed to ") + "*" + str(player.level) + "*.",
        parse_mode="Markdown")


async def cmd_admin_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_token <uid> [N] — выдать токены"""
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("Использование: /admin\\_token <uid> [кол-во]", parse_mode="Markdown")
        return

    amount_str = context.args[1] if len(context.args) > 1 else "1"
    uid, amount, error = validate_admin_args(
        context.args[0],
        amount_str,
        min_val=-1000, max_val=10000
    )
    if error:
        await update.message.reply_text(f"Ошибка: {error}")
        return

    player = await Player.objects.get_or_none(uid=uid)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return

    player.tokens += amount
    await player.update(_columns=["tokens"])
    _pl_lang = player.lang or "ru"
    _tok_msg = (
        "Администратор выдал *" + str(amount) + " токенов*! Всего: *" + str(player.tokens) + "*."
        if _pl_lang != "en" else
        "Admin gave *" + str(amount) + " tokens*! Total: *" + str(player.tokens) + "*."
    )
    await send_to_players(update.get_bot(), _tok_msg, player_uids=[player.uid], force=True)
    await update.message.reply_text(
        "Выдано *" + str(amount) + "* токенов игроку *" + player.name + "*.",
        parse_mode="Markdown")


async def cmd_admin_onlinetime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_onlinetime <uid> <минуты 1-60000>"""
    if not is_admin(update.effective_user.id): return
    if len(context.args) < 2:
        await update.message.reply_text(
            "Использование: /admin\\_onlinetime <uid> <минуты>\nДиапазон: 1 — 60000 (≈1000 часов)",
            parse_mode="Markdown")
        return

    uid, minutes, error = validate_admin_args(
        context.args[0],
        context.args[1],
        min_val=1, max_val=60000
    )
    if error:
        await update.message.reply_text(f"Ошибка: {error}")
        return

    player = await Player.objects.get_or_none(uid=uid)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return

    player.total_online_seconds = minutes * 60
    player.total_idle_seconds = 0
    await player.update(_columns=["total_online_seconds", "total_idle_seconds"])
    admin_pl = await Player.objects.get_or_none(uid=update.effective_user.id)
    alang = admin_pl.lang or "ru" if admin_pl else "ru"
    await update.message.reply_text(
        ("Время онлайна " if alang != "en" else "Online time ") + "*" + player.name + "* " + ("установлено: " if alang != "en" else "set to: ") + "*" + ctime(player.total_online_seconds, alang) + "*.",
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
    lang = "ru"
    if not context.args:
        await update.message.reply_text(
            "Текущее TIME\\_BASE: *" + str(cfg.TIME_BASE) + " сек* (" + ctime(cfg.TIME_BASE, lang) + ")\n\n"
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
        "TIME_BASE: *" + str(seconds) + " сек* (" + ctime(seconds, lang) + ")\n\n"
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
            await send_to_players(update.get_bot(), text, player_uids=[p.uid], force=True)
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
            await send_to_players(update.get_bot(), text, player_uids=[p.uid], force=True)
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
    player.hp = player.max_hp
    await player.update(_columns=["hp", "max_hp"])
    _pl_lang = player.lang or "ru"
    _heal_msg = (
        "Администратор восстановил тебе HP!"
        if _pl_lang != "en" else
        "Admin restored your HP!"
    )
    await send_to_players(update.get_bot(), _heal_msg, player_uids=[player.uid], force=True)
    await update.message.reply_text(
        "HP игрока *" + player.name + "* восстановлены.",
        parse_mode="Markdown")


async def cmd_admin_gold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_gold <uid> [+N/-N] — изменить баланс золота"""
    if not is_admin(update.effective_user.id): return
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /admin\\_gold <uid> <+N/-N>", parse_mode="Markdown")
        return

    uid, amount, error = validate_admin_args(
        context.args[0],
        context.args[1],
        min_val=-1000000, max_val=1000000
    )
    if error:
        await update.message.reply_text(f"Ошибка: {error}")
        return

    player = await Player.objects.get_or_none(uid=uid)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return

    player.gold = max(0, player.gold + amount)
    await player.update(_columns=["gold"])
    _pl_lang = player.lang or "ru"
    _action_ru = "добавлено" if amount > 0 else "изьято"
    _action_en = "added" if amount > 0 else "removed"
    _gold_msg = (
        f"Администратор {_action_ru} *{abs(amount)}* золота! Всего: *{player.gold}*."
        if _pl_lang != "en" else
        f"Admin {_action_en} *{abs(amount)}* gold! Balance: *{player.gold}*."
    )
    await send_to_players(update.get_bot(), _gold_msg, player_uids=[player.uid], force=True)
    await update.message.reply_text(
        f"Игроку *{player.name}* {_action_ru} *{abs(amount)}* золота. Баланс: *{player.gold}*.",
        parse_mode="Markdown")


async def cmd_admin_xp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_xp <uid> [+N/-N] — изменить XP"""
    if not is_admin(update.effective_user.id): return
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /admin\\_xp <uid> <+N/-N>", parse_mode="Markdown")
        return

    uid, amount, error = validate_admin_args(
        context.args[0],
        context.args[1],
        min_val=-1000000, max_val=1000000
    )
    if error:
        await update.message.reply_text(f"Ошибка: {error}")
        return

    player = await Player.objects.get_or_none(uid=uid)
    if not player:
        await update.message.reply_text("Игрок не найден.")
        return
    player.currentxp = max(0, player.currentxp + amount)
    await player.update(_columns=["currentxp"])
    _pl_lang = player.lang or "ru"
    _action_ru = "добавлено" if amount > 0 else "изьято"
    _action_en = "added" if amount > 0 else "removed"
    _xp_msg = (
        f"Администратор {_action_ru} *{abs(amount)}* XP!"
        if _pl_lang != "en" else
        f"Admin {_action_en} *{abs(amount)}* XP!"
    )
    await send_to_players(update.get_bot(), _xp_msg, player_uids=[player.uid], force=True)
    await update.message.reply_text(
        f"Игроку *{player.name}* {_action_ru} *{abs(amount)}* XP.",
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
    _pl_lang = player.lang or "ru"
    race_name = cfg.RACES[race].get(_pl_lang, cfg.RACES[race]["ru"])
    _race_msg = (
        f"Администратор изменил тебе расу! Теперь ты *{race_name}*."
        if _pl_lang != "en" else
        f"Admin changed your race! You are now *{race_name}*."
    )
    await send_to_players(update.get_bot(), _race_msg, player_uids=[player.uid], force=True)
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
    lang = player.lang or "ru"
    await update.message.reply_text(
        "Дроп для *" + player.name + "*:\n" + item_string(item, lang) + upgrade,
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
    """/admin_spawn [uid] — вызвать монстра к игроку или всем онлайн"""
    if not is_admin(update.effective_user.id): return
    
    if not context.args:
        from game.monsters import spawn_all
        bot = update.get_bot()
        await spawn_all(bot)
        await update.message.reply_text(
            "🧟 Монстры вызваны ко всем онлайн-игрокам!",
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
    await send_to_players(update.get_bot(), answer, player_uids=[player.uid], force=True)
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
    
    from game.bosses import ensure_bosses_available
    if not await ensure_bosses_available():
        await update.message.reply_text("Нет доступных боссов (не удалось восстановить).")
        return
    
    bosses = await Boss.objects.filter(defeated=False).all()
    if not bosses:
        await update.message.reply_text("Нет доступных боссов.")
        return
    
    import random
    boss = random.choice(bosses)
    await send_to_players(update.get_bot(),
        f"👹 *{boss.title}* появился поблизости!\n"
        f"Уровень: {boss.level}\n"
        f"Локация: {boss.location_name}",
        player_uids=[player.uid], force=True)
    await update.message.reply_text(
        f"Босс *{boss.title}* вызван к *{player.name}*!",
        parse_mode="Markdown")


async def cmd_admin_killboss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin_killboss — убить активного босса"""
    if not is_admin(update.effective_user.id): return
    import random
    bosses = await Boss.objects.filter(defeated=False).all()
    if not bosses:
        await update.message.reply_text("Нет активного босса.")
        return
    boss = random.choice(bosses)
    boss_name = boss.title
    boss.defeated = True
    boss.defeated_at = int(datetime.now().timestamp())
    await boss.update(_columns=["defeated", "defeated_at"])
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
    
    quest_type = args[1] if len(args) > 1 else "kill"
    allowed_types = ["kill", "explore", "xp", "duel", "boss", "survive", "streak", "rare"]
    if quest_type not in allowed_types:
        await update.message.reply_text(f"Неверный тип. Используйте: {', '.join(allowed_types)}")
        return
    
    from handlers.quests import offer_quest
    await offer_quest(bot, player, quest_type=quest_type)
    await update.message.reply_text(
        f"✅ Квест ({quest_type}) предложен игроку *{player.name}*!",
        parse_mode="Markdown")


def register(app: Application) -> None:
    """Регистрация всех админ-хендлеров."""
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
    app.add_handler(CommandHandler("admin_xp",        cmd_admin_xp))
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
