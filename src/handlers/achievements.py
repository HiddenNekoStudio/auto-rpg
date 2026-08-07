"""
handlers/achievements.py — /achievements команда и меню достижений
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from db import Player, PlayerAchievement
from game import achievements as ach_api
from i18n import t


async def build_achievements_text(player, lang: str):
    await ach_api.check_all_achievements(player)
    confs = ach_api.all_achievements()
    unlocked = {
        a.achievement_id for a in await PlayerAchievement.objects.filter(
            player_uid=player.uid, achievement_id__in=list(confs.keys())
        ).all()
    }
    lines = ["🏆 <b>" + ("Achievements" if lang != "en" else "Achievements") + f"</b> ({len(unlocked)}/{len(confs)})\n"]
    for aid, conf in confs.items():
        name = conf.get("name_ru", aid) if lang != "en" else conf.get("name_en", aid)
        desc = conf.get("desc_ru", "") if lang != "en" else conf.get("desc_en", "")
        icon = conf.get("icon", "🏆")
        if aid in unlocked:
            lines.append(f"{icon} ✅ <b>{name}</b>")
        else:
            cur = ach_api._current_value(player, conf.get("type", ""))
            target = conf.get("target", 1)
            lines.append(f"{icon} {name} — {desc} ({min(cur, target)}/{target})")
    return "\n".join(lines)


async def show_achievements_menu(query, player, lang: str):
    text = await build_achievements_text(player, lang)
    from core.telegram_utils import safe_edit
    rows = [[InlineKeyboardButton(t(lang, "btn_profile"), callback_data="menu_profile")]]
    await safe_edit(query, text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))


async def cmd_achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = await Player.objects.get_or_none(uid=user.id)
    if not player:
        return
    lang = player.lang or "ru"
    text = await build_achievements_text(player, lang)
    rows = [[InlineKeyboardButton(t(lang, "btn_profile"), callback_data="menu_profile")]]
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))


async def callback_achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    if not player:
        from core.telegram_utils import safe_edit
        await safe_edit(query, t(lang, "not_registered"))
        return
    await show_achievements_menu(query, player, lang)


def register(app: Application):
    app.add_handler(CommandHandler("achievements", cmd_achievements))
    app.add_handler(CallbackQueryHandler(callback_achievements, pattern="^ach_menu$"))
