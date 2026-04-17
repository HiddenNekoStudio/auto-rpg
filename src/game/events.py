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


async def randomevent(bot: Bot, player: Player):
    """Запускает случайное событие для игрока и шлёт ему в личку."""
    event_choice = random.choices(
        ["gevent", "bevent", "hog"],
        weights=[70, 25, 5],
        k=1
    )[0]

    alvar = 90 if player.align == 1 else 100
    val = int((random.randint(4, 6) / alvar) * (player.nextxp - player.currentxp))

    if event_choice == "gevent":
        player.nextxp -= val
        if player.nextxp - player.currentxp < 0:
            player.nextxp = player.currentxp + 1
        event = random.choice(readfile("gevents"))
        title  = f"⚡ *Ты {event}!*"
        detail = (
            f"Это чудесное событие ускорило тебя на *{ctime(val)}* к уровню *{player.level + 1}*.\n"
            f"До следующего уровня: *{ctime(player.nextxp - player.currentxp)}*"
        )
    elif event_choice == "bevent":
        player.nextxp += val
        player.totalxplost += val
        event = random.choice(readfile("bevents"))
        title  = f"⚡ *Ты {event}!*"
        detail = (
            f"Это несчастливое событие замедлило тебя на *{ctime(val)}* к уровню *{player.level + 1}*.\n"
            f"До следующего уровня: *{ctime(player.nextxp - player.currentxp)}*"
        )
    else:  # hog — очень редкое
        val = int((10 + random.randint(1, 8)) / alvar * player.nextxp)
        player.nextxp -= val
        if player.nextxp - player.currentxp < 0:
            player.nextxp = player.currentxp + 1
        title  = f"⚡ *Благословение! Ты был коснут Рукой Закона!*"
        detail = (
            f"Это редчайшее событие ускорило тебя на *{ctime(val)}* к уровню *{player.level + 1}*.\n"
            f"До следующего уровня: *{ctime(player.nextxp - player.currentxp)}*"
        )

    await player.update(_columns=["nextxp", "totalxplost"])

    item, slot, replaced = await get_item(player)
    footer = (
        f"🎒 Этот {slot} *сильнее* — экипирован!"
        if replaced else
        f"🎒 Этот {slot} слабее — выброшен."
    )

    text = (
        f"{title}\n\n"
        f"{detail}\n\n"
        f"🎁 *Новый лут!*\n"
        f"{item_string(item)}\n"
        f"_{footer}_"
    )

    # Шлём только этому игроку
    await send_to_players(bot, text, player_uids=[player.uid])
