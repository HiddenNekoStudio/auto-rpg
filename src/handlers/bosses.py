"""handlers/bosses.py — обработчики боссов"""
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ContextTypes

from db import Player, Boss
from bot import ctime
from i18n import t
from game.bosses import (
    get_boss_at,
    send_boss_encounter_alert,
    resolve_battle,
    respawn_boss,
    get_total_dps_from_equipment,
    get_equipment_quality_rank,
    battle_victory_chance,
)
import config as cfg


async def callback_boss_fight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Сразиться'."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    player = await Player.objects.get_or_none(uid=user.id)
    if not player:
        return
    
    boss_id = query.data.removeprefix("boss_fight_")
    boss = await Boss.objects.get_or_none(boss_id=boss_id)
    if not boss or boss.defeated:
        if boss and boss.defeated:
            lang = player.lang or "ru"
            msg = "Этот босс уже побеждён!" if lang != "en" else "This boss is already defeated!"
            try:
                await query.message.edit_text(msg)
            except Exception:
                pass
        return
    
    lang = player.lang or "ru"
    
    from game.bosses import BOSS_RADIUS_CHOICE, _boss_distance
    dist = _boss_distance(player.x, player.y, boss.x, boss.y)
    if dist > BOSS_RADIUS_CHOICE:
        msg = "Босс слишком далеко!" if lang != "en" else "Boss too far!"
        try:
            await query.message.edit_text(msg)
        except Exception:
            pass
        return
    
    try:
        await query.message.delete()
    except Exception:
        pass
    
    await resolve_battle(context.bot, player, boss, forced=True, lang=lang)


async def callback_boss_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Уйти'."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    player = await Player.objects.get_or_none(uid=user.id)
    if not player:
        lang = "ru"
    else:
        lang = player.lang or "ru"
        
        boss_id = query.data.removeprefix("boss_leave_")
        import json as json_module
        import time
        boss = await Boss.objects.get_or_none(boss_id=boss_id)
        state_ctx = {}
        try:
            if player.state_context:
                state_ctx = json_module.loads(player.state_context) if isinstance(player.state_context, str) else player.state_context
        except Exception:
            state_ctx = {}
        
        if boss:
            state_ctx["last_boss_id"] = boss.boss_id
            state_ctx["boss_respawn_at"] = getattr(boss, 'respawn_available', 0) or 0
        player.state_context = json_module.dumps(state_ctx)
        await player.update(_columns=["state_context"])
    
    if lang != "en":
        msg = "Ты покинул зону босса."
    else:
        msg = "You left the boss zone."
    
    try:
        await query.message.delete()
    except Exception:
        pass


def register_handlers(app):
    """Регистрация обработчиков боссов."""
    app.add_handler(CallbackQueryHandler(callback_boss_fight, pattern="^boss_fight_"))
    app.add_handler(CallbackQueryHandler(callback_boss_leave, pattern="^boss_leave_"))
    logging.info("Boss handlers registered")