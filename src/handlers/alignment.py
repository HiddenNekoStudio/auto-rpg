"""handlers/alignment.py — /align"""

import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import NetworkError, RetryAfter, TimedOut
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from db import Player
from i18n import t


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
            else:
                logging.warning("safe_edit failed after %d attempts", retries)
        except Exception as e:
            if "Message is not modified" in str(e):
                return
            logging.warning("safe_edit error: %s", e)
            return


def _align_keyboard(lang):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t(lang, "align_good"),    callback_data="align_1"),
            InlineKeyboardButton(t(lang, "align_neutral"), callback_data="align_0"),
            InlineKeyboardButton(t(lang, "align_evil"),    callback_data="align_2"),
        ],
        [InlineKeyboardButton(t(lang, "menu"), callback_data="menu_back")],
    ])


async def cmd_align(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    if not player:
        await update.message.reply_text(t(lang, "not_registered"))
        return
    await update.message.reply_text(t(lang, "align_title"), parse_mode="Markdown",
                                    reply_markup=_align_keyboard(lang))


async def callback_align_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    await safe_edit(query, t(lang, "align_title"), parse_mode="Markdown",
                    reply_markup=_align_keyboard(lang))


async def callback_align(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    if not player:
        await safe_edit(query, t(lang, "not_registered"))
        return
    choice = int(query.data.split("_")[1])
    match choice:
        case 1: align_name = t(lang, "align_good")
        case 2: align_name = t(lang, "align_evil")
        case _: align_name = t(lang, "align_neutral")
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "menu"), callback_data="menu_back"),
    ]])
    if player.align == choice:
        await safe_edit(query, t(lang, "align_already", align=align_name), reply_markup=keyboard)
    else:
        player.align = choice
        await player.update(_columns=["align"])
        await safe_edit(query, t(lang, "align_set", align=align_name),
                        parse_mode="Markdown", reply_markup=keyboard)


def register(app: Application):
    app.add_handler(CommandHandler("align", cmd_align))
    app.add_handler(CallbackQueryHandler(callback_align_menu, pattern="^align_menu$"))
    app.add_handler(CallbackQueryHandler(callback_align, pattern="^align_[012]$"))
