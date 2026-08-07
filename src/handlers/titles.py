"""
handlers/titles.py — /titles команда и меню титулов
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from db import Player
from game import titles as titles_api
from i18n import t


async def build_titles_text(player, lang: str):
    from db import PlayerTitle
    owned = {
        a.title_id for a in await PlayerTitle.objects.filter(
            player_uid=player.uid, title_id__in=list(titles_api.all_titles().keys())
        ).all()
    }
    lines = ["📜 <b>" + ("Titles" if lang != "en" else "Titles") + f"</b> ({len(owned)}/{len(titles_api.all_titles())})\n"]
    eq = getattr(player, "title_id", "") or ""
    for tid, conf in titles_api.all_titles().items():
        name = conf.get("name_ru", tid) if lang != "en" else conf.get("name_en", tid)
        desc = conf.get("desc_ru", "") if lang != "en" else conf.get("desc_en", "")
        mark = "✅" if tid in owned else "🔒"
        eq_mark = " ⭐" if tid == eq else ""
        lines.append(f"{mark} {name}{eq_mark} — {desc}")
    return "\n".join(lines)


def _keyboard(lang: str):
    rows = []
    for tid in titles_api.all_titles():
        label = titles_api.get_title_config(tid).get("name_ru", tid) if lang != "en" else titles_api.get_title_config(tid).get("name_en", tid)
        rows.append([InlineKeyboardButton(f"⭐ {label}", callback_data=f"title_equip_{tid}")])
    rows.append([InlineKeyboardButton(t(lang, "btn_profile"), callback_data="menu_profile")])
    return InlineKeyboardMarkup(rows)


async def show_titles_menu(query, player, lang: str):
    text = await build_titles_text(player, lang)
    from core.telegram_utils import safe_edit
    await safe_edit(query, text, parse_mode="HTML", reply_markup=_keyboard(lang))


async def cmd_titles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = await Player.objects.get_or_none(uid=user.id)
    if not player:
        return
    lang = player.lang or "ru"
    text = await build_titles_text(player, lang)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=_keyboard(lang))


async def callback_titles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    if not player:
        from core.telegram_utils import safe_edit
        await safe_edit(query, t(lang, "not_registered"))
        return
    data = query.data

    if data.startswith("title_equip_"):
        tid = data[len("title_equip_"):]
        if not titles_api.is_unlocked(player, tid):
            await query.answer(("Титул ещё не открыт" if lang != "en" else "Title not unlocked"), show_alert=True)
            return
        player.title_id = tid
        await player.update(_columns=["title_id"])
        await query.answer(("Титул экипирован!" if lang != "en" else "Title equipped!"))

    await show_titles_menu(query, player, lang)


def register(app: Application):
    app.add_handler(CommandHandler("titles", cmd_titles))
    app.add_handler(CallbackQueryHandler(callback_titles, pattern="^(title_equip_|titles_menu)"))
