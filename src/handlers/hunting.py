"""
handlers/hunting.py — интерфейс системы охоты

Вход: кнопка «Охота» в меню профиля (callback_data="menu_hunt") или /hunt.
Колбэки: hunt_menu, hunt_mode_<mode>, hunt_start_<mode>_<dur>, hunt_status, hunt_cancel.
"""
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

import config as cfg
from db import Player
from bot import ctime
from i18n import t
from core.cache import TTLCache
from core.telegram_utils import safe_edit

from game.hunting import (
    is_hunting, get_hunt_data, hunt_mode_name,
    estimate_hunt_rewards, start_hunt, cancel_hunt, _hunt_finish_report,
)

_callback_rate_limit = TTLCache(ttl=1.0, maxsize=10000)


def _can_act(uid: int) -> bool:
    key = str(uid)
    if _callback_rate_limit.get(key) is not None:
        return False
    _callback_rate_limit.set(key, True)
    return True


# ─────────────────────────────────────────────
#  Тексты и клавиатуры
# ─────────────────────────────────────────────

def _hunt_menu_text(player, lang: str) -> str:
    if not is_hunting(player):
        return t(lang, "hunt_idle")
    data = get_hunt_data(player)
    mode = data.get("mode", "weak")
    left = max(0, player.hunting_expires_at - int(time.time()))
    return t(lang, "hunt_active",
             mode=hunt_mode_name(mode, lang),
             time=ctime(left, lang),
             kills=data.get("kills", 0),
             escapes=data.get("escapes", 0))


def _nav_row(lang: str):
    return [
        InlineKeyboardButton("⚔️ Сражение" if lang != "en" else "⚔️ Battle", callback_data="battle_menu"),
        InlineKeyboardButton(t(lang, "btn_profile"), callback_data="menu_profile"),
    ]


def _hunt_menu_keyboard(player, lang: str):
    if is_hunting(player):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(t(lang, "refresh"), callback_data="hunt_status")],
            [InlineKeyboardButton(t(lang, "hunt_cancel_btn"), callback_data="hunt_cancel")],
            _nav_row(lang),
        ])
    rows = []
    for mid, m in cfg.HUNTING_MODES.items():
        name = m["name_en"] if lang == "en" else m["name_ru"]
        rows.append([InlineKeyboardButton(f"{m['icon']} {name}",
                                          callback_data=f"hunt_mode_{mid}")])
    rows.append(_nav_row(lang))
    return InlineKeyboardMarkup(rows)


def _hunt_mode_text(mode: str, lang: str) -> str:
    m = cfg.HUNTING_MODES[mode]
    name = m["name_en"] if lang == "en" else m["name_ru"]
    off_lo, off_hi = m["level_offset"]
    if off_lo == off_hi:
        level_str = str(off_lo)
    else:
        level_str = f"{off_lo:+}..{off_hi:+}" if off_lo < 0 else f"{off_lo}..{off_hi}"
    if m.get("retreat_hp_pct", 0) > 0:
        death_line = t(lang, "hunt_death_retreat",
                       pct=int(m["retreat_hp_pct"] * 100))
    elif m.get("death_item_chance", 0) > 0:
        death_line = t(lang, "hunt_death_gold_item",
                       pct=int(m["death_gold_penalty"] * 100),
                       item=int(m["death_item_chance"] * 100))
    else:
        death_line = t(lang, "hunt_death_gold",
                       pct=int(m["death_gold_penalty"] * 100))
    return t(lang, "hunt_mode_desc",
             icon=m["icon"], mode=name, level=level_str,
             xp=int(m["xp_mult"] * 100), gold=int(m["gold_mult"] * 100),
             loot=int(m.get("loot_chance", 0) * 100),
             survive=int(m.get("survive_bonus", 1.0) * 100),
             death=death_line)


def _hunt_duration_keyboard(player, mode: str, lang: str):
    rows = []
    for dur, bonus in cfg.HUNTING_DURATIONS.items():
        est_xp, est_gold = estimate_hunt_rewards(player, mode, dur)
        label = t(lang, "hunt_dur_btn", hours=dur // 3600,
                  bonus=int(bonus * 100), xp=est_xp, gold=est_gold)
        rows.append([InlineKeyboardButton(label, callback_data=f"hunt_start_{mode}_{dur}")])
    rows.append([InlineKeyboardButton(t(lang, "back"), callback_data="hunt_menu")])
    return InlineKeyboardMarkup(rows)


# ─────────────────────────────────────────────
#  Хендлеры
# ─────────────────────────────────────────────

async def handle_hunt_menu(query, player, lang: str) -> None:
    await safe_edit(query, _hunt_menu_text(player, lang), parse_mode="HTML",
                    reply_markup=_hunt_menu_keyboard(player, lang))


async def callback_hunt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    lang = "ru"
    if not _can_act(uid):
        await query.answer("Wait a second!" if lang == "en" else "Подожди секунду!", show_alert=True)
        return
    await query.answer()
    player = await Player.objects.get_or_none(uid=uid)
    lang = (player.lang or "ru") if player else "ru"
    if not player:
        await safe_edit(query, t(lang, "not_registered"))
        return

    action = query.data
    if action == "hunt_menu":
        await handle_hunt_menu(query, player, lang)

    elif action.startswith("hunt_mode_"):
        mode = action[len("hunt_mode_"):]
        if mode not in cfg.HUNTING_MODES:
            return
        await safe_edit(query, _hunt_mode_text(mode, lang), parse_mode="HTML",
                        reply_markup=_hunt_duration_keyboard(player, mode, lang))

    elif action.startswith("hunt_start_"):
        parts = action.split("_")
        mode, dur = parts[2], int(parts[3])
        ok, result = await start_hunt(player, mode, dur)
        if not ok:
            await handle_hunt_menu(query, player, lang)
            return
        mode_name = hunt_mode_name(mode, lang)
        text = t(lang, "hunt_started", mode=mode_name,
                 hours=dur // 3600) + "\n\n" + _hunt_menu_text(player, lang)
        await safe_edit(query, text, parse_mode="HTML",
                        reply_markup=_hunt_menu_keyboard(player, lang))

    elif action == "hunt_status":
        await handle_hunt_menu(query, player, lang)

    elif action == "hunt_cancel":
        summary = await cancel_hunt(player)
        text = t(lang, "hunt_cancelled") + "\n" + await _hunt_finish_report(summary, lang)
        await safe_edit(query, text, parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup([_nav_row(lang)]))


async def cmd_hunt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player = await Player.objects.get_or_none(uid=update.effective_user.id)
    if not player:
        await update.message.reply_text(t("ru", "not_registered"))
        return
    lang = player.lang or "ru"
    await update.message.reply_text(_hunt_menu_text(player, lang), parse_mode="HTML",
                                    reply_markup=_hunt_menu_keyboard(player, lang))


def register(app: Application) -> None:
    app.add_handler(CommandHandler("hunt", cmd_hunt))
    app.add_handler(CallbackQueryHandler(callback_hunt, pattern="^hunt_"))
