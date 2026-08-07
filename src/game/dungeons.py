"""
game/dungeons.py — подземелья (авто-бой комнатами)

Игрок выбирает подземелье, забег прогрессирует пока он онлайн:
каждые DUNGEON_INTERVAL секунд бой с монстром текущей комнаты
(переиспользует движок охоты game/hunting). Победа -> следующая
комната, последняя комната — босс. Награды (xp/gold) начисляются
за каждую комнату, токены — за полное прохождение.
"""
import json
import logging
import time
from pathlib import Path

import config as cfg
from db import Player, DungeonRun
from game.hunting import generate_hunt_monster, make_miniboss, auto_resolve_hunt_battle, calc_hunt_reward

logger = logging.getLogger(__name__)

_DUNGEONS_JSON = Path(__file__).resolve().parent.parent / "data" / "dungeons.json"


def load_dungeons() -> dict:
    try:
        data = json.loads(_DUNGEONS_JSON.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.error("dungeons.json load error: %s", e)
        return {}


def get_dungeon(dungeon_id: str) -> dict | None:
    return load_dungeons().get(dungeon_id)


async def get_active_run_async(player_uid: int) -> DungeonRun | None:
    run = await DungeonRun.objects.filter(
        player_uid=player_uid, status="active"
    ).get_or_none()
    return run


async def start_run(player, dungeon_id: str) -> tuple[bool, str]:
    """Начать забег в подземелье. Возвращает (успех, причина/название)."""
    dungeon = get_dungeon(dungeon_id)
    if not dungeon:
        return False, "invalid"
    if await get_active_run_async(player.uid):
        return False, "already"
    if player.level < dungeon["min_level"]:
        return False, "level"

    now = int(time.time())
    data = {
        "dungeon_id": dungeon_id,
        "kills": 0,
        "total_xp": 0,
        "total_gold": 0,
        "monsters": {},
        "tokens": 0,
    }
    await DungeonRun.objects.create(
        player_uid=player.uid, dungeon_id=dungeon_id,
        floor=1, max_floor=dungeon["rooms"], status="active",
        data=json.dumps(data, ensure_ascii=False),
        started_at=now, last_tick_at=now,
    )
    return True, dungeon["name_ru" if player.lang != "en" else "name_en"]


async def _run_data(run: DungeonRun) -> dict:
    raw = run.data
    if isinstance(raw, dict):
        return raw
    try:
        d = json.loads(raw or "{}")
        return d if isinstance(d, dict) else {}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


async def _save(run: DungeonRun, data: dict, extra_cols: list = None) -> None:
    run.data = json.dumps(data, ensure_ascii=False)
    cols = ["data", "floor", "last_tick_at", "status"]
    if extra_cols:
        cols.extend(extra_cols)
    await run.update(_columns=cols)


def _room_monster(player, dungeon: dict, floor: int) -> dict:
    """Монстр комнаты: движок охоты (strong) + масштаб пола и подземелья."""
    growth = 1 + (floor - 1) * cfg.DUNGEON_ROOM_GROWTH
    monster = generate_hunt_monster(player, "strong", wave_bonus=floor - 1)
    monster["max_hp"] = int(monster["max_hp"] * dungeon["hp_mult"] * growth)
    monster["dps"] = int(monster["dps"] * dungeon["dps_mult"] * growth)
    if floor >= dungeon["rooms"]:
        monster = make_miniboss(monster)
        monster["is_dungeon_boss"] = True
    return monster


def _room_reward(player, dungeon: dict, floor: int) -> tuple[int, int]:
    """XP/золото за комнату (последняя — босс, награда выше)."""
    monster = {"name": "Комнатный страж", "name_en": "Room Warden",
               "level": player.level + floor}
    xp, gold = calc_hunt_reward(player, monster, cfg.HUNTING_MODES["strong"])
    mult = dungeon["rooms"] if floor >= dungeon["rooms"] else 1.0
    return int(xp * dungeon["xp_mult"] * mult), int(gold * dungeon["gold_mult"] * mult)


async def process_dungeon_tick(bot, player: Player, run: DungeonRun) -> None:
    """Один бой в подземелье. Вызывается из dungeon_loop."""
    now = int(time.time())
    if now - run.last_tick_at < cfg.DUNGEON_INTERVAL:
        return

    dungeon = get_dungeon(run.dungeon_id)
    if not dungeon:
        run.status = "abandoned"
        await run.update(_columns=["status"])
        return

    data = await _run_data(run)
    player.sync_max_hp_mp()
    if player.hp <= 0:
        player.hp = player.get_max_hp()

    floor = run.floor
    monster = _room_monster(player, dungeon, floor)
    result = await auto_resolve_hunt_battle(player, monster)
    player.hp = max(0, result["hp_left"])
    player.mp = max(0, result["mp_left"])

    if not result["player_won"]:
        run.status = "failed"
        from game.combat import reset_fury
        reset_fury(player.uid, cfg.FURY_RESET_LOSS)
        await _save(run, data, extra_cols=["hp", "mp"])
        await player.update(_columns=["hp", "mp"])
        await _notify(bot, player, "failed", monster, data)
        return

    data["kills"] = data.get("kills", 0) + 1
    lang = player.lang or "ru"
    name_key = monster["name_en"] if lang == "en" else monster["name"]
    monsters = data.setdefault("monsters", {})
    monsters[name_key] = monsters.get(name_key, 0) + 1
    xp, gold = _room_reward(player, dungeon, floor)
    data["total_xp"] = data.get("total_xp", 0) + xp
    data["total_gold"] = data.get("total_gold", 0) + gold

    player.monster_kills = (player.monster_kills or 0) + 1
    player.nextxp = max(player.currentxp + 1, player.nextxp - xp)
    player.gold += gold
    try:
        from game.quests import on_monster_defeated
        await on_monster_defeated(player, name_key)
    except Exception as e:
        logger.debug("Quest progress error (dungeon): %s", e)

    run.last_tick_at = now
    if floor >= dungeon["rooms"]:
        run.status = "won"
        data["tokens"] = cfg.DUNGEON_TOKEN_REWARD
        player.tokens = (player.tokens or 0) + cfg.DUNGEON_TOKEN_REWARD
        await _save(run, data, extra_cols=["hp", "mp"])
        await player.update(_columns=["hp", "mp", "nextxp", "gold", "tokens", "monster_kills"])
        await _notify(bot, player, "won", monster, data)
        return

    run.floor = floor + 1
    await _save(run, data, extra_cols=["hp", "mp"])
    await player.update(_columns=["hp", "mp", "nextxp", "gold", "monster_kills"])
    await _notify(bot, player, "room", monster, data)


async def cancel_run(player) -> dict:
    """Досрочно выйти из подземелья: накопленное остаётся, без токенов."""
    run = await get_active_run_async(player.uid)
    if not run:
        return {}
    data = await _run_data(run)
    run.status = "abandoned"
    await run.update(_columns=["status"])
    return data


async def _notify(bot, player, kind: str, monster: dict, data: dict) -> None:
    lang = player.lang or "ru"
    dungeon = get_dungeon(data.get("dungeon_id", ""))
    name = dungeon["name_en"] if (dungeon and lang == "en") else (dungeon["name_ru"] if dungeon else "")
    mname = monster["name_en"] if lang == "en" else monster["name"]
    if kind == "won":
        text = (f"🏆 <b>Dungeon complete: {name}!</b>\n"
                f"Reward: +{data.get('total_xp', 0)} XP, +{data.get('total_gold', 0)}💰, "
                f"+{data.get('tokens', 0)}🪙") if lang == "en" else (
                f"🏆 <b>Подземелье «{name}» пройдено!</b>\n"
                f"Награда: +{data.get('total_xp', 0)} XP, +{data.get('total_gold', 0)}💰, "
                f"+{data.get('tokens', 0)}🪙")
    elif kind == "failed":
        text = (f"💀 <b>Dungeon run failed!</b>\n{mname} was too strong.") if lang == "en" else (
                f"💀 <b>Забег в подземелье провален!</b>\n{mname} оказался слишком силён.")
    else:
        text = (f"⚔️ <b>{name}</b> — room cleared!\n"
                f"{mname} defeated. +{data.get('total_xp', 0)} XP, +{data.get('total_gold', 0)}💰") if lang == "en" else (
                f"⚔️ <b>{name}</b> — комната пройдена!\n"
                f"{mname} повержен. +{data.get('total_xp', 0)} XP, +{data.get('total_gold', 0)}💰")
    try:
        from bot import send_to_players
        await send_to_players(bot, text, player_uids=[player.uid], parse_mode="HTML")
    except Exception as e:
        logger.error("Dungeon notify error: %s", e)
