"""
game/quests.py — Event-based система прогресса квестов
Вызывается из game events при победах, XP, дуэлях и т.д.
"""
import logging
import time
from typing import Optional

from db import Player, PlayerQuest
from data.quest_config import (
    QuestCategory,
    calculate_rewards,
    calculate_penalty,
    is_expired,
    EVENT_TO_CATEGORY,
)

# ═══════════════════════════════════════════════════════════════
# MONSTER TYPE NORMALIZER — маппинг русских имён в типы
# ═══════════════════════════════════════════════════════════════

_MONSTER_TYPE_MAP = {
    # Крысы
    "Бешеная Крыса": "rat",
    "Mad Rat": "rat",
    # Гоблины
    "Больной Гоблин": "goblin",
    "Sick Goblin": "goblin",
    # Помидор
    "Помидор": "plant",
    "Tomato": "plant",
    # Пёс
    "Паршивый Пёс": "canine",
    "Mangy Dog": "canine",
    # Пульсирующая масса
    "Пульсирующая Масса": "slime",
    "Pulsating Mass": "slime",
    # Двойник
    "Двойник": "doppelganger",
    "Doppelganger": "doppelganger",
    # Попугай
    "Кричащий Попугай": "parrot",
    "Screaming Parrot": "parrot",
    # Бродяга
    "Злобный Бродяга": "bandit",
    "Evil Vagrant": "bandit",
    # Дилетант
    "Профессиональный Дилетант": "amateur",
    "Professional Amateur": "amateur",
    # Садист
    "Садистский Садист": "sadist",
    "Sadistic Sadist": "sadist",
    # Прокрастинатор
    "Стойкий Прокрастинатор": "slacker",
    "Stubborn Procrastinator": "slacker",
    # Фурри
    "Конвенционный Фурри": "furry",
    "Furry Convention": "furry",
    # Крабы
    "Клацающие Крабы": "crab",
    "Clacking Crabs": "crab",
    # Драконы
    "Позолоченный Дракон": "dragon",
    "Gilded Dragon": "dragon",
    "Дракон": "dragon",
    "Dragon": "dragon",
    # Вор
    "Удачливый Вор": "thief",
    "Lucky Thief": "thief",
    # Отряд
    "Военный Отряд": "military",
    "War Party": "military",
    # Бабуля
    "Бабуля": "undead",
    "Grandma": "undead",
    # Вампиры
    "Голодные Кровопийцы": "vampire",
    "Hungry Bloodsuckers": "vampire",
    "Теневой Вампир": "vampire",
    "Shadow Vampire": "vampire",
    # Пчела
    "Пчела": "bee",
    "Bee": "bee",
    # Лесоруб
    "Косолапый Лесоруб": "lumberjack",
    "Clumsy Lumberjack": "lumberjack",
    # Троглодит
    "Троглодит": "troglodyte",
    "Troglodyte": "troglodyte",
    # Големы
    "Ледяной Голе��": "golem",
    "Ice Golem": "golem",
    # Рыцари
    "Костяной Рыцарь": "undead_knight",
    "Bone Knight": "undead_knight",
    # Змеи
    "Морской Змей": "serpent",
    "Sea Serpent": "serpent",
    # Ведьмы
    "Кровавая Ведьма": "witch",
    "Blood Witch": "witch",
    # Элементали
    "Огненный Элементаль": "elemental",
    "Fire Elemental": "elemental",
    # Редис
    "Переросший Редис": "plant",
    "Giant Radish": "plant",
    # Кунзиле
    "Дух Кунзиле": "spirit",
    "Spirit of Kunzile": "spirit",
}

def _normalize_monster_type(monster_name: str) -> str:
    """Нормализовать имя монстра в тип для квестов"""
    if not monster_name:
        return ""
    return _MONSTER_TYPE_MAP.get(monster_name, "")


# ═══════════════════════════════════════════════════════════════
# QUEST PROGRESS NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════

QUEST_THRESHOLDS = [25, 50, 75]
THRESHOLD_ICONS = {
    25: "🔵",
    50: "🟡",
    75: "🟠",
}


async def send_quest_progress_notification(player: Player, quest: PlayerQuest, new_pct: int, bot=None):
    """Отправляет уведомление о прогрессе квеста при пороге 25%/50%/75%"""
    from bot import get_bot
    bot_instance = bot or get_bot()
    if bot_instance is None:
        return
    try:
        from bot import send_to_players
        
        icon = THRESHOLD_ICONS.get(new_pct, "⚪")
        lang = player.lang or "ru"
        
        if lang == "en":
            text = (
                f"{icon} *Quest Progress: {quest.title}*\n"
                f"Progress: {quest.progress}/{quest.target_count} ({new_pct}%)"
            )
        else:
            text = (
                f"{icon} *Прогресс квеста: {quest.title}*\n"
                f"Прогресс: {quest.progress}/{quest.target_count} ({new_pct}%)"
            )
        
        await send_to_players(bot_instance, text, player_uids=[player.uid], parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Quest progress notification error: {e}")


# ═══════════════════════════════════════════════════════════════
# QUEST PROGRESS CHECKER
# ═══════════════════════════════════════════════════════════════

async def check_quest_progress(
    player: Player,
    event_type: str,
    event_data: dict
):
    """
    Main функция проверки прогресса квестов.
    Вызывается из game events после побед, получения XP и т.д.
    
    Args:
        player: Игрок
        event_type: "monster_defeated" | "xp_gained" | "duel_win" | "location_enter" | "boss_defeated"
        event_data: {"target_id": "goblin", "amount": 100, и т.д.}
    """
    category = EVENT_TO_CATEGORY.get(event_type)
    if not category:
        return
    
    target_id = event_data.get("target_id", "*")
    
    quests = await PlayerQuest.objects.filter(
        player_uid=player.uid,
        category=category,
        status="active"
    ).all()
    
    for quest in quests:
        # Проверяем соответствие цели
        # Разрешаем: точный матч, *, пустой (любой), или нормализованный тип
        normalized_target = _normalize_monster_type(target_id)
        if quest.target_id not in (target_id, "*", "", normalized_target):
            continue
        
        # Проверяем дедлайн
        if is_expired(quest):
            await fail_quest(player, quest)
            continue

        # Проверяем порог для уведомления до увеличения
        old_progress = quest.progress
        old_pct = 0
        if quest.target_count > 1:
            old_pct = int(old_progress / quest.target_count * 100)

        # Увеличиваем прогресс
        quest.progress += 1
        quest.last_progress_at = int(time.time())

        # Проверяем новый порог
        new_pct = 0
        thresholds_passed = []
        if quest.target_count > 1:
            new_pct = int(quest.progress / quest.target_count * 100)
            for threshold in QUEST_THRESHOLDS:
                if old_pct < threshold <= new_pct:
                    thresholds_passed.append(threshold)

        if quest.progress >= quest.target_count:
            await complete_quest(player, quest)
        else:
            await quest.update()

        # Отправляем уведомления при порогах 25%/50%/75%
        for threshold in thresholds_passed:
            await send_quest_progress_notification(player, quest, threshold)


# ═══════════════════════════════════════════════════════════════
# EVENT TRIGGERS (вызывать из game code)
# ═══════════════════════════════════════════════════════════════

async def on_monster_defeated(player: Player, monster_type: str):
    """При победе над монстром"""
    await check_quest_progress(
        player,
        "monster_defeated",
        {"target_id": monster_type}
    )


async def on_xp_gained(player: Player, amount: int):
    """При получении XP"""
    await check_quest_progress(
        player,
        "xp_gained",
        {"target_id": "xp", "amount": amount}
    )


async def on_duel_win(player: Player):
    """При победе в дуэли"""
    await check_quest_progress(
        player,
        "duel_win",
        {"target_id": "player"}
    )


async def on_location_enter(player: Player, location_id: str):
    """При входе на локацию"""
    await check_quest_progress(
        player,
        "location_enter",
        {"target_id": location_id}
    )


async def on_level_reached(player: Player, new_level: int):
    """При повышении уровня — авто-выполнение level квестов"""
    await check_quest_progress(
        player,
        "level_up",
        {"target_id": str(new_level), "level": new_level}
    )


async def on_boss_defeated(player: Player, boss_id: str, team_size: int = 1):
    """При победе над боссом"""
    await check_quest_progress(
        player,
        "boss_defeated",
        {"target_id": boss_id, "team_size": team_size}
    )


# ═══════════════════════════════════════════════════════════════
# НОВЫЕ EVENT TRIGGERS: выживание, серия побед, редкий дроп
# ═══════════════════════════════════════════════════════════════

async def on_death(player: Player):
    """При проигрыше в бою (триггер для квестов выживания)"""
    await check_quest_progress(
        player,
        "death",
        {"target_id": "survive"}
    )


async def on_win_streak(player: Player, streak_count: int):
    """При победе в бою - обновляет серию побед"""
    await check_quest_progress(
        player,
        "win_streak",
        {"target_id": str(streak_count), "count": streak_count}
    )


async def on_rare_drop(player: Player, rarity: str):
    """При получении редкого/легендарного предмета"""
    await check_quest_progress(
        player,
        "rare_drop",
        {"target_id": rarity}
    )


# ═══════════════════════════════════════════════════════════════
# QUEST COMPLETION
# ═══════════════════════════════════════════════════════════════

async def complete_quest(player: Player, quest: PlayerQuest, bot=None):
    """Успешное выполнение квеста"""
    
    xp, gold = calculate_rewards(quest.quest_type, player.level)
    
    team_bonus = quest.category == "kill_boss"
    if team_bonus and quest.completed_at and quest.completed_at > 0:
        team_size = getattr(quest, "team_size", 1)
        if team_size > 1:
            xp = int(xp * min(1 + (team_size - 1) * 0.5, 2.5))
            gold = int(gold * min(1 + (team_size - 1) * 0.5, 2.5))
    
    player.totalxp += xp
    player.gold += gold
    await player.update(_columns=["totalxp", "gold"])
    
    quest.status = "completed"
    quest.completed_at = int(time.time())
    await quest.update()
    
    from bot import get_bot
    bot_instance = bot or get_bot()
    if bot_instance is None:
        return
    
    from bot import send_to_players
    
    text = f"✅ *Квест выполнен!*\n\n*{quest.title}*\n\n🎁 Награда:\n• XP: +{xp}\n• Золото: +{gold}"
    
    try:
        await send_to_players(bot_instance, text, player_uids=[player.uid], parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Quest complete notification error: {e}")


# ═══════════════════════════════════════════════════════════════════════
# QUEST FAILURE (TIMEOUT)
# ═══════════════════════════════════════════════════════════════

async def fail_quest(player: Player, quest: PlayerQuest, apply_penalty: bool = True, bot=None):
    """Проваленный квест (истёк дедлайн)"""
    
    if apply_penalty:
        xp_penalty, gold_penalty = calculate_penalty(quest.quest_type)
        
        player.totalxp = max(0, player.totalxp - xp_penalty)
        player.gold = max(0, player.gold - gold_penalty)
        
        if quest.quest_type == "story":
            player.align = max(-1000, player.align - 1)
        await player.update(_columns=["totalxp", "gold", "align"])
    
    quest.status = "failed"
    await quest.update()
    
    from bot import get_bot
    bot_instance = bot or get_bot()
    if bot_instance is None:
        return
    
    from bot import send_to_players
    text = f"❌ *Квест провален!*\n\n*{quest.title}*\n\nИстёк срок выполнения."
    
    try:
        await send_to_players(bot_instance, text, player_uids=[player.uid], parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Quest fail notification error: {e}")


# ═══════════════════════════════════════════════════════════════
# QUEST ABANDON
# ════════��══════════════════════════════════════════════════════

async def abandon_quest(player: Player, quest: PlayerQuest):
    """Отмена квеста игроком"""
    
    quest.status = "abandoned"
    quest.cooldown_until = int(time.time()) + 600  # 10 минут
    await quest.update()


# ═══════════════════════════════════════════════════════════════════════
# CHECK EXPIRED QUESTS (для loop)
# ═══════════════════════════════════════════════════════════════

async def check_expired_quests():
    """Проверяет истёкшие квесты"""
    
    now = int(time.time())
    
    expired = await PlayerQuest.objects.filter(
        status="active",
        expires_at__lt=now
    ).all()
    
    for quest in expired:
        player = await Player.objects.get_or_none(uid=quest.player_uid)
        if player:
            await fail_quest(player, quest)


# ═══════════════════════════════════════════════════════════════
# ACTIVE QUEST CHECKER
# ═══════════════════════════════════════════════════════════════

async def get_active_quests(player: Player) -> list[PlayerQuest]:
    """Получить активные квесты игрока"""
    return await PlayerQuest.objects.filter(
        player_uid=player.uid,
        status="active"
    ).all()


async def get_quest_count(player: Player, quest_type: str = None) -> int:
    """Количество активных кquest определённого типа"""
    query = PlayerQuest.objects.filter(
        player_uid=player.uid,
        status="active"
    )
    
    if quest_type:
        query = query.filter(quest_type=quest_type)
    
    return await query.count()


async def can_get_quest(player: Player, quest_type: str) -> bool:
    """Проверяет может ли игрок получить новый квест"""
    from data.quest_config import QUEST_TYPE_CONFIG, MAX_TOTAL_ACTIVE_QUESTS
    
    config = QUEST_TYPE_CONFIG.get(quest_type)
    if not config:
        return False
    
    now = int(time.time())
    if player.quest_cooldown < now:
        return False
    
    current = await get_quest_count(player, quest_type)
    return current < config.max_active


async def can_offer_new_quests(player: Player) -> bool:
    """
    Проверяет может ли игрок получить НОВЫЕ предложения квестов.
    Используется для анти-спам системы.
    """
    from data.quest_config import MAX_TOTAL_ACTIVE_QUESTS, QUEST_COMPLETE_REQUIRED_TO_OFFER
    
    active_or_offered = await PlayerQuest.objects.filter(
        player_uid=player.uid,
        status__in=["active", "offered"]
    ).count()
    
    if active_or_offered >= MAX_TOTAL_ACTIVE_QUESTS:
        return False
    
    if active_or_offered >= MAX_TOTAL_ACTIVE_QUESTS - QUEST_COMPLETE_REQUIRED_TO_OFFER:
        active_only = await PlayerQuest.objects.filter(
            player_uid=player.uid,
            status="active"
        ).count()
        if active_only >= MAX_TOTAL_ACTIVE_QUESTS:
            return False
    
    return True


async def get_quest_slots_available(player: Player) -> int:
    """Возвращает количество свободных слотов для квестов"""
    from data.quest_config import MAX_TOTAL_ACTIVE_QUESTS
    
    active = await PlayerQuest.objects.filter(
        player_uid=player.uid,
        status__in=["active", "offered"]
    ).count()
    
    return max(0, MAX_TOTAL_ACTIVE_QUESTS - active)