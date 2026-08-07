"""
handlers/battle.py — хаб «Сражение»: объединяет охоту, подземелья, арену и рейд.

Вход: кнопка «Сражение» в меню профиля (callback_data="battle_menu") или /battle.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from db import Player
from i18n import t
from core.telegram_utils import safe_edit


def _battle_text(lang: str) -> str:
    if lang != "en":
        return "⚔️ <b>Сражение</b>\n\nВыберите, куда отправиться в бой:"
    return "⚔️ <b>Battle</b>\n\nChoose where to go to fight:"


def _battle_keyboard(lang: str):
    hunt = "🗡️ Охота" if lang != "en" else "🗡️ Hunt"
    dungeons = "🏰 Подземелья" if lang != "en" else "🏰 Dungeons"
    arena = "⚔️ Арена" if lang != "en" else "⚔️ Arena"
    raid = "👹 Рейд" if lang != "en" else "👹 Raid"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(hunt, callback_data="menu_hunt"),
            InlineKeyboardButton(dungeons, callback_data="menu_dungeons"),
        ],
        [
            InlineKeyboardButton(arena, callback_data="arena_menu"),
            InlineKeyboardButton(raid, callback_data="raid_menu"),
        ],
        [
            InlineKeyboardButton(t(lang, "btn_profile"), callback_data="menu_profile"),
            InlineKeyboardButton(t(lang, "menu"), callback_data="menu_back"),
        ],
    ])


async def handle_battle_menu(query, player, lang: str) -> None:
    await safe_edit(query, _battle_text(lang), parse_mode="HTML",
                    reply_markup=_battle_keyboard(lang))


async def cmd_battle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player = await Player.objects.get_or_none(uid=update.effective_user.id)
    if not player:
        await update.message.reply_text(t("ru", "not_registered"))
        return
    lang = player.lang or "ru"
    await update.message.reply_text(_battle_text(lang), parse_mode="HTML",
                                    reply_markup=_battle_keyboard(lang))


async def callback_battle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    player = await Player.objects.get_or_none(uid=query.from_user.id)
    lang = (player.lang or "ru") if player else "ru"
    if not player:
        await safe_edit(query, t(lang, "not_registered"))
        return
    await handle_battle_menu(query, player, lang)


def register(app: Application):
    app.add_handler(CommandHandler("battle", cmd_battle))
    app.add_handler(CallbackQueryHandler(callback_battle, pattern="^battle_menu$"))
