"""
game/quests.py — Event-based система прогресса квестов
Вызывается из game events при победах, XP, дуэлях и т.д.
"""
import logging
import time
from typing import Optional

import config as cfg
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
                f"{icon} <b>Quest Progress: {quest.title}</b>\n"
                f"Progress: {quest.progress}/{quest.target_count} ({new_pct}%)"
            )
        else:
            text = (
                f"{icon} <b>Прогресс квеста: {quest.title}</b>\n"
                f"Прогресс: {quest.progress}/{quest.target_count} ({new_pct}%)"
            )
        
        await send_to_players(bot_instance, text, player_uids=[player.uid], parse_mode="HTML")
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
    
    if event_type == "location_enter":
        quests = await PlayerQuest.objects.filter(
            player_uid=player.uid,
            category="explore_any",
            status="active"
        ).all()
    else:
        quests = await PlayerQuest.objects.filter(
            player_uid=player.uid,
            category=category,
            status="active"
        ).all()
    
    visited_locations = set()
    
    for quest in quests:
        # Проверяем соответствие цели
        # Разрешаем: точный матч, *, пустой (любой), или нормализованный тип
        normalized_target = _normalize_monster_type(target_id)
        if quest.target_id not in (target_id, "*", "", normalized_target):
            continue
        
        if quest.category == "explore_any" and target_id != "*":
            if target_id in visited_locations:
                continue
            visited_locations.add(target_id)
        
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
        if quest.category == "win_battle":
            quest.progress = max(quest.progress, event_data.get("count", 1))
        elif quest.category == "earn_xp":
            quest.progress += max(1, event_data.get("amount", 1))
        else:
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
    from game.pets import add_pet_xp
    try:
        await add_pet_xp(player, cfg.PET_XP_PER_KILL)
    except Exception:
        logging.exception("pet xp on kill error")
    from game.achievements import on_monster_defeated as _ach
    try:
        await _ach(player)
    except Exception:
        logging.exception("achievements on kill error")


async def on_xp_gained(player: Player, amount: int):
    """При получении XP"""
    await check_quest_progress(
        player,
        "xp_gained",
        {"target_id": "xp", "amount": amount}
    )
    from game.achievements import on_xp_gained as _ach
    try:
        await _ach(player)
    except Exception:
        logging.exception("achievements on xp error")


async def on_duel_win(player: Player):
    """При победе в дуэли"""
    await check_quest_progress(
        player,
        "duel_win",
        {"target_id": "player"}
    )
    from game.achievements import on_duel_win as _ach
    try:
        await _ach(player)
    except Exception:
        logging.exception("achievements on duel error")


async def on_location_enter(player: Player, location_id: str):
    """При входе на локацию"""
    await check_quest_progress(
        player,
        "location_enter",
        {"target_id": location_id}
    )


async def on_boss_defeated(player: Player, boss_id: str, team_size: int = 1):
    """При победе над боссом"""
    await check_quest_progress(
        player,
        "boss_defeated",
        {"target_id": boss_id, "team_size": team_size}
    )
    from game.pets import add_pet_xp, maybe_drop_pet
    try:
        await add_pet_xp(player, cfg.PET_XP_PER_BOSS)
        dropped = await maybe_drop_pet(player, "boss")
        if dropped:
            await _notify_pet_drop(player, dropped)
    except Exception:
        logging.exception("pet boss hook error")
    from game.achievements import on_boss_defeated as _ach
    try:
        await _ach(player)
    except Exception:
        logging.exception("achievements on boss error")


# ═══════════════════════════════════════════════════════════════
# НОВЫЕ EVENT TRIGGERS: выживание, серия побед, редкий дроп
# ═══════════════════════════════════════════════════════════════

async def on_death(player: Player):
    """При проигрыше в бою — сброс прогресса квестов серии/выживания."""
    quests = await PlayerQuest.objects.filter(
        player_uid=player.uid,
        category__in=["survive", "win_battle"],
        status="active"
    ).all()

    for quest in quests:
        if quest.progress > 0:
            quest.progress = 0
            quest.last_progress_at = int(time.time())
            await quest.update()


async def on_win_streak(player: Player, streak_count: int):
    """При победе в бою — обновляет серию побед и квесты выживания"""
    await check_quest_progress(
        player,
        "win_streak",
        {"target_id": "streak", "count": streak_count}
    )
    await check_quest_progress(
        player,
        "battle_won",
        {"target_id": "survive"}
    )
    from game.achievements import on_win_streak as _ach
    try:
        await _ach(player)
    except Exception:
        logging.exception("achievements on streak error")


async def on_rare_drop(player: Player, rarity: str):
    """При получении редкого/легендарного предмета"""
    await check_quest_progress(
        player,
        "rare_drop",
        {"target_id": rarity}
    )
    from game.achievements import on_rare_drop as _ach
    try:
        await _ach(player)
    except Exception:
        logging.exception("achievements on rare drop error")
    from game.pets import maybe_drop_pet
    try:
        dropped = await maybe_drop_pet(player, "rare")
        if dropped:
            await _notify_pet_drop(player, dropped)
    except Exception:
        logging.exception("pet rare drop hook error")


async def _notify_pet_drop(player: Player, pet_id: str):
    """Сообщить игроку о дропнувшемся питомце."""
    try:
        from game.pets import get_pet_config
        from bot import send_to_players, get_bot
        bot = get_bot()
        if bot is None:
            return
        conf = get_pet_config(pet_id) or {}
        lang = player.lang or "ru"
        name = conf.get("name_ru", pet_id) if lang != "en" else conf.get("name_en", pet_id)
        icon = conf.get("icon", "✨")
        if lang == "en":
            text = f"🎁 <b>New pet found!</b>\n{icon} {name} joined you! Check /pets"
        else:
            text = f"🎁 <b>Новый питомец найден!</b>\n{icon} {name} присоединился к тебе! Загляни в /pets"
        await send_to_players(bot, text, player_uids=[player.uid], parse_mode="HTML")
    except Exception as e:
        logging.error(f"Pet drop notification error: {e}")


# ═══════════════════════════════════════════════════════════════
# QUEST COMPLETION
# ═══════════════════════════════════════════════════════════════

async def complete_quest(player: Player, quest: PlayerQuest, bot=None):
    """Успешное выполнение квеста"""
    
    xp, gold = calculate_rewards(quest.quest_type, player.level)
    # ponytail: team_bonus для kill_boss удалён — колонки team_size в PlayerQuest нет,
    # getattr возвращал 1, блок был мёртв. Если командные квесты понадобятся — добавить
    # колонку team_size и пересчитать бонус здесь.
    
    # Prestige бонус XP
    from plugins.vip_shop import has_prestige_xp_bonus, has_prestige_gold_bonus, get_prestige_xp_multiplier, get_prestige_gold_multiplier
    if has_prestige_xp_bonus(player):
        prestige_mult = get_prestige_xp_multiplier(player)
        xp = int(xp * prestige_mult)
    
    # Prestige бонус Gold
    if has_prestige_gold_bonus(player):
        prestige_mult = get_prestige_gold_multiplier(player)
        gold = int(gold * prestige_mult)
    
    player.totalxp += xp
    player.gold += gold
    player.totalquests += 1
    tokens = getattr(quest, "bonus_tokens", 0) or 0
    if tokens:
        player.tokens = (player.tokens or 0) + tokens
    await player.update(_columns=["totalxp", "gold", "totalquests", "tokens"])
    
    quest.status = "completed"
    quest.completed_at = int(time.time())
    await quest.update()
    
    auto_mode = getattr(player, "auto_accept_quests", "off") or "off"
    
    from bot import get_bot
    bot_instance = bot or get_bot()
    if bot_instance is None:
        return
    
    if auto_mode == "silent":
        return
    
    from bot import send_to_players
    
    lang = player.lang or "ru"
    reward_lines = [f"• XP: +{xp}", f"• Gold: +{gold}"]
    if tokens:
        reward_lines.append(f"• 🎫 Tokens: +{tokens}")
    if lang == "en":
        text = f"✅ <b>Quest completed!</b>\n\n<b>{quest.title}</b>\n\n🎁 Reward:\n" + "\n".join(reward_lines)
    else:
        text = f"✅ <b>Квест выполнен!</b>\n\n<b>{quest.title}</b>\n\n🎁 Награда:\n" + "\n".join(reward_lines)
    
    try:
        await send_to_players(bot_instance, text, player_uids=[player.uid], parse_mode="HTML")
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
        
        await player.update(_columns=["totalxp", "gold"])
    
    quest.status = "failed"
    await quest.update()
    
    from bot import get_bot
    bot_instance = bot or get_bot()
    if bot_instance is None:
        return
    
    from bot import send_to_players
    lang = player.lang or "ru"
    if lang == "en":
        text = f"❌ <b>Quest failed!</b>\n\n<b>{quest.title}</b>\n\nDeadline expired."
    else:
        text = f"❌ <b>Квест провален!</b>\n\n<b>{quest.title}</b>\n\nИстёк срок выполнения."
    
    try:
        await send_to_players(bot_instance, text, player_uids=[player.uid], parse_mode="HTML")
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
    from data.quest_config import QUEST_TYPE_CONFIG, get_max_slots_for_player, get_slot_cost
    
    config = QUEST_TYPE_CONFIG.get(quest_type)
    if not config:
        return False
    
    now = int(time.time())
    if player.quest_cooldown > now:
        return False
    
    current = await get_quest_count(player, quest_type)
    if current >= config.max_active:
        return False
    
    active_quests = await PlayerQuest.objects.filter(
        player_uid=player.uid,
        status="active"
    ).all()
    
    used_slots = sum(get_slot_cost(q.quest_type) for q in active_quests)
    max_slots = get_max_slots_for_player(player.level)
    
    return (used_slots + get_slot_cost(quest_type)) <= max_slots


async def get_quest_slots_available(player: Player) -> int:
    """Возвращает количество свободных слотов для квестов"""
    from data.quest_config import get_max_slots_for_player, get_slot_cost
    
    active_quests = await PlayerQuest.objects.filter(
        player_uid=player.uid,
        status="active"
    ).all()
    
    used_slots = sum(get_slot_cost(q.quest_type) for q in active_quests)
    max_slots = get_max_slots_for_player(player.level)
    
    return max(0, max_slots - used_slots)


# ═══════════════════════════════════════════════════════════════
# QUEST CLEANUP FUNCTIONS
# ═══════════════════════════════════════════════════════════════

async def cleanup_expired_offers():
    """Удаляет предложенные/просроченные/отклонённые квесты старше N минут."""
    import time
    from data.quest_config import OFFERED_EXPIRE_MINUTES
    
    expire_threshold = int(time.time()) - (OFFERED_EXPIRE_MINUTES * 60)
    
    expired_offers = await PlayerQuest.objects.filter(
        status__in=["offered", "expired", "declined"],
        created_at__lt=expire_threshold
    ).all()
    
    count = len(expired_offers)
    for quest in expired_offers:
        await quest.delete()
    
    if count > 0:
        logging.info(f"Cleaned up {count} expired/declined/offered quest offers")
    
    return count


async def cleanup_old_completed_quests(days: int = 7):
    """Удаляет старые выполненные/проваленные/отмененные квесты."""
    import time
    from datetime import datetime, timedelta
    
    threshold = int((datetime.now() - timedelta(days=days)).timestamp())
    
    old_quests = await PlayerQuest.objects.filter(
        status__in=["completed", "failed", "abandoned"],
        completed_at__lt=threshold
    ).all()
    
    count = len(old_quests)
    for quest in old_quests:
        await quest.delete()
    
    if count > 0:
        logging.info(f"Cleaned up {count} old completed/failed quests")
    
    return count


async def cleanup_player_quests(player: Player) -> int:
    """Полная очистка всех неактивных квестов игрока."""
    from datetime import datetime, timedelta
    
    threshold = int((datetime.now() - timedelta(days=30)).timestamp())
    
    old_quests = await PlayerQuest.objects.filter(
        player_uid=player.uid,
        status__in=["completed", "failed", "abandoned"],
        completed_at__lt=threshold
    ).all()
    
    count = len(old_quests)
    for quest in old_quests:
        await quest.delete()
    
    return count


async def archive_completed_quest(quest: PlayerQuest) -> bool:
    """Архивирует выполненный квест (для будущего использования)."""
    import time
    
    quest.status = "archived"
    quest.archived_at = int(time.time())
    await quest.update()
    return True


# ═══════════════════════════════════════════════════════════════
# UPDATED QUEST OFFER LOGIC
# ═══════════════════════════════════════════════════════════════

async def can_offer_new_quests(player: Player) -> bool:
    """
    Проверяет может ли игрок получить НОВЫЕ предложения квестов.
    Теперь считает только active квесты (offered не блокируют).
    """
    from data.quest_config import get_max_slots_for_player, get_slot_cost, QUEST_COMPLETE_REQUIRED_TO_OFFER
    
    active_quests = await PlayerQuest.objects.filter(
        player_uid=player.uid,
        status="active"
    ).all()
    
    used_slots = sum(get_slot_cost(q.quest_type) for q in active_quests)
    max_slots = get_max_slots_for_player(player.level)
    
    if used_slots >= max_slots:
        return False
    
    if used_slots >= max_slots - QUEST_COMPLETE_REQUIRED_TO_OFFER:
        completed_recent = await PlayerQuest.objects.filter(
            player_uid=player.uid,
            status="completed"
        ).order_by("-completed_at").limit(1).all()
        
        if not completed_recent:
            return False
    
    return True


async def get_available_quest_types(player: Player) -> list[str]:
    """Возвращает типы квестов, которые доступны игроку."""
    from data.quest_config import QUEST_TYPE_CONFIG, get_slot_cost, get_max_slots_for_player
    
    active_quests = await PlayerQuest.objects.filter(
        player_uid=player.uid,
        status="active"
    ).all()
    
    used_slots = sum(get_slot_cost(q.quest_type) for q in active_quests)
    max_slots = get_max_slots_for_player(player.level)
    
    available_types = []
    for quest_type, config in QUEST_TYPE_CONFIG.items():
        current_of_type = sum(1 for q in active_quests if q.quest_type == quest_type)
        slot_cost = get_slot_cost(quest_type)
        
        if current_of_type < config.max_active and (used_slots + slot_cost) <= max_slots:
            available_types.append(quest_type)
    
    return available_types


async def endquest(bot, quest, win: bool = True):
    """Завершить глобальный квест из старой системы (модель Quest)."""
    from bot import send_to_players
    en_status = "✅ Victory!" if win else "❌ Defeat"
    ru_status = "✅ Победа!" if win else "❌ Провал"
    text = f"*Global quest completed!* / *Глобальный квест завершён!*\n\n{en_status} / {ru_status}\n\n*{quest.goal}*"
    try:
        await send_to_players(bot, text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Global endquest notification error: {e}")
    await quest.delete()