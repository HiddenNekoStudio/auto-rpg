"""
loops.py — игровые циклы

Содержит основной игровой тик (main_loop), квестовый тик (quest_loop),
обработку повышения уровня, глобальные события и управление циклами.
"""
import asyncio
from datetime import datetime
import logging
import random
import os

logger = logging.getLogger(__name__)

from telegram.ext import Application

import config as cfg
from db import Player, Quest
from bot import ctime, send_to_players
from game.events import randomevent
from game.challenge import challenge_opp
from data.locations import get_location_coords
from handlers.quests import get_player_locked_quest
from core.event_bus import (
    emit_idle_enter, emit_idle_exit,
    emit_monster_defeated, emit_gold_changed, emit_global_event
)
from core.redis_cache import PlayerState

_use_redis = os.getenv("USE_REDIS", "false").lower() == "true"
_player_state: PlayerState = None

# Счётчики
_token_counter        = 0
_global_event_counter = 0
_monster_counter      = 0  # для встреч с монстрами каждые 1 час
_daily_quest_counter = 0  # для ежедневных квестов
_boss_respawn_counter = 0  # для респауна боссов каждые 4 дня
_quest_cleanup_counter = 0  # для очистки старых квестов
_online_time_counter = 0  # для инкремента total_online_seconds каждый tick
_pet_counter = 0  # для прокачки питомцев каждые PET_XP_INTERVAL
_clan_boss_spawn_counter = 0  # для спавна клановых боссов каждые CLAN_BOSS_SPAWN_INTERVAL


async def init_player_state():
    """Инициализировать PlayerState если Redis доступен."""
    global _player_state
    if _use_redis:
        try:
            _player_state = await PlayerState.get_instance()
            logging.info("PlayerState initialized with Redis")
        except Exception as e:
            logging.warning(f"PlayerState init failed: {e}")

GLOBAL_EVENT_INTERVAL = 5 * 3600  # 5 часов
DAILY_QUEST_INTERVAL  = 3600  # 1 час
BOSS_RESPAWN_INTERVAL = 3600  # 1 час (проверка респавна боссов)
QUEST_CLEANUP_INTERVAL = 6 * 3600  # каждые 6 часов


async def levelup(bot, player: Player) -> None:
    """Повышение уровня игрока.

    Начисляет +1 уровень, сбрасывает currentxp,
    генерирует предмет-награду и шлёт уведомление.

    Args:
        bot: Экземпляр Telegram Bot.
        player: Игрок, получивший уровень.
    """
    from loot import get_item
    from bot import item_string

    lang = player.lang or "ru"
    player.level    += 1
    player.currentxp = 0
    player.nextxp    = cfg.xp_for_level(player.level)

    item, slot, replaced = await get_item(player)

    if lang == "en":
        footer = (
            f"🎒 {slot} *stronger* — equipped!"
            if replaced else
            f"🎒 {slot} weaker — discarded."
        )
    else:
        footer = (
            f"🎒 {slot} *сильнее* — экипирован!"
            if replaced else
            f"🎒 {slot} слабее — выброшен."
        )

    if lang == "en":
        text = (
            "*LEVEL UP!*\n\n"
            + player.name + " has reached level *" + str(player.level) + "*!\n"
            + "Next level in: *" + ctime(player.nextxp, lang) + "*\n\n"
            + "🎁 *Reward!*\n"
            + item_string(item, lang) + "\n"
            + "_" + footer + "_"
        )
    else:
        text = (
            "*ПОВЫШЕНИЕ УРОВНЯ!*\n\n"
            + player.name + " достиг *" + str(player.level) + "* уровня!\n"
            + "До следующего уровня: *" + ctime(player.nextxp, lang) + "*\n\n"
            + "🎁 *Награда!*\n"
            + item_string(item, lang) + "\n"
            + "_" + footer + "_"
        )

    await send_to_players(bot, text, player_uids=[player.uid])


async def main_loop(bot) -> None:
    """Основной игровой тик — обработка всех активных игроков.

    Каждый тик: оффлайн по таймауту, движение игроков,
    встречи с боссами, проверка levelup, начисление XP,
    idle XP для офлайн-игроков, случайные события,
    PvP на карте, токены за онлайн, глобальные события.

    Args:
        bot: Экземпляр Telegram Bot.
    """
    global _token_counter, _global_event_counter, _monster_counter, _boss_respawn_counter, _quest_cleanup_counter, _online_time_counter
    tick_number = _monster_counter  # используется passive-скиллами
    _token_counter        += cfg.INTERVAL
    _global_event_counter += cfg.INTERVAL
    _monster_counter      += cfg.INTERVAL
    _boss_respawn_counter += cfg.INTERVAL
    _quest_cleanup_counter += cfg.INTERVAL
    _online_time_counter  += cfg.INTERVAL

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
            p.total_offline_seconds = (p.total_offline_seconds or 0) + max(0, now - (p.last_online_at or now))
            p.last_online_at = 0
            p.last_idle_at = now
            p.online = False
            p.idle_since = now
            p.idle_xp = 0
            await p.update(_columns=["online", "idle_since", "idle_xp",
                                      "last_online_at", "last_idle_at",
                                      "total_offline_seconds"])
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

    # ── Plugin game tick ─────────────────────────
    # Вызываем ДО проверки игроков, чтобы работал даже без активных игроков
    from plugins.registry import PluginRegistry
    await PluginRegistry.trigger_game_tick(tick_number, bot)

    from health import track_tick
    track_tick(0)

    # ── Idle Mode: начисление XP офлайн-игрокам ───────────────────
    # Выполняется ДО проверки онлайн-игроков — чтобы работало даже когда все офлайн
    idle_players = await Player.objects.filter(
        online=False,
        idle_since__gt=0
    ).all()

    if idle_players:
        FULL_DAY = 86400
        track_tick(len(idle_players))

        for p in idle_players:
            elapsed = now - p.idle_since
            rate = cfg.IDLE_XP_RATE_EXTENDED if elapsed > FULL_DAY else cfg.IDLE_XP_RATE
            idle_gain = max(1, int(cfg.INTERVAL * rate))

            from game.races import get_race_xp_mult
            idle_gain = int(idle_gain * get_race_xp_mult(p.race))

            from plugins.vip_shop import has_prestige_xp_bonus, get_prestige_xp_multiplier
            if has_prestige_xp_bonus(p):
                idle_gain = int(idle_gain * get_prestige_xp_multiplier(p))

            p.hp = min(p.max_hp, p.hp + max(1, int(p.max_hp * cfg.HP_REGEN_IDLE_PCT)))
            p.mp = min(p.max_mp, p.mp + max(1, int(p.max_mp * cfg.MP_REGEN_IDLE_PCT)))

            if (tick_number // cfg.INTERVAL) % (cfg.STREAK_DECAY_INTERVAL // cfg.INTERVAL) == 0:
                streak = p.fight_streak or 0
                if streak > 0:
                    p.fight_streak = streak - 1

            p.idle_xp += idle_gain
            p.total_idle_seconds += cfg.INTERVAL

            if _use_redis and _player_state and _player_state._client:
                try:
                    await _player_state.set_idle_state(p.uid, p.idle_since, p.idle_xp)
                    await p.update(_columns=["idle_xp", "hp", "mp", "fight_streak", "total_idle_seconds"])
                except Exception:
                    logging.warning("Redis idle save failed, falling back to PG: uid=%s", p.uid)
                    await p.update(_columns=["idle_xp", "hp", "mp", "fight_streak", "total_idle_seconds"])
            else:
                await p.update(_columns=["idle_xp", "hp", "mp", "fight_streak", "total_idle_seconds"])
            logging.info("Idle XP сохранён: uid=%s elapsed=%s xp=%s",
                p.uid, elapsed, p.idle_xp)

    # ── Основной список онлайн-игроков ────────────
    players = await Player.get_active_players()
    if not players:
        return

    for player in players:
        locked_quest = await get_player_locked_quest(player)
        passives_changed = False
        old_x, old_y = player.x, player.y

        from plugins.vip_shop import get_speed_multiplier
        boost = get_speed_multiplier(player)
        move_r = round(1 * boost)
        move_big = round(3 * boost)

        if locked_quest:
            target_loc_id = locked_quest.target_location_id
            target_x, target_y = await get_location_coords(target_loc_id)
            
            if target_x is not None:
                move_direction = random.choice(["north", "south", "east", "west"])
                
                if move_direction == "north" and player.y < target_y:
                    player.y = min(player.y + move_r, target_y)
                elif move_direction == "south" and player.y > target_y:
                    player.y = max(player.y - move_r, target_y)
                elif move_direction == "east" and player.x < target_x:
                    player.x = min(player.x + move_r, target_x)
                elif move_direction == "west" and player.x > target_x:
                    player.x = max(player.x - move_r, target_x)
                else:
                    move_roll = random.random()
                    if move_roll < 0.7:
                        player.x = random.randint(player.x - move_r, player.x + move_r) % cfg.MAP_SIZE[0]
                        player.y = random.randint(player.y - move_r, player.y + move_r) % cfg.MAP_SIZE[1]
                    else:
                        player.x = random.randint(player.x - move_big, player.x + move_big) % cfg.MAP_SIZE[0]
                        player.y = random.randint(player.y - move_big, player.y + move_big) % cfg.MAP_SIZE[1]
        else:
            move_roll = random.random()
            if move_roll < 0.7:
                player.x = random.randint(player.x - move_r, player.x + move_r) % cfg.MAP_SIZE[0]
                player.y = random.randint(player.y - move_r, player.y + move_r) % cfg.MAP_SIZE[1]
            else:
                player.x = random.randint(player.x - move_big, player.x + move_big) % cfg.MAP_SIZE[0]
                player.y = random.randint(player.y - move_big, player.y + move_big) % cfg.MAP_SIZE[1]

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
            except (json_module.JSONDecodeError, TypeError, ValueError):
                state_ctx = {}

            boss, zone_type = await get_boss_at(player.x, player.y)
            if boss and zone_type:
                last_boss_id = state_ctx.get("last_boss_id")
                last_boss_x = state_ctx.get("last_boss_x", 0)
                last_boss_y = state_ctx.get("last_boss_y", 0)
                boss_respawn = getattr(boss, 'respawn_available', 0) or 0
                now_ts = int(time.time())

                distance_from_cached = abs(player.x - last_boss_x) + abs(player.y - last_boss_y)
                should_trigger = (
                    last_boss_id != boss.boss_id or
                    distance_from_cached > cfg.BOSS_MIN_DISTANCE
                )

                if should_trigger:
                    lang = player.lang or "ru"
                    alert_sent = await send_boss_encounter_alert(bot, player, boss, zone_type, lang)
                    
                    if alert_sent and zone_type == "auto":
                        await resolve_battle(bot, player, boss, forced=True, lang=lang)

                    # reload state_ctx чтобы подхватить кулдауны сохранённые send_boss_encounter_alert / resolve_battle
                    try:
                        state_ctx = json_module.loads(player.state_context) if isinstance(player.state_context, str) else player.state_context
                    except (json_module.JSONDecodeError, TypeError, ValueError):
                        pass

                    state_ctx["last_boss_id"] = boss.boss_id
                    state_ctx["last_boss_x"] = boss.x
                    state_ctx["last_boss_y"] = boss.y
                    state_ctx["boss_respawn_at"] = boss_respawn
                    player.state_context = json_module.dumps(state_ctx)
                    await player.update(_columns=["state_context"])
                elif boss_respawn and boss_respawn > now:
                    pass

            last_boss_id = state_ctx.get("last_boss_id")
            last_boss_x = state_ctx.get("last_boss_x", 0)
            last_boss_y = state_ctx.get("last_boss_y", 0)
            if last_boss_id:
                dist = abs(player.x - last_boss_x) + abs(player.y - last_boss_y)
                if dist > cfg.BOSS_MIN_DISTANCE:
                    state_ctx.pop("last_boss_id", None)
                    state_ctx.pop("last_boss_x", None)
                    state_ctx.pop("last_boss_y", None)
                    state_ctx.pop("boss_respawn_at", None)
                    player.state_context = json_module.dumps(state_ctx)
                    await player.update(_columns=["state_context"])

        if player.currentxp >= player.nextxp:
            await levelup(bot, player)

        from game.races import get_race_xp_mult
        xp_gain = max(1, int(cfg.INTERVAL * get_race_xp_mult(player.race) + 0.5))
        
        # VIP буст XP
        from plugins.vip_shop import get_xp_multiplier
        xp_mult = get_xp_multiplier(player)
        xp_gain = int(xp_gain * xp_mult)
        
        # Prestige бонус XP
        from plugins.vip_shop import has_prestige_xp_bonus, get_prestige_xp_multiplier
        if has_prestige_xp_bonus(player):
            prestige_mult = get_prestige_xp_multiplier(player)
            xp_gain = int(xp_gain * prestige_mult)
        
        player.currentxp += xp_gain
        player.totalxp += cfg.INTERVAL  # totalxp считает реальное время
        
        # Базовая регенерация HP/MP (каждый тик)
        hp_regen = max(1, int(player.max_hp * cfg.HP_REGEN_PCT))
        player.hp = min(player.max_hp, player.hp + hp_regen)
        mp_regen = max(1, int(player.max_mp * cfg.MP_REGEN_PCT))
        player.mp = min(player.max_mp, player.mp + mp_regen)

        # Пассивки ON_TICK (регенерация итд — применяют хилл внутри)
        from game.skills.passives.registry import PassiveSkillRegistry
        regen_res = await PassiveSkillRegistry.trigger_on_tick(player, tick_number)
        if regen_res.triggered and regen_res.healing > 0:
            passives_changed = True

        # Стамина: уменьшаем fight_streak раз в 5 минут
        if (tick_number // cfg.INTERVAL) % (cfg.STREAK_DECAY_INTERVAL // cfg.INTERVAL) == 0:
            streak = player.fight_streak or 0
            if streak > 0:
                player.fight_streak = streak - 1



    # Случайное событие (вероятностное)
    if random.random() < len(players) * cfg.INTERVAL / (4 * 86400):
        await randomevent(bot, random.choice(players))

    # ── Встреча с монстрами: теперь обрабатывается плагином monster_encounters ──
    # (старый код перенесён в plugins/monsters.py)

    # ── Респаун боссов: каждые 4 дня ──────────────────────
    if _boss_respawn_counter >= BOSS_RESPAWN_INTERVAL:
        _boss_respawn_counter = 0
        from game.bosses import check_and_spawn_bosses, check_boss_despawn
        await check_and_spawn_bosses(bot)
        await check_boss_despawn(bot)
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
    batch_cols = ["level", "nextxp", "totalxplost", "currentxp", "totalxp",
                  "wins", "loss", "x", "y", "hp", "mp", "fight_streak"]
    for i in range(0, len(players), BATCH_SIZE):
        batch = players[i:i + BATCH_SIZE]
        try:
            await Player.objects.bulk_update(batch, columns=batch_cols)
        except Exception as e:
            logging.warning("bulk_update failed (non-fatal): %s", e)

    # ── Токены за время онлайна ───────────────────
    if _token_counter >= cfg.TOKEN_TIME:
        _token_counter = 0
        for p in players:
            p.tokens += 1
        try:
            await Player.objects.bulk_update(players, columns=["tokens"])
            logging.info("Токены выданы %d игрокам", len(players))
        except Exception as e:
            logging.warning("token bulk_update failed (non-fatal): %s", e)

    # ── Аккумуляция total_online_seconds каждый tick ─────
    if _online_time_counter >= cfg.INTERVAL:
        _online_time_counter = 0
        for p in players:
            p.total_online_seconds = (p.total_online_seconds or 0) + cfg.INTERVAL
        try:
            await Player.objects.bulk_update(players, columns=["total_online_seconds"])
        except Exception as e:
            logging.warning("online_time bulk_update failed (non-fatal): %s", e)

    # ── Глобальное событие каждые 5 часов ────────
    if _global_event_counter >= GLOBAL_EVENT_INTERVAL:
        _global_event_counter = 0
        if players:
            await global_event(bot, players)
            logging.info("Глобальное событие для %d игроков", len(players))


async def quest_loop(bot) -> None:
    """Тик квестов — генерация ежедневных квестов и обновление прогресса.

    Каждый тик: проверка интервала для генерации daily-квестов,
    начисление XP активному глобальному квесту, очистка старых квестов.

    Args:
        bot: Экземпляр Telegram Bot.
    """
    from ormar.exceptions import NoMatch
    global _daily_quest_counter, _quest_cleanup_counter
    
    _daily_quest_counter += cfg.INTERVAL
    if _daily_quest_counter >= DAILY_QUEST_INTERVAL:
        _daily_quest_counter = 0
        try:
            await generate_daily_quests(bot)
        except Exception as e:
            # Проверяем по тексту ошибки — ormar может не иметь DatabaseError
            err_msg = str(e).lower()
            if "database" in err_msg or "connection" in err_msg or "sqlite" in err_msg or "postgresql" in err_msg:
                logger.error(f"Daily quest generation failed (DB unavailable): {e}")
                _daily_quest_counter = DAILY_QUEST_INTERVAL - cfg.INTERVAL
            else:
                logger.error(f"Daily quest generation failed: {e}")
    
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
    except NoMatch:
        # Нет активного квеста — нормально
        pass
    except Exception as e:
        err_msg = str(e).lower()
        if "database" in err_msg or "connection" in err_msg or "sqlite" in err_msg or "postgresql" in err_msg:
            logger.error(f"Quest fetch failed (DB unavailable): {e}")
        else:
            logger.warning(f"Quest loop error: {e}")

    # ── Очистка старых квестов ──────────────────────
    if _quest_cleanup_counter >= QUEST_CLEANUP_INTERVAL:
        _quest_cleanup_counter = 0
        try:
            from game.quests import cleanup_expired_offers, cleanup_old_completed_quests
            await cleanup_expired_offers()
            await cleanup_old_completed_quests(days=7)
        except Exception as e:
            logger.warning(f"Quest cleanup error: {e}")


async def generate_daily_quests(bot) -> None:
    """Генерация ежедневных квестов для всех онлайн-игроков.

    Для каждого игрока выбирает доступные типы квестов
    (daily, periodic, collection, trade) с учётом лимита
    активных квестов каждого типа.

    Args:
        bot: Экземпляр Telegram Bot.
    """
    import random
    from db import PlayerQuest
    from handlers.quests import offer_quest
    from game.quests import can_offer_new_quests, get_quest_slots_available
    from data.quest_config import QUEST_TYPE_CONFIG

    players = await Player.get_active_players()

    if not players:
        return

    DAILY_QUEST_TYPES = ["kill", "explore", "xp", "duel", "boss", "rare"]

    for player in players:

        if not await can_offer_new_quests(player):
            continue

        if await get_quest_slots_available(player) <= 0:
            continue

        available_types = []
        for qtype in DAILY_QUEST_TYPES:
            config = QUEST_TYPE_CONFIG.get(qtype)
            if config:
                current_count = await PlayerQuest.objects.filter(
                    player_uid=player.uid,
                    quest_type=qtype,
                    status="active"
                ).count()
                if current_count < config.max_active:
                    available_types.append(qtype)

        if not available_types:
            continue

        quest_type = random.choice(available_types)
        await offer_quest(bot, player, quest_type=quest_type, location=None)


async def global_event(bot, players: list) -> None:
    """Глобальное случайное событие — бонус или штраф для всех онлайн.

    Выбирает случайный тип (bonus/penalty) и применяет
    процентную прибавку/скидку к nextxp всех активных игроков.

    Args:
        bot: Экземпляр Telegram Bot.
        players: Список активных игроков.
    """
    event_type = random.choice(["bonus", "penalty"])
    pct    = random.randint(3, 8)
    factor = (100 - pct) / 100 if event_type == "bonus" else (100 + pct) / 100

    for p in players:
        p.nextxp = max(p.currentxp + 1, int(p.nextxp * factor))
    await Player.objects.bulk_update(players, columns=["nextxp"])

    event_messages = []
    for p in players:
        lang = p.lang or "ru"
        if event_type == "bonus":
            ev = ("Gods smile on adventurers! *-" + str(pct) + "% to next level time!*") if lang == "en" else ("Боги улыбаются! *-" + str(pct) + "% ко времени до след. уровня!*")
        else:
            ev = ("A dark omen! *+" + str(pct) + "% to next level time.*") if lang == "en" else ("Тёмное предзнаменование! *+" + str(pct) + "% ко времени до след. уровня.*")

        msg = ("⚡ *World Event!*\n\n" + ev) if lang == "en" else ("⚡ *Мировое событие!*\n\n" + ev)
        event_messages.append((p.uid, msg))

    await emit_global_event(event_type, "global", [p.uid for p in players])

    for uid, msg in event_messages:
        await send_to_players(bot, msg, player_uids=[uid])


async def hunting_loop(bot) -> None:
    """Тик охоты — симуляция боёв для активных охотников."""
    hunters = await Player.objects.filter(
        online=True, hunting_expires_at__gt=0
    ).all()
    if not hunters:
        return
    from game.hunting import process_hunting_tick
    for p in hunters:
        try:
            await process_hunting_tick(bot, p)
        except Exception as e:
            logging.error(f"Hunting tick error uid={p.uid}: {e}")


async def pet_loop(bot) -> None:
    """Тик питомцев — прокачка XP и обновление бонусов активных игроков."""
    global _pet_counter
    _pet_counter += cfg.INTERVAL
    if _pet_counter < cfg.PET_XP_INTERVAL:
        return
    _pet_counter = 0
    from game.pets import refresh_cache, add_pet_xp
    players = await Player.objects.filter(online=True).all()
    for p in players:
        try:
            await refresh_cache(p)
            await add_pet_xp(p, cfg.PET_XP_PER_TICK)
        except Exception as e:
            logging.error(f"Pet tick error uid={p.uid}: {e}")


async def clan_boss_loop(bot) -> None:
    """Тик клановых боссов — спавн, авто-вклад урона, победа/деспаун."""
    global _clan_boss_spawn_counter
    from game.clan_bosses import spawn_for_clans, tick
    try:
        await tick(bot)
    except Exception as e:
        logging.error("clan_boss tick error: %s", e, exc_info=True)
    _clan_boss_spawn_counter += cfg.INTERVAL
    if _clan_boss_spawn_counter < cfg.CLAN_BOSS_SPAWN_INTERVAL:
        return
    _clan_boss_spawn_counter = 0
    try:
        spawned = await spawn_for_clans()
        if spawned:
            logging.info("Spawned %d clan bosses", spawned)
    except Exception as e:
        logging.error("clan_boss spawn error: %s", e, exc_info=True)


async def raid_boss_loop(bot) -> None:
    """Тик мирового рейд-босса — спавн, авто-вклад урона, победа/деспаун."""
    from game.raid_boss import tick
    try:
        await tick(bot)
    except Exception as e:
        logging.error("raid_boss tick error: %s", e, exc_info=True)


async def dungeon_loop(bot) -> None:
    """Тик подземелий — авто-бой за комнату для активных забегов."""
    from db import DungeonRun
    runs = await DungeonRun.objects.filter(status="active").all()
    if not runs:
        return
    from game.dungeons import process_dungeon_tick
    for run in runs:
        player = await Player.objects.get_or_none(uid=run.player_uid)
        if not player or not player.online:
            continue
        try:
            await process_dungeon_tick(bot, player, run)
        except Exception as e:
            logging.error(f"Dungeon tick error uid={player.uid}: {e}")


async def arena_loop(bot) -> None:
    """Тик арены — авто-бой за волну для активных забегов."""
    from db import ArenaRun
    runs = await ArenaRun.objects.filter(status="active").all()
    if not runs:
        return
    from game.arena import process_arena_tick
    for run in runs:
        player = await Player.objects.get_or_none(uid=run.player_uid)
        if not player or not player.online:
            continue
        try:
            await process_arena_tick(bot, player, run)
        except Exception as e:
            logging.error(f"Arena tick error uid={player.uid}: {e}")


async def run_loops(app: Application) -> None:
    """Запускает все игровые циклы в бесконечном loop.

    Поочерёдно выполняет main_loop и quest_loop
    с паузой cfg.INTERVAL между итерациями.

    Args:
        app: Экземпляр Application Telegram Bot.
    """
    bot = app.bot
    while True:
        try:
            await main_loop(bot)
        except Exception as e:
            logging.error("main_loop error: %s", e, exc_info=True)
        try:
            await quest_loop(bot)
        except Exception as e:
            logging.error("quest_loop error: %s", e, exc_info=True)
        try:
            await hunting_loop(bot)
        except Exception as e:
            logging.error("hunting_loop error: %s", e, exc_info=True)
        try:
            await pet_loop(bot)
        except Exception as e:
            logging.error("pet_loop error: %s", e, exc_info=True)
        try:
            await clan_boss_loop(bot)
        except Exception as e:
            logging.error("clan_boss_loop error: %s", e, exc_info=True)
        try:
            await raid_boss_loop(bot)
        except Exception as e:
            logging.error("raid_boss_loop error: %s", e, exc_info=True)
        try:
            await dungeon_loop(bot)
        except Exception as e:
            logging.error("dungeon_loop error: %s", e, exc_info=True)
        try:
            await arena_loop(bot)
        except Exception as e:
            logging.error("arena_loop error: %s", e, exc_info=True)
        await asyncio.sleep(cfg.INTERVAL)


async def start_loops(app: Application) -> None:
    """Запускает игровые циклы в фоновой задаче.

    Args:
        app: Экземпляр Application Telegram Bot.
    """
    await init_player_state()
    asyncio.create_task(run_loops(app))
