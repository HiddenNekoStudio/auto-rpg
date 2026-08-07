"""
game/hunting.py — Система охоты

Тихий авто-бой: игрок выбирает режим (weak/strong/epic) и длительность
(1/2/4/5ч). Каждый HUNTING_INTERVAL секунд сервер симулирует бой раундами
по 5с с авто-использованием активных скиллов (тратится MP). Волны: каждые
HUNTING_WAVE_KILLS убийств монстры +1 уровень (макс HUNTING_WAVE_MAX_BONUS).

Охота прогрессирует только пока игрок онлайн. Награды копятся в
hunting_data и выдаются при завершении (× бонус длительности × бонус
выживания). Смерть (strong/epic) — штраф голда + шанс потери предмета.
"""
import json
import logging
import random
import time

import config as cfg
from db import Player
import game.combat as combat

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  Утилиты
# ─────────────────────────────────────────────

def is_hunting(player) -> bool:
    """Игрок сейчас на охоте."""
    return bool(player.hunting_expires_at) and int(player.hunting_expires_at or 0) > int(time.time())


def get_hunt_data(player) -> dict:
    """Распарсить hunting_data игрока в dict."""
    raw = player.hunting_data
    if isinstance(raw, dict):
        return raw
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def hunt_mode_name(mode: str, lang: str = "ru") -> str:
    m = cfg.HUNTING_MODES.get(mode)
    if not m:
        return mode
    return m["name_en"] if lang == "en" else m["name_ru"]


def get_total_player_dps(player) -> int:
    """DPS игрока с учётом классового бонуса."""
    total = player.get_dps()
    try:
        from game.classes import get_class_bonus
        cls_bonus = get_class_bonus(player.job)
        if cls_bonus.get("dps_pct"):
            total = int(total * (1 + cls_bonus["dps_pct"] / 100))
    except Exception:
        pass
    return total


def estimate_hunt_rewards(player, mode: str, duration: int) -> tuple[int, int]:
    """Ожидаемые награды за охоту (для экрана подтверждения)."""
    mode_cfg = cfg.HUNTING_MODES.get(mode, cfg.HUNTING_MODES["weak"])
    interval = cfg.HUNTING_INTERVAL.get(mode, 240)
    fights = max(1, duration // interval)
    dur_bonus = cfg.HUNTING_DURATIONS.get(duration, 1.0)
    base = max(1, player.nextxp - player.currentxp)
    est_xp = int(fights * base * 0.02 * mode_cfg["xp_mult"] * dur_bonus)
    est_gold = int(fights * player.level * 3 * mode_cfg["gold_mult"] * dur_bonus)
    return est_xp, est_gold


# ─────────────────────────────────────────────
#  Генерация монстра
# ─────────────────────────────────────────────

def generate_hunt_monster(player, mode: str, wave_bonus: int = 0) -> dict:
    """Сгенерировать монстра для охоты (статы от DPS игрока — самобаланс)."""
    from core.monsters import monster_list, monster_list_en
    mode_cfg = cfg.HUNTING_MODES[mode]
    player_dps = get_total_player_dps(player)
    level = max(1, player.level + random.randint(*mode_cfg["level_offset"]) + wave_bonus)
    wave_mult = 1 + wave_bonus * cfg.HUNTING_WAVE_MULT
    lifesteal = 0.0
    if random.random() < cfg.HUNTING_LIFESTEAL_CHANCE.get(mode, 0.0):
        lifesteal = random.uniform(0.05, 0.12)
    element = random.choice(list(cfg.ELEMENT_NAMES_RU.keys()))
    return {
        "name": random.choice(monster_list),
        "name_en": random.choice(monster_list_en),
        "level": level,
        "max_hp": max(10, int(player_dps * cfg.HUNTING_MONSTER_HP_FACTOR[mode] * wave_mult)),
        "dps": max(1, int(player_dps * cfg.HUNTING_MONSTER_DPS_FACTOR[mode] * wave_mult)),
        "is_miniboss": False,
        "lifesteal": lifesteal,
        "element": element,
        "type": random.choice(list(cfg.MONSTER_TYPE_ELEMENT.keys())),
    }


def make_miniboss(monster: dict) -> dict:
    """Превратить монстра в мини-босса (эпический финал)."""
    monster["is_miniboss"] = True
    monster["max_hp"] = int(monster["max_hp"] * cfg.HUNTING_MINIBOSS_HP_MULT)
    monster["dps"] = int(monster["dps"] * cfg.HUNTING_MINIBOSS_DPS_MULT)
    return monster


# ─────────────────────────────────────────────
#  Авто-бой
# ─────────────────────────────────────────────

async def _get_skill_level(player, skill_name: str) -> int:
    try:
        from db import PlayerActiveSkill
        rec = await PlayerActiveSkill.objects.filter(
            player_uid=player.uid, skill_id=skill_name
        ).get_or_none()
        return rec.level if rec else 1
    except Exception:
        return 1


def _apply_hunt_skill(player, skill, base_dmg: int, skill_lv: int) -> tuple[int, int]:
    """Применить скилл. Возвращает (урон, лечение)."""
    name = skill.name
    if name == "heal":
        return base_dmg, int(player.get_max_hp() * 0.3)
    if name == "smite":
        return int(base_dmg * 2.0), 0
    if name == "fireball":
        return int(base_dmg * 1.5), 0
    if name == "poison":
        return int(base_dmg * 0.8), 0
    if name == "purifying_light":
        from game.skills.base import PurifyingLightSkill
        pct = PurifyingLightSkill.get_heal_pct(skill_lv)
        return base_dmg, int(player.get_max_hp() * pct)
    if name == "seismic_slam":
        from game.skills.base import SeismicSlamSkill
        return int(base_dmg * SeismicSlamSkill.get_damage_mult(skill_lv)), 0
    if name == "quick_volley":
        from game.skills.base import QuickVolleySkill
        return int(base_dmg * QuickVolleySkill.get_hit_mult(skill_lv) * 3), 0
    return base_dmg, 0


async def _choose_hunt_skill(player, player_hp: int, player_max_hp: int, player_mp: int,
                             skill_cd: dict, round_num: int, skill_levels: dict):
    """Выбрать скилл для раунда: лечение при HP<50%, иначе лучший урон."""
    from game.skills.base import SkillRegistry
    if player_mp <= 0:
        return None

    racial_skills = list(cfg.RACIAL_ACTIVE_SKILLS.values())
    player_racial = cfg.RACIAL_ACTIVE_SKILLS.get(player.race or "")

    heal_skills, dmg_skills = [], []
    for name in SkillRegistry.list_names():
        if name == "attack":
            continue
        skill = SkillRegistry.get(name)
        if not skill:
            continue
        if name in skill_cd and skill_cd[name] > round_num:
            continue
        if name == "smite" and player.align != 1:
            continue
        if name in racial_skills and name != player_racial:
            continue
        if player_mp < skill.mana_cost:
            continue
        if name in ("heal", "purifying_light"):
            heal_skills.append(skill)
        else:
            dmg_skills.append(skill)

    if player_hp < player_max_hp * 0.5 and heal_skills:
        chosen = heal_skills[0]
        if chosen.name not in skill_levels:
            skill_levels[chosen.name] = await _get_skill_level(player, chosen.name)
        return chosen

    if dmg_skills:
        base_dmg = max(1, get_total_player_dps(player) // 2)
        best, best_dmg = None, -1
        for s in dmg_skills:
            if s.name not in skill_levels:
                skill_levels[s.name] = await _get_skill_level(player, s.name)
            est, _ = _apply_hunt_skill(player, s, base_dmg, skill_levels[s.name])
            if est > best_dmg:
                best, best_dmg = s, est
        return best
    return None


async def auto_resolve_hunt_battle(player, monster: dict) -> dict:
    """Симулировать бой раундами по 5с. Не пишет в БД."""
    p_max = get_total_player_dps(player)
    player_hp = max(1, player.hp or 1)
    player_max_hp = player.get_max_hp()
    player_mp = max(0, player.mp or 0)
    player_def = player.defense or 0
    p_def_reduction = min(0.75, player_def / (player_def + 200))
    streak = player.fight_streak or 0
    combo_mult = min(1.0 + streak * cfg.COMBO_STREAK_BONUS_PER_WIN,
                     1.0 + cfg.COMBO_STREAK_MAX_MULT)

    monster_max_hp = monster["max_hp"]
    monster_hp = monster_max_hp
    monster_dps = monster["dps"]

    weapon_element = ""
    weapon_item = getattr(player, "weapon", None)
    if isinstance(weapon_item, dict):
        weapon_element = weapon_item.get("element", "")

    skill_cd = {}
    skill_levels = {}
    rounds = 0
    total_heal = 0
    skills_used = []
    active_dots: dict[str, dict] = {}

    while player_hp > 0 and monster_hp > 0 and rounds < cfg.HUNTING_MAX_ROUNDS:
        rounds += 1
        p_dmg = max(1, p_max // 2)
        p_dmg = int(p_dmg * combo_mult)
        ult_used = combat.get_fury(player.uid) >= 100
        if ult_used:
            p_dmg = int(p_dmg * cfg.FURY_ULT_MULT)
            combat.reset_fury(player.uid)

        w_mult = combat.weakness_mult(weapon_element, monster)
        if w_mult > 1.0:
            p_dmg = int(p_dmg * w_mult)

        max_per_round = max(1, monster_max_hp // 3)
        if p_dmg > max_per_round:
            p_dmg = max_per_round

        skill = await _choose_hunt_skill(player, player_hp, player_max_hp, player_mp,
                                         skill_cd, rounds, skill_levels)
        if skill:
            player_mp -= skill.mana_cost
            p_dmg, heal = _apply_hunt_skill(player, skill, p_dmg, skill_levels.get(skill.name, 1))
            if heal:
                total_heal += heal
                player_hp = min(player_max_hp, player_hp + heal)
            skill_cd[skill.name] = rounds + max(2, skill.cooldown // cfg.HUNTING_ROUND_SECONDS)
            skills_used.append(skill.get_display_name(player.lang or "ru"))

        monster_hp = max(0, monster_hp - p_dmg)
        if not ult_used:
            combat.add_fury(player.uid, cfg.FURY_GAIN_ON_HIT)

        # Burn DoT от огненного оружия
        if weapon_element == "fire" and monster_hp > 0 and "burn" not in active_dots:
            if random.random() < cfg.DOT_BURN_CHANCE:
                active_dots["burn"] = {"ticks": cfg.DOT_BURN_TICKS, "dmg": int(p_dmg * cfg.DOT_BURN_DMG_PCT)}
        if active_dots.get("burn"):
            monster_hp = max(0, monster_hp - active_dots["burn"]["dmg"])
            active_dots["burn"]["ticks"] -= 1
            if active_dots["burn"]["ticks"] <= 0:
                del active_dots["burn"]

        # Боевой призыв пета — шансовый бонусный удар
        if monster_hp > 0:
            try:
                from game.pets import maybe_pet_combat
                pet_dmg, _pet_name = await maybe_pet_combat(player)
                if pet_dmg > 0:
                    monster_hp = max(0, monster_hp - pet_dmg)
                    skills_used.append(f"🐾 {_pet_name}")
            except Exception:
                pass

        if monster_hp <= 0:
            break

        m_dmg = max(1, monster_dps // 2)
        m_dmg = int(m_dmg * (1 - p_def_reduction))
        player_hp = max(0, player_hp - m_dmg)
        if m_dmg > 0:
            combat.add_fury(player.uid, cfg.FURY_GAIN_ON_TAKEN)

        if monster.get("lifesteal", 0) > 0 and m_dmg > 0:
            monster_hp = min(monster_max_hp, monster_hp + int(m_dmg * monster["lifesteal"]))

    player_won = monster_hp <= 0 and player_hp > 0
    return {
        "player_won": player_won,
        "hp_left": player_hp,
        "mp_left": player_mp,
        "rounds": rounds,
        "monster_hp_left": monster_hp,
        "skills_used": skills_used,
    }


# ─────────────────────────────────────────────
#  Награды и штрафы
# ─────────────────────────────────────────────

def calc_hunt_reward(player, monster: dict, mode_cfg: dict, wave_bonus: int = 0) -> tuple[int, int]:
    """Сырая награда за одного монстра (бонусы завершения применяются в finish_hunt)."""
    monster_level = monster["level"]
    alvar = 90 if player.align == 1 else 100
    level_diff = monster_level - player.level
    factor = 1.0 + max(0, level_diff) * 0.15
    xp = int(factor * random.randint(2, 4) / alvar * (player.nextxp - player.currentxp))
    xp = max(1, int(xp * mode_cfg["xp_mult"]))
    gold = int(((monster_level * 5) + random.randint(0, player.level * 2)) * mode_cfg["gold_mult"])
    return xp, gold


async def _roll_hunt_loot(player, monster_level: int, mode_cfg: dict, force: bool = False):
    """Шанс выпадения предмета. Возвращает item dict или None."""
    if not force and random.random() >= mode_cfg.get("loot_chance", 0.0):
        return None
    try:
        from core.loot import generate_item_data, get_random_slot
        slot = get_random_slot()
        item = generate_item_data(slot, max(1, monster_level))
        item["_slot"] = slot
        return item
    except Exception as e:
        logger.error(f"Hunt loot error: {e}")
        return None


async def apply_death_penalty(player, mode_cfg: dict, data: dict) -> dict:
    """Штраф за смерть на охоте. Возвращает детали для отчёта."""
    result = {"gold_lost": 0, "item_slot": None, "update_cols": []}
    pct = mode_cfg.get("death_gold_penalty", 0.0)
    if pct > 0 and player.gold > 0:
        loss = int(player.gold * pct)
        player.gold -= loss
        result["gold_lost"] = loss
        data["gold_lost"] = loss
        result["update_cols"].append("gold")

    chance = mode_cfg.get("death_item_chance", 0.0)
    if chance > 0 and random.random() < chance:
        try:
            from core.loot import generate_item_data
            slot = random.choice(cfg.WEAPON_SLOTS)
            setattr(player, slot, generate_item_data(slot, 1))
            player.sync_max_hp_mp()
            from plugins.monsters import invalidate_dps_cache
            invalidate_dps_cache(player.uid)
            result["item_slot"] = slot
            data["lost_item"] = slot
            result["update_cols"].extend([slot, "max_hp", "max_mp"])
        except Exception as e:
            logger.error(f"Hunt item loss error: {e}")
    return result


# ─────────────────────────────────────────────
#  Старт / тик / финал
# ─────────────────────────────────────────────

async def start_hunt(player, mode: str, duration: int) -> tuple[bool, str]:
    """Начать охоту. Возвращает (успех, причина/режим)."""
    if is_hunting(player):
        return False, "already"
    if mode not in cfg.HUNTING_MODES:
        return False, "invalid"
    if duration not in cfg.HUNTING_DURATIONS:
        return False, "invalid"

    data = {
        "mode": mode,
        "duration": duration,
        "kills": 0,
        "escapes": 0,
        "monsters": {},
        "total_xp": 0,
        "total_gold": 0,
        "loot_items": [],
        "died": False,
        "last_hunt_tick": int(time.time()),
    }
    player.hunting_expires_at = int(time.time()) + duration
    player.hunting_data = json.dumps(data, ensure_ascii=False)
    await player.update(_columns=["hunting_expires_at", "hunting_data"])
    return True, mode


async def _save(player, data: dict, extra_cols: list = None):
    player.hunting_data = json.dumps(data, ensure_ascii=False)
    cols = ["hunting_data"]
    if extra_cols:
        cols.extend(extra_cols)
    await player.update(_columns=cols)


async def process_hunting_tick(bot, player) -> None:
    """Один тик охоты для игрока. Вызывается из hunting_loop."""
    now = int(time.time())
    data = get_hunt_data(player)
    if not data:
        player.hunting_expires_at = 0
        await player.update(_columns=["hunting_expires_at"])
        return

    if player.hunting_expires_at <= now:
        await _finish_and_notify(bot, player)
        return

    mode = data.get("mode", "weak")
    interval = cfg.HUNTING_INTERVAL.get(mode, 240)
    last_tick = data.get("last_hunt_tick", 0)
    if now - last_tick < interval:
        return
    data["last_hunt_tick"] = now

    mode_cfg = cfg.HUNTING_MODES[mode]
    kills = data.get("kills", 0)
    wave_bonus = min(cfg.HUNTING_WAVE_MAX_BONUS, kills // cfg.HUNTING_WAVE_KILLS)

    player.sync_max_hp_mp()
    if player.hp <= 0:
        player.hp = player.get_max_hp()

    # Слабый режим: отступление при низком HP — бой пропускается
    retreat_pct = mode_cfg.get("retreat_hp_pct", 0.0)
    if retreat_pct > 0 and player.hp < player.get_max_hp() * retreat_pct:
        data["escapes"] = data.get("escapes", 0) + 1
        await _save(player, data)
        return

    monster = generate_hunt_monster(player, mode, wave_bonus)
    remaining = player.hunting_expires_at - now
    is_miniboss = False
    if (mode == "epic" and remaining <= interval
            and random.random() < cfg.HUNTING_MINIBOSS_CHANCE):
        monster = make_miniboss(monster)
        is_miniboss = True

    result = await auto_resolve_hunt_battle(player, monster)
    player.hp = max(0, result["hp_left"])
    player.mp = max(0, result["mp_left"])
    update_cols = ["hp", "mp"]

    if result["player_won"]:
        data["kills"] = kills + 1
        lang = player.lang or "ru"
        name_key = monster["name_en"] if lang == "en" else monster["name"]
        monsters = data.setdefault("monsters", {})
        monsters[name_key] = monsters.get(name_key, 0) + 1

        xp, gold = calc_hunt_reward(player, monster, mode_cfg, wave_bonus)
        if is_miniboss:
            xp = int(xp * cfg.HUNTING_MINIBOSS_REWARD_MULT)
            gold = int(gold * cfg.HUNTING_MINIBOSS_REWARD_MULT)
        data["total_xp"] = data.get("total_xp", 0) + xp
        data["total_gold"] = data.get("total_gold", 0) + gold

        item = await _roll_hunt_loot(player, monster["level"], mode_cfg,
                                     force=bool(monster.get("is_miniboss")))
        if item:
            data.setdefault("loot_items", []).append(item)

        player.monster_kills = (player.monster_kills or 0) + 1
        update_cols.append("monster_kills")
        try:
            from game.quests import on_monster_defeated
            await on_monster_defeated(player, name_key)
        except Exception as e:
            logger.debug(f"Quest progress error (hunt): {e}")
        else:
            if mode == "weak":
                data["escapes"] = data.get("escapes", 0) + 1
            else:
                data["died"] = True
                combat.reset_fury(player.uid, cfg.FURY_RESET_LOSS)
                player.monster_deaths = (player.monster_deaths or 0) + 1
            update_cols.append("monster_deaths")
            penalty = await apply_death_penalty(player, mode_cfg, data)
            update_cols.extend(penalty["update_cols"])
            await _save(player, data, extra_cols=update_cols)
            await finish_hunt(bot, player)
            return

    await _save(player, data, extra_cols=update_cols)
    if player.hunting_expires_at <= now:
        await _finish_and_notify(bot, player)


async def _hunt_finish_report(summary: dict, lang: str = "ru") -> str:
    """Собрать текстовый отчёт о завершении охоты."""
    from i18n import t
    if summary.get("died"):
        lines = [t(lang, "hunt_dead")]
    else:
        lines = [t(lang, "hunt_done")]
    lines.append(t(lang, "hunt_report_mode", mode=hunt_mode_name(summary.get("mode", "weak"), lang)))
    lines.append(t(lang, "hunt_report_kills", kills=summary.get("kills", 0)))
    if summary.get("escapes"):
        lines.append(t(lang, "hunt_report_escapes", n=summary["escapes"]))
    if summary.get("xp_granted"):
        lines.append(t(lang, "hunt_report_xp", xp=summary["xp_granted"]))
    if summary.get("gold_granted"):
        lines.append(t(lang, "hunt_report_gold", gold=summary["gold_granted"]))
    if summary.get("loot_items"):
        lines.append(t(lang, "hunt_report_loot", n=len(summary["loot_items"])))
    if summary.get("gold_lost"):
        lines.append(t(lang, "hunt_report_gold_lost", gold=summary["gold_lost"]))
    if summary.get("item_slot"):
        lines.append(t(lang, "hunt_report_item_lost", slot=summary["item_slot"]))
    return "\n".join(lines)


async def _finish_and_notify(bot, player) -> dict:
    """Завершить охоту и уведомить игрока об итогах."""
    summary = await finish_hunt(bot, player)
    try:
        from bot import send_to_players
        lang = player.lang or "ru"
        await send_to_players(bot, await _hunt_finish_report(summary, lang),
                              player_uids=[player.uid], parse_mode="HTML")
    except Exception as e:
        logger.error(f"Hunt finish notify error: {e}")
    return summary


async def _equip_loot(player, item: dict, update_cols: list) -> bool:
    """Попытаться экипировать предмет. Возвращает True если экипирован."""
    slot = item.pop("_slot", "weapon")
    from core.loot import is_item_better
    current = getattr(player, slot, None)
    if not isinstance(current, dict) or is_item_better(item, current):
        setattr(player, slot, item)
        player.sync_max_hp_mp()
        update_cols.extend([slot, "max_hp", "max_mp"])
        from plugins.monsters import invalidate_dps_cache
        invalidate_dps_cache(player.uid)
        return True
    return False


async def finish_hunt(bot, player) -> dict:
    """Завершить охоту: выдать накопленное, применить бонусы, почистить поля.
    Возвращает dict с итогами для отчёта."""
    data = get_hunt_data(player)
    player.hunting_expires_at = 0
    player.hunting_data = "{}"
    update_cols = ["hunting_expires_at", "hunting_data"]

    summary = {
        "mode": data.get("mode", "weak"),
        "kills": data.get("kills", 0),
        "escapes": data.get("escapes", 0),
        "monsters": data.get("monsters", {}),
        "died": data.get("died", False),
        "gold_lost": 0,
        "item_slot": None,
        "xp_granted": 0,
        "gold_granted": 0,
        "loot_equipped": 0,
        "loot_items": list(data.get("loot_items", [])),
    }

    if not data:
        await player.update(_columns=update_cols)
        return summary

    mode_cfg = cfg.HUNTING_MODES.get(summary["mode"], cfg.HUNTING_MODES["weak"])
    duration = data.get("duration", 3600)
    dur_bonus = cfg.HUNTING_DURATIONS.get(duration, 1.0)
    survived = not summary["died"]
    survive_bonus = mode_cfg.get("survive_bonus", 1.0) if survived else 1.0

    total_xp = data.get("total_xp", 0)
    total_gold = data.get("total_gold", 0)
    if survived and total_xp > 0:
        total_xp = int(total_xp * dur_bonus * survive_bonus)
        total_gold = int(total_gold * dur_bonus * survive_bonus)

    if total_xp > 0:
        player.nextxp = max(player.currentxp + 1, player.nextxp - total_xp)
        update_cols.append("nextxp")
        summary["xp_granted"] = total_xp

    if total_gold > 0:
        player.gold += total_gold
        update_cols.append("gold")
        summary["gold_granted"] = total_gold

    summary["gold_lost"] = data.get("gold_lost", 0)
    summary["item_slot"] = data.get("lost_item")

    for item in summary["loot_items"]:
        try:
            if await _equip_loot(player, dict(item), update_cols):
                summary["loot_equipped"] += 1
        except Exception as e:
            logger.error(f"Hunt loot equip error: {e}")

    player.sync_max_hp_mp()
    for c in ("max_hp", "max_mp"):
        if c not in update_cols:
            update_cols.append(c)

    await player.update(_columns=update_cols)
    logger.info(f"Hunt finished uid={player.uid} mode={summary['mode']} "
                f"kills={summary['kills']} survived={survived}")
    return summary


async def cancel_hunt(player) -> dict:
    """Досрочно прервать охоту: выдать сырое накопленное без бонусов."""
    data = get_hunt_data(player)
    summary = {
        "mode": data.get("mode", "weak"),
        "kills": data.get("kills", 0),
        "escapes": data.get("escapes", 0),
        "monsters": data.get("monsters", {}),
        "died": data.get("died", False),
        "gold_lost": 0,
        "item_slot": None,
        "xp_granted": 0,
        "gold_granted": 0,
        "loot_equipped": 0,
        "loot_items": list(data.get("loot_items", [])),
    }
    player.hunting_expires_at = 0
    player.hunting_data = "{}"
    update_cols = ["hunting_expires_at", "hunting_data"]

    if data:
        total_xp = data.get("total_xp", 0)
        total_gold = data.get("total_gold", 0)
        if total_xp > 0:
            player.nextxp = max(player.currentxp + 1, player.nextxp - total_xp)
            update_cols.append("nextxp")
            summary["xp_granted"] = total_xp
        if total_gold > 0:
            player.gold += total_gold
            update_cols.append("gold")
            summary["gold_granted"] = total_gold
        for item in summary["loot_items"]:
            try:
                if await _equip_loot(player, dict(item), update_cols):
                    summary["loot_equipped"] += 1
            except Exception:
                pass
        player.sync_max_hp_mp()
        for c in ("max_hp", "max_mp"):
            if c not in update_cols:
                update_cols.append(c)

    await player.update(_columns=update_cols)
    return summary
