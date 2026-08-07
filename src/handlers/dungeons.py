"""
handlers/dungeons.py — интерфейс подземелий

Вход: кнопка «Подземелье» в меню профиля (callback_data="menu_dungeons") или /dungeon.
Колбэки: dungeons_menu, dungeons_start_<id>, dungeons_status, dungeons_cancel.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from db import Player
from i18n import t
from core.cache import TTLCache
from core.telegram_utils import safe_edit

from game.dungeons import (
    load_dungeons, get_active_run_async, start_run, cancel_run,
)

_callback_rate_limit = TTLCache(ttl=1.0, maxsize=10000)


def _can_act(uid: int) -> bool:
    key = str(uid)
    if _callback_rate_limit.get(key) is not None:
        return False
    _callback_rate_limit.set(key, True)
    return True


def _dungeon_name(dungeon: dict, lang: str) -> str:
    return dungeon["name_en"] if lang == "en" else dungeon["name_ru"]


async def _menu_text(player, lang: str) -> str:
    run = await get_active_run_async(player.uid)
    if not run:
        return t(lang, "dungeon_idle")
    dungeon = load_dungeons().get(run.dungeon_id, {})
    name = _dungeon_name(dungeon, lang)
    return t(lang, "dungeon_active", name=name, floor=run.floor,
             rooms=run.max_floor)

def _nav_row(lang: str):
    return [
        InlineKeyboardButton("⚔️ Сражение" if lang != "en" else "⚔️ Battle", callback_data="battle_menu"),
        InlineKeyboardButton(t(lang, "btn_profile"), callback_data="menu_profile"),
    ]


async def _menu_keyboard(player, lang: str):
    run = await get_active_run_async(player.uid)
    if run:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(t(lang, "refresh"), callback_data="dungeons_status")],
            [InlineKeyboardButton(t(lang, "dungeon_cancel_btn"), callback_data="dungeons_cancel")],
            _nav_row(lang),
        ])
    rows = []
    for did, d in load_dungeons().items():
        locked = player.level < d["min_level"]
        label = f"{_dungeon_name(d, lang)} (L{d['min_level']}+)"
        if locked:
            label = "🔒 " + label
        rows.append([InlineKeyboardButton(label, callback_data=f"dungeons_start_{did}")])
    rows.append(_nav_row(lang))
    return InlineKeyboardMarkup(rows)


async def handle_dungeons_menu(query, player, lang: str) -> None:
    await safe_edit(query, await _menu_text(player, lang), parse_mode="HTML",
                    reply_markup=await _menu_keyboard(player, lang))


async def callback_dungeons(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    if action == "dungeons_menu":
        await handle_dungeons_menu(query, player, lang)

    elif action == "dungeons_status":
        await handle_dungeons_menu(query, player, lang)

    elif action.startswith("dungeons_start_"):
        did = action[len("dungeons_start_"):]
        ok, result = await start_run(player, did)
        if not ok:
            await handle_dungeons_menu(query, player, lang)
            return
        text = t(lang, "dungeon_started", name=result) + "\n\n" + await _menu_text(player, lang)
        await safe_edit(query, text, parse_mode="HTML",
                        reply_markup=await _menu_keyboard(player, lang))

    elif action == "dungeons_cancel":
        summary = await cancel_run(player)
        text = t(lang, "dungeon_cancelled")
        if summary.get("total_xp"):
            text += f"\n{t(lang, 'dungeon_earned', xp=summary['total_xp'], gold=summary['total_gold'])}"
        await safe_edit(query, text, parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup([_nav_row(lang)]))


async def cmd_dungeon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player = await Player.objects.get_or_none(uid=update.effective_user.id)
    if not player:
        await update.message.reply_text(t("ru", "not_registered"))
        return
    lang = player.lang or "ru"
    await update.message.reply_text(await _menu_text(player, lang), parse_mode="HTML",
                                    reply_markup=await _menu_keyboard(player, lang))


def register(app: Application) -> None:
    app.add_handler(CommandHandler("dungeon", cmd_dungeon))
    app.add_handler(CallbackQueryHandler(callback_dungeons, pattern="^dungeons_"))
