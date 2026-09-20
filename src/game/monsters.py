"""
game/monsters.py — Встречи с монстрами (для обратной совместимости)

Основная логика встреч перенесена в plugins/monsters.py.
Этот файл оставлен для:
- Обратной совместимости с существующим кодом
- Команды админа /admin_spawn для ручного спауна

Race Conditions Protection: Rate limiting 1 encounter в 2 секунды

Расовые бонусы:
  Эльф  (elf)   — +10% к бонусу при победе (быстрее уровень)
  Гном  (dwarf) — +15% к боевой силе (defence = труднее победить монстру)
  Человек (human)— шанс 20% «удача» при проигрыше: штраф не применяется
"""
import datetime
import random
from telegram import Bot

import config as cfg
from db import Player, database
from bot import ctime, send_to_players
from core.cache import TTLCache
from core.monsters import monster_list, monster_list_en
from core.event_bus import emit_monster_defeated, emit_gold_changed

# Rate limiting — TTL cache вместо бесконечного dict
_encounter_cooldown = TTLCache(ttl=2.0, maxsize=10000)

# Серия побед игроков (win_streak для квестов)
_win_streak = {}

# DPS считается в core/dps.py — единый расчёт и единый кэш на весь проект.
# Ре-экспорт для обратной совместимости с существующими импортами.
from core.dps import get_total_dps, invalidate_dps_cache  # noqa: E402,F401


async def encounter_one(bot: Bot, player: Player, monster: str, monster_level: int) -> None:
    """Битва одного игрока с указанным монстром. Обновляет БД и шлёт личный алерт."""

    # Rate limiting — TTL cache автоматически очищается
    uid = player.uid
    if _encounter_cooldown.get(str(uid)) is not None:
        return  # Cooldown active

    _encounter_cooldown.set(str(uid), True)

    lang = player.lang or "ru"
    from game.classes import get_class_bonus
    cls_bonus = get_class_bonus(player.job)

    # Инициализация HP/MP если не установлены
    if not player.hp or player.hp <= 0:
        player.hp = player.get_max_hp()
    player.sync_max_hp_mp()
    if not player.mp or player.mp <= 0:
        player.mp = player.get_max_mp()
    if not player.defense:
        player.defense = 0

    await player.update(_columns=["hp", "max_hp", "mp", "max_mp", "defense"])

    # Паладин: +15% к защите (только для боя, не сохраняем)
    if cls_bonus.get("defense_pct"):
        player.defense = int(player.defense * (1 + cls_bonus["defense_pct"] / 100))

    # Параметры монстра
    p_max = get_total_dps(player)
    m_max = random.randint(max(1, p_max - 500), p_max + 250)
    monster_hp = 50 + monster_level * 10
    monster_max_hp = monster_hp
    monster_defense = monster_level * 2

    # Раунды боя
    rounds = []
    round_num = 0
    player_hp = player.hp
    monster_hp_current = monster_hp

    while player_hp > 0 and monster_hp_current > 0:
        round_num += 1

        # Атака игрока
        player_dmg = max(1, p_max // 2)
        defense_reduction = min(0.75, monster_defense / (monster_defense + 200))
        player_dmg = int(player_dmg * (1 - defense_reduction))
        monster_hp_current = max(0, monster_hp_current - player_dmg)

        round_result = {
            "num": round_num,
            "player_attack": player_dmg,
            "monster_hp": monster_hp_current,
            "monster_max": monster_max_hp,
        }

        # Если монстр жив - его атака
        if monster_hp_current > 0:
            monster_dmg = max(1, m_max // 2)
            player_def_reduction = player.get_defense_reduction()
            monster_dmg = int(monster_dmg * (1 - player_def_reduction))
            player_hp = max(0, player_hp - monster_dmg)

            round_result["monster_attack"] = monster_dmg
            round_result["player_hp"] = player_hp
            round_result["player_max"] = player.max_hp

        rounds.append(round_result)

        if round_num >= 20:
            break

    player_won = monster_hp_current <= 0

    # Проверка уклонения
    from game.skills.passives.registry import PassiveSkillRegistry
    # Разбойник: +15% к уклонению
    rogue_dodge = cls_bonus.get("dodge_pct", 0) > 0 and random.random() < 0.15
    dodge_ok, first_strike_active, encounter_res = await PassiveSkillRegistry.trigger_on_encounter(player)
    if dodge_ok or rogue_dodge:
        _encounter_cooldown.delete(str(uid))
        msg_extra = encounter_res.message if encounter_res.message else ""
        if lang == "en":
            msg = "\n".join([
                "⚔️ *Monster Encounter!*",
                "", f"{player.name} vs *{monster}*", "",
                "👤 *DODGE!*\nYou evaded the monster completely!",
                f"\n{msg_extra}" if msg_extra else "",
            ])
        else:
            msg = "\n".join([
                "⚔️ *Встреча с монстром!*",
                "", f"{player.name} vs *{monster}*", "",
                "👤 *УКЛОНЕНИЕ!*\nТы полностью уклонился от монстра!",
                f"\n{msg_extra}" if msg_extra else "",
            ])
        await send_to_players(bot, msg, player_uids=[player.uid], parse_mode="HTML")
        return

    # Расчёт штрафа/награды (старая логика)
    p_max = get_total_dps(player)
    m_max = random.randint(max(1, p_max - 500), p_max + 250)
    alvar = 90 if player.align == 1 else 100
    val = int(random.randint(4, 6) / alvar * (player.nextxp - player.currentxp))

    # Лучник: +10% к шансу крита
    archer_crit = cls_bonus.get("crit_pct", 0) > 0 and random.random() < 0.10
    smite_chance = (random.random() <= 0.10 and player.align == 1) or archer_crit
    smite_str = "\n✨ *СМАЙТ!* " if smite_chance and lang != "en" else ("\n✨ *SMITE!* " if smite_chance else "")

    _deaths = 0
    _pen_xp = 0

    if player_won:
        player.monster_kills = (player.monster_kills or 0) + 1
        from game.races import get_race_xp_mult
        elf_mult = get_race_xp_mult(player.race)
        # Маг: +15% к опыту
        mage_mult = 1.0
        if cls_bonus.get("xp_pct"):
            mage_mult = 1.0 + cls_bonus["xp_pct"] / 100
        effective_val = max(1, int(val * elf_mult * mage_mult))

        player.nextxp = max(player.currentxp + 1, player.nextxp - effective_val)

        gold_reward = (monster_level * 5) + random.randint(0, player.level * 2)

        bonus_gold, bonus_xp, kill_res = await PassiveSkillRegistry.trigger_on_kill(
            player, monster_level, gold_reward, effective_val
        )
        gold_reward += bonus_gold
        effective_val += bonus_xp

        if bonus_xp > 0:
            player.nextxp = max(player.currentxp + 1, player.nextxp - bonus_xp)

        # Prestige бонус на всю XP (база + пассивки)
        from plugins.vip_shop import has_prestige_xp_bonus, get_prestige_xp_multiplier
        if has_prestige_xp_bonus(player):
            prestige_mult = get_prestige_xp_multiplier(player)
            additional_xp = int(effective_val * (prestige_mult - 1.0))
            if additional_xp > 0:
                player.nextxp = max(player.currentxp + 1, player.nextxp - additional_xp)
                effective_val += additional_xp

        from plugins.vip_shop import has_prestige_gold_bonus, get_prestige_gold_multiplier
        if has_prestige_gold_bonus(player):
            gold_reward = int(gold_reward * get_prestige_gold_multiplier(player))

        player.gold += gold_reward

        await emit_monster_defeated(player.uid, effective_val, gold_reward, monster_level)
        await emit_gold_changed(player.uid, gold_reward, "monster_victory")

        passive_kill_msg = f"\n{kill_res.message}" if kill_res.triggered and kill_res.message else ""

        # Формируем сообщение с раундами
        round_lines = []
        for r in rounds:
            p_hp_bar = "█" * int(r["player_hp"] / r["player_max"] * 6) + "░" * (6 - int(r["player_hp"] / r["player_max"] * 6))
            m_hp_bar = "█" * int(r["monster_hp"] / r["monster_max"] * 6) + "░" * (6 - int(r["monster_hp"] / r["monster_max"] * 6))
            dmg_label = "dmg" if lang == "en" else "урона"
            round_lines.append(
                f"  ⚔️ {r['player_attack']} {dmg_label} → 👹 [{m_hp_bar}] {r['monster_hp']}/{r['monster_max']}"
            )
            if "monster_attack" in r:
                round_lines.append(
                    f"  👹 {r['monster_attack']} {dmg_label} → 👤 [{p_hp_bar}] {r['player_hp']}/{r['player_max']}"
                )

        rounds_str = "\n".join(round_lines[:10])

        if lang == "en":
            msg = "\n".join([
                "⚔️ *Monster Encounter!*",
                f"  👤 *{player.name}* vs 👹 *{monster}* (Lv.{monster_level})",
                f"  📊 HP: {player.hp}/{player.max_hp} | 🛡️ {player.get_defense()}",
                "",
                f"━━━ Rounds {len(rounds)} ━━━",
                rounds_str,
                "",
                 f"🏆 *YOU WIN!* -{ctime(effective_val, lang)} to level {player.level + 1}!",
                 f"💰 Gold: +{gold_reward}",
                 f"Next level in: *{ctime(player.nextxp - player.currentxp, lang)}*",
                passive_kill_msg,
            ])
        else:
            msg = "\n".join([
                "⚔️ *Встреча с монстром!*",
                f"  👤 *{player.name}* vs 👹 *{monster}* (Ур.{monster_level})",
                f"  📊 HP: {player.hp}/{player.max_hp} | 🛡️ {player.get_defense()}",
                "",
                f"━━━ Раунды ({len(rounds)}) ━━━",
                rounds_str,
                "",
                 f"🏆 *ТЫ ПОБЕДИЛ!* Бонус -{ctime(effective_val, lang)} к уровню {player.level + 1}!",
                 f"💰 Золото: +{gold_reward}",
                 f"До след. уровня: *{ctime(player.nextxp - player.currentxp, lang)}*",
                passive_kill_msg,
            ])

        current_streak = _win_streak.get(player.uid, 0) + 1
        _win_streak[player.uid] = current_streak

    else:
        from game.races import get_race_bonus
        lucky = player.race == "human" and random.random() < get_race_bonus(player.race, "luck_chance", 0.0)

        if lucky:
            if lang == "en":
                msg = "\n".join([
                    "⚔️ *Monster Encounter!*",
                    f"  👤 *{player.name}* vs 👹 *{monster}* (Lv.{monster_level})",
                    "",
                    "🍀 *HUMAN LUCK!* You narrowly escaped — no penalty this time!",
                ])
            else:
                msg = "\n".join([
                    "⚔️ *Встреча с монстром!*",
                    f"  👤 *{player.name}* vs 👹 *{monster}* (Ур.{monster_level})",
                    "",
                    "🍀 *УДАЧА ЧЕЛОВЕКА!* Ты едва ускользнул — штраф отменяется!",
                ])
        else:
            player.monster_deaths = (player.monster_deaths or 0) + 1
            _deaths = 1

            from plugins.vip_shop import has_active_protect
            protect_active = has_active_protect(player)
            if not protect_active:
                player.nextxp += val
                player.totalxplost += val
                _pen_xp = val

            round_lines = []
            for r in rounds:
                p_hp_bar = "█" * int(r["player_hp"] / r["player_max"] * 6) + "░" * (6 - int(r["player_hp"] / r["player_max"] * 6))
                m_hp_bar = "█" * int(r["monster_hp"] / r["monster_max"] * 6) + "░" * (6 - int(r["monster_hp"] / r["monster_max"] * 6))
                dmg_label = "dmg" if lang == "en" else "урона"
                round_lines.append(
                    f"  ⚔️ {r['player_attack']} {dmg_label} → 👹 [{m_hp_bar}] {r['monster_hp']}/{r['monster_max']}"
                )
                if "monster_attack" in r:
                    round_lines.append(
                        f"  👹 {r['monster_attack']} {dmg_label} → 👤 [{p_hp_bar}] {r['player_hp']}/{r['player_max']}"
                    )

            rounds_str = "\n".join(round_lines[:10])

            if lang == "en":
                penalty_line = (
                    "🛡️ *PROTECT!* Penalty cancelled!"
                    if protect_active else
                    f"💀 *MONSTER WINS!* Penalty +{ctime(val, lang)} to level {player.level + 1}."
                )
                msg = "\n".join([
                    "⚔️ *Monster Encounter!*",
                    f"  👤 *{player.name}* vs 👹 *{monster}* (Lv.{monster_level})",
                    f"  📊 HP: {player.hp}/{player.max_hp} | 🛡️ {player.get_defense()}",
                    "",
                    f"━━━ Rounds {len(rounds)} ━━━",
                    rounds_str,
                    "",
                    penalty_line,
                     f"Next level in: *{ctime(player.nextxp - player.currentxp, lang)}*",
                ])
            else:
                penalty_line = (
                    "🛡️ *ЗАЩИТА!* Штраф отменён!"
                    if protect_active else
                    f"💀 *МОНСТР ПОБЕДИЛ!* Штраф +{ctime(val, lang)} к уровню {player.level + 1}."
                )
                msg = "\n".join([
                    "⚔️ *Встреча с монстром!*",
                    f"  👤 *{player.name}* vs 👹 *{monster}* (Ур.{monster_level})",
                    f"  📊 HP: {player.hp}/{player.max_hp} | 🛡️ {player.get_defense()}",
                    "",
                    f"━━━ Раунды ({len(rounds)}) ━━━",
                    rounds_str,
                    "",
                    penalty_line,
                     f"До след. уровня: *{ctime(player.nextxp - player.currentxp, lang)}*",
                ])

            _win_streak[player.uid] = 0

    if player_won:
        await database.execute(
            "UPDATE users SET nextxp = CASE WHEN nextxp - :xp > currentxp + 1 THEN nextxp - :xp ELSE currentxp + 1 END, "
            "gold = gold + :gold, monster_kills = monster_kills + 1 WHERE uid = :uid",
            {"xp": effective_val, "gold": gold_reward, "uid": player.uid},
        )
    else:
        sql = "UPDATE users SET monster_deaths = monster_deaths + :d"
        params = {"d": _deaths, "uid": player.uid}
        if _pen_xp:
            sql += ", nextxp = nextxp + :pen, totalxplost = totalxplost + :pen"
            params["pen"] = _pen_xp
        await database.execute(sql + " WHERE uid = :uid", params)

    from game.quests import on_win_streak, on_death
    if player_won:
        try:
            await on_win_streak(player, _win_streak.get(player.uid, 1))
        except Exception:
            import logging
            logging.exception("win streak hook error")
        # NEW QUEST SYSTEM
        try:
            from game.quests import on_monster_defeated
            await on_monster_defeated(player, monster)
        except Exception as e:
            import logging
            logging.error(f"Quest progress error: {e}")
        try:
            from core.loot import maybe_drop_gem
            await maybe_drop_gem(player.uid)
        except Exception as e:
            import logging
            logging.error(f"Gem drop error: {e}")
    else:
        await on_death(player)
    
    await send_to_players(bot, msg, player_uids=[player.uid])


async def encounter_all(bot: Bot, players: list) -> None:
    """
    Встреча с монстром для ВСЕХ онлайн-игроков одновременно.
    Каждый игрок сражается со своим экземпляром одного и того же монстра.
    """
    if not players:
        return

    # Один монстр на всех — одинаковый уровень, но броски у каждого свои
    # Выбираем монстра по большинству языка (берём первого игрока)
    sample_lang    = players[0].lang or "ru"
    monster        = random.choice(monster_list_en if sample_lang == "en" else monster_list)
    # Уровень монстра — средний по всем игрокам
    avg_level      = max(1, sum(p.level for p in players) // len(players))
    monster_level  = random.randint(max(1, avg_level - 5), avg_level + 15)

    for player in players:
        try:
            await encounter_one(bot, player, monster, monster_level)
        except Exception as e:
            import logging
            logging.warning("encounter_one failed for %s: %s", player.name, e)


# Алиас для обратной совместимости
async def encounter(bot: Bot, player: Player) -> None:
    """Встреча с одним игроком (используется в admin-панели)."""
    lang    = player.lang or "ru"
    monster = random.choice(monster_list_en if lang == "en" else monster_list)
    monster_level = random.randint(max(1, player.level - 10), player.level + 20)
    await encounter_one(bot, player, monster, monster_level)


async def spawn_all(bot: Bot) -> None:
    """Вызвать встречу с монстрами для всех онлайн-игроков (для admin)."""
    from db import Player
    players = await Player.get_active_players()
    if players:
        from plugins.monsters import spawn_all_monsters
        await spawn_all_monsters(bot)
