"""
game/bosses.py — система боссов
Встречи с боссами на карте, бои, лут, штрафы
"""
import datetime
import json
import math
import random
from pathlib import Path
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import config as cfg
from db import Boss, Player
from bot import ctime, send_to_players
from core.cache import TTLCache

BOSSES_FILE = Path(__file__).parent.parent / "data" / "bosses.json"

BOSS_RADIUS_AUTO = 10
BOSS_RADIUS_CHOICE = 100
BOSS_RESPAWN_DAYS = 1
BOSS_XP_BONUS = 2.0
BOSS_PENALTY_MULT = 3.0

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


def select_difficulty_for_encounter() -> str:
    """Рандомный выбор сложности с весами"""
    import logging
    choices = [d for d, w in DIFFICULTY_WEIGHTS]
    weights = [w for d, w in DIFFICULTY_WEIGHTS]
    result = random.choices(choices, weights)[0]
    logging.info(f"Boss difficulty selected: {result}")
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
            print(f"Failed to load bosses: {e}")
    return _loaded_bosses


def _ensure_boss_columns_sync() -> None:
    """Синхронная миграция таблицы bosses — выполняется один раз при старте."""
    import logging
    from db import engine
    from sqlalchemy import text
    
    try:
        conn = engine.connect()
        try:
            conn.execute(text("SELECT difficulty FROM bosses LIMIT 1"))
        except Exception:
            try:
                conn.execute(text(
                    "ALTER TABLE bosses ADD COLUMN difficulty TEXT DEFAULT 'medium'"
                ))
                conn.execute(text(
                    "ALTER TABLE bosses ADD COLUMN legendary_counter INTEGER DEFAULT 0"
                ))
                conn.commit()
                logging.info("Boss table migrated: columns added")
            except Exception as me:
                logging.warning(f"Boss alter error: {me}")
                conn.rollback()
        finally:
            conn.close()
    except Exception as e:
        logging.warning(f"Boss sync migration error: {e}")


async def init_bosses() -> None:
    """Инициализировать боссов в БД. Автовосстановление при пустой таблице."""
    import logging
    from sqlalchemy import text
    from db import engine
    
    conn = engine.connect()
    try:
        conn.execute(text("SELECT boss_id FROM bosses LIMIT 1"))
    except Exception:
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
    finally:
        conn.close()


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
        
        restored_count = 0
        for boss_id, b in boss_data.items():
            try:
                existing = await Boss.objects.get_or_none(boss_id=boss_id)
                if existing:
                    existing.defeated = False
                    existing.defeated_at = 0
                    existing.defeated_by = 0
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
    total = 0
    for slot, item in equipment.items():
        if isinstance(item, dict):
            total += item.get("dps", 0)
    return total


def get_equipment_total_level(equipment: dict) -> int:
    """Средний уровень снаряжения (approximate)."""
    if not equipment:
        return 1
    levels = []
    for slot, item in equipment.items():
        if isinstance(item, dict):
            dps = item.get("dps", 0)
            if dps >= 200:
                levels.append(60)
            elif dps >= 150:
                levels.append(45)
            elif dps >= 100:
                levels.append(30)
            elif dps >= 50:
                levels.append(20)
            else:
                levels.append(10)
    return sum(levels) // max(1, len(levels))


def get_equipment_quality_rank(equipment: dict) -> int:
    """Получить числовой ранг качества снаряжения."""
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
    
    level_diff = player.level - boss.level
    equipment_bonus = (player_rank - boss_rank) * 0.1
    
    base_chance = 0.5 + (level_diff * 0.1) + equipment_bonus
    
    dps_factor = 0.0
    if player_dps > 0 and boss_dps > 0:
        dps_factor = (player_dps / boss_dps) - 0.5
    
    difficulty = get_boss_difficulty(boss)
    
    chance = base_chance + dps_factor
    
    return max(0.05, min(0.95, chance))


async def send_boss_encounter_alert(bot, player: Player, boss: Boss, zone_type: str, lang: str = "ru") -> None:
    """Отправить уведомление о встрече с боссом."""
    if lang is None:
        lang = "ru"
    
    chance = battle_victory_chance(player, boss)
    chance_pct = int(chance * 100)
    
    equipment = boss.equipment
    weapon = equipment.get("weapon", {})
    weapon_name = weapon.get("name", "Неизвестное оружие")
    weapon_dps = weapon.get("dps", 0)
    weapon_rank = weapon.get("rank", "Common")
    
    if zone_type == "auto":
        if lang != "en":
            msg = "\n".join([
                "⚠️ *ВСТРЕЧА С БОССОМ!*",
                "",
                f"*{boss.title}*",
                f"📍 {boss.location_name} ({boss.x}, {boss.y})",
                f"🎓 Уровень: *{boss.level}*",
                "",
                f"⚔️ Шанс победы: *{chance_pct}%*",
                "",
                "🔄 *АВТОМАТИЧЕСКИЙ БОЙ!*",
            ])
        else:
            msg = "\n".join([
                "⚠️ *BOSS ENCOUNTER!*",
                "",
                f"*{boss.title}*",
                f"📍 {boss.location_name} ({boss.x}, {boss.y})",
                f"🎓 Level: *{boss.level}*",
                "",
                f"⚔️ Victory chance: *{chance_pct}%*",
                "",
                "🔄 *AUTO BATTLE!*",
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
                "⚠️ *ЗОНА БОССА!*",
                "",
                f"*{boss.title}*",
                f"📍 {boss.location_name} ({boss.x}, {boss.y})",
                f"🎓 Уровень: *{boss.level}*",
                "",
                f"⚔️ Шанс победы: *{chance_pct}%*",
                "",
                loot_preview,
                "",
                "Выбери действие:" if lang != "en" else "Choose action:",
            ])
        else:
            msg = "\n".join([
                "⚠️ *BOSS ZONE!*",
                "",
                f"*{boss.title}*",
                f"📍 {boss.location_name} ({boss.x}, {boss.y})",
                f"🎓 Level: *{boss.level}*",
                "",
                f"⚔️ Victory chance: *{chance_pct}%*",
                "",
                loot_preview,
                "",
                "Choose action:",
            ])
        
        await send_to_players(bot, msg, player_uids=[player.uid], reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    await send_to_players(bot, msg, player_uids=[player.uid])


def apply_legendary_mechanics(player_dps: int, player_score: int, boss_score: int, lang: str = "ru") -> tuple[int, int, str]:
    """
    Применить особые механики для Legendary босса.
    Возвращает (модифицированный_player_score, модифицированный_boss_score, описание_эффекта)
    """
    effects = []
    modified_player_score = player_score
    modified_boss_score = boss_score
    
    roll = random.random()
    if roll < 0.3:
        modified_player_score = int(player_score * 0.5)
        effects.append("🛡️ щит" if lang != "en" else "🛡️ shield")
    
    if roll < 0.1:
        modified_boss_score = int(boss_score * 1.5)
        effects.append("⚔️ ярость" if lang != "en" else "⚔️ fury")
    
    effect_str = ""
    if effects:
        effect_str = " " + " ".join(effects)
    
    return modified_player_score, modified_boss_score, effect_str


async def resolve_battle(bot, player: Player, boss: Boss, forced: bool = False, lang: str = "ru") -> bool:
    """
    Провести бой с боссом.
    Учитывает сложность босса для адаптивного DPS.
    Returns: True если победил, False если проиграл.
    """
    import time
    now = int(time.time())
    
    if lang is None:
        lang = "ru"
    
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
    
    now_difficulty = select_difficulty_for_encounter()
    try:
        boss.difficulty = now_difficulty
    except Exception:
        now_difficulty = "medium"
    
    boss_dps = get_boss_effective_dps(boss, player_dps)
    
    if now_difficulty == "legendary":
        try:
            boss.legendary_counter = get_boss_legendary_counter(boss) + 1
        except Exception:
            pass
    
    chance = battle_victory_chance(player, boss)
    win = random.random() < chance
    
    player_score = int(random.randint(1, 1000) * chance)
    boss_score = random.randint(1, 1000)
    
    legend_effect = ""
    if now_difficulty == "legendary":
        player_score, boss_score, legend_effect = apply_legendary_mechanics(player_dps, player_score, boss_score, lang)
    
    if win:
        player.wins += 1
        diff_mult = DIFFICULTY_MULTIPLIERS.get(now_difficulty, DIFFICULTY_MULTIPLIERS["medium"])
        base_val = int((player.nextxp - player.currentxp) / 2 * diff_mult["xp_bonus"])
        val = max(1, base_val)
        player.nextxp = max(player.currentxp + 1, player.nextxp - val)
        
        boss.defeated = True
        boss.defeated_at = now
        boss.defeated_by = player.uid
        await boss.update(_columns=["defeated", "defeated_at", "defeated_by", "wins", "difficulty", "legendary_counter"])
        
        await player.update(_columns=["nextxp", "wins"])
        
        # Проверить квесты на убийство босса
        try:
            from game.quests import on_boss_defeated
            await on_boss_defeated(player, boss.boss_id, team_size=1)
        except Exception as e:
            logging.error(f"Quest progress check error: {e}")
        
        if lang != "en":
            msg = "\n".join([
                "👑 *ПОБЕДА НАД БОССОМ!*",
                "",
                f"*{boss.title}* повержен!",
                f"📍 {boss.location_name}",
                "",
                f"Твой счёт: *{player_score}* vs {boss_score} (босс){legend_effect}",
                f"⚔️ Твой DPS: *{player_dps}* | DPS босса: *{boss_dps}*",
                "",
                f"🏆 *НАГРАДА:*",
            ])
        else:
            msg = "\n".join([
                "👑 *BOSS DEFEATED!*",
                "",
                f"*{boss.title}* has been slain!",
                f"📍 {boss.location_name}",
                "",
                f"Your score: *{player_score}* vs {boss_score} (boss){legend_effect}",
                f"⚔️ Your DPS: *{player_dps}* | Boss DPS: *{boss_dps}*",
                "",
                f"🏆 *REWARD:*",
            ])
        
        loot_item = await award_boss_loot(player, boss, lang)
        msg += "\n" + loot_item
        
        msg += f"\n\n🎖️ XP-бонус: -{ctime(val)} до уровня {player.level + 1}!"
        if lang == "en":
            msg += f"\n\n🎖️ XP-bonus: -{ctime(val)} to level {player.level + 1}!"
        
    else:
        player.loss += 1
        diff_mult = DIFFICULTY_MULTIPLIERS.get(now_difficulty, DIFFICULTY_MULTIPLIERS["medium"])
        val = int(random.randint(4, 6) / 90 * (player.nextxp - player.currentxp) * diff_mult["penalty_mult"])
        val = max(60, val)
        player.nextxp += val
        player.totalxplost += val
        
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
            if slot_to_downgrade == "weapon":
                current_item["name"] = "Затупившийся " + current_item.get("name", "меч")
            setattr(player, slot_to_downgrade, current_item)
        
        await player.update(_columns=["nextxp", "totalxplost", "level", "loss", slot_to_downgrade])
        
        boss.respawn_available = now + (BOSS_RESPAWN_DAYS * 86400)
        await boss.update(_columns=["respawn_available", "difficulty", "legendary_counter"])
        
        slot_name = slot_to_downgrade.capitalize()
        if lang != "en":
            msg = "\n".join([
                "💀 *ПОРАЖЕНИЕ ОТ БОССА!*",
                "",
                f"*{boss.title}* оказался сильнее...",
                f"📍 {boss.location_name}",
                "",
                f"Твой счёт: *{player_score}* vs {boss_score} (босс)",
                f"⚔️ Твой DPS: *{player_dps}* | DPS босса: *{boss_dps}*",
                "",
                f"⏱️ Штраф: *+{ctime(val)}*",
                f"📉 Уровень понижен до: *{player.level}*",
                f"🗡️ {slot_name} ухудшен(а): {current_item.get('name', '?')}",
                "",
                f"Босс вернётся через {BOSS_RESPAWN_DAYS} дней." if lang != "en" else f"Boss returns in {BOSS_RESPAWN_DAYS} days.",
            ])
        else:
            msg = "\n".join([
                "💀 *DEFEATED BY BOSS!*",
                "",
                f"*{boss.title}* was too strong...",
                f"📍 {boss.location_name}",
                "",
                f"Your score: *{player_score}* vs {boss_score} (boss)",
                f"⚔️ Your DPS: *{player_dps}* | Boss DPS: *{boss_dps}*",
                "",
                f"⏱️ Penalty: *+{ctime(val)}*",
                f"📉 Level reduced to: *{player.level}*",
                f"🗡️ {slot_name} downgraded: {current_item.get('name', '?')}",
                "",
                f"Boss returns in {BOSS_RESPAWN_DAYS} days.",
            ])
    
    await send_to_players(bot, msg, player_uids=[player.uid])
    return win


async def award_boss_loot(player: Player, boss: Boss, lang: str = "ru") -> str:
    """Выдать лут с босса."""
    import time
    
    equipment = boss.equipment
    weapon = equipment.get("weapon", {})
    
    player_weapon = player.weapon if isinstance(player.weapon, dict) else {}
    old_dps = player_weapon.get("dps", 0)
    new_dps = weapon.get("dps", 0)
    
    if player_weapon.get("name") == weapon.get("name"):
        new_dps = old_dps + new_dps // 2
        player_weapon["dps"] = new_dps
        player_weapon["condition"] = "Улучшенный"
        setattr(player, "weapon", player_weapon)
        await player.update(_columns=["weapon"])
        
        if lang != "en":
            return f"🗡️ Улучшен '{weapon.get('name')}'! DPS: {old_dps} → {new_dps}"
        else:
            return f"🗡️ Upgraded '{weapon.get('name')}'! DPS: {old_dps} → {new_dps}"
    else:
        player.weapon = weapon
        await player.update(_columns=["weapon"])
        
        rank_emoji = cfg.RARITY_EMOJI.get(weapon.get("rank", "Common"), "⚪")
        
        if lang != "en":
            return f"{rank_emoji} *{weapon.get('name')}*\n   {weapon.get('quality')} {weapon.get('condition')} ({weapon.get('dps')} DPS)"
        else:
            return f"{rank_emoji} *{weapon.get('name')}*\n   {weapon.get('quality')} {weapon.get('condition')} ({weapon.get('dps')} DPS)"


async def respawn_boss(player: Player, boss_id: str, fight_count: int = 1, lang: str = "ru") -> tuple:
    """
    Платный респаун босса для сражения.
    Возвращает (успех, сообщение).
    """
    boss = await Boss.objects.get_or_none(boss_id=boss_id)
    if not boss:
        return False, "Босс не найден" if lang != "en" else "Boss not found"
    
    if not boss.defeated:
        return False, "Босс уже доступен" if lang != "en" else "Boss is already available"
    
    import time
    now = int(time.time())
    if boss.respawn_available > now:
        wait_time = boss.respawn_available - now
        hours = wait_time // 3600
        wait_str = f"{hours}ч" if lang != "en" else f"{hours}h"
        return False, f"Босс недоступен. Подожди {wait_str}" if lang != "en" else f"Boss unavailable. Wait {wait_str}"
    
    total_cost = boss.respawn_cost * fight_count
    if player.gold < total_cost:
        return False, f"Нужно {total_cost} золота, у тебя {player.gold}" if lang != "en" else f"Need {total_cost} gold, you have {player.gold}"
    
    player.gold -= total_cost
    
    player.x = boss.x
    player.y = boss.y
    
    boss.defeated = False
    boss.respawn_available = 0
    
    await player.update(_columns=["gold", "x", "y"])
    await boss.update(_columns=["defeated", "respawn_available"])
    
    if lang != "en":
        return True, f"Телепортирован к {boss.title}! Осталось {player.gold} золота."
    else:
        return True, f"Teleported to {boss.title}! {player.gold} gold left."


async def check_and_spawn_bosses(bot) -> None:
    """Проверить игроков и отправить алерты о боссах."""
    import time
    now = int(time.time())
    respawn_threshold = now - (BOSS_RESPAWN_DAYS * 86400)
    
    defeated_bosses = await Boss.objects.filter(defeated=True, respawn_available__lte=respawn_threshold).all()
    for boss in defeated_bosses:
        boss.defeated = False
        boss.respawn_available = 0
        await boss.update(_columns=["defeated", "respawn_available"])
    
    players = await Player.objects.filter(online=True).all()
    
    for player in players:
        boss_obj, zone_type = await get_boss_at(player.x, player.y)
        
        if boss_obj and zone_type:
            lang = player.lang or "ru"
            await send_boss_encounter_alert(bot, player, boss_obj, zone_type, lang)


def format_boss_list(lang: str = "ru") -> str:
    """Форматировать список боссов."""
    lines = ["🏰 *Список боссов:*" if lang != "en" else "🏰 *Boss list:*", ""]
    
    data = _load_bosses()
    for i, (boss_id, boss) in enumerate(data.items(), 1):
        status = "✅" if not boss.get("defeated", False) else "❌"
        title = boss.get("title", "")
        loc = boss.get("location_name", "")
        level = boss.get("level", 1)
        
        lines.append(f"{i}. {status} *{title}*")
        lines.append(f"   📍 {loc} — 🎓 {level}" if lang != "en" else f"   📍 {loc} — 🎓 {level}")
    
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