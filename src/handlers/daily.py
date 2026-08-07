"""
handlers/daily.py — ежедневные награды (ретеншн)

Вход: /daily или кнопка «Ежедневно» в меню профиля (callback_data="daily_menu").
Механика: стрик ежедневного входа (7-дневный цикл токенов) + оффлайн-бонус
+ ежедневный бонусный квест (награда токенами).
"""
import random
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

import config as cfg
from db import Player
from i18n import t
from core.cache import TTLCache
from core.telegram_utils import safe_edit

_callback_rate_limit = TTLCache(ttl=1.0, maxsize=10000)

DAY_SECONDS = 86400


def _can_act(uid: int) -> bool:
    key = str(uid)
    if _callback_rate_limit.get(key) is not None:
        return False
    _callback_rate_limit.set(key, True)
    return True


def _cycle_len() -> int:
    return len(cfg.DAILY_REWARD_CYCLE)


def _next_reward(streak: int) -> int:
    """Награда за следующий забор при текущем стрике."""
    return cfg.DAILY_REWARD_CYCLE[streak % _cycle_len()]


def _offline_seconds(player) -> int:
    now = int(time.time())
    if player.online:
        return 0
    since = player.last_idle_at or player.last_online_at or 0
    return max(0, now - since) if since else 0


def _daily_text(player, lang: str) -> str:
    now = int(time.time())
    today = now // DAY_SECONDS
    last = player.last_daily_claim or 0
    streak = player.daily_streak or 0
    already = bool(last) and today == last // DAY_SECONDS

    total = _cycle_len()
    day = (streak % total) + 1
    reward = _next_reward(streak)

    off_sec = _offline_seconds(player)
    off_hours = off_sec // 3600
    off_bonus = 1 if off_hours >= cfg.OFFLINE_BONUS_HOURS else 0

    lines = [t(lang, "daily_title"), "━━━━━━━━━━━━━━━━━━",
             t(lang, "daily_streak", streak=streak),
             t(lang, "daily_cycle", day=day, total=total)]
    lines.append(t(lang, "daily_already") if already else t(lang, "daily_today", reward=reward))
    if off_bonus:
        lines.append(t(lang, "daily_offline_bonus", hours=off_hours, bonus=off_bonus))
    lines += ["━━━━━━━━━━━━━━━━━━", t(lang, "daily_hint")]
    return "\n".join(lines)


def _daily_keyboard(lang: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "daily_claim_btn"), callback_data="daily_claim")],
        [InlineKeyboardButton(t(lang, "menu"), callback_data="menu_back")],
    ])


async def _claim(player, lang: str) -> tuple[str, bool]:
    """Забрать ежедневную награду. Возвращает (сообщение, зачислено_ли)."""
    now = int(time.time())
    today = now // DAY_SECONDS
    last = player.last_daily_claim or 0
    streak = player.daily_streak or 0

    if last and today == last // DAY_SECONDS:
        return t(lang, "daily_already_msg"), False

    streak = streak + 1 if (last and today == last // DAY_SECONDS + 1) else 1
    reward = _next_reward(streak - 1)

    bonus = 0
    if _offline_seconds(player) >= cfg.OFFLINE_BONUS_HOURS * 3600:
        bonus = 1

    clan_bonus = 0
    try:
        from db import ClanMember, Clan
        from handlers.clans import _daily_bonus
        cm = await ClanMember.objects.filter(player_uid=player.uid).get_or_none()
        if cm:
            clan = await Clan.objects.get_or_none(id=cm.clan_id)
            if clan:
                clan_bonus = _daily_bonus(clan.level)
    except Exception:
        pass
    if clan_bonus:
        bonus += clan_bonus

    player.daily_streak = streak
    player.last_daily_claim = now
    player.tokens = (player.tokens or 0) + reward + bonus
    await player.update(_columns=["daily_streak", "last_daily_claim", "tokens"])

    msg = t(lang, "daily_claimed", reward=reward, streak=streak)
    if bonus:
        msg += "\n" + t(lang, "daily_bonus_line", bonus=bonus)
    return msg, True


async def _offer_daily_bonus_quest(bot, player) -> bool:
    """Предложить ежедневный бонусный квест (награда токенами). Возвращает True если предложен."""
    from db import PlayerQuest
    from handlers.quests import offer_quest
    existing = await PlayerQuest.objects.filter(
        player_uid=player.uid,
        status__in=["offered", "active"],
        bonus_tokens__gt=0,
    ).all()
    if existing:
        return False
    quest_type = random.choice(["kill", "explore", "xp", "duel", "boss", "rare"])
    quest = await offer_quest(bot, player, quest_type=quest_type,
                              bonus_tokens=cfg.DAILY_QUEST_TOKEN_REWARD)
    return quest is not None


async def cmd_daily(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    player = await Player.objects.get_or_none(uid=update.effective_user.id)
    lang = (player.lang or "ru") if player else "ru"
    if not player:
        await update.message.reply_text(t(lang, "not_registered"))
        return
    await update.message.reply_text(_daily_text(player, lang), parse_mode="HTML",
                                    reply_markup=_daily_keyboard(lang))


async def callback_daily(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    uid = query.from_user.id
    if not _can_act(uid):
        await query.answer("Wait a second!" if query.from_user.language_code == "en" else "Подожди секунду!",
                           show_alert=True)
        return
    await query.answer()
    player = await Player.objects.get_or_none(uid=uid)
    lang = (player.lang or "ru") if player else "ru"
    if not player:
        await safe_edit(query, t(lang, "not_registered"))
        return

    action = query.data
    if action == "daily_menu":
        await safe_edit(query, _daily_text(player, lang), parse_mode="HTML",
                        reply_markup=_daily_keyboard(lang))
    elif action == "daily_claim":
        msg, credited = await _claim(player, lang)
        if credited:
            offered = await _offer_daily_bonus_quest(context.bot, player)
            if offered:
                msg += "\n\n" + (t(lang, "daily_quest_offered") if lang != "en"
                                 else "🎯 <b>Bonus quest offered!</b>")
        text = msg + "\n\n" + _daily_text(player, lang)
        await safe_edit(query, text, parse_mode="HTML", reply_markup=_daily_keyboard(lang))


def register(app: Application) -> None:
    app.add_handler(CommandHandler("daily", cmd_daily))
    app.add_handler(CallbackQueryHandler(callback_daily, pattern="^daily_"))
