"""
game/challenge.py — дуэли между игроками
Возвращает два отдельных сообщения: для победителя и для проигравшего.
"""
import random
from typing import Optional

import config as cfg
from db import Player, database
from bot import ctime

WEAPON_SLOTS = cfg.WEAPON_SLOTS


def get_total_dps(player: Player) -> int:
    """Суммарный DPS игрока со всего снаряжения + классовый бонус."""
    total = 0
    for slot in WEAPON_SLOTS:
        item = getattr(player, slot)
        if isinstance(item, dict):
            total += item.get("dps", 0)
    from game.classes import get_class_bonus
    cls_bonus = get_class_bonus(player.job)
    if cls_bonus.get("dps_pct"):
        total = int(total * (1 + cls_bonus["dps_pct"] / 100))
    from game.pets import pet_dps_mult
    total = int(total * pet_dps_mult(player.uid))
    return total


async def challenge_opp(player: Player, opp: Optional[Player] = None) -> tuple[str, str]:
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
        opp = random.choice(eligible)

    player_max = int(get_total_dps(player) * (player.level / 100))
    opp_max    = int(get_total_dps(opp)    * (opp.level    / 100))

    backstab = (random.random() <= 0.21 and player.align == 2)

    if player.align == 1:
        player_max += int(0.10 * player_max)
        alvar = 90
    elif player.align == 2:
        player_max -= int(0.10 * player_max)
        if backstab:
            player_max *= 2
        alvar = 110
    else:
        alvar = 100

    from game.races import get_race_dps_mult
    opp_max = int(opp_max * get_race_dps_mult(opp.race))
    player_max = int(player_max * get_race_dps_mult(player.race))

    from game.classes import get_class_bonus
    p_cls_bonus = get_class_bonus(player.job)
    o_cls_bonus = get_class_bonus(opp.job)

    # Паладин: +15% к защите = уменьшаем opp_max для паладина
    if p_cls_bonus.get("defense_pct"):
        opp_max = int(opp_max * (1 - p_cls_bonus["defense_pct"] / 100))
    if o_cls_bonus.get("defense_pct"):
        player_max = int(player_max * (1 - o_cls_bonus["defense_pct"] / 100))
    
    player_val = random.randint(1, max(1, player_max))
    opp_val = random.randint(1, max(1, opp_max))
    nextval = int(random.randint(4, 6) / alvar * (player.nextxp - player.currentxp))
    
    from game.skills.passives.registry import PassiveSkillRegistry
    
    dodge_p, first_p, enc_p = await PassiveSkillRegistry.trigger_on_encounter(player)
    dodge_o, first_o, enc_o = await PassiveSkillRegistry.trigger_on_encounter(opp)
    
    p_lang = player.lang or "ru"
    o_lang = opp.lang or "ru"

    backstab_str_p = ""
    backstab_str_o = ""
    
    if dodge_p:
        backstab_str_p += "\n👤 *Уклонение!*" if p_lang != "en" else "\n👤 *DODGE!*"
    if first_p:
        player_val = int(player_val * (1.0 + enc_p.damage_bonus))
    if dodge_o:
        backstab_str_o += "\n👤 *Уклонение!*" if o_lang != "en" else "\n👤 *DODGE!*"
    if first_o:
        opp_val = int(opp_val * (1.0 + enc_o.damage_bonus))

    # Разбойник: +15% уклонения
    rogue_dodge_p = p_cls_bonus.get("dodge_pct", 0) > 0 and random.random() < 0.15
    rogue_dodge_o = o_cls_bonus.get("dodge_pct", 0) > 0 and random.random() < 0.15
    if rogue_dodge_p:
        opp_val = 0
        backstab_str_p += "\n👤 *Уклонение!*" if p_lang != "en" else "\n👤 *DODGE!*"
    if rogue_dodge_o:
        player_val = 0
        backstab_str_o += "\n👤 *Уклонение!*" if o_lang != "en" else "\n👤 *DODGE!*"

    if backstab:
        backstab_str_p += ("\n🗡️ Ты нанёс *Подлый удар* " + opp.name + "!") if p_lang != "en" else ("\n🗡️ You used *Backstab* on " + opp.name + "!")
        backstab_str_o += ("\n🗡️ " + player.name + " нанёс тебе *Подлый удар*!") if o_lang != "en" else ("\n🗡️ " + player.name + " used *Backstab* on you!")

    # H1: ON_DAMAGE_DEALT passives BEFORE winner (Crit, Vampirism, SlowPoison)
    p_dealt = await PassiveSkillRegistry.trigger_on_damage_dealt(
        player, player_val, False,
        opp_val / max(opp_max, 1), False
    )
    o_dealt = await PassiveSkillRegistry.trigger_on_damage_dealt(
        opp, opp_val, False,
        player_val / max(player_max, 1), False
    )

    if p_dealt.is_crit:
        player_val = int(player_val * 2.0)
        backstab_str_p += "\n⚡ CRIT!" if p_lang == "en" else "\n⚡ КРИТ!"
    archer_crit_p = p_cls_bonus.get("crit_pct", 0) > 0 and random.random() < 0.10
    if archer_crit_p:
        player_val = int(player_val * 2.0)
        backstab_str_p += "\n⚡ CRIT!" if p_lang == "en" else "\n⚡ КРИТ!"
    if p_dealt.damage_bonus:
        player_val = int(player_val * (1.0 + p_dealt.damage_bonus))
    if p_dealt.message:
        backstab_str_p += f"\n{p_dealt.message}"

    if o_dealt.is_crit:
        opp_val = int(opp_val * 2.0)
        backstab_str_o += "\n⚡ CRIT!" if o_lang == "en" else "\n⚡ КРИТ!"
    archer_crit_o = o_cls_bonus.get("crit_pct", 0) > 0 and random.random() < 0.10
    if archer_crit_o:
        opp_val = int(opp_val * 2.0)
        backstab_str_o += "\n⚡ CRIT!" if o_lang == "en" else "\n⚡ КРИТ!"
    if o_dealt.damage_bonus:
        opp_val = int(opp_val * (1.0 + o_dealt.damage_bonus))
    if o_dealt.message:
        backstab_str_o += f"\n{o_dealt.message}"

    # M2: ON_DAMAGE_TAKEN passives (Thorns, ShieldWall) BEFORE winner
    p_taken_mod, p_taken_res = await PassiveSkillRegistry.trigger_on_damage_taken(player, opp_val)
    o_taken_mod, o_taken_res = await PassiveSkillRegistry.trigger_on_damage_taken(opp, player_val)
    if p_taken_res.damage_reflect > 0:
        opp_val = max(1, opp_val - p_taken_res.damage_reflect)
    if o_taken_res.damage_reflect > 0:
        player_val = max(1, player_val - o_taken_res.damage_reflect)
    if p_taken_res.message:
        backstab_str_p += f"\n{p_taken_res.message}"
    if o_taken_res.message:
        backstab_str_o += f"\n{o_taken_res.message}"

    real_gold = max(1, int(nextval * 0.5))
    real_xp = max(1, abs(nextval))

    xp_reduction = 0
    xp_reduction_o = 0
    kill_gold_p = 0
    kill_gold_o = 0

    if player_val >= opp_val:
        steal_str_p = ""
        steal_str_o = ""
        if player.align == 2 and random.random() < 0.15:
            swapped_slot = random.choice(WEAPON_SLOTS)
            p_item = getattr(player, swapped_slot)
            o_item = getattr(opp, swapped_slot)
            if isinstance(p_item, dict) and isinstance(o_item, dict) and o_item["dps"] > p_item["dps"]:
                setattr(player, swapped_slot, o_item)
                setattr(opp, swapped_slot, p_item)
                await player.update(_columns=[swapped_slot])
                await opp.update(_columns=[swapped_slot])
                steal_str_p = ("\n😈 Ты похитил *" + swapped_slot + "* у " + opp.name + "!") if p_lang != "en" else ("\n😈 You stole *" + swapped_slot + "* from " + opp.name + "!")
                steal_str_o = ("\n😈 " + player.name + " похитил твой *" + swapped_slot + "*!") if o_lang != "en" else ("\n😈 " + player.name + " stole your *" + swapped_slot + "*!")

        # Prestige XP bonus for winner
        from plugins.vip_shop import has_prestige_xp_bonus, get_prestige_xp_multiplier
        mage_mult = 1.0 + p_cls_bonus.get("xp_pct", 0) / 100
        xp_reduction = int(nextval * mage_mult)
        if has_prestige_xp_bonus(player):
            xp_reduction = int(xp_reduction * get_prestige_xp_multiplier(player))

        player.nextxp -= xp_reduction
        player.wins   += 1
        opp.loss      += 1

        # Проигравший (opp) получает штраф XP независимо от порядка аргументов
        opp.nextxp += nextval
        opp.totalxplost += nextval

        # H1: apply healing/poison from dealt
        if p_dealt.healing > 0:
            backstab_str_p += f"\n🩸 +{p_dealt.healing} HP"
        if p_dealt.poison_damage > 0:
            backstab_str_p += f"\n☣️ -{p_dealt.poison_damage} HP" if p_lang == "en" else f"\n☣️ -{p_dealt.poison_damage} HP"
            backstab_str_o += f"\n☣️ -{p_dealt.poison_damage} HP" if o_lang == "en" else f"\n☣️ -{p_dealt.poison_damage} HP"

        # ON_KILL for winner
        kill_gold_p, kill_xp_p, kill_res_p = await PassiveSkillRegistry.trigger_on_kill(
            player, opp.level, real_gold, real_xp
        )
        if kill_res_p.triggered and kill_res_p.message:
            backstab_str_p += f"\n{kill_res_p.message}"

        # Apply passive kill XP to reduction
        if kill_xp_p > 0:
            player.nextxp = max(player.currentxp + 1, player.nextxp - kill_xp_p)
            xp_reduction += kill_xp_p

        player.gold += real_gold + kill_gold_p
        p_gold_line = f"\n💰 Gold: +{real_gold + kill_gold_p}\n"
        win_duel_progress_uid = player

        from plugins.monsters import invalidate_dps_cache, MonsterEncountersPlugin
        invalidate_dps_cache(player.uid)
        racial_aid = cfg.RACIAL_ACTIVE_SKILLS.get(player.race or "")
        if racial_aid:
            await MonsterEncountersPlugin._add_active_skill_xp(player, racial_aid)

        if p_lang == "en":
            msg_p = (
                "⚔️ *PVP Encounter!*\n\n"
                "You [" + str(player_val) + "/" + str(player_max) + "] vs *" + opp.name + "* [" + str(opp_val) + "/" + str(opp_max) + "]\n\n"
                "🏆 *YOU WIN!* Next level *" + ctime(xp_reduction, 'en') + "* faster!"
                + p_gold_line + steal_str_p + backstab_str_p
            )
        else:
            msg_p = (
                "⚔️ *PVP Встреча!*\n\n"
                "Ты [" + str(player_val) + "/" + str(player_max) + "] vs *" + opp.name + "* [" + str(opp_val) + "/" + str(opp_max) + "]\n\n"
                "🏆 *ТЫ ПОБЕДИЛ!* До следующего уровня на *" + ctime(xp_reduction, 'ru') + "* быстрее!"
                + p_gold_line + steal_str_p + backstab_str_p
            )

        if o_lang == "en":
            msg_o = (
                "⚔️ *PVP Encounter!*\n\n"
                "*" + player.name + "* [" + str(player_val) + "/" + str(player_max) + "] vs You [" + str(opp_val) + "/" + str(opp_max) + "]\n\n"
                "💀 *YOU LOST!* Next level *" + ctime(nextval, 'en') + "* slower."
                + steal_str_o + backstab_str_o
            )
        else:
            msg_o = (
                "⚔️ *PVP Встреча!*\n\n"
                "*" + player.name + "* [" + str(player_val) + "/" + str(player_max) + "] vs Ты [" + str(opp_val) + "/" + str(opp_max) + "]\n\n"
                "💀 *ТЫ ПРОИГРАЛ!* До следующего уровня на *" + ctime(nextval, 'ru') + "* медленнее."
                + steal_str_o + backstab_str_o
            )

    else:
        # Prestige XP bonus for winner (opp)
        from plugins.vip_shop import has_prestige_xp_bonus, get_prestige_xp_multiplier
        mage_mult_o = 1.0 + o_cls_bonus.get("xp_pct", 0) / 100
        xp_reduction_o = int(nextval * mage_mult_o)
        if has_prestige_xp_bonus(opp):
            xp_reduction_o = int(xp_reduction_o * get_prestige_xp_multiplier(opp))

        player.nextxp      += nextval
        player.totalxplost += nextval
        player.loss        += 1
        opp.wins           += 1

        # H1: apply healing/poison from dealt (opp won)
        if o_dealt.healing > 0:
            backstab_str_o += f"\n🩸 +{o_dealt.healing} HP"
        if o_dealt.poison_damage > 0:
            backstab_str_p += f"\n☣️ -{o_dealt.poison_damage} HP" if p_lang == "en" else f"\n☣️ -{o_dealt.poison_damage} HP"
            backstab_str_o += f"\n☣️ -{o_dealt.poison_damage} HP" if o_lang == "en" else f"\n☣️ -{o_dealt.poison_damage} HP"

        # ON_KILL for winner (opp)
        kill_gold_o, kill_xp_o, kill_res_o = await PassiveSkillRegistry.trigger_on_kill(
            opp, player.level, real_gold, real_xp
        )
        if kill_res_o.triggered and kill_res_o.message:
            backstab_str_o += f"\n{kill_res_o.message}"

        # Apply passive kill XP for winner
        if kill_xp_o > 0:
            xp_reduction_o += kill_xp_o

        opp.nextxp = max(opp.currentxp + 1, opp.nextxp - xp_reduction_o)
        opp.gold += real_gold + kill_gold_o
        o_gold_line = f"\n💰 Gold: +{real_gold + kill_gold_o}\n"
        win_duel_progress_uid = opp

        from plugins.monsters import invalidate_dps_cache, MonsterEncountersPlugin
        invalidate_dps_cache(opp.uid)
        racial_aid_o = cfg.RACIAL_ACTIVE_SKILLS.get(opp.race or "")
        if racial_aid_o:
            await MonsterEncountersPlugin._add_active_skill_xp(opp, racial_aid_o)

        if p_lang == "en":
            msg_p = (
                "⚔️ *PVP Encounter!*\n\n"
                "You [" + str(player_val) + "/" + str(player_max) + "] vs *" + opp.name + "* [" + str(opp_val) + "/" + str(opp_max) + "]\n\n"
                "💀 *YOU LOST!* Next level *" + ctime(nextval, 'en') + "* slower."
                + backstab_str_p
            )
        else:
            msg_p = (
                "⚔️ *PVP Встреча!*\n\n"
                "Ты [" + str(player_val) + "/" + str(player_max) + "] vs *" + opp.name + "* [" + str(opp_val) + "/" + str(opp_max) + "]\n\n"
                "💀 *ТЫ ПРОИГРАЛ!* До следующего уровня на *" + ctime(nextval, 'ru') + "* медленнее."
                + backstab_str_p
            )

        if o_lang == "en":
            msg_o = (
                "⚔️ *PVP Encounter!*\n\n"
                "*" + player.name + "* [" + str(player_val) + "/" + str(player_max) + "] vs You [" + str(opp_val) + "/" + str(opp_max) + "]\n\n"
                "🏆 *YOU WIN!* Next level *" + ctime(xp_reduction_o, 'en') + "* faster!"
                + o_gold_line + backstab_str_o
            )
        else:
            msg_o = (
                "⚔️ *PVP Встреча!*\n\n"
                "*" + player.name + "* [" + str(player_val) + "/" + str(player_max) + "] vs Ты [" + str(opp_val) + "/" + str(opp_max) + "]\n\n"
                "🏆 *ТЫ ПОБЕДИЛ!* До следующего уровня на *" + ctime(xp_reduction_o, 'ru') + "* быстрее!"
                + o_gold_line + backstab_str_o
            )

    # Атомарные инкременты вместо снапшота — не теряем изменения от гонок
    async def _duel_stats(u, *, win: bool, xp_reduction: int, xp_penalty: int, gold_delta: int):
        if win:
            await database.execute(
                "UPDATE users SET nextxp = CASE WHEN nextxp - :red > currentxp + 1 THEN nextxp - :red ELSE currentxp + 1 END, "
                "wins = wins + 1, gold = gold + :gold WHERE uid = :uid",
                {"red": xp_reduction, "gold": gold_delta, "uid": u},
            )
        else:
            await database.execute(
                "UPDATE users SET nextxp = nextxp + :pen, totalxplost = totalxplost + :pen, "
                "loss = loss + 1 WHERE uid = :uid",
                {"pen": xp_penalty, "uid": u},
            )

    await _duel_stats(
        player.uid, win=(player_val >= opp_val),
        xp_reduction=xp_reduction, xp_penalty=nextval,
        gold_delta=real_gold + kill_gold_p,
    )
    await _duel_stats(
        opp.uid, win=(opp_val > player_val),
        xp_reduction=xp_reduction_o, xp_penalty=nextval,
        gold_delta=real_gold + kill_gold_o,
    )

    from game.quests import on_duel_win
    await on_duel_win(win_duel_progress_uid)

    return msg_p, msg_o
