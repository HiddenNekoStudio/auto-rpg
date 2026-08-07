"""
handlers/arena.py — интерфейс арены волн

Вход: кнопка «Арена» в меню профиля (callback_data="arena_menu") или /arena.
Колбэки: arena_menu, arena_status, arena_start, arena_cancel.
"""
import config as cfg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from db import Player
from i18n import t
from core.cache import TTLCache
from core.telegram_utils import safe_edit

from game.arena import get_active_run_async, start_run, cancel_run

_callback_rate_limit = TTLCache(ttl=1.0, maxsize=10000)


def _can_act(uid: int) -> bool:
    key = str(uid)
    if _callback_rate_limit.get(key) is not None:
        return False
    _callback_rate_limit.set(key, True)
    return True


async def _menu_text(player, lang: str) -> str:
    run = await get_active_run_async(player.uid)
    if not run:
        return t(lang, "arena_idle", level=cfg.ARENA_MIN_LEVEL)
    return t(lang, "arena_active", wave=run.wave, best=run.best_wave)


def _nav_row(lang: str):
    return [
        InlineKeyboardButton("⚔️ Сражение" if lang != "en" else "⚔️ Battle", callback_data="battle_menu"),
        InlineKeyboardButton(t(lang, "btn_profile"), callback_data="menu_profile"),
    ]


async def _menu_keyboard(player, lang: str):
    run = await get_active_run_async(player.uid)
    if run:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(t(lang, "refresh"), callback_data="arena_status")],
            [InlineKeyboardButton(t(lang, "arena_cancel_btn"), callback_data="arena_cancel")],
            _nav_row(lang),
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "arena_start_btn"), callback_data="arena_start")],
        _nav_row(lang),
    ])


async def handle_arena_menu(query, player, lang: str) -> None:
    await safe_edit(query, await _menu_text(player, lang), parse_mode="HTML",
                    reply_markup=await _menu_keyboard(player, lang))


async def callback_arena(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    if not _can_act(uid):
        await query.answer()
        return
    await query.answer()
    player = await Player.objects.get_or_none(uid=uid)
    lang = (player.lang or "ru") if player else "ru"
    if not player:
        await safe_edit(query, t(lang, "not_registered"))
        return

    action = query.data
    if action in ("arena_menu", "arena_status"):
        await handle_arena_menu(query, player, lang)

    elif action == "arena_start":
        ok, reason = await start_run(player)
        if not ok:
            if reason == "already":
                text = t(lang, "arena_already") + "\n\n" + await _menu_text(player, lang)
            elif reason == "level":
                text = t(lang, "arena_locked", level=cfg.ARENA_MIN_LEVEL) + "\n\n" + await _menu_text(player, lang)
            else:
                text = await _menu_text(player, lang)
            await safe_edit(query, text, parse_mode="HTML",
                            reply_markup=await _menu_keyboard(player, lang))
            return
        text = t(lang, "arena_started") + "\n\n" + await _menu_text(player, lang)
        await safe_edit(query, text, parse_mode="HTML",
                        reply_markup=await _menu_keyboard(player, lang))

    elif action == "arena_cancel":
        summary = await cancel_run(player)
        text = t(lang, "arena_cancelled")
        if summary.get("total_xp"):
            text += f"\n{t(lang, 'arena_earned', xp=summary['total_xp'], gold=summary['total_gold'])}"
        await safe_edit(query, text, parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup([_nav_row(lang)]))


async def cmd_arena(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player = await Player.objects.get_or_none(uid=update.effective_user.id)
    if not player:
        await update.message.reply_text(t("ru", "not_registered"))
        return
    lang = player.lang or "ru"
    await update.message.reply_text(await _menu_text(player, lang), parse_mode="HTML",
                                    reply_markup=await _menu_keyboard(player, lang))


def register(app: Application) -> None:
    app.add_handler(CommandHandler("arena", cmd_arena))
    app.add_handler(CallbackQueryHandler(callback_arena, pattern="^arena_"))
