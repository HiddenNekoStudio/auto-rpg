"""
handlers/pets.py — /pets команда и меню питомцев
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from db import Player
from game import pets as pets_api
from i18n import t


def _pet_line(lang: str, pet_id: str, conf: dict, owned: dict, player=None) -> str:
    icon = conf.get("icon", "✨")
    name = conf.get("name_ru", pet_id) if lang != "en" else conf.get("name_en", pet_id)
    if pet_id in owned:
        p = owned[pet_id]
        threshold = max(1, p.level * pets_api.cfg.PET_XP_THRESHOLD_BASE)
        bar_len = 10
        filled = min(bar_len, int(p.xp / threshold * bar_len))
        bar = "█" * filled + "░" * (bar_len - filled)
        eq = "⚔️" if p.equipped else "📦"
        evo = " ✨" if p.equipped and player and pets_api.can_evolve(p, player) else ""
        return f"{icon} {eq} <b>{name}</b> Lv.{p.level} [{bar}] {p.xp}/{threshold}{evo}"
    price = conf.get("price_tokens", 5)
    return f"{icon} {name} — {price}🪙"


def _bonus_text(conf: dict, mult: float, lang: str) -> str:
    b = conf.get("bonuses", {})
    parts = []
    if b.get("dps_pct"):
        parts.append(f"DPS +{int(b['dps_pct'] * mult)}%")
    if b.get("hp_pct"):
        parts.append(f"HP +{int(b['hp_pct'] * mult)}%")
    if b.get("def"):
        parts.append(f"Def +{int(b['def'] * mult)}")
    if b.get("gold_pct"):
        parts.append(f"Gold +{int(b['gold_pct'] * mult)}%")
    if b.get("xp_pct"):
        parts.append(f"XP +{int(b['xp_pct'] * mult)}%")
    sep = ", " if lang == "en" else ", "
    return sep.join(parts)


async def build_pets_text(player, lang: str):
    owned = {p.pet_id: p for p in await pets_api.get_owned(player.uid)}
    confs = pets_api.all_pets()
    lines = ["🐾 <b>" + ("Питомцы" if lang == "en" else "Питомцы") + "</b>\n"]
    if not confs:
        lines.append("Пока нет питомцев в мире.")
    for pet_id, conf in confs.items():
        lines.append(_pet_line(lang, pet_id, conf, owned, player))
    lines.append("")
    eq = await pets_api.get_equipped(player.uid)
    if eq and eq.pet_id in confs:
        conf = confs[eq.pet_id]
        mult = pets_api._level_mult(eq.level)
        lines.append("✨ " + ("Активные бонусы:" if lang == "en" else "Активные бонусы:"))
        lines.append(_bonus_text(conf, mult, lang))

    rows = []
    for pet_id, conf in confs.items():
        if pet_id in owned:
            p = owned[pet_id]
            if not p.equipped:
                label = "⚔️ " + ("Экипировать" if lang == "en" else "Экипировать")
                rows.append([InlineKeyboardButton(f"{conf['icon']} {label}", callback_data=f"pet_equip_{pet_id}")])
            elif pets_api.can_evolve(p, player):
                label = "✨ " + ("Эволюция" if lang == "en" else "Эволюция")
                rows.append([InlineKeyboardButton(f"{conf['icon']} {label}", callback_data=f"pet_evolve_{pet_id}")])
        else:
            if conf.get("evolution"):
                continue
            label = "🪙 " + ("Купить" if lang == "en" else "Купить")
            rows.append([InlineKeyboardButton(f"{conf['icon']} {label} ({conf.get('price_tokens', 5)}🪙)", callback_data=f"pet_buy_{pet_id}")])
    rows.append([InlineKeyboardButton(t(lang, "btn_profile"), callback_data="menu_profile")])
    keyboard = InlineKeyboardMarkup(rows)
    return "\n".join(lines), keyboard


async def show_pets_menu(query, player, lang: str):
    await pets_api.refresh_cache(player)
    text, keyboard = await build_pets_text(player, lang)
    from core.telegram_utils import safe_edit
    await safe_edit(query, text, parse_mode="HTML", reply_markup=keyboard)


async def cmd_pets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = await Player.objects.get_or_none(uid=user.id)
    if not player:
        return
    lang = player.lang or "ru"
    await pets_api.refresh_cache(player)
    text, keyboard = await build_pets_text(player, lang)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def callback_pets(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    if data.startswith("pet_buy_"):
        pet_id = data[len("pet_buy_"):]
        ok, msg = await pets_api.buy_pet(player, pet_id)
        if not ok:
            await query.answer(msg, show_alert=True)
            return
        await query.answer(msg)
    elif data.startswith("pet_equip_"):
        pet_id = data[len("pet_equip_"):]
        ok, msg = await pets_api.equip_pet(player, pet_id)
        if not ok:
            await query.answer(msg, show_alert=True)
            return
        await query.answer(msg)
        player.sync_max_hp_mp()
        await player.update(_columns=["max_hp", "max_mp"])
    elif data.startswith("pet_evolve_"):
        pet_id = data[len("pet_evolve_"):]
        ok, msg = await pets_api.evolve_pet(player, pet_id)
        if not ok:
            await query.answer(msg, show_alert=True)
            return
        await query.answer(msg)
        player.sync_max_hp_mp()
        await player.update(_columns=["max_hp", "max_mp"])

    await show_pets_menu(query, player, lang)


def register(app: Application):
    app.add_handler(CommandHandler("pets", cmd_pets))
    app.add_handler(CallbackQueryHandler(callback_pets, pattern="^(pet_buy_|pet_equip_|pet_evolve_|pets_menu)"))
