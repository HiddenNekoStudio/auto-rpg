"""
game/events.py — случайные события
Уведомление приходит ТОЛЬКО причастному игроку в личку.
"""

import random
from telegram import Bot

import config as cfg
from db import Player
from loot import get_item
from bot import ctime, item_string, send_to_players, readfile
from i18n import t


async def randomevent(bot: Bot, player: Player):
    """Запускает случайное событие для игрока и шлёт ему в личку."""
    lang = player.lang or "ru"
    event_choice = random.choices(
        ["gevent", "bevent", "hog"],
        weights=[70, 25, 5],
        k=1
    )[0]

    alvar = 90 if player.align == 1 else 100
    val = int((random.randint(4, 6) / alvar) * (player.nextxp - player.currentxp))

    if event_choice == "gevent":
        from plugins.vip_shop import has_prestige_xp_bonus, get_prestige_xp_multiplier
        if has_prestige_xp_bonus(player):
            val = int(val * get_prestige_xp_multiplier(player))
        player.nextxp -= val
        if player.nextxp - player.currentxp < 0:
            player.nextxp = player.currentxp + 1
        event = random.choice(readfile("gevents"))
        title  = t(lang, "gevent_title", event=event)
        detail = t(lang, "gevent_detail", time=ctime(val, lang), level=player.level + 1, next=ctime(player.nextxp - player.currentxp, lang))
    elif event_choice == "bevent":
        player.nextxp += val
        player.totalxplost += val
        event = random.choice(readfile("bevents"))
        title  = t(lang, "bevent_title", event=event)
        detail = t(lang, "bevent_detail", time=ctime(val, lang), level=player.level + 1, next=ctime(player.nextxp - player.currentxp, lang))
    else:  # hog — очень редкое
        val = int((10 + random.randint(1, 8)) / alvar * player.nextxp)
        from plugins.vip_shop import has_prestige_xp_bonus, get_prestige_xp_multiplier
        if has_prestige_xp_bonus(player):
            val = int(val * get_prestige_xp_multiplier(player))
        player.nextxp -= val
        if player.nextxp - player.currentxp < 0:
            player.nextxp = player.currentxp + 1
        title  = t(lang, "hog_title")
        detail = t(lang, "hog_detail", time=ctime(val, lang), level=player.level + 1, next=ctime(player.nextxp - player.currentxp, lang))

    await player.update(_columns=["nextxp", "totalxplost"])

    # NEW QUEST SYSTEM - XP gained
    try:
        from game.quests import on_xp_gained
        await on_xp_gained(player, val)
    except Exception:
        pass

    item, slot, replaced = await get_item(player)
    footer = t(lang, "loot_stronger", slot=slot) if replaced else t(lang, "loot_weaker", slot=slot)

    text = (
        f"{title}\n\n"
        f"{detail}\n\n"
        f"{t(lang, 'loot_new')}\n"
        f"{item_string(item, lang)}\n"
        f"<i>{footer}</i>"
    )

    # Шлём только этому игроку
    await send_to_players(bot, text, player_uids=[player.uid], parse_mode="HTML")
