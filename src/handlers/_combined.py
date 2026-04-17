"""handlers/_combined.py — /setjob, /help, /alert, /quest"""

import asyncio
import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import NetworkError, RetryAfter, TimedOut
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

import config as cfg
from db import Player, Quest
from bot import ctime
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


async def cmd_setjob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    if not player:
        await update.message.reply_text(t(lang, "not_registered"))
        return
    if player.level < 10:
        await update.message.reply_text(t(lang, "job_low_level"), parse_mode="Markdown")
        return
    if not context.args:
        await update.message.reply_text(
            t(lang, "job_prompt", job=player.job), parse_mode="Markdown")
        return
    job_name = " ".join(context.args)
    if not all(x.isalpha() or x.isspace() for x in job_name) or len(job_name) > 50:
        return
    player.job = job_name
    await player.update(_columns=["job"])
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "btn_profile") if lang == "ru" else "👤 Profile",
                             callback_data="menu_profile"),
    ]])
    await update.message.reply_text(t(lang, "job_set", job=job_name),
                                    parse_mode="Markdown", reply_markup=keyboard)


async def callback_job_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "back"), callback_data="menu_settings"),
    ]])
    if not player or player.level < 10:
        await safe_edit(query, t(lang, "job_low_level"),
                        parse_mode="Markdown", reply_markup=keyboard)
        return
    await safe_edit(query, t(lang, "job_prompt", job=player.job),
                    parse_mode="Markdown", reply_markup=keyboard)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from handlers.user import main_menu_keyboard
    user = update.effective_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    await update.message.reply_text(
        t(lang, "info_commands"), parse_mode="Markdown",
        reply_markup=main_menu_keyboard(lang))


async def cmd_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    if not player:
        await update.message.reply_text(t(lang, "not_registered"))
        return
    player.optin = not player.optin
    await player.update(_columns=["optin"])
    status_str = t(lang, "notif_on_txt") if player.optin else t(lang, "notif_off_txt")
    await update.message.reply_text(t(lang, "notif_status", status=status_str),
                                    parse_mode="Markdown")


async def cmd_quest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    quest = await Quest.objects.get_or_none()
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "refresh"), callback_data="menu_quest"),
        InlineKeyboardButton(t(lang, "menu"),    callback_data="menu_back"),
    ]])
    if not quest:
        await update.message.reply_text(t(lang, "quest_none"), reply_markup=keyboard)
        return
    remaining = quest.deadline - int(datetime.now().timestamp())
    text = (
        t(lang, "quest_title") + "\n"
        + t(lang, "quest_players", players=quest.players) + "\n"
        + t(lang, "quest_goal", goal=quest.goal) + "\n"
        + t(lang, "quest_progress", time=ctime(quest.endxp - quest.currentxp)) + "\n"
        + t(lang, "quest_deadline", time=ctime(max(0, remaining)))
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


def register_jobs(app: Application):
    app.add_handler(CommandHandler("setjob", cmd_setjob))
    app.add_handler(CommandHandler("job",    cmd_setjob))
    app.add_handler(CallbackQueryHandler(callback_job_prompt, pattern="^job_prompt$"))


def register_listeners(app: Application):
    app.add_handler(CommandHandler("help",  cmd_help))
    app.add_handler(CommandHandler("alert", cmd_alert))
    app.add_handler(CommandHandler("quest", cmd_quest))
