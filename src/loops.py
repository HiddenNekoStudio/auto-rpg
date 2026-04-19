"""
loops.py — игровые циклы
"""
import asyncio
from datetime import datetime
import logging
import random

from telegram.ext import Application

import config as cfg
from db import Player, Quest
from bot import ctime, send_to_players
from game.events import randomevent
from game.monsters import encounter, encounter_all
from game.challenge import challenge_opp
from i18n import t
from data.locations import get_location_coords
from handlers.quests import get_player_locked_quest

# Счётчики
_token_counter        = 0
_global_event_counter = 0
_monster_counter      = 0  # для встреч с монстрами каждые 1 час
_daily_quest_counter = 0  # для ежедневных квестов
_boss_respawn_counter = 0  # для респауна боссов каждые 4 дня

GLOBAL_EVENT_INTERVAL = 5 * 3600  # 5 часов
DAILY_QUEST_INTERVAL  = 24 * 3600  # 24 часа
BOSS_RESPAWN_INTERVAL = 4 * 24 * 3600  # 4 дня


async def levelup(bot, player: Player):
    from loot import get_item
    from bot import item_string
    
    lang = player.lang or "ru"
    player.level    += 1
    player.currentxp = 0
    player.nextxp    = cfg.xp_for_level(player.level)

    from game.quests import on_level_reached
    await on_level_reached(player, player.level)

    item, slot, replaced = await get_item(player)
    
    footer = (
        f"🎒 {slot} *сильнее* — экипирован!"
        if replaced else
        f"🎒 {slot} слабее — выброшен."
    )

    if lang == "en":
        text = (
            "*LEVEL UP!*\n\n"
            + player.name + " has reached level *" + str(player.level) + "*!\n"
            + "Next level in: *" + ctime(player.nextxp) + "*\n\n"
            + "🎁 *Reward!*\n"
            + item_string(item) + "\n"
            + "_" + footer + "_"
        )
    else:
        text = (
            "*ПОВЫШЕНИЕ УРОВНЯ!*\n\n"
            + player.name + " достиг *" + str(player.level) + "* уровня!\n"
            + "До следующего уровня: *" + ctime(player.nextxp) + "*\n\n"
            + "🎁 *Награда!*\n"
            + item_string(item) + "\n"
            + "_" + footer + "_"
        )

    if player.optin:
        await send_to_players(bot, text, player_uids=[player.uid])


async def main_loop(bot):
    """Основной игровой тик."""
    global _token_counter, _global_event_counter, _monster_counter, _boss_respawn_counter
    _token_counter        += cfg.INTERVAL
    _global_event_counter += cfg.INTERVAL
    _monster_counter      += cfg.INTERVAL
    _boss_respawn_counter += cfg.INTERVAL

    # ── Оффлайн по таймауту ──────────────────────
    now   = int(datetime.today().timestamp())
    cutoff = now - cfg.OFFLINE_TIMEOUT
    
    # Один запрос: получить тех кто был онлайн, но уже неактивен
    went_offline = await Player.objects.filter(
        online=True,
        lastlogin__lt=cutoff
    ).all()
    
    if went_offline:
        for p in went_offline:
            p.online = False
        await Player.objects.bulk_update(went_offline, columns=["online"])
        logging.info("Ушли оффлайн (таймаут): %s", [p.name for p in went_offline])
        for p in went_offline:
            mins = cfg.OFFLINE_TIMEOUT // 60
            lang = p.lang or "ru"
            msg = (
                f"*{p.name}*, your hero went to rest!\n\n"
                f"No activity for {mins} min. — offline now, XP stopped.\n\n"
                "Open /start to continue your adventure! ⚔️"
            ) if lang == "en" else (
                f"⏸️ *{p.name}*, твой герой ушёл на отдых!\n\n"
                f"Ты не проявлял активности более {mins} мин. и переведён в оффлайн.\n\n"
                "Зайди и нажми /start чтобы продолжить приключение! ⚔️"
            )
            await send_to_players(bot, msg, player_uids=[p.uid])

    # ── Основной список онлайн-игроков ────────────
    # Один запрос вместо двух — используем оптимизированный метод
    players = await Player.get_active_players()
    if not players:
        return

    for player in players:
        locked_quest = await get_player_locked_quest(player)
        
        if locked_quest:
            target_loc_id = locked_quest.target_location_id
            target_x, target_y = await get_location_coords(target_loc_id)
            
            if target_x is not None:
                move_direction = random.choice(["north", "south", "east", "west"])
                
                if move_direction == "north" and player.y < target_y:
                    player.y = min(player.y + 1, target_y)
                elif move_direction == "south" and player.y > target_y:
                    player.y = max(player.y - 1, target_y)
                elif move_direction == "east" and player.x < target_x:
                    player.x = min(player.x + 1, target_x)
                elif move_direction == "west" and player.x > target_x:
                    player.x = max(player.x - 1, target_x)
                else:
                    move_roll = random.random()
                    if move_roll < 0.7:
                        player.x = random.randint(player.x - 1, player.x + 1) % cfg.MAP_SIZE[0]
                        player.y = random.randint(player.y - 1, player.y + 1) % cfg.MAP_SIZE[1]
                    else:
                        player.x = random.randint(player.x - 3, player.x + 5) % cfg.MAP_SIZE[0]
                        player.y = random.randint(player.y - 3, player.y + 5) % cfg.MAP_SIZE[1]
        else:
            old_x, old_y = player.x, player.y
            move_roll = random.random()
            if move_roll < 0.7:
                player.x = random.randint(player.x - 1, player.x + 1) % cfg.MAP_SIZE[0]
                player.y = random.randint(player.y - 1, player.y + 1) % cfg.MAP_SIZE[1]
            else:
                player.x = random.randint(player.x - 3, player.x + 5) % cfg.MAP_SIZE[0]
                player.y = random.randint(player.y - 3, player.y + 5) % cfg.MAP_SIZE[1]

        if old_x != player.x or old_y != player.y:
            from handlers.quests import check_location_quests
            from game.quests import on_location_enter
            from data.locations import find_location

            await check_location_quests(bot, player)

            loc = find_location(player.x, player.y)
            if loc and loc.get("quest_enabled", False):
                await on_location_enter(player, loc.get("id"))

            from game.bosses import get_boss_at, send_boss_encounter_alert, resolve_battle
            import json as json_module
            import time
            state_ctx = {}
            try:
                if player.state_context:
                    state_ctx = json_module.loads(player.state_context) if isinstance(player.state_context, str) else player.state_context
            except:
                state_ctx = {}

            boss, zone_type = await get_boss_at(player.x, player.y)
            if boss and zone_type:
                last_boss_id = state_ctx.get("last_boss_id")
                last_boss_x = state_ctx.get("last_boss_x", 0)
                last_boss_y = state_ctx.get("last_boss_y", 0)
                boss_respawn = getattr(boss, 'respawn_available', 0) or 0
                now = int(time.time())

                # Проверяем: новый босс ИЛИ игрок вернулся после ухода
                distance_from_cached = abs(player.x - last_boss_x) + abs(player.y - last_boss_y)
                should_trigger = (
                    last_boss_id != boss.boss_id or  # Новый босс
                    distance_from_cached > 150  # Вернулся после ухода далеко
                )

                if should_trigger:
                    lang = player.lang or "ru"
                    await send_boss_encounter_alert(bot, player, boss, zone_type, lang)
                    if zone_type == "auto":
                        await resolve_battle(bot, player, boss, forced=True, lang=lang)

                    # Сохраняем ID и позицию босса
                    state_ctx["last_boss_id"] = boss.boss_id
                    state_ctx["last_boss_x"] = boss.x
                    state_ctx["last_boss_y"] = boss.y
                    state_ctx["boss_respawn_at"] = boss_respawn
                    player.state_context = json_module.dumps(state_ctx)
                    await player.update(_columns=["state_context"])
                elif boss_respawn and boss_respawn > now:
                    pass  # Босс ещё не вернулся

            # СБРОС last_boss_id когда игрок далеко от последнего босса (> 150 пикселей)
            last_boss_id = state_ctx.get("last_boss_id")
            last_boss_x = state_ctx.get("last_boss_x", 0)
            last_boss_y = state_ctx.get("last_boss_y", 0)
            if last_boss_id:
                dist = abs(player.x - last_boss_x) + abs(player.y - last_boss_y)
                if dist > 150:
                    state_ctx.pop("last_boss_id", None)
                    state_ctx.pop("last_boss_x", None)
                    state_ctx.pop("last_boss_y", None)
                    state_ctx.pop("boss_respawn_at", None)
                    player.state_context = json_module.dumps(state_ctx)
                    await player.update(_columns=["state_context"])

        if player.currentxp >= player.nextxp:
            await levelup(bot, player)

        # Эльф: +10% к скорости прокачки (начисляем чуть больше XP)
        xp_gain = int(cfg.INTERVAL * 1.1) if player.race == "elf" else cfg.INTERVAL
        player.currentxp += xp_gain
        player.totalxp   += cfg.INTERVAL  # totalxp считает реальное время

    # Случайное событие (вероятностное)
    if random.randint(1, 4 * 86400) / cfg.INTERVAL < len(players):
        await randomevent(bot, random.choice(players))

    # ── Встреча с монстром: каждые MONSTER_INTERVAL сек для ВСЕХ онлайн ──
    if _monster_counter >= cfg.MONSTER_INTERVAL:
        _monster_counter = 0
        if players:
            await encounter_all(bot, players)
            logging.info("Встреча с монстром: %d игроков", len(players))

    # ── Респаун боссов: каждые 4 дня ──────────────────────
    if _boss_respawn_counter >= BOSS_RESPAWN_INTERVAL:
        _boss_respawn_counter = 0
        from game.bosses import check_and_spawn_bosses
        await check_and_spawn_bosses(bot)
        logging.info("Респаун боссов выполнен")

    # ── PVP встреча на карте ──────────────────────
    # Собираем dict {(x,y): [players]} за O(n) вместо N запросов
    if cfg.ENABLE_COMBAT:
        coord_map = {}
        for p in players:
            if p.level >= cfg.MIN_CHALLENGE_LEVEL:
                coord_map.setdefault((p.x, p.y), []).append(p)
        
        # Ищем пару на одной координате
        for (x, y), group in coord_map.items():
            if len(group) >= 2 and random.random() <= 0.25:
                player, opp = group[0], group[1]
                msg_p, msg_o = await challenge_opp(player, opp)
                if msg_p:
                    await send_to_players(bot, msg_p, player_uids=[player.uid])
                if msg_o:
                    await send_to_players(bot, msg_o, player_uids=[opp.uid])
                break

    # Batch update — лимит 100 записей
    BATCH_SIZE = 100
    for i in range(0, len(players), BATCH_SIZE):
        batch = players[i:i + BATCH_SIZE]
        await Player.objects.bulk_update(
            batch,
            columns=["level", "nextxp", "totalxplost", "currentxp", "totalxp",
                     "wins", "loss", "x", "y"],
        )

    # ── Токены за время онлайна ───────────────────
    if _token_counter >= cfg.TOKEN_TIME:
        _token_counter = 0
        for p in players:
            p.tokens += 1
        await Player.objects.bulk_update(players, columns=["tokens"])
        logging.info("Токены выданы %d игрокам", len(players))

    # ── Глобальное событие каждые 5 часов ────────
    if _global_event_counter >= GLOBAL_EVENT_INTERVAL:
        _global_event_counter = 0
        if players:
            await global_event(bot, players)
            logging.info("Глобальное событие для %d игроков", len(players))


async def quest_loop(bot):
    """Тик квестов."""
    from ormar.exceptions import NoMatch
    global _daily_quest_counter
    
    _daily_quest_counter += cfg.INTERVAL
    if _daily_quest_counter >= DAILY_QUEST_INTERVAL:
        _daily_quest_counter = 0
        await generate_daily_quests(bot)
        logging.info("Ежедневные квесты обновлены")
    
    try:
        quest = await Quest.objects.get()
        count = (
            await Player.objects.filter(onquest=True, online=True).count()
            * cfg.INTERVAL
        )
        quest.currentxp += count
        await quest.update(_columns=["currentxp"])

        if quest.currentxp >= quest.endxp:
            from game.quests import endquest
            await endquest(bot, quest, win=True)
        elif quest.deadline < int(datetime.today().timestamp()):
            from game.quests import endquest
            await endquest(bot, quest, win=False)
    except Exception:
        pass


async def generate_daily_quests(bot):
    """Генерация ежедневных квестов для всех игроков (новая система)."""
    from db import PlayerQuest
    from handlers.quests import offer_quest
    from game.quests import can_offer_new_quests, get_quest_slots_available

    players = await Player.objects.all()

    if not players:
        return

    for player in players:
        if not player.online:
            continue

        if not await can_offer_new_quests(player):
            continue

        if await get_quest_slots_available(player) <= 0:
            continue

        await offer_quest(bot, player, quest_type="daily", location=None)


async def global_event(bot, players: list):
    """Глобальное случайное событие — бонус или штраф для всех онлайн."""
    event_type = random.choice(["bonus", "penalty"])
    pct    = random.randint(3, 8)
    factor = (100 - pct) / 100 if event_type == "bonus" else (100 + pct) / 100

    for p in players:
        p.nextxp = max(p.currentxp + 1, int(p.nextxp * factor))
    await Player.objects.bulk_update(players, columns=["nextxp"])

    for p in players:
        lang = p.lang or "ru"
        if event_type == "bonus":
            ev = ("Gods smile on adventurers! *-" + str(pct) + "% to next level time!*") if lang == "en" else ("Боги улыбаются! *-" + str(pct) + "% ко времени до след. уровня!*")
        else:
            ev = ("A dark omen! *+" + str(pct) + "% to next level time.*") if lang == "en" else ("Тёмное предзнаменование! *+" + str(pct) + "% ко времени до след. уровня.*")

        msg = ("⚡ *World Event!*\n\n" + ev) if lang == "en" else ("⚡ *Мировое событие!*\n\n" + ev)
        await send_to_players(bot, msg, player_uids=[p.uid])


async def run_loops(app: Application):
    """Запускает все игровые циклы."""
    bot = app.bot
    while True:
        try:
            await main_loop(bot)
        except Exception as e:
            logging.error("main_loop error: %s", e)
        try:
            await quest_loop(bot)
        except Exception as e:
            logging.error("quest_loop error: %s", e)
        await asyncio.sleep(cfg.INTERVAL)


async def start_loops(app: Application):
    asyncio.create_task(run_loops(app))
