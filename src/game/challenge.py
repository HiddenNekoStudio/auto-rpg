"""
game/challenge.py — дуэли между игроками
Возвращает два отдельных сообщения: для победителя и для проигравшего.
"""
import random
from typing import Optional, Tuple

import config as cfg
from db import Player
from bot import ctime

WEAPON_SLOTS = cfg.WEAPON_SLOTS


def get_total_dps(player: Player) -> int:
    total = 0
    for slot in WEAPON_SLOTS:
        item = getattr(player, slot)
        if isinstance(item, dict):
            total += item.get("dps", 0)
    return total


async def challenge_opp(player: Player, opp: Optional[Player] = None) -> Tuple[str, str]:
    """
    Проводит дуэль.
    Возвращает (msg_for_player, msg_for_opp) — персональные сообщения каждому.
    """
    if not opp:
        eligible = await Player.objects.exclude(uid=player.uid).all(
            level__gte=cfg.MIN_CHALLENGE_LEVEL, online=True
        )
        if not eligible:
            msg = "Ищешь соперника, но никого нет рядом." if (player.lang or "ru") == "ru" else "Looking for an opponent, but no one is around."
            return msg, ""

    player_max = int(get_total_dps(player) * (player.level / 100))
    opp_max    = int(get_total_dps(opp)    * (opp.level    / 100))

    backstab = (random.random() <= 0.21 and player.align == 2)

    match player.align:
        case 1:
            player_max += int(0.10 * player_max)
            alvar = 90
        case 2:
            player_max -= int(0.10 * player_max)
            if backstab:
                player_max *= 2
            alvar = 110
        case _:
            alvar = 100

    # Гном: +15% к защите = уменьшаем opp_max если opponent — гном
    if opp.race == "dwarf":
        opp_max = int(opp_max * 1.15)

    nextval    = int((random.randint(3, 5) / alvar) * (player.nextxp - player.currentxp))
    player_val = random.randint(1, max(1, player_max))
    opp_val    = random.randint(1, max(1, opp_max))

    p_lang = player.lang or "ru"
    o_lang = opp.lang or "ru"

    backstab_str_p = ""
    backstab_str_o = ""
    if backstab:
        backstab_str_p = ("\n🗡️ Ты нанёс *Подлый удар* " + opp.name + "!") if p_lang != "en" else ("\n🗡️ You used *Backstab* on " + opp.name + "!")
        backstab_str_o = ("\n🗡️ " + player.name + " нанёс тебе *Подлый удар*!") if o_lang != "en" else ("\n🗡️ " + player.name + " used *Backstab* on you!")

    if player_val >= opp_val:
        # Злой: шанс украсть вещь
        steal_str_p = ""
        steal_str_o = ""
        if player.align == 2 and random.random() < 0.15:
            swapped_slot = random.choice(WEAPON_SLOTS)
            p_item = getattr(player, swapped_slot)
            o_item = getattr(opp, swapped_slot)
            if isinstance(p_item, dict) and isinstance(o_item, dict) and p_item["dps"] > o_item["dps"]:
                setattr(player, swapped_slot, o_item)
                setattr(opp, swapped_slot, p_item)
                await player.update(_columns=[swapped_slot])
                await opp.update(_columns=[swapped_slot])
                steal_str_p = ("\n😈 Ты похитил *" + swapped_slot + "* у " + opp.name + "!") if p_lang != "en" else ("\n😈 You stole *" + swapped_slot + "* from " + opp.name + "!")
                steal_str_o = ("\n😈 " + player.name + " похитил твой *" + swapped_slot + "*!") if o_lang != "en" else ("\n😈 " + player.name + " stole your *" + swapped_slot + "*!")

        player.nextxp -= nextval
        player.wins   += 1
        opp.loss      += 1

        if p_lang == "en":
            msg_p = (
                "⚔️ *PVP Encounter!*\n\n"
                "You [" + str(player_val) + "/" + str(player_max) + "] vs *" + opp.name + "* [" + str(opp_val) + "/" + str(opp_max) + "]\n\n"
                "🏆 *YOU WIN!* Next level *" + ctime(nextval) + "* faster!"
                + steal_str_p + backstab_str_p
            )
        else:
            msg_p = (
                "⚔️ *PVP Встреча!*\n\n"
                "Ты [" + str(player_val) + "/" + str(player_max) + "] vs *" + opp.name + "* [" + str(opp_val) + "/" + str(opp_max) + "]\n\n"
                "🏆 *ТЫ ПОБЕДИЛ!* До следующего уровня на *" + ctime(nextval) + "* быстрее!"
                + steal_str_p + backstab_str_p
            )

        if o_lang == "en":
            msg_o = (
                "⚔️ *PVP Encounter!*\n\n"
                "*" + player.name + "* [" + str(player_val) + "/" + str(player_max) + "] vs You [" + str(opp_val) + "/" + str(opp_max) + "]\n\n"
                "💀 *YOU LOST!* Next level *" + ctime(nextval) + "* slower."
                + steal_str_o + backstab_str_o
            )
        else:
            msg_o = (
                "⚔️ *PVP Встреча!*\n\n"
                "*" + player.name + "* [" + str(player_val) + "/" + str(player_max) + "] vs Ты [" + str(opp_val) + "/" + str(opp_max) + "]\n\n"
                "💀 *ТЫ ПРОИГРАЛ!* До следующего уровня на *" + ctime(nextval) + "* медленнее."
                + steal_str_o + backstab_str_o
            )

    else:
        player.nextxp      += nextval
        player.totalxplost += nextval
        player.loss        += 1
        opp.wins           += 1

        if p_lang == "en":
            msg_p = (
                "⚔️ *PVP Encounter!*\n\n"
                "You [" + str(player_val) + "/" + str(player_max) + "] vs *" + opp.name + "* [" + str(opp_val) + "/" + str(opp_max) + "]\n\n"
                "💀 *YOU LOST!* Next level *" + ctime(nextval) + "* slower."
                + backstab_str_p
            )
        else:
            msg_p = (
                "⚔️ *PVP Встреча!*\n\n"
                "Ты [" + str(player_val) + "/" + str(player_max) + "] vs *" + opp.name + "* [" + str(opp_val) + "/" + str(opp_max) + "]\n\n"
                "💀 *ТЫ ПРОИГРАЛ!* До следующего уровня на *" + ctime(nextval) + "* медленнее."
                + backstab_str_p
            )

        if o_lang == "en":
            msg_o = (
                "⚔️ *PVP Encounter!*\n\n"
                "*" + player.name + "* [" + str(player_val) + "/" + str(player_max) + "] vs You [" + str(opp_val) + "/" + str(opp_max) + "]\n\n"
                "🏆 *YOU WIN!* Next level *" + ctime(nextval) + "* faster!"
                + backstab_str_o
            )
        else:
            msg_o = (
                "⚔️ *PVP Встреча!*\n\n"
                "*" + player.name + "* [" + str(player_val) + "/" + str(player_max) + "] vs Ты [" + str(opp_val) + "/" + str(opp_max) + "]\n\n"
                "🏆 *ТЫ ПОБЕДИЛ!* До следующего уровня на *" + ctime(nextval) + "* быстрее!"
                + backstab_str_o
            )

    await player.update(_columns=["nextxp", "totalxplost", "wins", "loss"])
    await opp.update(_columns=["nextxp", "wins", "loss"])

    return msg_p, msg_o
