"""
plugins/monsters.py — Плагин встреч с монстрами

Features:
- Staggered spawn: monsters appear 1-5 minutes apart
- Loot drops: random item on victory (8% base chance)
- Stamina system: consecutive fights reduce damage
- Party monsters: rare strong monsters with nearby-player bonus
- Regional bonuses: XP/Gold multipliers by location type
"""
import logging
import random
import time
from typing import Any, Optional
from telegram import Bot

import config as cfg
from db import Player
from bot import ctime, item_string
from core.cache import TTLCache
from core.monsters import monster_list, monster_list_en
from plugins.base import GamePlugin, PluginMetadata
from plugins.registry import PluginRegistry

logger = logging.getLogger(__name__)

# Module-level DPS cache for cross-module access (5 min TTL)
_dps_cache: 'TTLCache[int]' = TTLCache(ttl=300, maxsize=10000)

def invalidate_dps_cache(uid: int) -> None:
    _dps_cache.delete(str(uid))

# Активные навыки монстров для раундового боя
MONSTER_COMBAT_SKILLS = [
    {"id": "heavy", "name_ru": "Тяжёлая атака", "name_en": "Heavy Strike",
     "damage_mult": 1.5, "cooldown": 3, "hp_max": 1.0, "icon": "💢"},
    {"id": "monster_heal", "name_ru": "Рёв восстановления", "name_en": "Healing Roar",
     "heal_pct": 0.25, "cooldown": 5, "hp_max": 0.5, "icon": "💚"},
    {"id": "rage", "name_ru": "Ярость", "name_en": "Rage",
     "damage_mult": 2.0, "cooldown": 6, "hp_max": 0.3, "icon": "🔥"},
]

METADATA = PluginMetadata(
    name="monster_encounters",
    version="3.0.0",
    description="Встречи с монстрами — HP/MP бой, лут, стамина, пати, регионы",
    author="AutoRPG",
)

RANK_POWER = {
    "Common": 1.0,
    "Uncommon": 1.3,
    "Rare": 1.7,
    "Epic": 2.2,
    "Legendary": 3.0,
}

RANK_DPS_MULT = {
    "Common": 1.0,
    "Uncommon": 1.2,
    "Rare": 1.5,
    "Epic": 2.0,
    "Legendary": 2.5,
}

RANK_PASSIVES = {
    "Common": ["fireball"],
    "Uncommon": ["fireball", "heal"],
    "Rare": ["fireball", "heal", "dark_burst"],
    "Epic": ["fireball", "heal", "dark_burst", "stun"],
    "Legendary": ["fireball", "heal", "dark_burst", "stun"],
}

RANK_PENALTY = {
    "Common": 1.0,
    "Uncommon": 1.0,
    "Rare": 1.3,
    "Epic": 1.6,
    "Legendary": 2.0,
}


@PluginRegistry.register(
    "monster_encounters",
    description="Встречи с монстрами — сбалансированная боевая система",
    author="AutoRPG"
)
class MonsterEncountersPlugin(GamePlugin):
    """Плагин встреч с монстрами."""

    metadata = METADATA

    def __init__(self):
        self._tick_counter = 0
        self._encounter_cooldown = TTLCache(ttl=2.0, maxsize=10000)
        self._pending_fights: dict[int, list] = {}
        self._next_fight_time: dict[int, int] = {}
        self._next_spawn_time: dict[int, int] = {}

    async def on_load(self) -> None:
        logger.info("MonsterEncounters plugin loaded (v3)")

    async def on_unload(self) -> None:
        logger.info("MonsterEncounters plugin unloaded")

    async def on_game_tick(self, tick_number: int, bot=None) -> Optional[str]:
        self._tick_counter += cfg.INTERVAL

        if self._tick_counter % 300 == 0:
            logger.info(f"Monster tick progress: {self._tick_counter}/{cfg.MONSTER_INTERVAL}")

        if self._tick_counter >= cfg.MONSTER_INTERVAL:
            self._tick_counter = 0
            logger.info("Monster tick threshold reached, spawning encounters")
            await self._spawn_encounters(bot)

        await self._process_pending_fights(bot)

        return None

    async def on_player_action(
        self,
        player_uid: int,
        action: str,
        data: dict[str, Any]
    ) -> Optional[str]:
        return None

    def _get_total_dps(self, player: Player) -> int:
        cache_key = str(player.uid)
        cached = _dps_cache.get(cache_key)
        if cached is not None:
            return cached
        total = player.get_dps()
        from game.classes import get_class_bonus
        cls_bonus = get_class_bonus(player.job)
        if cls_bonus.get("dps_pct"):
            total = int(total * (1 + cls_bonus["dps_pct"] / 100))
        _dps_cache.set(cache_key, total)
        return total

    async def _spawn_encounters(self, bot: Bot = None) -> None:
        if not bot:
            logger.warning("Bot not available for monster encounters")
            return

        players = await Player.get_active_players()
        logger.info(f"Spawning monsters: {len(players)} active players found")
        if not players:
            return

        total_monsters = 0
        now = int(time.time())
        from data.locations import find_location

        for player in players:
            uid = player.uid
            if uid in self._pending_fights and self._pending_fights[uid]:
                logger.info(f"Player {uid} already has pending fights, skipping")
                continue

            # per-player staggered timer
            next_spawn = self._next_spawn_time.get(uid, 0)
            if next_spawn > now:
                continue

            streak = player.fight_streak or 0

            # biome filter
            loc = find_location(player.x, player.y)
            loc_type = loc.get("type", "") if loc else ""
            allowed_types = cfg.BIOME_MONSTERS.get(loc_type) or cfg.BIOME_MONSTERS.get("default")

            # level-based rank cap
            rank_cap = "Legendary"
            for level, rcap in cfg.LEVEL_RANK_CAP:
                if player.level <= level:
                    rank_cap = rcap
                    break

            # streak-based min rank
            min_rank = None
            for s, rfloor in cfg.STREAK_RANK_FLOOR:
                if streak >= s:
                    min_rank = rfloor

            # count by streak
            if streak >= 5:
                count = random.randint(2, 3)
            elif streak >= 2:
                count = random.randint(1, 2)
            else:
                count = 1

            is_party = random.random() < cfg.PARTY_CHANCE
            if is_party:
                count = max(2, count * 2)

            monsters = []
            for _ in range(count):
                from game.factories import MonsterFactory
                monster = MonsterFactory.create_random(
                    player.level,
                    allowed_types=allowed_types,
                    max_rank=rank_cap,
                    min_rank=min_rank,
                )

                if is_party:
                    monster._is_party = True
                else:
                    monster._is_party = False

                # elite/boss variant (cumulative thresholds)
                var_roll = random.random()
                variant = "normal"
                cumulative = 0.0
                for vname, vchance in cfg.VARIANT_CHANCES.items():
                    cumulative += vchance
                    if var_roll < cumulative:
                        variant = vname
                        break
                monster._variant = variant

                monsters.append(monster)
                total_monsters += 1

            if monsters:
                self._pending_fights[uid] = monsters
                if uid not in self._next_fight_time:
                    self._next_fight_time[uid] = now
                logger.info(f"Player {uid} (lvl {player.level}): queued {len(monsters)} monsters (party={is_party}, streak={streak})")

        logger.info(f"Monster spawn complete: {total_monsters} monsters for {len(players)} players")

    async def _process_pending_fights(self, bot: Bot = None) -> None:
        if not bot or not self._pending_fights:
            return

        now = int(time.time())
        to_remove = []

        for uid, monsters in list(self._pending_fights.items()):
            next_time = self._next_fight_time.get(uid, 0)
            if next_time > now:
                continue

            if not monsters:
                to_remove.append(uid)
                continue

            player = await Player.objects.get_or_none(uid=uid)
            if not player or not player.online:
                to_remove.append(uid)
                continue

            try:
                monster = monsters.pop(0)
                logger.info(f"Processing fight for {uid}: {len(monsters)} monsters remaining")
                await self._combat_single(bot, player, monster)
            except Exception as e:
                logger.error(f"Fight error for {uid}: {e}")
                to_remove.append(uid)
                continue

            if monsters:
                delay = random.randint(cfg.SPAWN_MIN_INTERVAL, cfg.SPAWN_MAX_INTERVAL)
                self._next_fight_time[uid] = now + delay
            else:
                to_remove.append(uid)

        for uid in to_remove:
            self._pending_fights.pop(uid, None)
            self._next_fight_time.pop(uid, None)

    async def _get_region_bonus(self, player: Player) -> tuple[float, str]:
        try:
            from data.locations import find_location, get_location_emoji
            loc = find_location(player.x, player.y)
            if not loc:
                return 1.0, ""
            loc_type = loc.get("type", "")
            kingdom = loc.get("kingdom", "")
            mult = cfg.REGION_BONUSES.get(loc_type, 1.0)
            mult *= cfg.KINGDOM_BONUSES.get(kingdom, 1.0)
            emoji = get_location_emoji(loc_type)
            return mult, emoji
        except Exception:
            return 1.0, ""

    async def _get_nearby_player_bonus(self, player: Player) -> tuple[float, Optional[str]]:
        try:
            nearby = await Player.objects.filter(
                online=True,
                x__range=(player.x - 5, player.x + 5),
                y__range=(player.y - 5, player.y + 5),
            ).exclude(uid=player.uid).all()
            if nearby:
                return 1.0 + (len(nearby) * 0.5), nearby[0].name
        except Exception:
            pass
        return 1.0, None

    async def _try_drop_loot(self, player: Player, monster_level: int, lang: str, update_cols: list, force: bool = False) -> str:
        if not force and random.random() >= cfg.LOOT_CHANCE:
            return ""

        try:
            from core.loot import generate_item_data, get_random_slot, is_item_better
            slot = get_random_slot()
            item = generate_item_data(slot, max(1, monster_level))
            rank_emoji = cfg.RARITY_EMOJI.get(item.get("rank", "Common"), "⚪")

            current_item = getattr(player, slot, None)
            if isinstance(current_item, dict) and is_item_better(item, current_item):
                setattr(player, slot, item)
                player.sync_max_hp_mp()
                if slot not in update_cols:
                    update_cols.append(slot)
                for c in ("max_hp", "max_mp"):
                    if c not in update_cols:
                        update_cols.append(c)

                from game.monsters import invalidate_dps_cache as core_invalidate
                core_invalidate(player.uid)
                invalidate_dps_cache(player.uid)

                if lang == "en":
                    return f"\n🎒 *Loot!* {rank_emoji} {item_string(item, lang)}"
                return f"\n🎒 *Дроп!* {rank_emoji} {item_string(item, lang)}"
            else:
                if lang == "en":
                    return f"\n🎒 *Loot!* {rank_emoji} {item_string(item, lang)} — your {slot} is better"
                return f"\n🎒 *Дроп!* {rank_emoji} {item_string(item, lang)} — твой {slot} лучше"
        except Exception as e:
            logger.error(f"Loot error: {e}")
            return ""

    def _get_available_player_skills(self, player, cooldowns, current_round):
        """Активные навыки игрока, доступные в этом раунде."""
        from game.skills.base import SkillRegistry
        import config as cfg
        available = []
        racial_skills = list(cfg.RACIAL_ACTIVE_SKILLS.values())
        player_racial = cfg.RACIAL_ACTIVE_SKILLS.get(player.race or "")
        for name in SkillRegistry.list_names():
            if name == "attack":
                continue
            skill = SkillRegistry.get(name)
            if not skill:
                continue
            if name in cooldowns and cooldowns[name] > current_round:
                continue
            if name == "smite" and player.align != 1:
                continue
            # Racial skills only available to matching race
            if name in racial_skills and name != player_racial:
                continue
            if player.mp < skill.mana_cost:
                continue
            available.append(skill)
        return available

    async def _get_active_skill_level(self, player, skill_name: str) -> int:
        """Получить уровень расового активного скилла из БД."""
        import config as cfg
        if skill_name not in cfg.RACIAL_ACTIVE_SKILLS.values():
            return 1
        from db import PlayerActiveSkill
        rec = await PlayerActiveSkill.objects.filter(
            player_uid=player.uid, skill_id=skill_name
        ).get_or_none()
        return rec.level if rec else 1

    @staticmethod
    async def _add_active_skill_xp(player, skill_name: str):
        """Начислить XP расовому активному скиллу после использования."""
        import config as cfg
        if skill_name not in cfg.RACIAL_ACTIVE_SKILLS.values():
            return
        from db import PlayerActiveSkill
        from game.skills.base import active_skill_xp_threshold
        rec = await PlayerActiveSkill.objects.filter(
            player_uid=player.uid, skill_id=skill_name
        ).get_or_none()
        if not rec:
            return
        rec.use_count += 1
        rec.xp_progress += cfg.ACTIVE_SKILL_XP_PER_USE
        while rec.xp_progress >= active_skill_xp_threshold(rec.level):
            rec.xp_progress -= active_skill_xp_threshold(rec.level)
            rec.level += 1
            if rec.level >= 100:
                rec.level = 100
                rec.xp_progress = active_skill_xp_threshold(100) - 1
                break
        await rec.update(_columns=["level", "xp_progress", "use_count"])

    def _apply_player_skill(self, skill, p_dmg, player_hp, player, skill_lv: int = 1, streak: int = 0):
        """Применить активный навык игрока. Возвращает (p_dmg, player_hp, msg, poison_dmg)."""
        name = skill.name
        msg = None
        poison = 0
        heal_mult = max(0.5, 1.0 - streak * 0.025)
        lang = player.lang or "ru"

        if name == "heal":
            heal = int(player.get_max_hp() * 0.3)
            actual = min(heal, player.get_max_hp() - player_hp)
            actual = int(actual * heal_mult)
            player_hp += actual
            msg = f"💚 +{actual} HP" + ((" (усталость)" if lang != "en" else " (fatigue)") if heal_mult < 1.0 else "")
        elif name == "smite":
            p_dmg = int(p_dmg * 2.0)
            msg = "✨ *Smite!* ×2" if lang == "en" else "✨ *Смайт!* ×2"
        elif name == "fireball":
            p_dmg = int(p_dmg * 1.5)
            msg = "🔥 *Fireball!* ×1.5" if lang == "en" else "🔥 *Огненный шар!* ×1.5"
        elif name == "poison":
            p_dmg = int(p_dmg * 0.8)
            poison = int(p_dmg * 0.3)
            msg = "☠️ *Poison Dart!*" if lang == "en" else "☠️ *Ядовитый дротик!*"
        elif name == "purifying_light":
            from game.skills.base import PurifyingLightSkill
            pct = PurifyingLightSkill.get_heal_pct(skill_lv)
            heal = int(player.get_max_hp() * pct)
            actual = min(heal, player.get_max_hp() - player_hp)
            actual = int(actual * heal_mult)
            player_hp += actual
            msg = f"✨ *Purifying Light Lv.{skill_lv}!* +{actual} HP" if lang == "en" else f"✨ *Очищающий свет Lv.{skill_lv}!* +{actual} HP"
            msg += ((" (усталость)" if lang != "en" else " (fatigue)") if heal_mult < 1.0 else "")
        elif name == "seismic_slam":
            from game.skills.base import SeismicSlamSkill
            mult = SeismicSlamSkill.get_damage_mult(skill_lv)
            p_dmg = int(p_dmg * mult)
            msg = f"💥 *Seismic Slam Lv.{skill_lv}!* ×{mult:.1f} + stun" if lang == "en" else f"💥 *Сейсмический удар Lv.{skill_lv}!* ×{mult:.1f} + оглушение"
        elif name == "quick_volley":
            from game.skills.base import QuickVolleySkill
            mult = QuickVolleySkill.get_hit_mult(skill_lv)
            total = 0
            for _ in range(3):
                total += int(p_dmg * mult)
            p_dmg = total
            msg = f"🏹 *Quick Volley Lv.{skill_lv}!* 3×{mult:.1f} hits" if lang == "en" else f"🏹 *Быстрый залп Lv.{skill_lv}!* 3×{mult:.1f} удара"

        return p_dmg, player_hp, msg, poison

    def _select_monster_skill(self, monster_hp, monster_max_hp, current_round, cooldowns):
        """Выбрать активный навык монстра."""
        if monster_max_hp <= 0:
            return None
        hp_pct = monster_hp / monster_max_hp
        available = []
        for sk in MONSTER_COMBAT_SKILLS:
            sid = sk["id"]
            if sid in cooldowns and cooldowns[sid] > current_round:
                continue
            if hp_pct <= sk["hp_max"]:
                available.append(sk)
        if available and random.random() < 0.4:
            return random.choice(available)
        return None

    def _apply_monster_skill(self, skill, m_dmg, monster_hp, monster_max_hp, lang="ru"):
        """Применить навык монстра. Возвращает (m_dmg, monster_hp, msg)."""
        sid = skill["id"]
        msg = None
        sk_name = skill['name_en'] if lang == "en" else skill['name_ru']

        if sid == "heavy":
            m_dmg = int(m_dmg * skill["damage_mult"])
            msg = f"{skill['icon']} *{sk_name}* ×{skill['damage_mult']}"
        elif sid == "monster_heal":
            heal = int(monster_max_hp * skill["heal_pct"])
            actual = min(heal, monster_max_hp - monster_hp)
            monster_hp += actual
            msg = f"{skill['icon']} *{sk_name}* +{actual} HP"
        elif sid == "rage":
            m_dmg = int(m_dmg * skill["damage_mult"])
            msg = f"{skill['icon']} *{sk_name}* ×{skill['damage_mult']}"

        return m_dmg, monster_hp, msg

    async def _combat_single(self, bot: Bot, player: Player, monster) -> bool:
        uid = player.uid
        if self._encounter_cooldown.get(uid) is not None:
            return False

        self._encounter_cooldown.set(uid, True)

        # Ensure racial skill DB records exist (for existing players)
        if player.race:
            import config as cfg
            from db import PlayerPassive, PlayerActiveSkill
            import time
            racial_pid = cfg.RACIAL_PASSIVES.get(player.race)
            if racial_pid:
                exists = await PlayerPassive.objects.filter(
                    player_uid=player.uid, passive_id=racial_pid
                ).get_or_none()
                if not exists:
                    rp = PlayerPassive(
                        player_uid=player.uid, passive_id=racial_pid,
                        level=1, xp_progress=0, equipped=True,
                        acquired_at=int(time.time()),
                    )
                    await rp.save()
            racial_aid = cfg.RACIAL_ACTIVE_SKILLS.get(player.race)
            if racial_aid:
                exists = await PlayerActiveSkill.objects.filter(
                    player_uid=player.uid, skill_id=racial_aid
                ).get_or_none()
                if not exists:
                    act = PlayerActiveSkill(
                        player_uid=player.uid, skill_id=racial_aid,
                        level=1, xp_progress=0, use_count=0,
                        acquired_at=int(time.time()),
                    )
                    await act.save()

        lang = player.lang or "ru"
        variant = getattr(monster, '_variant', 'normal')
        vmult = cfg.VARIANT_MULT.get(variant, {})
        vprefix = vmult.get(f"prefix_{lang}", "") if vmult else ""
        monster_name = f"{vprefix}{monster.get_display_name(lang)}"
        monster_level = max(1, monster.level)
        monster_rank = monster.rank if hasattr(monster, 'rank') else "Common"
        is_party = getattr(monster, '_is_party', False)

        p_max = self._get_total_dps(player)

        from game.skills.passives.registry import PassiveSkillRegistry
        dodge_ok, first_strike_active, encounter_res = await PassiveSkillRegistry.trigger_on_encounter(player)

        from game.classes import get_class_bonus
        cls_bonus = get_class_bonus(player.job)
        rogue_dodge = cls_bonus.get("dodge_pct", 0) > 0 and random.random() < 0.15

        if dodge_ok or rogue_dodge:
            self._encounter_cooldown.delete(uid)
            msg_extra = f"\n{encounter_res.message}" if encounter_res.message else ""

            if lang == "en":
                msg = "\n".join([
                    "⚔️ *Monster Encounter!*",
                    "", f"{player.name} vs *{monster_name}*", "",
                    "👤 *DODGE!*\nYou evaded the monster completely!",
                    msg_extra,
                ])
            else:
                msg = "\n".join([
                    "⚔️ *Встреча с монстром!*",
                    "", f"{player.name} vs *{monster_name}*", "",
                    "👤 *УКЛОНЕНИЕ!*\nТы полностью уклонился от монстра!",
                    msg_extra,
                ])

            from bot import send_to_players
            await send_to_players(bot, msg, player_uids=[player.uid])
            return True

        rank_power_val = RANK_POWER.get(monster_rank, 1.0)
        penalty_factor = RANK_PENALTY.get(monster_rank, 1.0)
        level_diff = monster_level - player.level
        if level_diff > 0:
            penalty_factor *= (1 + level_diff * 0.15)

        # --- HP/MP combat ---
        defense_changed = False
        if not player.hp or player.hp <= 0:
            player.hp = player.get_max_hp()
        player.sync_max_hp_mp()
        if not player.mp or player.mp <= 0:
            player.mp = player.get_max_mp()
        if not player.defense:
            player.defense = 0
            defense_changed = True

        monster_max_hp = int(player.level * 40 * rank_power_val)
        monster_max_mp = int(monster_level * 3)
        monster_defense = int(monster_level * 0.5 * rank_power_val)
        monster_dps = int(monster.dps * RANK_DPS_MULT.get(monster_rank, 1.0))

        # Apply variant HP/DPS multipliers (vmult from line 515)
        if vmult:
            monster_max_hp = int(monster_max_hp * vmult.get("hp", 1.0))
            monster_dps = int(monster_dps * vmult.get("dps", 1.0))



        # Stamina penalty
        base_def = int(player.level * 1.0)
        effective_defense = max(player.defense or 0, base_def)
        if cls_bonus.get("defense_pct"):
            effective_defense = int(effective_defense * (1 + cls_bonus["defense_pct"] / 100))
        stamina_penalty = 0.0
        streak = player.fight_streak or 0
        if streak >= cfg.STAMINA_MAX:
            stamina_penalty = min(0.5, (streak - cfg.STAMINA_MAX + 1) * 0.20)
            effective_defense = int(effective_defense * (1.0 - stamina_penalty))

        first_strike_bonus = 0.0
        if first_strike_active:
            first_strike_bonus = encounter_res.damage_bonus

        nearby_damage_bonus = 1.0
        nearby_name = None
        if is_party:
            dmg_mult, helper_name = await self._get_nearby_player_bonus(player)
            nearby_damage_bonus = dmg_mult
            nearby_name = helper_name

        rounds = []
        round_num = 0
        player_hp = player.hp
        monster_hp = monster_max_hp
        player_max_hp = player.max_hp
        monster_max = monster_max_hp
        MAX_ROUNDS = 15

        player_skill_cd = {}
        monster_skill_cd = {}
        _boss_skill_last: dict[str, int] = {}
        _skill_level_cache: dict[str, int] = {}
        _pending_skill_xp: list[tuple] = []
        active_poison_ticks = 0
        active_poison_dmg = 0
        player_stunned = False

        while player_hp > 0 and monster_hp > 0 and round_num < MAX_ROUNDS:
            round_num += 1
            r = {"num": round_num}
            round_passives = []
            skill_msgs = []

            if player_stunned:
                p_dmg = 0
                r["player_attack"] = 0
                r["stunned_skip"] = True
                player_stunned = False
            else:
                p_dmg = max(1, p_max // 2)

            if first_strike_bonus > 0 and round_num == 1:
                p_dmg = int(p_dmg * (1.0 + first_strike_bonus))
                r["first_strike"] = True

            if nearby_damage_bonus > 1.0:
                p_dmg = int(p_dmg * nearby_damage_bonus)

            # Active player skill attempt
            avail_skills = self._get_available_player_skills(player, player_skill_cd, round_num)
            if avail_skills and random.random() < 0.25:
                chosen = random.choice(avail_skills)
                player.mp -= chosen.mana_cost
                if chosen.name not in _skill_level_cache:
                    _skill_level_cache[chosen.name] = await self._get_active_skill_level(player, chosen.name)
                skill_lv = _skill_level_cache[chosen.name]
                p_dmg, player_hp, skill_msg, skill_poison = self._apply_player_skill(
                    chosen, p_dmg, player_hp, player, skill_lv, streak
                )
                _pending_skill_xp.append((player.uid, chosen.name))
                cooldown_rounds = max(2, chosen.cooldown // 5)
                player_skill_cd[chosen.name] = round_num + cooldown_rounds
                if skill_msg:
                    skill_msgs.append(skill_msg)
                r["skill_used"] = chosen.get_display_name(lang)
                if skill_poison > 0:
                    active_poison_ticks = 2
                    active_poison_dmg = skill_poison

            # Poison DoT tick
            if active_poison_ticks > 0 and monster_hp > 0:
                dot = active_poison_dmg
                monster_hp = max(0, monster_hp - dot)
                active_poison_ticks -= 1
                r["dot"] = dot

            player.hp = player_hp
            damage_dealt_res = await PassiveSkillRegistry.trigger_on_damage_dealt(
                player, p_dmg, is_crit=False,
                target_hp_pct=monster_hp / monster_max if monster_max > 0 else 1.0
            )
            if damage_dealt_res.is_crit:
                p_dmg = int(p_dmg * 2.0)
                r["crit"] = True
            archer_crit = cls_bonus.get("crit_pct", 0) > 0 and random.random() < 0.10
            if archer_crit:
                p_dmg = int(p_dmg * 2.0)
                r["crit"] = True
            from game.races import get_race_crit_chance
            if random.random() < get_race_crit_chance(player.race):
                p_dmg = int(p_dmg * 2.0)
                r["crit"] = True
            if damage_dealt_res.damage_bonus:
                p_dmg = int(p_dmg * (1.0 + damage_dealt_res.damage_bonus))
            if damage_dealt_res.message:
                round_passives.append(damage_dealt_res.message)

            # C3 — reduce vampirism healing on high streak
            if damage_dealt_res.healing > 0 and stamina_penalty > 0:
                heal_mult = max(0.5, 1.0 - streak * 0.025)
                player.hp -= damage_dealt_res.healing
                reduced = int(damage_dealt_res.healing * heal_mult)
                player.hp = min(player.max_hp, player.hp + reduced)
                damage_dealt_res.healing = reduced

            player_hp = player.hp

            # C1 — stamina penalty reduces player damage
            if stamina_penalty > 0:
                p_dmg = int(p_dmg * (1.0 - stamina_penalty))
                r["fatigue"] = int(stamina_penalty * 100)

            # Damage cap — минимум 3 раунда
            max_per_round = max(1, monster_max_hp // 3)
            if p_dmg > max_per_round:
                p_dmg = max_per_round
                r["capped"] = True

            mon_def_reduction = min(0.75, monster_defense / (monster_defense + 200))
            p_dmg = int(p_dmg * (1 - mon_def_reduction))
            monster_hp = max(0, monster_hp - p_dmg)

            if damage_dealt_res.poison_damage > 0:
                monster_hp = max(0, monster_hp - damage_dealt_res.poison_damage)
                r["poison"] = damage_dealt_res.poison_damage

            r["player_attack"] = p_dmg
            r["monster_hp"] = monster_hp
            r["monster_max"] = monster_max

            if monster_hp <= 0:
                r["monster_hp"] = 0
                if skill_msgs:
                    r["skill_msg"] = "\n".join(skill_msgs)
                if round_passives:
                    r["passive_msg"] = "\n".join(round_passives)
                rounds.append(r)
                break

            m_dmg = max(1, monster_dps // 2)

            # C2 — monster rage per streak
            streak_bonus = min(0.5, streak * 0.04)
            if streak_bonus > 0:
                m_dmg = int(m_dmg * (1.0 + streak_bonus))
                r["rage"] = int(streak_bonus * 100)

            # B — monster passive procs from BOSS_SKILLS
            monster_passives = RANK_PASSIVES.get(monster_rank, [])
            for passive_id in monster_passives:
                skill_cfg = cfg.BOSS_SKILLS.get(passive_id)
                if not skill_cfg:
                    continue
                last_round = _boss_skill_last.get(passive_id, -999)
                if round_num - last_round < 2:
                    continue
                if random.random() < skill_cfg["chance"]:
                    _boss_skill_last[passive_id] = round_num
                    if passive_id == "fireball":
                        m_dmg = int(m_dmg * skill_cfg["damage_mult"])
                        skill_msgs.append("🔥 *Fireball!*")
                    elif passive_id == "heal":
                        pct = skill_cfg["heal_pct"]
                        heal = int(monster_max_hp * pct)
                        actual = min(heal, monster_max_hp - monster_hp)
                        monster_hp += actual
                        skill_msgs.append(f"💚 *Heal:* +{actual} HP")
                    elif passive_id == "dark_burst":
                        m_dmg = int(m_dmg * skill_cfg["damage_mult"])
                        skill_msgs.append("💥 *Dark Burst!*")
                    elif passive_id == "stun":
                        player_stunned = True
                        skill_msgs.append("💫 *Stun!* — player loses turn" if lang == "en" else "💫 *Stun!* — игрок теряет ход")

            # Active monster skill attempt
            monster_skill = self._select_monster_skill(monster_hp, monster_max, round_num, monster_skill_cd)
            if monster_skill:
                m_dmg, monster_hp, mon_skill_msg = self._apply_monster_skill(
                    monster_skill, m_dmg, monster_hp, monster_max, lang
                )
                monster_skill_cd[monster_skill["id"]] = round_num + monster_skill["cooldown"]
                if mon_skill_msg:
                    skill_msgs.append(mon_skill_msg)

            modified_m_dmg, damage_taken_res = await PassiveSkillRegistry.trigger_on_damage_taken(
                player, m_dmg
            )

            if damage_taken_res.damage_reflect > 0:
                monster_hp = max(0, monster_hp - damage_taken_res.damage_reflect)
                r["reflect"] = damage_taken_res.damage_reflect
            if damage_taken_res.message:
                round_passives.append(damage_taken_res.message)

            m_dmg = modified_m_dmg
            p_def_reduction = min(0.75, effective_defense / (effective_defense + 200))
            m_dmg = int(m_dmg * (1 - p_def_reduction))
            player_hp = max(0, player_hp - m_dmg)
            r["monster_attack"] = m_dmg
            r["player_hp"] = player_hp
            r["player_max"] = player_max_hp

            if skill_msgs:
                r["skill_msg"] = "\n".join(skill_msgs)
            if round_passives:
                r["passive_msg"] = "\n".join(round_passives)
            rounds.append(r)

        # Format rounds
        round_lines = []
        for r in rounds:
            m_hp = r.get("monster_hp", monster_max)
            m_mx = r.get("monster_max", monster_max)
            p_hp_val = r.get("player_hp", player_hp)
            p_mx = r.get("player_max", player_max_hp)

            m_bar_len = int(m_hp / m_mx * 6) if m_mx > 0 else 0
            m_bar = "█" * m_bar_len + "░" * (6 - m_bar_len)
            p_bar_len = int(p_hp_val / p_mx * 6) if p_mx > 0 else 0
            p_bar = "█" * p_bar_len + "░" * (6 - p_bar_len)

            line = f"  ⚔️ {r.get('player_attack', 0)} → 👹 [{m_bar}] {m_hp}"
            if "monster_attack" in r:
                line += f"\n  👹 {r['monster_attack']} → 👤 [{p_bar}] {p_hp_val}"
            if "first_strike" in r:
                line += "\n  ⚡ *First Strike!*" if lang == "en" else "\n  ⚡ *Первая атака!*"
            if r.get("skill_msg"):
                for sm in r["skill_msg"].split("\n"):
                    if sm.strip():
                        line += f"\n  {sm.strip()}"
            if "crit" in r:
                line += "\n  ⚡ *CRIT!*" if lang == "en" else "\n  ⚡ *КРИТ!*"
            if "capped" in r:
                line += "\n  ⛔ *DAMAGE CAPPED*" if lang == "en" else "\n  ⛔ *УРОН ОГРАНИЧЕН*"
            if "fatigue" in r:
                line += f"\n  💤 *Fatigue:* -{r['fatigue']}%" if lang == "en" else f"\n  💤 *Усталость:* -{r['fatigue']}%"
            if "rage" in r:
                line += f"\n  🔥 *Rage:* +{r['rage']}% dmg" if lang == "en" else f"\n  🔥 *Ярость:* +{r['rage']}% урона"
            if "stunned_skip" in r:
                line += "\n  💫 *STUNNED!*" if lang == "en" else "\n  💫 *ОГЛУШЕН!*"
            if "dot" in r:
                line += f"\n  ☠️ *DoT:* -{r['dot']} HP" if lang == "en" else f"\n  ☠️ *DoT:* -{r['dot']} HP"
            if "poison" in r:
                line += f"\n  ☠️ *Poison:* -{r['poison']} HP" if lang == "en" else f"\n  ☠️ *Яд:* -{r['poison']} HP"
            if "reflect" in r:
                line += f"\n  🌵 *Reflect:* -{r['reflect']} HP" if lang == "en" else f"\n  🌵 *Отражено:* -{r['reflect']} HP"
            if r.get("passive_msg"):
                for pm in r["passive_msg"].split("\n"):
                    if pm.strip():
                        line += f"\n  {pm.strip()}"
            round_lines.append(line)
        rounds_str = "\n".join(round_lines)
        player_won = monster_hp <= 0 and player_hp > 0

        # Apply HP/MP
        if player_hp <= 0:
            player.hp = max(1, player.get_max_hp() // 4)
        else:
            player.hp = player_hp


        # Stamina
        if player_won:
            player.fight_streak = (player.fight_streak or 0) + 1
            player.monster_kills = (player.monster_kills or 0) + 1
        else:
            player.fight_streak = 0

        # Penalty calc
        alvar = 90 if player.align == 1 else 100
        val = int(penalty_factor * random.randint(2, 4) / alvar * (player.nextxp - player.currentxp))
        val = max(1, val)

        # Regional bonus
        region_mult, region_emoji = await self._get_region_bonus(player)

        # Build update columns list
        update_cols = ["nextxp", "totalxplost", "gold", "hp", "mp", "max_hp", "max_mp",
                       "fight_streak", "monster_kills", "monster_deaths"]
        if defense_changed:
            update_cols.append("defense")

        new_streak = player.fight_streak or 0
        streak_header = ""
        if new_streak > 0:
            if lang == "en":
                streak_header = f"\n🏆 Streak: {new_streak}"
            else:
                streak_header = f"\n🏆 Серия: {new_streak}"

        if player_won:
            # variant multipliers for XP/gold
            vxp_mult = vmult.get("xp", 1.0) if vmult else 1.0
            vgold_mult = vmult.get("gold", 1.0) if vmult else 1.0
            if is_party:
                vxp_mult *= 2.0
                vgold_mult *= 2.0

            from game.races import get_race_xp_mult
            elf_mult = get_race_xp_mult(player.race)
            mage_mult = 1.0 + cls_bonus.get("xp_pct", 0) / 100
            effective_val = max(1, int(val * elf_mult * mage_mult * vxp_mult))

            effective_val = int(effective_val * region_mult)
            player.nextxp = max(player.currentxp + 1, player.nextxp - effective_val)

            gold_reward = int(((monster_level * 5) + random.randint(0, player.level * 2)) * vgold_mult)
            from game.races import get_race_gold_mult
            gold_reward = int(gold_reward * get_race_gold_mult(player.race))
            gold_reward = int(gold_reward * region_mult)
            base_xp_reward = effective_val

            bonus_gold, bonus_xp, kill_res = await PassiveSkillRegistry.trigger_on_kill(
                player, monster_level, gold_reward, base_xp_reward
            )
            gold_reward += bonus_gold
            effective_val += bonus_xp

            if bonus_xp > 0:
                player.nextxp = max(player.currentxp + 1, player.nextxp - bonus_xp)

            # Prestige бонус XP на всю сумму (база + регион + пассивки)
            from plugins.vip_shop import has_prestige_xp_bonus, get_prestige_xp_multiplier
            if has_prestige_xp_bonus(player):
                prestige_mult = get_prestige_xp_multiplier(player)
                additional_xp = int(effective_val * (prestige_mult - 1.0))
                if additional_xp > 0:
                    player.nextxp = max(player.currentxp + 1, player.nextxp - additional_xp)
                    effective_val += additional_xp

            passive_kill_msg = f"\n{kill_res.message}" if kill_res.triggered and kill_res.message else ""

            # Prestige бонус Gold
            from plugins.vip_shop import has_prestige_gold_bonus, get_prestige_gold_multiplier
            if has_prestige_gold_bonus(player):
                prestige_mult = get_prestige_gold_multiplier(player)
                gold_reward = int(gold_reward * prestige_mult)

            player.gold += gold_reward

            # Loot (boss = guaranteed, read from config)
            force_loot = vmult.get("loot_guaranteed", False) if vmult else False
            loot_msg = await self._try_drop_loot(player, monster_level, lang, update_cols, force=force_loot)

            # Extra info lines
            extra_lines = []
            if variant == "boss":
                extra_lines.append("👑 *BOSS!*" if lang == "en" else "👑 *БОСС!*")
            elif variant == "elite":
                extra_lines.append("⭐ *ELITE!*" if lang == "en" else "⭐ *ЭЛИТА!*")
            if is_party:
                extra_lines.append("👥 *ГРУППОВОЙ МОНСТР!*" if lang == "en" else "👥 *ГРУППОВОЙ МОНСТР!*")
                if nearby_name:
                    extra_lines.append(f"👤 +{nearby_name} помогает в бою!" if lang == "en" else f"👤 +{nearby_name} помогает в бою!")
            if region_mult > 1.0:
                pct = int((region_mult - 1) * 100)
                extra_lines.append(f"{region_emoji} {'Region: +' if lang == 'en' else 'Регион: +'}{pct}%")
            if stamina_penalty > 0:
                pct = int(stamina_penalty * 100)
                if lang == "en":
                    extra_lines.append(f"💤 *Fatigue:* -{pct}% dmg / -{pct}% heal")
                else:
                    extra_lines.append(f"💤 *Усталость:* -{pct}% урона / -{pct}% лечения")
            extra_str = "\n" + "\n".join(extra_lines) if extra_lines else ""

            if lang == "en":
                msg = "\n".join([
                    "⚔️ *Monster Encounter!*",
                    "", f"{player.name} vs *{monster_name}* (Lv.{monster_level}){streak_header}",
                    "",
                    f"━━━ Rounds ({round_num}) ━━━",
                    rounds_str,
                    "",
                    f"🏆 *YOU WIN!* -{ctime(effective_val, lang)} to level {player.level + 1}!",
                    f"💰 Gold: +{gold_reward}",
                    f"📊 HP: {player.hp}/{player.max_hp}",
                    f"Next level in: *{ctime(player.nextxp - player.currentxp, lang)}*",
                    passive_kill_msg,
                    loot_msg,
                    extra_str,
                ])
            else:
                msg = "\n".join([
                    "⚔️ *Встреча с монстром!*",
                    "", f"{player.name} vs *{monster_name}* (Ур.{monster_level}){streak_header}",
                    "",
                    f"━━━ Раунды ({round_num}) ━━━",
                    rounds_str,
                    "",
                    f"🏆 *ТЫ ПОБЕДИЛ!* Бонус -{ctime(effective_val, lang)} к уровню {player.level + 1}!",
                    f"💰 Золото: +{gold_reward}",
                    f"📊 HP: {player.hp}/{player.max_hp}",
                    f"До след. уровня: *{ctime(player.nextxp - player.currentxp, lang)}*",
                    passive_kill_msg,
                    loot_msg,
                    extra_str,
                ])
        else:
            from game.races import get_race_bonus
            lucky = player.race == "human" and random.random() < get_race_bonus(player.race, "luck_chance", 0.0)

            if lucky:
                if lang == "en":
                    msg = "\n".join([
                        "⚔️ *Monster Encounter!*",
                        "", f"{player.name} vs *{monster_name}* (Lv.{monster_level}){streak_header}",
                        "",
                        f"━━━ Rounds ({round_num}) ━━━",
                        rounds_str,
                        "",
                        "💀 Monster got the upper hand...",
                        "🍀 *HUMAN LUCK!* You narrowly escaped — no penalty this time!",
                    ])
                else:
                    msg = "\n".join([
                        "⚔️ *Встреча с монстром!*",
                        "", f"{player.name} vs *{monster_name}* (Ур.{monster_level}){streak_header}",
                        "",
                        f"━━━ Раунды ({round_num}) ━━━",
                        rounds_str,
                        "",
                        "💀 Монстр взял верх...",
                        "🍀 *УДАЧА ЧЕЛОВЕКА!* Ты едва ускользнул — штраф отменяется!",
                    ])
            else:
                player.monster_deaths = (player.monster_deaths or 0) + 1
                player.nextxp += val
                player.totalxplost += val

                if lang == "en":
                    msg = "\n".join([
                        "⚔️ *Monster Encounter!*",
                        "", f"{player.name} vs *{monster_name}* (Lv.{monster_level}){streak_header}",
                        "",
                        f"━━━ Rounds ({round_num}) ━━━",
                        rounds_str,
                        "",
                        f"💀 *MONSTER WINS!* Penalty +{ctime(val, lang)} to level {player.level + 1}.",
                        f"📊 HP: {player.hp}/{player.max_hp}",
                        f"Next level in: *{ctime(player.nextxp - player.currentxp, lang)}*",
                    ])
                else:
                    msg = "\n".join([
                        "⚔️ *Встреча с монстром!*",
                        "", f"{player.name} vs *{monster_name}* (Ур.{monster_level}){streak_header}",
                        "",
                        f"━━━ Раунды ({round_num}) ━━━",
                        rounds_str,
                        "",
                        f"💀 *МОНСТР ПОБЕДИЛ!* Штраф +{ctime(val, lang)} к уровню {player.level + 1}.",
                        f"📊 HP: {player.hp}/{player.max_hp}",
                        f"До след. уровня: *{ctime(player.nextxp - player.currentxp, lang)}*",
                    ])

        await player.update(_columns=update_cols)

        from handlers.quests import update_quest_progress
        await update_quest_progress(player, "kill_monster", 1)

        try:
            from game.quests import on_monster_defeated
            await on_monster_defeated(player, monster_name)
        except Exception as e:
            logger.error(f"Quest progress error: {e}")

        from bot import send_to_players
        await send_to_players(bot, msg, player_uids=[player.uid])

        # Deferred skill XP (batch after combat to reduce DB queries)
        for p_uid, skill_name in _pending_skill_xp:
            await self._add_active_skill_xp(player, skill_name)

        outcome = "won" if player_won else "lost"
        logger.info(f"Combat result {uid}: {outcome} vs {monster_name} Lv.{monster_level} ({round_num} rounds)")

        now_ts = int(time.time())
        if player_won:
            self._next_spawn_time[uid] = now_ts + random.randint(300, 900)
        else:
            self._next_spawn_time[uid] = now_ts + 1800

        return player_won


async def spawn_all_monsters(bot: Bot) -> None:
    """Вызвать встречу с монстрами для всех онлайн-игроков (для admin)."""
    plugin = PluginRegistry.get_loaded("monster_encounters")
    if plugin:
        await plugin._spawn_encounters(bot)
    else:
        logger.error("MonsterEncounters plugin not loaded")
