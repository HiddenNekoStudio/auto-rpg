"""
game/bosses.py — система боссов
Встречи с боссами на карте, бои, лут, штрафы
"""
import asyncio
import datetime
import json
import logging
import math
import random
from pathlib import Path
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import config as cfg
from db import Boss, Player, database
from bot import ctime, send_to_players
from core.cache import TTLCache

BOSSES_FILE = Path(__file__).parent.parent / "data" / "bosses.json"

BOSS_RADIUS_AUTO = cfg.BOSS_RADIUS_AUTO
BOSS_RADIUS_CHOICE = cfg.BOSS_RADIUS_CHOICE
BOSS_RESPAWN_DAYS = cfg.BOSS_RESPAWN_DAYS
BOSS_XP_BONUS = cfg.BOSS_XP_BONUS
BOSS_PENALTY_MULT = cfg.BOSS_PENALTY_MULT

BOSS_PLAYER_COOLDOWN = cfg.BOSS_PLAYER_COOLDOWN
BOSS_ENCOUNTER_COOLDOWN = cfg.BOSS_ENCOUNTER_COOLDOWN
BOSS_MIN_DISTANCE = cfg.BOSS_MIN_DISTANCE
BOSS_LEVEL_TOLERANCE = cfg.BOSS_LEVEL_TOLERANCE
BOSS_SHOW_ALL_FOR_VIP = cfg.BOSS_SHOW_ALL_FOR_VIP

DIFFICULTY_MULTIPLIERS = {
    "easy": {"dps": 0.3, "xp_bonus": 1.2, "penalty_mult": 1.0},
    "medium": {"dps": 0.6, "xp_bonus": 1.5, "penalty_mult": 2.0},
    "hard": {"dps": 1.0, "xp_bonus": 2.0, "penalty_mult": 3.0},
    "legendary": {"dps": 1.5, "xp_bonus": 3.0, "penalty_mult": 4.0},
}

DIFFICULTY_NAMES = {
    "easy": {"ru": "Слабый", "en": "Weak"},
    "medium": {"ru": "Обычный", "en": "Normal"},
    "hard": {"ru": "Сильный", "en": "Strong"},
    "legendary": {"ru": "Легендарный", "en": "Legendary"},
}

DIFFICULTY_WEIGHTS = [
    ("easy", 0.30),
    ("medium", 0.40),
    ("hard", 0.25),
    ("legendary", 0.05),
]

BOSS_SCALE_FACTOR = 0.8

BOSS_MIN_BASE_DPS = 100

_loaded_bosses = {}


def _boss_distance(x1: int, y1: int, x2: int, y2: int) -> int:
    """Расстояние Манхэттена между точками."""
    return abs(x1 - x2) + abs(y1 - y2)


def check_player_boss_cooldown(state_ctx: dict, boss_id: str, now: int) -> bool:
    """
    Проверить персональный cooldown для игрока на конкретного босса.
    Возвращает True если алерт можно отправить (нет cooldown).
    """
    cooldowns = state_ctx.get("boss_cooldowns", {})
    
    last_alert = state_ctx.get("last_boss_alert_at", 0)
    if now - last_alert < BOSS_PLAYER_COOLDOWN:
        return False
    
    boss_cd = cooldowns.get(boss_id, 0)
    if now - boss_cd < BOSS_ENCOUNTER_COOLDOWN:
        return False
    
    return True


def set_boss_cooldown(state_ctx: dict, boss_id: str, now: int) -> dict:
    """
    Установить cooldown для босса после боя.
    Возвращает обновлённый state_context.
    """
    if "boss_cooldowns" not in state_ctx:
        state_ctx["boss_cooldowns"] = {}
    
    state_ctx["boss_cooldowns"][boss_id] = now
    state_ctx["last_boss_alert_at"] = now
    
    return state_ctx


def should_show_boss_to_player(player: Player, boss: Boss, now: int, state_ctx: dict) -> bool:
    """
    Проверить, должен ли игрок видеть алерт о боссе.
    Учитывает: cooldown, уровень, расстояние, VIP-статус.
    """
    import logging
    
    if not check_player_boss_cooldown(state_ctx, boss.boss_id, now):
        logging.debug(f"Boss {boss.boss_id}: cooldown active for player {player.uid}")
        return False
    
    if BOSS_SHOW_ALL_FOR_VIP:
        try:
            is_vip = getattr(player, 'vip', False) or getattr(player, 'is_vip', False)
        except Exception:
            is_vip = False
        
        if is_vip:
            return True
    
    level_diff = abs((player.level or 0) - (boss.level or 0))
    if level_diff > BOSS_LEVEL_TOLERANCE:
        logging.debug(f"Boss {boss.boss_id}: level diff {level_diff} > {BOSS_LEVEL_TOLERANCE}")
        return False
    
    return True


def select_difficulty_for_encounter() -> str:
    """Рандомный выбор сложности с весами"""
    import logging
    choices = [d for d, w in DIFFICULTY_WEIGHTS]
    weights = [w for d, w in DIFFICULTY_WEIGHTS]
    result = random.choices(choices, weights)[0]
    logging.debug(f"Boss difficulty selected: {result}")
    return result


BOSS_MAX_DPS_MULT = 2.0

def calculate_adaptive_boss_dps(player_dps: int, base_boss_dps: int, difficulty: str) -> int:
    """Адаптивный DPS босса — подстраивается под игрока"""
    import logging
    mult = DIFFICULTY_MULTIPLIERS.get(difficulty, DIFFICULTY_MULTIPLIERS["medium"])
    max_allowed = int(player_dps * BOSS_MAX_DPS_MULT)
    scaled = int(player_dps * mult["dps"] * BOSS_SCALE_FACTOR)
    
    result = max(base_boss_dps, scaled)
    result = min(result, max_allowed)
    
    logging.debug(f"Boss DPS: player_dps={player_dps}, base={base_boss_dps}, diff={difficulty}, scaled={scaled}, result={result}")
    return result


def get_boss_effective_dps(boss: Boss, player_dps: int = 0) -> int:
    """Получить эффективный DPS босса с учётом сложности"""
    base_dps = get_total_dps_from_equipment(boss.equipment)
    try:
        difficulty = getattr(boss, 'difficulty', None) or "medium"
    except Exception:
        difficulty = "medium"
    if player_dps > 0:
        return calculate_adaptive_boss_dps(player_dps, base_dps, difficulty)
    return base_dps


def get_boss_difficulty(boss: Boss) -> str:
    """Безопасное получение сложности босса"""
    try:
        return getattr(boss, 'difficulty', None) or "medium"
    except Exception:
        return "medium"


def get_boss_legendary_counter(boss: Boss) -> int:
    """Безопасное получение счётчика Legendary"""
    try:
        return getattr(boss, 'legendary_counter', None) or 0
    except Exception:
        return 0


def _load_bosses() -> dict:
    """Загрузить данные боссов из JSON."""
    global _loaded_bosses
    if not _loaded_bosses:
        try:
            data = json.loads(BOSSES_FILE.read_text())
            for b in data.get("bosses", []):
                _loaded_bosses[b["boss_id"]] = b
        except Exception as e:
            logging.error("Failed to load bosses: %s", e)
    return _loaded_bosses


async def init_bosses() -> None:
    """Инициализировать боссов в БД. Автовосстановление при пустой таблице."""
    import logging
    
    existing_count = await Boss.objects.count()
    if existing_count > 0:
        return
    
    boss_data = _load_bosses()
    for boss_id, b in boss_data.items():
        try:
            existing = await Boss.objects.get_or_none(boss_id=boss_id)
            if existing:
                continue
            new_boss = Boss(
                boss_id=boss_id,
                title=b.get("title", ""),
                location_name=b.get("location_name", ""),
                x=b.get("x", 0),
                y=b.get("y", 0),
                level=b.get("level", 1),
                equipment=b.get("equipment", {}),
                defeated=False,
                respawn_cost=b.get("respawn_cost", 50),
                difficulty=b.get("difficulty", "medium"),
                legendary_counter=0,
            )
            await new_boss.save()
        except Exception as create_err:
            logging.warning(f"Failed to create boss {boss_id}: {create_err}")
    logging.info(f"Boss system initialized: {len(boss_data)} bosses")


async def ensure_bosses_available() -> bool:
    """
    Проверить доступность боссов и автовосстановить при необходимости.
    Вызывается перед спавном босса в админке.
    Возвращает True если боссы доступны.
    """
    import logging
    
    try:
        bosses = await Boss.objects.filter(defeated=False).all()
        if bosses:
            return True
        
        logging.info("All bosses defeated, restoring from bosses.json...")
        boss_data = _load_bosses()
        if not boss_data:
            logging.warning("No boss data found in bosses.json")
            return False
        
        from plugins.boss_passives import BossPassiveManager
        
        restored_count = 0
        for boss_id, b in boss_data.items():
            try:
                existing = await Boss.objects.get_or_none(boss_id=boss_id)
                if existing:
                    existing.defeated = False
                    existing.defeated_at = 0
                    existing.defeated_by = 0
                    BossPassiveManager.clear_boss_passives(boss_id)
                    await existing.update(_columns=["defeated", "defeated_at", "defeated_by"])
                else:
                    new_boss = Boss(
                        boss_id=boss_id,
                        title=b.get("title", ""),
                        location_name=b.get("location_name", ""),
                        x=b.get("x", 0),
                        y=b.get("y", 0),
                        level=b.get("level", 1),
                        equipment=b.get("equipment", {}),
                        defeated=False,
                        respawn_cost=b.get("respawn_cost", 50),
                        difficulty=b.get("difficulty", "medium"),
                        legendary_counter=0,
                    )
                    await new_boss.save()
                restored_count += 1
            except Exception as restore_err:
                logging.warning(f"Failed to restore boss {boss_id}: {restore_err}")
        
        logging.info(f"Restored {restored_count} bosses from bosses.json")
        return restored_count > 0
    except Exception as e:
        logging.warning(f"Boss availability check failed: {e}")
        return False


async def get_boss_at(x: int, y: int) -> Optional[tuple]:
    """
    Проверить, находится ли игрок в зоне босса.
    Возвращает (boss, zone_type) где zone_type:
    - "auto" - в радиусе 10px (автобой)
    - "choice" - в радиусе 100px (выбор боя)
    - None - не в зоне
    """
    try:
        bosses = await Boss.objects.filter(defeated=False).all()
    except Exception:
        return None, None
    for boss in bosses:
        dist = _boss_distance(x, y, boss.x, boss.y)
        if dist <= BOSS_RADIUS_AUTO:
            return boss, "auto"
        elif dist <= BOSS_RADIUS_CHOICE:
            return boss, "choice"
    return None, None


def get_total_dps_from_equipment(equipment: dict) -> int:
    """Суммарный DPS из словаря снаряжения."""
    if not equipment:
        return 0
    total = 0
    for slot, item in equipment.items():
        if isinstance(item, dict):
            total += item.get("dps", 0)
    return total


def get_equipment_quality_rank(equipment: dict) -> int:
    """Получить числовой ранг качества снаряжения."""
    if not equipment:
        return 1
    rank_map = {
        "Common": 1,
        "Uncommon": 2,
        "Rare": 3,
        "Epic": 4,
        "Legendary": 5,
        "Ascended": 6,
        "Unique": 7,
    }
    max_rank = 1
    for slot, item in equipment.items():
        if isinstance(item, dict):
            rank = rank_map.get(item.get("rank", "Common"), 1)
            if rank > max_rank:
                max_rank = rank
    return max_rank


def battle_victory_chance(player: Player, boss: Boss) -> float:
    """
    Расчитать шанс победы над боссом.
    Основан на разнице уровней и качестве снаряжения.
    Учитывает сложность босса для адаптивного DPS.
    """
    from game.classes import get_class_bonus
    player_dps = get_total_dps_from_equipment({
        "weapon": player.weapon,
        "shield": player.shield,
        "helmet": player.helmet,
        "chest": player.chest,
        "gloves": player.gloves,
        "boots": player.boots,
        "ring": player.ring,
        "amulet": player.amulet,
    })
    cls_bonus = get_class_bonus(player.job)
    if cls_bonus.get("dps_pct"):
        player_dps = int(player_dps * (1 + cls_bonus["dps_pct"] / 100))
    player_rank = get_equipment_quality_rank({
        "weapon": player.weapon,
        "shield": player.shield,
        "helmet": player.helmet,
        "chest": player.chest,
        "gloves": player.gloves,
        "boots": player.boots,
        "ring": player.ring,
        "amulet": player.amulet,
    })
    
    boss_dps = get_boss_effective_dps(boss, player_dps)
    boss_rank = get_equipment_quality_rank(boss.equipment)
    
    level_diff = (player.level or 0) - (boss.level or 0)
    equipment_bonus = (player_rank - boss_rank) * 0.1
    
    base_chance = 0.5 + (level_diff * 0.1) + equipment_bonus
    
    dps_factor = 0.0
    if player_dps > 0 and boss_dps > 0:
        dps_factor = (player_dps / boss_dps) - 0.5
    
    difficulty = get_boss_difficulty(boss)
    
    chance = base_chance + dps_factor
    
    return max(0.05, min(0.95, chance))


async def send_boss_encounter_alert(bot, player: Player, boss: Boss, zone_type: str, lang: str = "ru") -> bool:
    """
    Отправить уведомление о встрече с боссом.
    Возвращает True если алерт отправлен, False если заблокирован (cooldown/уровень/offline).
    """
    if not getattr(player, 'online', True):
        return False

    import time
    import json as json_module
    
    if lang is None:
        lang = "ru"
    
    now = int(time.time())
    
    state_ctx = {}
    try:
        if player.state_context:
            state_ctx = json_module.loads(player.state_context) if isinstance(player.state_context, str) else player.state_context
    except Exception:
        state_ctx = {}
    
    if not should_show_boss_to_player(player, boss, now, state_ctx):
        return False
    
    if boss.defeated:
        return False
    
    chance = battle_victory_chance(player, boss)
    chance_pct = int(chance * 100)
    
    equipment = boss.equipment
    weapon = equipment.get("weapon", {})
    weapon_name = weapon.get("name_en", weapon.get("name", "Неизвестное оружие"))
    weapon_dps = weapon.get("dps", 0)
    weapon_rank = weapon.get("rank", "Common")
    
    if zone_type == "auto":
        if lang != "en":
            msg = "\n".join([
                "⚠️ <b>ВСТРЕЧА С БОССОМ!</b>",
                "",
                f"<b>{boss.title}</b>",
                f"📍 {boss.location_name} ({boss.x}, {boss.y})",
                f"🎓 Уровень: <b>{boss.level}</b>",
                "",
                f"⚔️ Шанс победы: <b>{chance_pct}%</b>",
                "",
                "🔄 <b>АВТОМАТИЧЕСКИЙ БОЙ!</b>",
            ])
        else:
            msg = "\n".join([
                "⚠️ <b>BOSS ENCOUNTER!</b>",
                "",
                f"<b>{boss.title}</b>",
                f"📍 {boss.location_name} ({boss.x}, {boss.y})",
                f"🎓 Level: <b>{boss.level}</b>",
                "",
                f"⚔️ Victory chance: <b>{chance_pct}%</b>",
                "",
                "🔄 <b>AUTO BATTLE!</b>",
            ])
    else:
        keyboard = [
            [
                InlineKeyboardButton("⚔️ Сразиться" if lang != "en" else "⚔️ Fight", callback_data=f"boss_fight_{boss.boss_id}"),
                InlineKeyboardButton("🚪 Уйти" if lang != "en" else "🚪 Leave", callback_data=f"boss_leave_{boss.boss_id}"),
            ]
        ]
        
        loot_preview = f"🎁 Награда: {weapon_name} ({weapon_dps} DPS, {weapon_rank})"
        if lang == "en":
            loot_preview = f"🎁 Reward: {weapon_name} ({weapon_dps} DPS, {weapon_rank})"
        
        if lang != "en":
            msg = "\n".join([
                "⚠️ <b>ЗОНА БОССА!</b>",
                "",
                f"<b>{boss.title}</b>",
                f"📍 {boss.location_name} ({boss.x}, {boss.y})",
                f"🎓 Уровень: <b>{boss.level}</b>",
                "",
                f"⚔️ Шанс победы: <b>{chance_pct}%</b>",
                "",
                loot_preview,
                "",
                "Выбери действие:",
            ])
        else:
            msg = "\n".join([
                "⚠️ <b>BOSS ZONE!</b>",
                "",
                f"<b>{boss.title}</b>",
                f"📍 {boss.location_name} ({boss.x}, {boss.y})",
                f"🎓 Level: <b>{boss.level}</b>",
                "",
                f"⚔️ Victory chance: <b>{chance_pct}%</b>",
                "",
                loot_preview,
                "",
                "Choose action:",
            ])
        
        try:
            msg_obj = await bot.send_message(
                chat_id=player.uid, text=msg,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception:
            return False

        async def _del_boss_msg():
            await asyncio.sleep(300)
            try:
                await bot.delete_message(chat_id=player.uid, message_id=msg_obj.message_id)
            except Exception:
                pass
        asyncio.create_task(_del_boss_msg())

        state_ctx = set_boss_cooldown(state_ctx, boss.boss_id, now)
        player.state_context = json_module.dumps(state_ctx)
        await player.update(_columns=["state_context"])
        return True
    
    try:
        msg_obj = await bot.send_message(chat_id=player.uid, text=msg, parse_mode="HTML")
    except Exception:
        return False
    
    async def _del_boss_auto_msg():
        await asyncio.sleep(300)
        try:
            await bot.delete_message(chat_id=player.uid, message_id=msg_obj.message_id)
        except Exception:
            pass
    asyncio.create_task(_del_boss_auto_msg())
    
    state_ctx = set_boss_cooldown(state_ctx, boss.boss_id, now)
    player.state_context = json_module.dumps(state_ctx)
    await player.update(_columns=["state_context"])
    return True


def apply_legendary_mechanics(player_dps: int, player_score: int, boss_score: int, lang: str = "ru") -> tuple[int, int, str]:
    """
    Применить особые механики для Legendary босса.
    Возвращает (модифицированный_player_score, модифицированный_boss_score, описание_эффекта)
    """
    effects = []
    modified_player_score = player_score
    modified_boss_score = boss_score
    
    if random.random() < 0.3:
        modified_player_score = int(player_score * 0.5)
        effects.append("🛡️ щит" if lang != "en" else "🛡️ shield")
    
    if random.random() < 0.1:
        modified_boss_score = int(boss_score * 1.5)
        effects.append("⚔️ ярость" if lang != "en" else "⚔️ fury")
    
    effect_str = ""
    if effects:
        effect_str = " " + " ".join(effects)
    
    return modified_player_score, modified_boss_score, effect_str


def _format_battle_rounds(rounds: list, player: Player, boss: Boss, player_hp: int, boss_hp: int, lang: str) -> str:
    """Форматировать раунды боя для вывода."""
    round_lines = []
    for r in rounds:
        p_hp = r.get("player_hp", player_hp)
        p_max = r.get("player_max", player.max_hp)
        b_hp = r.get("boss_hp", boss_hp)
        b_max = r.get("boss_max", boss.max_hp)

        p_filled = min(6, max(0, int(p_hp / max(p_max, 1) * 6)))
        b_filled = min(6, max(0, int(b_hp / max(b_max, 1) * 6)))
        p_bar = "█" * p_filled + "░" * (6 - p_filled)
        b_bar = "█" * b_filled + "░" * (6 - b_filled)

        line = f"  ⚔️ {r.get('player_attack', 0)} → 👹 [{b_bar}] {b_hp}"
        if r.get("legendary_effect"):
            line += f"\n  {r['legendary_effect']}"
        if "passive_on_taken" in r:
            line += f"\n  {r['passive_on_taken']}"
        if "passive_reflect" in r:
            line += f"\n  🔥 Отражено: -{r['passive_reflect']} HP" if lang != "en" else f"\n  🔥 Reflected: -{r['passive_reflect']} HP"
        if "player_crit" in r:
            line += f"\n  ⚡ КРИТ ИГРОКА!" if lang != "en" else "\n  ⚡ PLAYER CRIT!"
        if "player_passive_dealt" in r:
            line += f"\n  {r['player_passive_dealt']}"
        if "player_heal_on_dealt" in r:
            line += f"\n  💚 +{r['player_heal_on_dealt']} HP"
        if "player_poison" in r:
            line += f"\n  ☣️ -{r['player_poison']} HP (яд)" if lang != "en" else f"\n  ☣️ -{r['player_poison']} HP (poison)"
        if "boss_attack" in r:
            line += f"\n  👹 {r['boss_attack']} → 👤 [{p_bar}] {p_hp}"
        if "passive_on_dealt" in r:
            line += f"\n  {r['passive_on_dealt']}"
        if "passive_crit" in r:
            line += f"\n  💥 КРИТ!" if lang != "en" else "\n  💥 CRIT!"
        if "passive_reflect_dealt" in r:
            line += f"\n  🔥 Отражено: -{r['passive_reflect_dealt']} HP" if lang != "en" else f"\n  🔥 Reflected: -{r['passive_reflect_dealt']} HP"
        if "player_passive_taken" in r:
            line += f"\n  {r['player_passive_taken']}"
        if "player_reflect" in r:
            line += f"\n  🌵 Отражено боссу: -{r['player_reflect']} HP" if lang != "en" else f"\n  🌵 Reflected: -{r['player_reflect']} HP"
        if "boss_skill" in r:
            line += f"\n  {r['boss_skill']}"
        round_lines.append(line)

    return "\n".join(round_lines[:15])


async def resolve_battle(bot, player: Player, boss: Boss, forced: bool = False, lang: str = "ru") -> bool:
    """
    Провести бой с боссом.
    Учитывает сложность босса для адаптивного DPS.
    Returns: True если победил, False если проиграл.
    """
    import time
    import config as cfg
    now = int(time.time())

    if lang is None:
        lang = "ru"

    from game.classes import get_class_bonus
    cls_bonus = get_class_bonus(player.job)

    # Инициализация HP/MP игрока
    if not player.hp or player.hp <= 0:
        player.hp = player.get_max_hp()
    player.sync_max_hp_mp()
    if not player.mp or player.mp <= 0:
        player.mp = player.get_max_mp()
    if not player.defense:
        player.defense = 0
    if cls_bonus.get("defense_pct"):
        player.defense = int(player.defense * (1 + cls_bonus["defense_pct"] / 100))
    await player.update(_columns=["hp", "max_hp", "mp", "max_mp", "defense"])

    # Инициализация HP/MP босса
    if not boss.hp or boss.hp <= 0:
        boss.hp = 500 + boss.level * 25
        boss.max_hp = boss.hp
    if not boss.max_hp or boss.max_hp <= 0:
        boss.max_hp = 500 + boss.level * 25
    if not boss.mp or boss.mp <= 0:
        boss.mp = 100 + boss.level * 15
        boss.max_mp = boss.mp
    if not boss.max_mp or boss.max_mp <= 0:
        boss.max_mp = 100 + boss.level * 15
    if not boss.defense or boss.defense <= 0:
        boss.defense = 10 + boss.level * 2
    await boss.update(_columns=["hp", "max_hp", "mp", "max_mp", "defense"])

    player_dps = get_total_dps_from_equipment({
        "weapon": player.weapon,
        "shield": player.shield,
        "helmet": player.helmet,
        "chest": player.chest,
        "gloves": player.gloves,
        "boots": player.boots,
        "ring": player.ring,
        "amulet": player.amulet,
    })
    if cls_bonus.get("dps_pct"):
        player_dps = int(player_dps * (1 + cls_bonus["dps_pct"] / 100))
    from game.pets import pet_dps_mult
    player_dps = int(player_dps * pet_dps_mult(player.uid))

    now_difficulty = get_boss_difficulty(boss)
    if now_difficulty == "medium":
        now_difficulty = select_difficulty_for_encounter()

    boss_dps = get_boss_effective_dps(boss, player_dps)

    from plugins.boss_passives import BossPassiveManager, assign_boss_passives_on_encounter, get_boss_passive_display
    assign_boss_passives_on_encounter(boss.boss_id, boss.level)
    boss_passive_info = await get_boss_passive_display(boss.boss_id, lang)

    from game.skills.passives.registry import PassiveSkillRegistry
    dodge_ok, first_strike_active, encounter_res = await PassiveSkillRegistry.trigger_on_encounter(player)

    # Роуг: +15% уклонения от босса
    rogue_dodge = cls_bonus.get("dodge_pct", 0) > 0 and random.random() < 0.15
    if rogue_dodge:
        dodge_ok = True

    if dodge_ok:
        msg = ""
        if lang != "en":
            msg = "\n".join([
                "👑 <b>БОСС — УКЛОНЕНИЕ!</b>",
                "",
                f"<b>{boss.title}</b>",
                f"📍 {boss.location_name}",
                "👤 <b>Ты уклонился от босса!</b>",
                encounter_res.message or "",
            ])
        else:
            msg = "\n".join([
                "👑 <b>BOSS — DODGE!</b>",
                "",
                f"<b>{boss.title}</b>",
                f"📍 {boss.location_name}",
                "👤 <b>You dodged the boss!</b>",
                encounter_res.message or "",
            ])
        await send_to_players(bot, msg, player_uids=[player.uid], parse_mode="HTML")
        return True

    first_strike_bonus = 0.0
    if first_strike_active:
        first_strike_bonus = encounter_res.damage_bonus

    if now_difficulty == "legendary":
        try:
            boss.legendary_counter = get_boss_legendary_counter(boss) + 1
        except Exception:
            pass

    # Раунды боя
    rounds = []
    round_num = 0
    player_hp = player.hp
    boss_hp = boss.hp
    player_mp = player.mp
    boss_mp = boss.mp
    boss_skill_cooldown = 0
    
    legendary_effect = ""
    if now_difficulty == "legendary":
        player_hp, boss_hp, legendary_effect = apply_legendary_mechanics(
            player_dps, player_hp, boss_hp, lang
        )

    while player_hp > 0 and boss_hp > 0:
        round_num += 1
        round_result = {"num": round_num, "legendary_effect": legendary_effect if round_num == 1 else ""}

        # Атака игрока
        player_dmg = max(1, player_dps // 2)
        if first_strike_bonus > 0 and round_num == 1:
            player_dmg = int(player_dmg * (1.0 + first_strike_bonus))
            round_result["first_strike"] = True

        boss_def_reduction = boss.get_defense_reduction()
        player_dmg = int(player_dmg * (1 - boss_def_reduction))

        # Пассивки босса: on_taken (босс получает урон)
        passive_reflect, passive_reduction, passive_on_taken_msg = (
            await BossPassiveManager.trigger_boss_passive_on_taken(boss.boss_id, player_dmg, lang)
        )
        player_dmg = max(0, int(player_dmg * (1 - min(0.9, passive_reduction))))
        if passive_reflect > 0:
            player_hp = max(0, player_hp - passive_reflect)
            round_result["passive_reflect"] = passive_reflect

        # Пассивки игрока ON_DAMAGE_DEALT (Vampirism, Critical, WindGrace, SlowPoison)
        player_dealt_res = await PassiveSkillRegistry.trigger_on_damage_dealt(
            player, player_dmg, is_crit=False,
            target_hp_pct=boss_hp / boss.max_hp if boss.max_hp > 0 else 1.0,
            target_is_boss=True
        )
        if player_dealt_res.is_crit:
            player_dmg = int(player_dmg * 2.0)
            round_result["player_crit"] = True
        if cls_bonus.get("crit_pct") and random.random() < 0.10:
            player_dmg = int(player_dmg * 2.0)
            round_result["player_crit"] = True
        if player_dealt_res.damage_bonus:
            player_dmg = int(player_dmg * (1.0 + player_dealt_res.damage_bonus))
        if player_dealt_res.message:
            round_result["player_passive_dealt"] = player_dealt_res.message
        if player_dealt_res.healing > 0:
            p_heal = min(player_dealt_res.healing, player.max_hp - player_hp)
            player_hp = min(player.max_hp, player_hp + p_heal)
            round_result["player_heal_on_dealt"] = p_heal
        if player_dealt_res.poison_damage > 0:
            boss_hp = max(0, boss_hp - player_dealt_res.poison_damage)
            round_result["player_poison"] = player_dealt_res.poison_damage

        boss_hp = max(0, boss_hp - player_dmg)

        round_result["player_attack"] = player_dmg
        round_result["boss_hp"] = boss_hp
        round_result["boss_max"] = boss.max_hp
        round_result["player_hp"] = player_hp
        round_result["player_max"] = player.max_hp
        if passive_on_taken_msg:
            round_result["passive_on_taken"] = passive_on_taken_msg

        # Если босс жив - его атака или навык
        if boss_hp > 0:
            skill_used = None
            boss_dmg_val = max(1, boss_dps // 2)

            # Пассивки босса: on_dealt (босс наносит урон)
            passive_bonus, passive_reflect_dealt, passive_on_dealt_msg, passive_crit, passive_healing, passive_poison = (
                await BossPassiveManager.trigger_boss_passive_on_dealt(
                    boss.boss_id, boss_dmg_val, boss_hp / boss.max_hp, lang
                )
            )
            boss_dmg_val = int(boss_dmg_val * (1 + passive_bonus))
            if passive_on_dealt_msg:
                round_result["passive_on_dealt"] = passive_on_dealt_msg
            if passive_crit:
                round_result["passive_crit"] = True
            if passive_reflect_dealt > 0:
                player_hp = max(0, player_hp - passive_reflect_dealt)
                round_result["passive_reflect_dealt"] = passive_reflect_dealt

            if passive_healing > 0:
                boss_hp = min(boss.max_hp, boss_hp + passive_healing)
            if passive_poison > 0:
                player_hp = max(0, player_hp - passive_poison)
                round_result.setdefault("passive_on_dealt", "")
                round_result["passive_on_dealt"] += f" ☣️ -{passive_poison} HP"

            raw_boss_dmg = boss_dmg_val
            skill_extra_mult = 1.0

            # 20% шанс использовать навык
            if boss_skill_cooldown <= 0 and random.random() < cfg.BOSS_SKILL_CHANCE:
                available_skills = []
                for skill_id, skill in cfg.BOSS_SKILLS.items():
                    if boss_mp >= skill["mp_cost"]:
                        available_skills.append((skill_id, skill))

                if available_skills:
                    skill_id, skill = random.choice(available_skills)
                    boss_mp -= skill["mp_cost"]
                    boss_skill_cooldown = cfg.BOSS_SKILL_COOLDOWN

                    if "heal_pct" in skill:
                        heal_amt = int(boss.max_hp * skill["heal_pct"])
                        boss_hp = min(boss.max_hp, boss_hp + heal_amt)
                        skill_used = f"✨ {skill.get('name_ru' if lang != 'en' else 'name_en', skill_id)}: +{heal_amt} HP"
                    elif skill.get("stun"):
                        skill_extra_mult = 0.8
                        skill_used = f"⚡ {skill.get('name_ru' if lang != 'en' else 'name_en', skill_id)}"
                    else:
                        skill_extra_mult = skill["damage_mult"]
                        skill_used = f"🔥 {skill.get('name_ru' if lang != 'en' else 'name_en', skill_id)}"

                    round_result["boss_skill"] = skill_used
            else:
                boss_skill_cooldown -= 1

            # Пассивки игрока ON_DAMAGE_TAKEN (Thorns, ShieldWall, FortuneFavor, StoneFortitude)
            raw_boss_dmg = int(boss_dmg_val * skill_extra_mult)
            player_dmg_taken_res, taken_passive_res = await PassiveSkillRegistry.trigger_on_damage_taken(
                player, raw_boss_dmg, is_from_boss=True
            )
            if taken_passive_res.damage_reflect > 0:
                monster_reflect = min(taken_passive_res.damage_reflect, boss_hp)
                boss_hp = max(0, boss_hp - monster_reflect)
                round_result["player_reflect"] = monster_reflect
            if taken_passive_res.message:
                round_result["player_passive_taken"] = taken_passive_res.message

            # Применяем защиту игрока к модифицированному урону + классовый бонус Паладина
            effective_defense = player.get_defense()
            if cls_bonus.get("defense_pct"):
                effective_defense = int(effective_defense * (1 + cls_bonus["defense_pct"] / 100))
            player_def_reduction = min(0.75, effective_defense / (effective_defense + 200))
            actual_dmg = max(1, int(player_dmg_taken_res * (1 - player_def_reduction)))
            player_hp = max(0, player_hp - actual_dmg)

            round_result["boss_attack"] = actual_dmg
            round_result["player_hp"] = player_hp
            round_result["boss_mp"] = boss_mp
            round_result["player_mp"] = player_mp

        rounds.append(round_result)

        if round_num >= 30:
            break

    player_won = boss_hp <= 0

    # Обновляем HP в базе
    player.hp = player_hp
    boss.hp = boss_hp

    # State context для cooldown
    import json as json_module
    state_ctx = {}
    try:
        if player.state_context:
            state_ctx = json_module.loads(player.state_context) if isinstance(player.state_context, str) else player.state_context
    except Exception:
        state_ctx = {}

    if player_won:
        player.wins += 1
        diff_mult = DIFFICULTY_MULTIPLIERS.get(now_difficulty, DIFFICULTY_MULTIPLIERS["medium"])
        base_val = int((player.nextxp - player.currentxp) / 2 * diff_mult["xp_bonus"])
        mage_mult = 1.0 + cls_bonus.get("xp_pct", 0) / 100
        val = max(1, int(base_val * mage_mult))
        player.nextxp = max(player.currentxp + 1, player.nextxp - val)

        boss.defeated = True
        boss.defeated_at = now
        boss.defeated_by = player.uid
        boss.despawn_at = 0
        await boss.update(_columns=["defeated", "defeated_at", "defeated_by", "despawn_at", "legendary_counter", "hp", "max_hp", "mp", "max_mp", "defense"])

        await player.update(_columns=["hp", "mp"])
        await database.execute(
            "UPDATE users SET nextxp = CASE WHEN nextxp - :xp > currentxp + 1 THEN nextxp - :xp ELSE currentxp + 1 END, "
            "wins = wins + 1 WHERE uid = :uid",
            {"xp": val, "uid": player.uid},
        )

        state_ctx = set_boss_cooldown(state_ctx, boss.boss_id, now)
        player.state_context = json_module.dumps(state_ctx)
        await player.update(_columns=["state_context"])

        bonus_gold, bonus_xp, kill_res = await PassiveSkillRegistry.trigger_on_kill(
            player, boss.level, boss_dps, val
        )
        val += bonus_xp

        if bonus_xp > 0:
            player.nextxp = max(player.currentxp + 1, player.nextxp - bonus_xp)

        # Prestige бонус для XP (включая пассивки)
        from plugins.vip_shop import has_prestige_xp_bonus, get_prestige_xp_multiplier
        additional_xp = 0
        if has_prestige_xp_bonus(player):
            prestige_mult = get_prestige_xp_multiplier(player)
            additional_xp = int(val * (prestige_mult - 1.0))
            if additional_xp > 0:
                player.nextxp = max(player.currentxp + 1, player.nextxp - additional_xp)
                val += additional_xp

        # Base gold reward + passive gold + prestige
        base_gold = max(1, int(boss_dps * diff_mult["xp_bonus"] * 0.3))
        total_gold = base_gold + bonus_gold
        from plugins.vip_shop import has_prestige_gold_bonus, get_prestige_gold_multiplier
        if has_prestige_gold_bonus(player):
            total_gold = int(total_gold * get_prestige_gold_multiplier(player))
        if total_gold > 0:
            player.gold += total_gold

        # ponytail: награды выше (пассивки/престиж/gold) применяются атомарными дельтами
        if bonus_xp > 0:
            await database.execute(
                "UPDATE users SET nextxp = CASE WHEN nextxp - :xp > currentxp + 1 THEN nextxp - :xp ELSE currentxp + 1 END WHERE uid = :uid",
                {"xp": bonus_xp, "uid": player.uid},
            )
        if additional_xp > 0:
            await database.execute(
                "UPDATE users SET nextxp = CASE WHEN nextxp - :xp > currentxp + 1 THEN nextxp - :xp ELSE currentxp + 1 END WHERE uid = :uid",
                {"xp": additional_xp, "uid": player.uid},
            )
        if total_gold > 0:
            await database.execute(
                "UPDATE users SET gold = gold + :g WHERE uid = :uid",
                {"g": total_gold, "uid": player.uid},
            )

        try:
            from game.quests import on_boss_defeated
            await on_boss_defeated(player, boss.boss_id, team_size=1)
        except Exception as e:
            import logging
            logging.error(f"Quest progress check error: {e}")

        # Active skill XP for boss win
        racial_skill = cfg.RACIAL_ACTIVE_SKILLS.get(player.race or "")
        if racial_skill:
            try:
                from plugins.monsters import MonsterEncountersPlugin
                await MonsterEncountersPlugin._add_active_skill_xp(player, racial_skill)
            except Exception as e:
                import logging
                logging.error(f"Active skill XP error: {e}")

        loot_msg = await award_boss_loot(player, boss, lang)

        from game.monsters import invalidate_dps_cache as core_invalidate
        core_invalidate(player.uid)
        from plugins.monsters import invalidate_dps_cache as plugin_invalidate
        plugin_invalidate(player.uid)

        passive_info_line = f"\n\n🎯 <b>{'Boss passives:' if lang == 'en' else 'Пассивки босса:'}</b> {boss_passive_info}" if boss_passive_info else ""

        rounds_str = _format_battle_rounds(rounds, player, boss, player_hp, boss_hp, lang)

        if lang != "en":
            msg = "\n".join([
                "👑 <b>ПОБЕДА НАД БОССОМ!</b>",
                "",
                f"<b>{boss.title}</b> повержен!",
                f"📍 {boss.location_name}",
                "",
                f"📊 HP: {player_hp}/{player.max_hp} | 🛡️ {player.get_defense()}",
                f"⚔️ DPS: {player_dps} | 👹 DPS: {boss_dps}",
                "",
                f"━━━ Раунды ({len(rounds)}) ━━━",
                rounds_str,
                "",
                f"🏆 <b>НАГРАДА:</b>",
            ])
            msg += "\n" + loot_msg
            msg += f"\n💰 Gold: +{total_gold}"
            msg += f"\n\n🎖️ XP-бонус: -{ctime(val, lang)} до уровня {player.level + 1}!"
            msg += passive_info_line
        else:
            msg = "\n".join([
                "👑 <b>BOSS DEFEATED!</b>",
                "",
                f"<b>{boss.title}</b> has been slain!",
                f"📍 {boss.location_name}",
                "",
                f"📊 HP: {player_hp}/{player.max_hp} | 🛡️ {player.get_defense()}",
                f"⚔️ DPS: {player_dps} | 👹 DPS: {boss_dps}",
                "",
                f"━━━ Rounds ({len(rounds)}) ━━━",
                rounds_str,
                "",
                f"🏆 <b>REWARD:</b>",
            ])
            msg += "\n" + loot_msg
            msg += f"\n💰 Gold: +{total_gold}"
            msg += f"\n\n🎖️ XP-bonus: -{ctime(val, 'en')} to level {player.level + 1}!"
            msg += passive_info_line
    else:
        player.loss += 1
        boss.wins = getattr(boss, 'wins', 0) + 1
        diff_mult = DIFFICULTY_MULTIPLIERS.get(now_difficulty, DIFFICULTY_MULTIPLIERS["medium"])
        val = int(random.randint(4, 6) / 90 * (player.nextxp - player.currentxp) * diff_mult["penalty_mult"])
        val = max(60, val)

        from plugins.vip_shop import has_active_protect
        protect_active = has_active_protect(player)
        if not protect_active:
            player.nextxp += val
            player.totalxplost += val
            await database.execute(
                "UPDATE users SET nextxp = nextxp + :val, totalxplost = totalxplost + :val WHERE uid = :uid",
                {"val": val, "uid": player.uid},
            )

        if player.level > 1:
            player.level -= 1

        slot_to_downgrade = random.choice(cfg.WEAPON_SLOTS)
        current_item = getattr(player, slot_to_downgrade, {})
        if isinstance(current_item, dict):
            old_dps = current_item.get("dps", 0)
            new_dps = max(1, old_dps - 4)
            current_item["dps"] = new_dps
            current_item["condition"] = "Затупившийся"
            current_item["quality"] = "Бывалый"
            current_item["condition_en"] = "Blunted"
            current_item["quality_en"] = "Veteran"
            # Переименовываем для всех слотов, не только weapon
            base_name = current_item.get("name", "предмет")
            current_item["name"] = f"Затупившийся {base_name}"
            base_name_en = current_item.get("name_en") or base_name
            current_item["name_en"] = f"Blunted {base_name_en}"
            setattr(player, slot_to_downgrade, current_item)

        player.sync_max_hp_mp()
        await player.update(_columns=["level", "loss",
                          slot_to_downgrade, "hp", "mp", "max_hp", "max_mp"])
        from game.monsters import invalidate_dps_cache as core_invalidate
        core_invalidate(player.uid)
        from plugins.monsters import invalidate_dps_cache as plugin_invalidate
        plugin_invalidate(player.uid)

        boss.respawn_available = now + (BOSS_RESPAWN_DAYS * 86400)
        boss.hp = boss.max_hp
        boss.mp = boss.max_mp
        await boss.update(_columns=["respawn_available", "legendary_counter", "hp", "max_hp", "mp", "max_mp", "defense", "wins"])

        slot_name = slot_to_downgrade.capitalize()
        item_name = current_item.get("name_en", current_item.get("name", "?"))
        passive_info_line = f"\n\n🎯 <b>{'Boss passives:' if lang == 'en' else 'Пассивки босса:'}</b> {boss_passive_info}" if boss_passive_info else ""

        rounds_str = _format_battle_rounds(rounds, player, boss, player_hp, boss_hp, lang)

        if lang != "en":
            penalty_line = (
                "🛡️ <b>ЗАЩИТА!</b> Штраф XP отменён!"
                if protect_active else
                f"⏱️ Штраф: <b>+{ctime(val, lang)}</b>"
            )
            msg = "\n".join([
                "💀 <b>ПОРАЖЕНИЕ ОТ БОССА!</b>",
                "",
                f"<b>{boss.title}</b> оказался сильнее...",
                f"📍 {boss.location_name}",
                "",
                f"📊 HP: {player_hp}/{player.max_hp} | 🛡️ {player.get_defense()}",
                f"⚔️ DPS: {player_dps} | 👹 DPS: {boss_dps}",
                "",
                f"━━━ Раунды ({len(rounds)}) ━━━",
                rounds_str,
                "",
                penalty_line,
                f"📉 Уровень понижен до: <b>{player.level}</b>",
                f"🗡️ {slot_name} ухудшен(а): {item_name}",
                "",
                f"Босс вернётся через {BOSS_RESPAWN_DAYS} дней.",
            ])
            msg += passive_info_line
        else:
            penalty_line = (
                "🛡️ <b>PROTECT!</b> XP penalty cancelled!"
                if protect_active else
                f"⏱️ Penalty: <b>+{ctime(val, 'en')}</b>"
            )
            msg = "\n".join([
                "💀 <b>DEFEATED BY BOSS!</b>",
                "",
                f"<b>{boss.title}</b> was too strong...",
                f"📍 {boss.location_name}",
                "",
                f"📊 HP: {player_hp}/{player.max_hp} | 🛡️ {player.get_defense()}",
                f"⚔️ DPS: {player_dps} | 👹 DPS: {boss_dps}",
                "",
                f"━━━ Rounds ({len(rounds)}) ━━━",
                rounds_str,
                "",
                penalty_line,
                f"📉 Level reduced to: <b>{player.level}</b>",
                f"🗡️ {slot_name} downgraded: {item_name}",
                "",
                f"Boss returns in {BOSS_RESPAWN_DAYS} days.",
            ])
            msg += passive_info_line
        
        state_ctx = set_boss_cooldown(state_ctx, boss.boss_id, now)
        player.state_context = json_module.dumps(state_ctx)
        await player.update(_columns=["state_context"])
    
    await send_to_players(bot, msg, player_uids=[player.uid])
    return player_won


async def award_boss_loot(player: Player, boss: Boss, lang: str = "ru") -> str:
    """Выдать лут с босса."""
    import time
    
    equipment = boss.equipment
    weapon = equipment.get("weapon", {})
    
    player_weapon = player.weapon if isinstance(player.weapon, dict) else {}
    old_dps = player_weapon.get("dps", 0)
    new_dps = weapon.get("dps", 0)
    
    w_name = weapon.get("name_en", weapon.get("name", "?"))

    if player_weapon.get("name") == weapon.get("name"):
        new_dps = old_dps + new_dps // 2
        player_weapon["dps"] = new_dps
        player_weapon["condition"] = "Улучшенный"
        player_weapon["condition_en"] = "Upgraded"
        setattr(player, "weapon", player_weapon)
        player.sync_max_hp_mp()
        await player.update(_columns=["weapon", "max_hp", "max_mp"])
        
        if lang != "en":
            return f"🗡️ Улучшен '{weapon.get('name')}'! DPS: {old_dps} → {new_dps}"
        else:
            return f"🗡️ Upgraded '{w_name}'! DPS: {old_dps} → {new_dps}"
    else:
        import copy
        player.weapon = copy.deepcopy(weapon)
        player.sync_max_hp_mp()
        await player.update(_columns=["weapon", "max_hp", "max_mp"])
        
        rank_emoji = cfg.RARITY_EMOJI.get(weapon.get("rank", "Common"), "⚪")
        
        if lang != "en":
            return f"{rank_emoji} *{weapon.get('name')}*\n   {weapon.get('quality')} {weapon.get('condition')} ({weapon.get('dps')} DPS)"
        else:
            w_quality = weapon.get("quality_en", weapon.get("quality", ""))
            w_condition = weapon.get("condition_en", weapon.get("condition", ""))
            return f"{rank_emoji} *{w_name}*\n   {w_quality} {w_condition} ({weapon.get('dps')} DPS)"


async def respawn_boss(player: Player, boss_id: str, fight_count: int = 1, lang: str = "ru") -> tuple:
    """
    Платный респаун босса для сражения.
    Возвращает (успех, сообщение).
    """
    boss = await Boss.objects.get_or_none(boss_id=boss_id)
    if not boss:
        return False, "Босс не найден" if lang != "en" else "Boss not found"
    
    import time
    now = int(time.time())
    
    if not boss.defeated:
        return False, "Босс уже доступен" if lang != "en" else "Boss is already available"
    
    total_cost = boss.respawn_cost * fight_count
    if player.gold < total_cost:
        return False, f"Нужно {total_cost} золота, у тебя {player.gold}" if lang != "en" else f"Need {total_cost} gold, you have {player.gold}"

    # Атомарное списание: защита от гонок (двойной респаун)
    res = await database.fetch_val(
        "UPDATE users SET gold = gold - :cost WHERE uid = :uid AND gold >= :cost RETURNING 1",
        {"cost": total_cost, "uid": player.uid},
    )
    if not res:
        return False, f"Нужно {total_cost} золота" if lang != "en" else f"Need {total_cost} gold"
    player.gold -= total_cost
    
    player.x = boss.x
    player.y = boss.y
    
    boss.defeated = False
    boss.respawn_available = 0
    boss.hp = 500 + boss.level * 25
    boss.max_hp = boss.hp
    boss.mp = 100 + boss.level * 15
    boss.max_mp = boss.mp
    
    from plugins.boss_passives import BossPassiveManager
    BossPassiveManager.clear_boss_passives(boss.boss_id)
    
    await player.update(_columns=["x", "y"])
    await boss.update(_columns=["defeated", "respawn_available", "hp", "max_hp", "mp", "max_mp"])
    
    if lang != "en":
        return True, f"Телепортирован к {boss.title}! Осталось {player.gold} золота."
    else:
        return True, f"Teleported to {boss.title}! {player.gold} gold left."


async def check_and_spawn_bosses(bot) -> None:
    """Проверить игроков и отправить алерты о боссах."""
    import time
    now = int(time.time())
    respawn_threshold = now
    
    defeated_bosses = await Boss.objects.filter(defeated=True, respawn_available__lte=respawn_threshold, respawn_available__gt=0).all()
    for boss in defeated_bosses:
        boss.defeated = False
        boss.respawn_available = 0
        boss.despawn_at = now + (cfg.BOSS_KILL_WINDOW_HOURS * 3600)
        await boss.update(_columns=["defeated", "respawn_available", "despawn_at"])
        from plugins.boss_passives import BossPassiveManager
        BossPassiveManager.clear_boss_passives(boss.boss_id)
        await notify_boss_respawn(bot, boss)
    
    players = await Player.objects.filter(online=True).all()
    
    for player in players:
        boss_obj, zone_type = await get_boss_at(player.x, player.y)
        
        if boss_obj and zone_type:
            lang = player.lang or "ru"
            await send_boss_encounter_alert(bot, player, boss_obj, zone_type, lang)
        await asyncio.sleep(0.05)


async def notify_boss_respawn(bot, boss: Boss) -> None:
    """Уведомить всех онлайн-игроков о респауне босса и окне убийства."""
    hours = cfg.BOSS_KILL_WINDOW_HOURS
    title = boss.title
    loc = boss.location_name
    msg_ru = (f"⚔️ <b>{title}</b> респаунулся в {loc}!\n"
              f"⏱️ Убей его в течение {hours} ч, пока он не исчез!")
    msg_en = (f"⚔️ <b>{title}</b> respawned at {loc}!\n"
              f"⏱️ Defeat it within {hours} h before it disappears!")
    players = await Player.objects.filter(online=True, optin=True).all()
    ru_uids = [p.uid for p in players if (p.lang or "ru") != "en"]
    en_uids = [p.uid for p in players if (p.lang or "ru") == "en"]
    if ru_uids:
        await send_to_players(bot, msg_ru, player_uids=ru_uids)
    if en_uids:
        await send_to_players(bot, msg_en, player_uids=en_uids)


async def check_boss_despawn(bot) -> None:
    """Деспаун боссов с истёкшим окном убийства — возврат в цикл респауна."""
    import time
    now = int(time.time())
    window_bosses = await Boss.objects.filter(defeated=False, despawn_at__gt=0).all()
    for boss in window_bosses:
        if boss.despawn_at and boss.despawn_at <= now:
            boss.defeated = True
            boss.respawn_available = now + (BOSS_RESPAWN_DAYS * 86400)
            boss.despawn_at = 0
            await boss.update(_columns=["defeated", "respawn_available", "despawn_at"])
            title = boss.title
            loc = boss.location_name
            msg_ru = (f"💨 <b>{title}</b> исчез из {loc}!\n"
                      f"Он не был побеждён вовремя и скрылся. Вернётся через несколько дней — поймай его в следующий раз!")
            msg_en = (f"💨 <b>{title}</b> disappeared from {loc}!\n"
                      f"It was not defeated in time and vanished. It will return in a few days — catch it next time!")
            players = await Player.objects.filter(online=True, optin=True).all()
            ru_uids = [p.uid for p in players if (p.lang or "ru") != "en"]
            en_uids = [p.uid for p in players if (p.lang or "ru") == "en"]
            if ru_uids:
                await send_to_players(bot, msg_ru, player_uids=ru_uids)
            if en_uids:
                await send_to_players(bot, msg_en, player_uids=en_uids)
            logging.info("Босс %s деспаунился (окно убийства истекло)", title)


async def format_boss_list(lang: str = "ru") -> str:
    """Форматировать список боссов из БД."""
    lines = ["🏰 <b>Список боссов:</b>" if lang != "en" else "🏰 <b>Boss list:</b>", ""]
    
    bosses = await Boss.objects.all()
    for i, boss in enumerate(bosses, 1):
        status = "✅" if not boss.defeated else "❌"
        title = boss.title
        loc = boss.location_name
        level = boss.level
        
        lines.append(f"{i}. {status} <b>{title}</b>")
        lines.append(f"   📍 {loc} — 🎓 {level}")
    
    return "\n".join(lines)


async def get_nearby_boss(player: Player) -> Optional[Boss]:
    """Получить ближайшего доступного босса."""
    boss = await Boss.objects.filter(defeated=False).all()
    
    closest = None
    min_dist = 10000
    
    for b in boss:
        dist = _boss_distance(player.x, player.y, b.x, b.y)
        if dist < min_dist:
            min_dist = dist
            closest = b
    
    return closest