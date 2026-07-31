"""
handlers/_combined.py — объединённые хендлеры

Содержит команды: /setjob, /help, /alert, /quest и их колбэки.
"""
import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

import config as cfg
from db import Player, Quest, set_player_optin
from bot import ctime
from i18n import t
from core.telegram_utils import safe_edit


async def cmd_setjob(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Установка профессии игрока (/setjob)."""
    user = update.effective_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    if not player:
        await update.message.reply_text(t(lang, "not_registered"))
        return
    if not player.onboarding_done and player.level < 10:
        await update.message.reply_text(t(lang, "job_low_level"), parse_mode="HTML")
        return

    if not context.args:
        from handlers.user import class_keyboard
        from game.classes import class_selector_text
        await update.message.reply_text(
            t(lang, "choose_class") + "\n\n" + class_selector_text(lang),
            parse_mode="HTML",
            reply_markup=class_keyboard(lang))
        return

    from game.classes import CLASSES, class_display
    job_name = " ".join(context.args)
    # Match preset class by name
    for c in CLASSES.values():
        if job_name.lower() in (c["name_ru"].lower(), c["name_en"].lower()):
            job_name = c["name_ru"] if lang == "ru" else c["name_en"]
            break

    if not all(x.isalpha() or x.isspace() for x in job_name) or len(job_name) > 50:
        return

    old_job = player.job
    player.job = job_name
    await player.update(_columns=["job"])

    if not player.onboarding_done:
        player.onboarding_done = True
        await player.update(_columns=["onboarding_done"])

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("👤 Profile" if lang == "en" else t(lang, "btn_profile"),
                             callback_data="menu_profile"),
    ]])
    t_key = "job_set" if not old_job else "class_changed"
    display = class_display(job_name, lang)
    await update.message.reply_text(t(lang, t_key, class_name=display),
                                    parse_mode="HTML", reply_markup=keyboard)


async def callback_job_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Колбэк меню установки профессии."""
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
                        parse_mode="HTML", reply_markup=keyboard)
        return
    await safe_edit(query, t(lang, "job_prompt", job=player.job or ("Recruit" if lang == "en" else "Новобранец")),
                    parse_mode="HTML", reply_markup=keyboard)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показ списка команд (/help)."""
    from handlers.user import main_menu_keyboard
    user = update.effective_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    await update.message.reply_text(
        t(lang, "info_commands"), parse_mode="HTML",
        reply_markup=main_menu_keyboard(lang))


async def cmd_alert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Переключение уведомлений игрока (/alert)."""
    user = update.effective_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    if not player:
        await update.message.reply_text(t(lang, "not_registered"))
        return
    new_optin = not player.optin
    await set_player_optin(player.uid, new_optin)
    player.optin = new_optin
    status_str = t(lang, "notif_on_txt") if player.optin else t(lang, "notif_off_txt")
    await update.message.reply_text(t(lang, "notif_status", status=status_str),
                                    parse_mode="HTML")


async def cmd_quest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Перенаправление на /quests."""
    from handlers.quests import cmd_myquests
    await cmd_myquests(update, context)


def register_jobs(app: Application) -> None:
    """Регистрация хендлеров команд setjob/job."""
    app.add_handler(CommandHandler("setjob", cmd_setjob))
    app.add_handler(CommandHandler("job",    cmd_setjob))
    app.add_handler(CallbackQueryHandler(callback_job_prompt, pattern="^job_prompt$"))


def register_listeners(app: Application) -> None:
    """Регистрация хендлеров команд help/alert/quest."""
    app.add_handler(CommandHandler("help",  cmd_help))
    app.add_handler(CommandHandler("alert", cmd_alert))
    app.add_handler(CommandHandler("quest", cmd_quest))
