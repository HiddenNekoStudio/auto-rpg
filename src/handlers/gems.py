"""
handlers/gems.py — /gems команда и меню камней
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from db import Player, PlayerGem
from game import gems as gems_api
from core.loot import SLOTS_DATA
from i18n import t


def _gem_list_text(lang: str, gems: list) -> str:
    lines = ["💎 <b>" + ("Камни" if lang != "en" else "Gems") + "</b>\n"]
    confs = gems_api._load_gems()
    if not gems:
        lines.append("Пока нет камней." if lang != "en" else "No gems yet.")
        return "\n".join(lines)
    for g in gems:
        conf = confs.get(g.gem_id, {})
        icon = conf.get("icon", "💎")
        name = conf.get("name_ru", g.gem_id) if lang != "en" else conf.get("name_en", g.gem_id)
        st = "⚔️" if g.equipped else "📦"
        lines.append(f"{icon} {st} {name}")
    return "\n".join(lines)


def _menu_keyboard(lang: str):
    rows = []
    slot_icons = {"weapon": "⚔️", "shield": "🛡️", "helmet": "⛑️", "chest": "🦺",
                  "gloves": "🧤", "boots": "🥾", "ring": "💍", "amulet": "📿"}
    for slot in SLOTS_DATA:
        icon = slot_icons.get(slot, "📦")
        rows.append([InlineKeyboardButton(f"{icon} {slot}", callback_data=f"gem_apply_{slot}")])
    rows.append([InlineKeyboardButton(t(lang, "btn_profile"), callback_data="menu_profile")])
    return InlineKeyboardMarkup(rows)


async def show_gems_menu(query, player, lang: str):
    gems = await PlayerGem.objects.filter(player_uid=player.uid).order_by("-id").all()
    text = _gem_list_text(lang, gems)
    from core.telegram_utils import safe_edit
    await safe_edit(query, text, parse_mode="HTML", reply_markup=_menu_keyboard(lang))


async def cmd_gems(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = await Player.objects.get_or_none(uid=user.id)
    if not player:
        return
    lang = player.lang or "ru"
    gems = await PlayerGem.objects.filter(player_uid=player.uid).order_by("-id").all()
    text = _gem_list_text(lang, gems)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=_menu_keyboard(lang))


async def callback_gems(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    if data.startswith("gem_apply_"):
        slot = data[len("gem_apply_"):]
        ok, status = await gems_api.apply_gem(player, slot)
        if status == "ok":
            player.sync_max_hp_mp()
            await player.update(_columns=["max_hp", "max_mp"])
            await query.answer(("Камень вставлен!" if lang != "en" else "Gem socketed!"))
        elif status == "full":
            await query.answer(("Гнёзда заняты" if lang != "en" else "Sockets full"), show_alert=True)
        elif status == "no_socket":
            await query.answer(("У предмета нет гнёзд" if lang != "en" else "Item has no sockets"), show_alert=True)
        elif status == "no_gem":
            await query.answer(("Нет камней в инвентаре" if lang != "en" else "No gems in inventory"), show_alert=True)
        else:
            await query.answer(("Предмет не найден" if lang != "en" else "Item not found"), show_alert=True)

    await show_gems_menu(query, player, lang)


def register(app: Application):
    app.add_handler(CommandHandler("gems", cmd_gems))
    app.add_handler(CallbackQueryHandler(callback_gems, pattern="^(gem_apply_|gems_menu)"))
