"""
game/arena.py — арена волн (бесконечный авто-бой)

Каждые ARENA_INTERVAL секунд бой с монстром текущей волны
(движок охоты, режим strong). Победа -> следующая волна, монстры
сильнее. Каждая N-я волна — мини-босс. Награды xp/gold за волну,
токены за каждую волну. Поражение завершает забег, рекорд
(лучшая волна) сохраняется.
"""
import json
import logging
import time

import config as cfg
from db import Player, ArenaRun
from game.hunting import generate_hunt_monster, make_miniboss, auto_resolve_hunt_battle, calc_hunt_reward

logger = logging.getLogger(__name__)


async def get_active_run_async(player_uid: int) -> ArenaRun | None:
    return await ArenaRun.objects.filter(
        player_uid=player_uid, status="active"
    ).get_or_none()


async def start_run(player) -> tuple[bool, str]:
    """Начать забег на арену. Возвращает (успех, причина)."""
    if await get_active_run_async(player.uid):
        return False, "already"
    if player.level < cfg.ARENA_MIN_LEVEL:
        return False, "level"

    now = int(time.time())
    data = {"kills": 0, "total_xp": 0, "total_gold": 0, "tokens": 0}
    best = await ArenaRun.objects.filter(
        player_uid=player.uid, status__in=["failed", "abandoned"]
    ).order_by("-best_wave").limit(1).get_or_none()
    best_wave = best.best_wave if best else 0
    await ArenaRun.objects.create(
        player_uid=player.uid, wave=1, best_wave=best_wave,
        status="active", data=json.dumps(data, ensure_ascii=False),
        started_at=now, last_tick_at=now,
    )
    return True, str(cfg.ARENA_MIN_LEVEL)


async def _run_data(run: ArenaRun) -> dict:
    raw = run.data
    if isinstance(raw, dict):
        return raw
    try:
        d = json.loads(raw or "{}")
        return d if isinstance(d, dict) else {}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


async def _save(run: ArenaRun, data: dict, extra_cols: list = None) -> None:
    run.data = json.dumps(data, ensure_ascii=False)
    cols = ["data", "wave", "best_wave", "last_tick_at", "status"]
    if extra_cols:
        cols.extend(extra_cols)
    await run.update(_columns=cols)


def _wave_monster(player, wave: int) -> dict:
    """Монстр волны: движок охоты + масштаб волны, мини-босс каждый N-й."""
    growth = 1 + (wave - 1) * cfg.ARENA_WAVE_GROWTH
    monster = generate_hunt_monster(player, "strong", wave_bonus=wave - 1)
    monster["max_hp"] = int(monster["max_hp"] * growth)
    monster["dps"] = int(monster["dps"] * growth)
    if wave % cfg.ARENA_BOSS_EVERY == 0:
        monster = make_miniboss(monster)
        monster["is_arena_boss"] = True
    return monster


def _wave_reward(player, wave: int) -> tuple[int, int]:
    """XP/золото за волну (мини-босс — награда выше)."""
    monster = {"name": "Волна", "name_en": "Wave", "level": player.level + wave}
    mode_cfg = cfg.HUNTING_MODES["strong"]
    xp, gold = calc_hunt_reward(player, monster, mode_cfg)
    mult = 2.0 if wave % cfg.ARENA_BOSS_EVERY == 0 else 1.0
    return int(xp * mult), int(gold * mult)


async def process_arena_tick(bot, player: Player, run: ArenaRun) -> None:
    """Один бой на арене. Вызывается из arena_loop."""
    now = int(time.time())
    if now - run.last_tick_at < cfg.ARENA_INTERVAL:
        return

    data = await _run_data(run)
    player.sync_max_hp_mp()
    if player.hp <= 0:
        player.hp = player.get_max_hp()

    wave = run.wave
    monster = _wave_monster(player, wave)
    result = await auto_resolve_hunt_battle(player, monster)
    player.hp = max(0, result["hp_left"])
    player.mp = max(0, result["mp_left"])

    if not result["player_won"]:
        run.status = "failed"
        run.best_wave = max(run.best_wave, wave - 1)
        data["tokens"] = data.get("tokens", 0)
        from game.combat import reset_fury
        reset_fury(player.uid, cfg.FURY_RESET_LOSS)
        await _save(run, data, extra_cols=["hp", "mp"])
        await player.update(_columns=["hp", "mp"])
        await _notify(bot, player, "failed", monster, data)
        return

    data["kills"] = data.get("kills", 0) + 1
    xp, gold = _wave_reward(player, wave)
    data["total_xp"] = data.get("total_xp", 0) + xp
    data["total_gold"] = data.get("total_gold", 0) + gold
    data["tokens"] = data.get("tokens", 0) + cfg.ARENA_TOKEN_PER_WAVE
    data["wave"] = wave

    player.monster_kills = (player.monster_kills or 0) + 1
    player.nextxp = max(player.currentxp + 1, player.nextxp - xp)
    player.gold += gold
    player.tokens = (player.tokens or 0) + cfg.ARENA_TOKEN_PER_WAVE
    try:
        from game.quests import on_monster_defeated
        name_key = monster["name_en"] if (player.lang or "ru") == "en" else monster["name"]
        await on_monster_defeated(player, name_key)
    except Exception as e:
        logger.debug("Quest progress error (arena): %s", e)

    run.last_tick_at = now
    run.wave = wave + 1
    run.best_wave = max(run.best_wave, wave)
    await _save(run, data, extra_cols=["hp", "mp"])
    await player.update(_columns=["hp", "mp", "nextxp", "gold", "tokens", "monster_kills"])
    await _notify(bot, player, "wave", monster, data)


async def cancel_run(player) -> dict:
    """Досрочно выйти с арены: накопленное остаётся."""
    run = await get_active_run_async(player.uid)
    if not run:
        return {}
    data = await _run_data(run)
    run.status = "abandoned"
    run.best_wave = max(run.best_wave, run.wave - 1)
    await run.update(_columns=["status", "best_wave"])
    return data


async def _notify(bot, player, kind: str, monster: dict, data: dict) -> None:
    lang = player.lang or "ru"
    wave = data.get("wave", 0)
    if kind == "failed":
        text = (f"💀 <b>Arena run ended!</b>\nYou fell on wave {wave}. "
                f"Reward: +{data.get('total_xp', 0)} XP, +{data.get('total_gold', 0)}💰, "
                f"+{data.get('tokens', 0)}🪙") if lang == "en" else (
                f"💀 <b>Забег на арене окончен!</b>\nТы пал на волне {wave}. "
                f"Награда: +{data.get('total_xp', 0)} XP, +{data.get('total_gold', 0)}💰, "
                f"+{data.get('tokens', 0)}🪙")
    else:
        mname = monster["name_en"] if lang == "en" else monster["name"]
        boss = " 👹 Boss!" if monster.get("is_arena_boss") else ""
        text = (f"⚔️ <b>Arena — wave {wave} cleared!</b>{boss}\n"
                f"{mname} defeated. +{data.get('total_xp', 0)} XP, +{data.get('total_gold', 0)}💰") if lang == "en" else (
                f"⚔️ <b>Арена — волна {wave} пройдена!</b>{boss}\n"
                f"{mname} повержен. +{data.get('total_xp', 0)} XP, +{data.get('total_gold', 0)}💰")
    try:
        from bot import send_to_players
        await send_to_players(bot, text, player_uids=[player.uid], parse_mode="HTML")
    except Exception as e:
        logger.error("Arena notify error: %s", e)
