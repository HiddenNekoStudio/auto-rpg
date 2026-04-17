"""
game/monsters.py — встречи с монстрами
Каждый час: встреча сразу для ВСЕХ онлайн-игроков, каждый получает личный алерт.

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
from db import Player
from bot import ctime, send_to_players
from core.cache import TTLCache

# Rate limiting — TTL cache вместо бесконечного dict
_encounter_cooldown = TTLCache(ttl=2.0, maxsize=10000)

# Кэш DPS — инвалидируется при смене снаряжения
_dps_cache = {}

monster_list = [
    "Бешеная Крыса", "Больной Гоблин", "Переросший Редис", "Дух Кунзиле",
    "Помидор", "Паршивый Пёс", "Пульсирующая Масса", "Растительное Нашествие",
    "Двойник", "Кричащий Попугай", "Злобный Бродяга", "Профессиональный Дилетант",
    "Садистский Садист", "Стойкий Прокрастинатор", "Конвенционный Фурри",
    "Клацающие Крабы", "Позолоченный Дракон", "Удачливый Вор", "Военный Отряд",
    "Бабуля", "Голодные Кровопийцы", "Пчела", "Косолапый Лесоруб",
    "Троглодит", "Ледяной Голем", "Теневой Вампир", "Костяной Рыцарь",
    "Морской Змей", "Кровавая Ведьма", "Огненный Элементаль",
]

monster_list_en = [
    "Mad Rat", "Sick Goblin", "Giant Radish", "Spirit of Kunzile",
    "Tomato", "Mangy Dog", "Pulsating Mass", "Plant Invasion",
    "Doppelganger", "Screaming Parrot", "Evil Vagrant", "Professional Amateur",
    "Sadistic Sadist", "Stubborn Procrastinator", "Furry Convention",
    "Clacking Crabs", "Gilded Dragon", "Lucky Thief", "War Party",
    "Grandma", "Hungry Bloodsuckers", "Bee", "Clumsy Lumberjack",
    "Troglodyte", "Ice Golem", "Shadow Vampire", "Bone Knight",
    "Sea Serpent", "Blood Witch", "Fire Elemental",
]


def get_total_dps(player: Player, use_cache: bool = True) -> int:
    """Кэшированный расчёт DPS. Инвалидируется при обновлении снаряжения."""
    cache_key = player.uid
    
    if use_cache and cache_key in _dps_cache:
        return _dps_cache[cache_key]
    
    total = sum(
        item.get("dps", 0)
        for slot in cfg.WEAPON_SLOTS
        if isinstance(item := getattr(player, slot, None), dict)
    )
    
    # Гном: +15% к боевой силе
    if player.race == "dwarf":
        total = int(total * 1.15)
    
    _dps_cache[cache_key] = total
    return total


def invalidate_dps_cache(uid: int) -> None:
    """Инвалидирует кэш DPS при смене снаряжения."""
    _dps_cache.pop(uid, None)


async def encounter_one(bot: Bot, player: Player, monster: str, monster_level: int) -> None:
    """Битва одного игрока с указанным монстром. Обновляет БД и шлёт личный алерт."""
    
    # Rate limiting — TTL cache автоматически очищается
    uid = player.uid
    if _encounter_cooldown.get(str(uid)) is not None:
        return  # Cooldown active
    
    _encounter_cooldown.set(str(uid), True)
    
    lang  = player.lang or "ru"
    p_max = get_total_dps(player)
    m_max = random.randint(max(1, p_max - 500), p_max + 250)

    smite_chance  = (random.random() <= 0.10 and player.align == 1)
    player_score  = (
        random.randint(1, p_max * 2) if smite_chance
        else random.randint(1, max(1, p_max))
    )
    monster_score = random.randint(1, max(1, m_max))

    alvar = 90 if player.align == 1 else 100
    val   = int(random.randint(4, 6) / alvar * (player.nextxp - player.currentxp))

    smite_str = ""
    if smite_chance:
        smite_str = "\n✨ *СМАЙТ!*" if lang != "en" else "\n✨ *SMITE!*"

    # Формируем общую часть сообщения
    score_line = f"{'Ты' if lang != 'en' else 'You'} [{player_score}/{p_max}] vs {f'Ур.{monster_level}' if lang != 'en' else f'Lv.{monster_level}'} *{monster}* [{monster_score}/{m_max}]{smite_str}"
    
    if player_score >= monster_score:
        elf_mult      = 1.1 if player.race == "elf" else 1.0
        effective_val = max(1, int(val * elf_mult))
        player.nextxp = max(player.currentxp + 1, player.nextxp - effective_val)

        if lang == "en":
            msg = "\n".join([
                "⚔️ *Monster Encounter!*",
                "", score_line, "",
                f"🏆 *YOU WIN!* -{ctime(effective_val)} to level {player.level + 1}!",
                f"Next level in: *{ctime(player.nextxp - player.currentxp)}*",
            ])
        else:
            msg = "\n".join([
                "⚔️ *Встреча с монстром!*",
                "", score_line, "",
                f"🏆 *ТЫ ПОБЕДИЛ!* Бонус -{ctime(effective_val)} к уровню {player.level + 1}!",
                f"До след. уровня: *{ctime(player.nextxp - player.currentxp)}*",
            ])

    else:
        lucky = (player.race == "human" and random.random() < 0.20)

        if lucky:
            if lang == "en":
                msg = "\n".join([
                    "⚔️ *Monster Encounter!*",
                    "", score_line, "",
                    "💀 Monster got the upper hand...",
                    "🍀 *HUMAN LUCK!* You narrowly escaped — no penalty this time!",
                ])
            else:
                msg = "\n".join([
                    "⚔️ *Встреча с монстром!*",
                    "", score_line, "",
                    "💀 Монстр взял верх...",
                    "🍀 *УДАЧА ЧЕЛОВЕКА!* Ты едва ускользнул — штраф отменяется!",
                ])
        else:
            player.nextxp      += val
            player.totalxplost += val
            if lang == "en":
                msg = "\n".join([
                    "⚔️ *Monster Encounter!*",
                    "", score_line, "",
                    f"💀 *MONSTER WINS!* Penalty +{ctime(val)} to level {player.level + 1}.",
                    f"Next level in: *{ctime(player.nextxp - player.currentxp)}*",
                ])
            else:
                msg = "\n".join([
                    "⚔️ *Встреча с монстром!*",
                    "", score_line, "",
                    f"💀 *МОНСТР ПОБЕДИЛ!* Штраф +{ctime(val)} к уровню {player.level + 1}.",
                    f"До след. уровня: *{ctime(player.nextxp - player.currentxp)}*",
                ])

    await player.update(_columns=["nextxp", "totalxplost"])
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
