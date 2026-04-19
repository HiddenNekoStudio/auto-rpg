"""
handlers/user.py — /start, /profile, /pull, /info, /top
"""
import asyncio
import datetime
import logging
import random
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import NetworkError, RetryAfter, TimedOut
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

import config as cfg
from db import Player
from data.locations import format_location
from game.monsters import get_total_dps
from loot import get_item
from bot import ctime, item_string, format_short
from i18n import t, tip, CHANGELOG, CHANGELOG_EN
from core.cache import TTLCache

SLOT_EMOJI = {
    "weapon": "⚔️", "shield": "🛡️", "helmet": "⛑️",
    "chest":  "🦺", "gloves": "🧤", "boots":  "👢",
    "ring":   "💍", "amulet": "📿",
}


def sanitize_name(name: str) -> str:
    """Очистка имени от опасных символов"""
    if not name:
        return "Adventurer"
    name = name[:50]
    name = re.sub(r'```[\s\S]*?```', '', name)
    name = re.sub(r'`', '', name)
    emojis = re.findall(r'[\U0001F300-\U0001F9FF]', name)
    for e in emojis[3:]:
        name = name.replace(e, '')
    return name.strip() or "Adventurer"

# Rate limiting для callback — TTL cache вместо бесконечного dict
_callback_rate_limit = TTLCache(ttl=1.0, maxsize=10000)

def check_callback_rate(uid: int) -> bool:
    """Возвращает True если можно обработать, False если rate limited"""
    key = str(uid)
    if _callback_rate_limit.get(key) is not None:
        return False
    _callback_rate_limit.set(key, True)
    return True


async def safe_edit(query, text: str, keyboard=None, parse_mode: str = "Markdown",
                    retries: int = 3, reply_markup=None):
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
                logging.warning("safe_edit: failed after %d attempts", retries)
        except Exception as e:
            if "Message is not modified" in str(e):
                return
            logging.warning("safe_edit error: %s", e)
            return


# ── Клавиатуры ────────────────────────────────

def main_menu_keyboard(lang: str = "ru"):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t(lang, "btn_profile"), callback_data="menu_profile"),
            InlineKeyboardButton(t(lang, "btn_quest"),   callback_data="menu_quest"),
        ],
        [
            InlineKeyboardButton(t(lang, "btn_settings"), callback_data="menu_settings"),
            InlineKeyboardButton(t(lang, "btn_top"),      callback_data="menu_top"),
        ],
        [
            InlineKeyboardButton(t(lang, "btn_maps"),    callback_data="menu_maps"),
            InlineKeyboardButton(t(lang, "btn_info"),    callback_data="menu_info"),
        ],
    ])


def lang_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇷🇺 Русский", callback_data="set_lang_ru"),
        InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en"),
    ]])


def race_keyboard(lang: str = "ru"):
    back = "🔙 Меню" if lang != "en" else "🔙 Menu"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤 Человек" if lang != "en" else "👤 Human", callback_data="set_race_human"),
            InlineKeyboardButton("⛏️ Гном"   if lang != "en" else "⛏️ Dwarf", callback_data="set_race_dwarf"),
            InlineKeyboardButton("🌿 Эльф"   if lang != "en" else "🌿 Elf",   callback_data="set_race_elf"),
        ],
        [InlineKeyboardButton(back, callback_data="menu_back")],
    ])


def _race_display(player) -> str:
    """Отображаемое имя расы для игрока."""
    lang = player.lang or "ru"
    race = player.race or "human"
    races = {
        "human": ("👤 Человек" if lang != "en" else "👤 Human"),
        "dwarf": ("⛏️ Гном"   if lang != "en" else "⛏️ Dwarf"),
        "elf":   ("🌿 Эльф"   if lang != "en" else "🌿 Elf"),
    }
    return races.get(race, races["human"])


# ── /start ────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    sanitized_name = sanitize_name(user.full_name or user.username or "Adventurer")
    player, created = await Player.objects.get_or_create(
        uid=user.id,
        _defaults={"name": sanitized_name},
    )
    if not created and player.name != sanitized_name:
        player.name = sanitized_name
        await player.update(_columns=["name"])

    # Если язык не выбран — спрашиваем
    if not player.lang:
        await update.message.reply_text(
            t("ru", "choose_lang"),
            reply_markup=lang_keyboard(),
        )
        return

    # Если раса не выбрана — спрашиваем (только новые игроки)
    if not player.race:
        lang = player.lang
        await update.message.reply_text(
            t(lang, "choose_race"),
            parse_mode="Markdown",
            reply_markup=race_keyboard(lang),
        )
        return

    lang = player.lang
    if created:
        text = t(lang, "welcome_new",
                 game=cfg.GAME_NAME, name=player.name,
                 info=cfg.GAME_INFO, tip=tip(lang))
    else:
        text = t(lang, "welcome_back",
                 name=player.name, info=cfg.GAME_INFO,
                 level=player.level,
                 next=ctime(player.nextxp - player.currentxp),
                 tip=tip(lang))
    await update.message.reply_text(text, parse_mode="Markdown",
                                    reply_markup=main_menu_keyboard(lang))


async def callback_set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    if not check_callback_rate(uid):
        await query.answer("Подожди секунду!", show_alert=True)
        return
    await query.answer()
    lang = query.data.split("_")[-1]  # "ru" или "en"
    user = query.from_user
    player, created = await Player.objects.get_or_create(
        uid=user.id,
        _defaults={"name": user.full_name or user.username or "Adventurer", "lang": lang},
    )
    if not created:
        player.lang = lang
        await player.update(_columns=["lang"])

    # После выбора языка — если раса ещё не выбрана, показываем выбор расы
    if not player.race:
        await safe_edit(query, t(lang, "choose_race"), parse_mode="Markdown",
                        reply_markup=race_keyboard(lang))
        return
    await safe_edit(query, t(lang, "lang_set"), parse_mode="Markdown",
                    reply_markup=main_menu_keyboard(lang))


# ── Профиль ───────────────────────────────────

def _align_str(player) -> str:
    lang = player.lang or "ru"
    match player.align:
        case 1: return t(lang, "align_good")
        case 2: return t(lang, "align_evil")
        case _: return t(lang, "align_neutral")


def _profile_text(player) -> str:
    return _profile_text_sync(player)


async def _profile_text_async(player) -> str:
    """Асинхронная версия профиля с подсчётом квестов"""
    from db import PlayerQuest
    
    lang = player.lang or "ru"
    nextlevel = max(1, player.nextxp - player.currentxp)
    align     = _align_str(player)
    
    qstring = t(lang, "on_quest") if player.onquest else t(lang, "not_on_quest")
    alert    = t(lang, "notif_on") if player.optin else t(lang, "notif_off")
    
    # Подсчёт квестов
    active_quests = await PlayerQuest.objects.filter(
        player_uid=player.uid,
        status="active"
    ).count()
    offered_quests = await PlayerQuest.objects.filter(
        player_uid=player.uid,
        status="offered"
    ).count()
    
    quest_info = ""
    if active_quests > 0:
        quest_info = f" | 🎯 {active_quests}кв"
    if offered_quests > 0:
        quest_info += f" | 📩 {offered_quests}нов"
    if quest_info:
        quest_info += " (/myquests)"
    
    duel_str  = (t(lang, "profile_duels", wins=player.wins, loss=player.loss) + "\n") if cfg.ENABLE_COMBAT else ""
    race_str = _race_display(player)
    location_str = format_location(player.x, player.y, lang)
    status    = t(lang, "online") if player.online else t(lang, "offline")
    player_dps = get_total_dps(player)
    text = (
        t(lang, "profile_title", name=player.name, status=status) + "\n"
        + t(lang, "profile_level", level=player.level) + "\n"
        + t(lang, "profile_race", race=race_str) + "\n"
        + t(lang, "profile_job", job=player.job) + "\n"
        + t(lang, "profile_align", align=align) + "\n"
        + t(lang, "profile_gold", gold=format_short(player.gold)) + "\n"
        + t(lang, "profile_xp", xp=format_short(player.totalxp)) + "\n"
        + t(lang, "profile_tokens", tokens=player.tokens) + "\n"
        + f"⚔️ DPS: *{player_dps}*\n"
        + t(lang, "profile_nextlvl", time=ctime(nextlevel)) + "\n"
        + t(lang, "profile_total", time=ctime(player.totalxp)) + "\n"
        + duel_str
    )
    if location_str:
        text += f"📍 Позиция: ({player.x}, {player.y}) - {location_str}\n"
    else:
        text += f"📍 Позиция: ({player.x}, {player.y})\n"

    # Новый формат: квест и уведомления на разных строках
    quest_status = f"🎯 Квест: {active_quests}"
    alert_icon = "🔔" if player.optin else "🔕"
    alert_status = "ВКЛ" if player.optin else "ВЫКЛ"

    text += quest_status + "\n"
    text += f"Уведомления: {alert_icon} {alert_status}\n\n"
    text += t(lang, "profile_gear") + "\n"
    for slot in cfg.WEAPON_SLOTS:
        item = getattr(player, slot)
        if item:
            text += f"{SLOT_EMOJI.get(slot, '•')} {item_string(item)}\n"
    return text


def _profile_text_sync(player) -> str:
    lang = player.lang or "ru"
    nextlevel = max(1, player.nextxp - player.currentxp)
    align     = _align_str(player)
    
    qstring = t(lang, "on_quest") if player.onquest else t(lang, "not_on_quest")
    alert    = t(lang, "notif_on") if player.optin else t(lang, "notif_off")
    
    duel_str  = (t(lang, "profile_duels", wins=player.wins, loss=player.loss) + "\n") if cfg.ENABLE_COMBAT else ""
    race_str = _race_display(player)
    location_str = format_location(player.x, player.y, lang)
    status    = t(lang, "online") if player.online else t(lang, "offline")
    player_dps = get_total_dps(player)
    text = (
        t(lang, "profile_title", name=player.name, status=status) + "\n"
        + t(lang, "profile_level", level=player.level) + "\n"
        + t(lang, "profile_race", race=race_str) + "\n"
        + t(lang, "profile_job", job=player.job) + "\n"
        + t(lang, "profile_align", align=align) + "\n"
        + t(lang, "profile_gold", gold=format_short(player.gold)) + "\n"
        + t(lang, "profile_xp", xp=format_short(player.totalxp)) + "\n"
        + t(lang, "profile_tokens", tokens=player.tokens) + "\n"
        + f"⚔️ DPS: *{player_dps}*\n"
        + t(lang, "profile_nextlvl", time=ctime(nextlevel)) + "\n"
        + t(lang, "profile_total", time=ctime(player.totalxp)) + "\n"
        + duel_str
    )
    if location_str:
        text += f"📍 Позиция: ({player.x}, {player.y}) - {location_str}\n"
    else:
        text += f"📍 Позиция: ({player.x}, {player.y})\n"

    # Новый формат: квест и уведомления на разных строках
    quest_status = f"🎯 Квест: {active_quests}"
    alert_icon = "🔔" if player.optin else "🔕"
    alert_status = "ВКЛ" if player.optin else "ВЫКЛ"

    text += quest_status + "\n"
    text += f"Уведомления: {alert_icon} {alert_status}\n\n"
    text += t(lang, "profile_gear") + "\n"
    for slot in cfg.WEAPON_SLOTS:
        item = getattr(player, slot)
        if item:
            text += f"{SLOT_EMOJI.get(slot, '•')} {item_string(item)}\n"
    return text


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = await Player.objects.get_or_none(uid=user.id)
    if not player:
        await update.message.reply_text(t("ru", "not_registered"))
        return
    lang = player.lang or "ru"
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t(lang, "refresh"),  callback_data="menu_profile"),
            InlineKeyboardButton(t(lang, "btn_loot"), callback_data="menu_pull"),
        ],
        [
            InlineKeyboardButton(t(lang, "btn_align"), callback_data="align_menu"),
            InlineKeyboardButton(t(lang, "btn_job"),   callback_data="job_prompt"),
        ],
        [
            InlineKeyboardButton(t(lang, "btn_race"), callback_data="menu_race"),
        ],
        [InlineKeyboardButton(t(lang, "menu"), callback_data="menu_back")],
    ])
    await update.message.reply_text(await _profile_text_async(player), parse_mode="Markdown",
                                    reply_markup=keyboard)


# ── Callback главного меню ────────────────────

async def callback_set_race(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    if not check_callback_rate(uid):
        await query.answer("Подожди секунду!", show_alert=True)
        return
    await query.answer()
    race = query.data.split("_")[-1]  # "human", "dwarf", "elf"
    user = query.from_user
    player = await Player.objects.get_or_none(uid=user.id)
    if not player:
        await safe_edit(query, t("ru", "not_registered"))
        return
    player.race = race
    await player.update(_columns=["race"])
    lang = player.lang or "ru"
    race_name = _race_display(player)
    key = "race_set" if not player.race else "race_changed"
    await safe_edit(query, t(lang, key, race=race_name),
                    parse_mode="Markdown", reply_markup=main_menu_keyboard(lang))


async def callback_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    if not check_callback_rate(uid):
        await query.answer("Подожди секунду!", show_alert=True)
        return
    await query.answer()
    action = query.data
    user = query.from_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"

    if action == "menu_back":
        name = player.name if player else user.full_name
        await safe_edit(query, t(lang, "main_menu", name=name),
                        parse_mode="Markdown", reply_markup=main_menu_keyboard(lang))

    elif action == "menu_profile":
        if not player:
            await safe_edit(query, t(lang, "not_registered"))
            return
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(t(lang, "refresh"),  callback_data="menu_profile"),
                InlineKeyboardButton(t(lang, "btn_loot"), callback_data="menu_pull"),
            ],
            [
                InlineKeyboardButton(t(lang, "btn_align"), callback_data="align_menu"),
                InlineKeyboardButton(t(lang, "btn_job"),   callback_data="job_prompt"),
            ],
            [
                InlineKeyboardButton(t(lang, "btn_race"), callback_data="menu_race"),
            ],
            [InlineKeyboardButton(t(lang, "menu"), callback_data="menu_back")],
        ])
        await safe_edit(query, await _profile_text_async(player), parse_mode="Markdown",
                        reply_markup=keyboard)

    elif action == "menu_quest":
        await _show_quest(query, lang)

    elif action == "menu_pull":
        await _show_pull_menu(query, player, lang)

    elif action == "menu_settings":
        if not player:
            await safe_edit(query, t(lang, "not_registered"))
            return
        alert_icon  = "🔔" if player.optin else "🔕"
        alert_label = f"{alert_icon} {t(lang, 'btn_notif')}"
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(alert_label,         callback_data="menu_alert_settings"),
                InlineKeyboardButton(t(lang, "btn_lang"), callback_data="menu_lang"),
            ],
            [InlineKeyboardButton(t(lang, "menu"), callback_data="menu_back")],
        ])
        await safe_edit(query, t(lang, "settings_title"),
                        parse_mode="Markdown", reply_markup=keyboard)

    elif action == "menu_lang":
        await safe_edit(query, t(lang, "choose_lang"), reply_markup=lang_keyboard())

    elif action in ("menu_alert", "menu_alert_settings"):
        if not player:
            await safe_edit(query, t(lang, "not_registered"))
            return
        player.optin = not player.optin
        await player.update(_columns=["optin"])
        status_str = t(lang, "notif_on_txt") if player.optin else t(lang, "notif_off_txt")
        back_cb = "menu_settings" if action == "menu_alert_settings" else "menu_back"
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(t(lang, "btn_toggle"), callback_data=action),
            InlineKeyboardButton(t(lang, "back"),       callback_data=back_cb),
        ]])
        await safe_edit(query, t(lang, "notif_status", status=status_str),
                        parse_mode="Markdown", reply_markup=keyboard)

    elif action in ("menu_top", "menu_top_combined"):
        await _show_top(query, lang)

    elif action == "menu_info":
        await _show_info(query, lang)

    elif action == "menu_bosses":
        from game.bosses import format_boss_list
        text = format_boss_list(lang)
        await safe_edit(query, text, parse_mode="Markdown")

    elif action == "menu_maps":
        from handlers.maps import send_map_view
        await send_map_view(query, player, lang)

    elif action == "menu_race":
        if not player:
            await safe_edit(query, t(lang, "not_registered"))
            return
        await safe_edit(query, t(lang, "choose_race"),
                        parse_mode="Markdown", reply_markup=race_keyboard(lang))


async def _show_pull_menu(query, player, lang):
    if not player:
        await safe_edit(query, t(lang, "not_registered"))
        return
    text = t(lang, "loot_title", gold=player.gold)
    rows = []
    if player.gold > 0:
        btns = [InlineKeyboardButton(f"x{n}", callback_data=f"pull_{n}")
                for n in [1, 3, 5, 10] if n <= player.gold]
        if btns:
            rows.append(btns)
    rows.append([InlineKeyboardButton(t(lang, "menu"), callback_data="menu_back")])
    await safe_edit(query, text, parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(rows))


async def callback_pull(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    amount = int(query.data.split("_")[1])
    user = query.from_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    if not player:
        await safe_edit(query, t(lang, "not_registered"))
        return
    if player.gold < amount:
        await query.answer(f"Only {player.gold} gold available.", show_alert=True)
        return
    text = t(lang, "loot_found", name=player.name)
    for _ in range(amount):
        item, slot, replaced = await get_item(player)
        upgrade = t(lang, "loot_upgrade") if replaced else ""
        text += f"{item_string(item)}{upgrade}\n"
    player.gold -= amount
    await player.update(_columns=["gold"])
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "loot_more"), callback_data="menu_pull"),
        InlineKeyboardButton(t(lang, "btn_profile"), callback_data="menu_profile"),
        InlineKeyboardButton(t(lang, "menu"),       callback_data="menu_back"),
    ]])
    await safe_edit(query, text, parse_mode="Markdown", reply_markup=keyboard)


async def _show_quest(query, lang: str):
    """Показать список квестов - НОВАЯ СИСТЕМА"""
    import time
    from db import PlayerQuest
    
    player = await Player.objects.get_or_none(uid=query.from_user.id)
    if not player:
        await safe_edit(query, t(lang, "not_registered"))
        return
    
    quests = await PlayerQuest.objects.filter(
        player_uid=player.uid,
        status="active"
    ).all()
    
    if not quests:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Меню", callback_data="menu_back")]
        ])
        await safe_edit(query, "🎯 *Мои квесты*\n\nНет активных квестов", 
                       parse_mode="Markdown", reply_markup=keyboard)
        return
    
    lines = ["🎯 *Мои квесты*", ""]
    
    for i, q in enumerate(quests, 1):
        deadline = ""
        if q.expires_at:
            left = q.expires_at - int(time.time())
            if left > 0:
                hours = left // 3600
                minutes = (left % 3600) // 60
                deadline = f" ⏰ {hours}ч {minutes}мин"
            else:
                deadline = " ⛔"
        
        lines.append(f"{i}. {q.title}")
        lines.append(f"   ⏳ {q.progress}/{q.target_count}{deadline}")
        lines.append(f"   🎁 +{q.reward_xp} XP, +{q.reward_gold} Gold")
        lines.append("")
    
    text = "\n".join(lines)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Обновить", callback_data="menu_quest")],
        [InlineKeyboardButton("🏠 Меню", callback_data="menu_back")]
    ])
    
    await safe_edit(query, text, parse_mode="Markdown", reply_markup=keyboard)


async def _show_top(query, lang: str):
    players = await Player.objects.all()
    
    # Top 10 via heapq — O(n log k) вместо O(n log n) полной сортировки
    import heapq
    top_players = heapq.nlargest(10, players, key=lambda p: (p.level, p.totalxp))
    
    total  = len(players)
    online = sum(1 for p in players if p.online)

    lines = [
        t(lang, "top_entry",
          medal="🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}.",
          status="🟢" if p.online else "🔴",
          name=p.name, level=p.level, job=p.job,
          align=_align_str(p), time=ctime(p.totalxp))
        for i, p in enumerate(top_players, 1)
    ]

    text = "\n".join([
        t(lang, "top_title"),
        t(lang, "top_stats", total=total, online=online),
        "━━━━━━━━━━━━━━━━━━",
        *lines,
    ])
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "refresh"), callback_data="menu_top"),
        InlineKeyboardButton(t(lang, "menu"),    callback_data="menu_back"),
    ]])
    await safe_edit(query, text, parse_mode="Markdown", reply_markup=keyboard)


async def _show_info(query, lang: str):
    changelog = CHANGELOG if lang == "ru" else CHANGELOG_EN
    text = (
        t(lang, "info_title", game=cfg.GAME_NAME, version=cfg.VERSION) + "\n\n"
        + t(lang, "info_about") + "\n\n"
        + t(lang, "info_updates") + "\n"
        + changelog + "\n\n"
        + t(lang, "info_commands")
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "menu"), callback_data="menu_back"),
    ]])
    await safe_edit(query, text, parse_mode="Markdown", reply_markup=keyboard)


async def cmd_pull(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    if not player:
        await update.message.reply_text(t(lang, "not_registered"))
        return
    amount = 1
    if context.args:
        try:
            amount = max(1, min(10, int(context.args[0])))
        except ValueError:
            pass
    if player.gold < 1:
        await update.message.reply_text(t(lang, "no_gold"))
        return
    if amount > player.gold:
        amount = player.gold
    text = t(lang, "loot_found", name=player.name)
    for _ in range(amount):
        item, slot, replaced = await get_item(player)
        upgrade = t(lang, "loot_upgrade") if replaced else ""
        text += f"{item_string(item)}{upgrade}\n"
    player.gold -= amount
    await player.update(_columns=["gold"])
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "loot_more"),   callback_data="menu_pull"),
        InlineKeyboardButton(t(lang, "btn_profile"), callback_data="menu_profile"),
    ]])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    players = await Player.objects.all()
    
    # Top 10 via heapq — O(n log k) вместо O(n log n)
    import heapq
    top_players = heapq.nlargest(10, players, key=lambda p: (p.level, p.totalxp))
    
    total  = len(players)
    online = sum(1 for p in players if p.online)
    lines = [
        t(lang, "top_entry",
          medal="🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}.",
          status="🟢" if p.online else "🔴",
          name=p.name, level=p.level, job=p.job,
          align=_align_str(p), time=ctime(p.totalxp))
        for i, p in enumerate(top_players, 1)
    ]
    text = "\n".join([
        t(lang, "top_title"),
        t(lang, "top_stats", total=total, online=online),
        "━━━━━━━━━━━━━━━━━━",
        *lines,
    ])
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "refresh"), callback_data="menu_top"),
        InlineKeyboardButton(t(lang, "menu"),    callback_data="menu_back"),
    ]])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    changelog = CHANGELOG if lang == "ru" else CHANGELOG_EN
    text = (
        t(lang, "info_title", game=cfg.GAME_NAME, version=cfg.VERSION) + "\n\n"
        + t(lang, "info_about") + "\n\n"
        + t(lang, "info_updates") + "\n"
        + changelog + "\n\n"
        + t(lang, "info_commands")
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "menu"), callback_data="menu_back"),
    ]])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


def register(app: Application):
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("pull",    cmd_pull))
    app.add_handler(CommandHandler("info",    cmd_info))
    app.add_handler(CommandHandler("top",     cmd_top))
    app.add_handler(CallbackQueryHandler(callback_set_lang, pattern="^set_lang_"))
    app.add_handler(CallbackQueryHandler(callback_set_race, pattern="^set_race_"))
    app.add_handler(CallbackQueryHandler(callback_menu,     pattern="^menu_"))
    app.add_handler(CallbackQueryHandler(callback_pull,     pattern="^pull_\\d+$"))
