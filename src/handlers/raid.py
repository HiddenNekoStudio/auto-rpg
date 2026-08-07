"""
handlers/raid.py — /raid команда: статус мирового рейд-босса
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from db import Player, RaidBoss, RaidBossHit
from core.telegram_utils import safe_edit
from i18n import t


def _hp_bar(pct: float, width: int = 12) -> str:
    filled = max(0, min(width, int(round(pct / 100 * width))))
    return "█" * filled + "░" * (width - filled)


async def build_raid_text(player, lang: str):
    boss = await RaidBoss.objects.filter(status="active").get_or_none()
    if not boss:
        if lang != "en":
            return "👹 <b>Рейд-босс</b>\n\nСейчас нет активного рейд-босса.\nОн появится автоматически — заглядывайте позже!"
        return "👹 <b>Raid boss</b>\n\nNo active raid boss right now.\nIt will appear automatically — check back later!"
    pct = round(boss.hp / boss.max_hp * 100, 1) if boss.max_hp else 0
    lines = ["👹 <b>" + ("Рейд-босс" if lang != "en" else "Raid boss") + f"</b> — {boss.name}"]
    lines.append("")
    lines.append(f"{_hp_bar(pct)} {pct}%")
    lines.append(f"❤️ {boss.hp:,} / {boss.max_hp:,}".replace(",", " "))
    hit = await RaidBossHit.objects.filter(
        raid_boss_id=boss.id, player_uid=player.uid
    ).get_or_none()
    if hit:
        lines.append("")
        lines.append(f"⚔️ " + ("Ваш урон:" if lang != "en" else "Your damage:") + f" {hit.damage:,}".replace(",", " "))
    lines.append("")
    if lang != "en":
        lines.append("Все игроки автоматически атакуют босса. Награда за победу достаётся всем участникам!")
    else:
        lines.append("All players automatically attack the boss. Everyone who contributes gets a reward!")
    return "\n".join(lines)


def _nav_row(lang: str):
    return [
        InlineKeyboardButton("⚔️ Сражение" if lang != "en" else "⚔️ Battle", callback_data="battle_menu"),
        InlineKeyboardButton(t(lang, "btn_profile"), callback_data="menu_profile"),
    ]


async def cmd_raid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = await Player.objects.get_or_none(uid=user.id)
    if not player:
        return
    lang = player.lang or "ru"
    text = await build_raid_text(player, lang)
    rows = [_nav_row(lang)]
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))


async def callback_raid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    if not player:
        await safe_edit(query, t(lang, "not_registered"))
        return
    text = await build_raid_text(player, lang)
    rows = [_nav_row(lang)]
    await safe_edit(query, text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))


def register(app: Application):
    app.add_handler(CommandHandler("raid", cmd_raid))
    app.add_handler(CallbackQueryHandler(callback_raid, pattern="^raid_menu$"))
