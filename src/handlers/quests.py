"""
handlers/quests.py — обработчики квестов
- /myquests — мои активные квесты
- Принятие/отказ от квеста
- Уведомления при входе на локацию с квестами
"""
import asyncio
import logging
import random
import time
from datetime import datetime
import datetime as datetime_module
from typing import Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes

from db import Player, PlayerQuest
import config as cfg
from data.locations import find_location, format_location
from core.telegram_utils import safe_edit
from ui.icons import SEP, QUEST_CAT
from ui.bars import quest_bar

_offer_messages: dict[str, tuple[int, int]] = {}


async def _auto_expire_offer(bot, quest_key: str, chat_id: int, message_id: int):
    """Удалить квест и сообщение через 60 сек, если не принят."""
    await asyncio.sleep(60)
    try:
        quest = await PlayerQuest.objects.get_or_none(quest_key=quest_key)
        if quest and quest.status == "offered":
            quest.status = "expired"
            quest.completed_at = int(time.time())
            await quest.update()
        _offer_messages.pop(quest_key, None)
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            pass
    except Exception:
        pass


def t(key: str, lang: str = "ru", **kwargs) -> str:
    """Translate string."""
    from i18n import STRINGS
    s = STRINGS.get(lang, {}).get(key, key)
    if kwargs:
        s = s.format(**kwargs)
    return s


async def get_player_quests(player) -> list:
    """Получить активные квесты игрока."""
    try:
        return await PlayerQuest.objects.filter(
            player_uid=player.uid,
            status="active"
        ).all()
    except Exception:
        return []


async def get_player_locked_quest(player) -> Optional[PlayerQuest]:
    """Получить активный квест с блокировкой локации."""
    try:
        return await PlayerQuest.objects.filter(
            player_uid=player.uid,
            status="active",
            location_locked=True
        ).first()
    except Exception:
        return None


def _quest_text(quests, player, lang: str) -> str:
    """Построить текст квестборда."""
    from data.quest_config import get_max_slots_for_player, get_slot_cost
    
    max_slots = get_max_slots_for_player(player.level)
    used_slots = sum(get_slot_cost(q.quest_type) for q in quests)
    
    lines = [
        "🎯 <b>КВЕСТБОРД</b>" if lang != "en" else "🎯 <b>QUEST BOARD</b>",
        f"⚡ Слоты: <b>{used_slots}/{max_slots}</b>" if lang != "en" else f"⚡ Slots: <b>{used_slots}/{max_slots}</b>",
        SEP,
    ]
    
    for i, q in enumerate(quests, 1):
        icon = QUEST_CAT.get(q.category, "📋")
        bar = quest_bar(q.progress, q.target_count)
        deadline = ""
        if q.expires_at:
            left = q.expires_at - int(time.time())
            if left > 0:
                hours = left // 3600
                minutes = (left % 3600) // 60
                deadline = f" ⏰ {hours}ч {minutes}мин" if lang != "en" else f" ⏰ {hours}h {minutes}m"
            else:
                deadline = " ⛔"
        
        lines.append(f"<b>{i}.</b> {icon} <b>{q.title}</b>")
        lines.append(f"   {bar} {q.progress}/{q.target_count}{deadline}")
        lines.append(f"   🎁 +{q.reward_xp} XP, +{q.reward_gold} Gold")
        lines.append("")
    
    if not quests:
        no_slots = f"⚡ Слоты: <b>0/{max_slots}</b>" if lang != "en" else f"⚡ Slots: <b>0/{max_slots}</b>"
        lines.extend([
            no_slots, "",
            t(lang, "quest_no_quests"),
        ])
    
    return "\n".join(lines)


def _quest_keyboard(quests, max_slots: int, used_slots: int, lang: str) -> InlineKeyboardMarkup:
    """Построить клавиатуру квестборда."""
    rows = []
    for i, q in enumerate(quests):
        abandon_label = "🚫 Отменить" if lang != "en" else "🚫 Abandon"
        rows.append([InlineKeyboardButton(f"{abandon_label} {i+1}",
                     callback_data=f"quest_abandon_{q.quest_key}")])
    
    if used_slots < max_slots:
        rows.append([InlineKeyboardButton(
            "＋ Взять квест" if lang != "en" else "＋ New quest",
            callback_data="quest_new"
        )])
    
    rows.append([
        InlineKeyboardButton("🔄", callback_data="menu_quest"),
        InlineKeyboardButton("🏠", callback_data="menu_back"),
    ])
    
    return InlineKeyboardMarkup(rows)


async def cmd_myquests(update, context):
    """Показать квестборд — HTML mode."""
    player = await Player.objects.get_or_none(uid=update.effective_user.id)
    if not player:
        await update.message.reply_text(t("not_registered", "ru"))
        return

    lang = player.lang or "ru"
    
    quests = await PlayerQuest.objects.filter(
        player_uid=player.uid,
        status="active"
    ).all()
    
    from data.quest_config import get_max_slots_for_player, get_slot_cost
    max_slots = get_max_slots_for_player(player.level)
    used_slots = sum(get_slot_cost(q.quest_type) for q in quests)
    
    text = _quest_text(quests, player, lang)
    keyboard = _quest_keyboard(quests, max_slots, used_slots, lang)
    
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def accept_quest_callback(update, context):
    """Принять квест."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    if len(parts) < 3:
        return

    quest_id = "_".join(parts[2:])
    player = await Player.objects.get_or_none(uid=query.from_user.id)
    if not player:
        return

    lang = player.lang or "ru"

    try:
        quest = await PlayerQuest.objects.filter(
            quest_key=quest_id,
            player_uid=player.uid
        ).get_or_none()
        
        if quest:
            quest.status = "active"
            await quest.update(_columns=["status"])
            text = t("location_quest_accept", lang)
            await safe_edit(query, text, parse_mode="HTML")
        else:
            quest = await PlayerQuest.objects.filter(
                quest_id_str=quest_id,
                player_uid=player.uid
            ).get_or_none()
            if not quest:
                quest = await PlayerQuest.objects.filter(
                    quest_id=quest_id,
                    player_uid=player.uid
                ).get_or_none()
            if quest:
                quest.status = "active"
                await quest.update(_columns=["status"])
                text = t("location_quest_accept", lang)
                await safe_edit(query, text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Accept quest error: {e}", exc_info=True)
        pass


async def decline_quest_callback(update, context):
    """Отказаться от квеста."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    if len(parts) < 3:
        return

    quest_id = "_".join(parts[2:])
    player = await Player.objects.get_or_none(uid=query.from_user.id)
    if not player:
        return

    lang = player.lang or "ru"

    try:
        quest = await PlayerQuest.objects.filter(
            quest_key=quest_id,
            player_uid=player.uid
        ).get_or_none()
        
        if not quest:
            quest = await PlayerQuest.objects.filter(
                quest_id_str=quest_id,
                player_uid=player.uid
            ).get_or_none()
        
        if quest:
            await quest.delete()
        
        text = t("location_quest_decline", lang)
        await safe_edit(query, text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Decline quest error: {e}")
        pass


QUEST_OFFER_COOLDOWN = 300
QUEST_LOCATION_COOLDOWN = 180


async def offer_quest(bot, player, quest_type, location=None):
    """Предложить квест игроку - создаёт и отправляет уведомление"""
    from data.quests import generate_quest
    from data.quest_config import get_max_slots_for_player
    from game.quests import get_quest_slots_available, can_offer_new_quests
    
    player_lang = player.lang or "ru"
    
    now = int(time.time())
    if not player.online or (now - (player.lastlogin or 0)) > cfg.OFFLINE_TIMEOUT:
        return None
    
    recent_any = await PlayerQuest.objects.filter(
        player_uid=player.uid
    ).order_by("-created_at").limit(1).all()
    if recent_any:
        last_time = recent_any[0].created_at
        if isinstance(last_time, (int, float)) and (now - last_time) < QUEST_OFFER_COOLDOWN:
            return None
    
    if not await can_offer_new_quests(player):
        slots = await get_quest_slots_available(player)
        max_slots = get_max_slots_for_player(player.level)
        if slots <= 0:
            text = (
                f"🎯 <b>{'Quests unavailable' if player_lang == 'en' else 'Квесты недоступны'}</b>\n\n"
                f"{'You already have' if player_lang == 'en' else 'У тебя уже'} <b>{max_slots}</b> "
                f"{'active quests. Complete at least one to get a new one!' if player_lang == 'en' else 'активных квестов. Заверши хотя бы один, чтобы получить новый!'}"
            )
            await bot.send_message(
                chat_id=player.uid,
                text=text,
                parse_mode="HTML"
            )
        return None
    
    recent_threshold = int(time.time()) - (7 * 24 * 3600)
    
    quest_data = generate_quest(player, quest_type, location, player_lang)
    if not quest_data:
        return None
    
    target_id = quest_data.get("target_id", "")
    if target_id != "*":
        for attempt in range(5):
            recent_quests = await PlayerQuest.objects.filter(
                player_uid=player.uid,
                target_id=target_id,
                category=quest_data["category"],
                status__in=["completed", "active", "offered"],
                completed_at__gt=recent_threshold
            ).all()
            if not recent_quests:
                break
            quest_data = generate_quest(player, quest_type, None, player_lang)
            if not quest_data:
                return None
            target_id = quest_data.get("target_id", "")
            if target_id == "*":
                break
        else:
            return None
    
    quest = await PlayerQuest.objects.create(
        player_uid=player.uid,
        quest_id=0,
        quest_id_str="",
        location_name="",
        location_x=0,
        location_y=0,
        quest_key=quest_data["quest_key"],
        quest_type=quest_data["quest_type"],
        category=quest_data["category"],
        title=quest_data["title"],
        description=quest_data["description"],
        location_id=quest_data.get("location_id", ""),
        target_type=quest_data.get("target_type", ""),
        target_id=quest_data.get("target_id", ""),
        target_count=quest_data["target_count"],
        progress=0,
        reward_xp=quest_data["reward_xp"],
        reward_gold=quest_data.get("reward_gold", 0),
        reward_item=quest_data.get("reward_item", ""),
        status="offered",
        expires_at=quest_data.get("expires_at", 0),
        created_at=int(time.time()),
    )
    
    auto_mode = player.auto_accept_quests or "off"
    
    if auto_mode != "off":
        from handlers.quests import schedule_auto_accept
        await schedule_auto_accept(player.uid, quest.quest_key, auto_mode, bot)
        
        if auto_mode == "notify":
            accept_notify = "Принятие через 1 сек..." if player_lang != "en" else "Accepting in 1 sec..."
            await bot.send_message(
                chat_id=player.uid,
                text=f"🎯 <b>{quest.title}</b>\n\n{accept_notify}",
                parse_mode="HTML"
            )
        return quest
    else:
        accept_label = "✅ Принять" if player_lang != "en" else "✅ Accept"
        decline_label = "❌ Отказаться" if player_lang != "en" else "❌ Decline"
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(accept_label, callback_data=f"quest_accept_{quest.quest_key}"),
                InlineKeyboardButton(decline_label, callback_data=f"quest_decline_{quest.quest_key}"),
            ]
        ])
        
        quest_header = "🎯 <b>Новый квест!</b>" if player_lang != "en" else "🎯 <b>New quest!</b>"
        reward_label = "🎁 Награда: " if player_lang != "en" else "🎁 Reward: "
        text = (
            f"{quest_header}\n\n"
            f"<b>{quest.title}</b>\n\n"
            f"{quest.description}\n\n"
            f"{reward_label}+{quest.reward_xp} XP, +{quest.reward_gold} Gold"
        )
        
        msg = await bot.send_message(
            chat_id=player.uid,
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        _offer_messages[quest.quest_key] = (player.uid, msg.message_id)
        asyncio.create_task(_auto_expire_offer(bot, quest.quest_key, player.uid, msg.message_id))
    
    return quest


async def check_location_quests(bot, player):
    """Проверить квесты при входе на локацию."""
    if not player:
        return

    if not player.online:
        return
    now = int(time.time())
    if (now - (player.lastlogin or 0)) > cfg.OFFLINE_TIMEOUT:
        return

    from game.quests import can_offer_new_quests, get_quest_slots_available

    if not await can_offer_new_quests(player):
        return

    loc = find_location(player.x, player.y, radius=30)
    if not loc:
        return

    if not loc.get("quest_enabled", False):
        return

    recent = await PlayerQuest.objects.filter(
        player_uid=player.uid,
        location_id=loc.get("id", ""),
        status__in=["active", "offered", "expired"]
    ).all()

    if recent:
        return

    recent_offers = await PlayerQuest.objects.filter(
        player_uid=player.uid,
        status__in=["active", "offered", "expired"]
    ).order_by("-created_at").limit(1).all()

    if recent_offers:
        last_time = recent_offers[0].created_at
        if isinstance(last_time, (int, float)):
            if time.time() - last_time < QUEST_OFFER_COOLDOWN:
                return

    recent_loc_offer = await PlayerQuest.objects.filter(
        player_uid=player.uid,
        location_id=loc.get("id", ""),
    ).order_by("-created_at").limit(1).all()

    if recent_loc_offer:
        loc_time = recent_loc_offer[0].created_at
        if isinstance(loc_time, (int, float)):
            if time.time() - loc_time < QUEST_LOCATION_COOLDOWN:
                return

    if await get_quest_slots_available(player) <= 0:
        return

    await offer_quest(bot, player, quest_type="explore", location=loc)


def find_location_by_id(loc_id: str) -> Optional[dict]:
    """Найти локацию по ID."""
    from data.locations import load_locations
    locations = load_locations()
    for loc in locations:
        if loc.get("id") == loc_id:
            return loc
    return None


async def update_quest_progress(player, quest_type: str, amount: int = 1):
    """Обновить прогресс квеста."""
    try:
        quests = await PlayerQuest.objects.filter(
            player_uid=player.uid,
            quest_type=quest_type,
            status="active"
        ).all()

        for quest in quests:
            quest.progress += amount
            if quest.progress >= quest.target_count:
                quest.status = "completed"
                quest.completed_at = int(datetime.now().timestamp())
                player.totalquests = (player.totalquests or 0) + 1
                
                if quest.location_locked:
                    quest.location_locked = False
                    quest.target_location_id = ""
                
                await quest.update()
                await player.update(_columns=["totalquests"])
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# AUTO ACCEPT QUEST SCHEDULER
# ═══════════════════════════════════════════════════════════════

async def schedule_auto_accept(player_uid: int, quest_key: str, mode: str, bot):
    """Авто-принятие квеста через 1 секунду"""
    await asyncio.sleep(1)
    
    player = await Player.objects.get_or_none(uid=player_uid)
    if not player:
        return
    
    quest = await PlayerQuest.objects.get_or_none(quest_key=quest_key, player_uid=player_uid)
    if not quest or quest.status != "offered":
        return
    
    quest.status = "active"
    quest.accepted_at = int(time.time())
    quest.expires_at = quest.expires_at or (int(time.time()) + 86400)
    await quest.update()
    
    player.onquest = True
    await player.update(_columns=["onquest"])
    
    if mode == "notify":
        from data.quest_config import calculate_rewards
        from i18n import t
        from bot import send_to_players
        
        xp, gold = calculate_rewards(quest.quest_type, player.level)
        lang = player.lang or "ru"
        
        text = f"✅ {t(lang, 'quest_accepted')} <b>{quest.title}</b>\n\n🎁 XP: +{xp} 💰 +{gold}"
        await send_to_players(bot, text, player_uids=[player_uid], parse_mode="HTML")


# ═══════════════════════════════════════════════════════════════
# SHOW PLAYER QUESTS
# ═══════════════════════════════════════════════════════════════

async def show_player_quests(bot, player):
    """Показать список активных квестов — HTML mode"""
    lang = player.lang or "ru"
    
    quests = await PlayerQuest.objects.filter(
        player_uid=player.uid,
        status="active"
    ).all()
    
    if not quests:
        text = f"{t(lang, 'quest_my_quests')}\n\n{t(lang, 'quest_no_quests')}"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t(lang, "menu"), callback_data="menu_back")]
        ])
        await bot.send_message(
            chat_id=player.uid,
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        return
    
    text = _quest_text(quests, player, lang)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "refresh"), callback_data="menu_quest")],
        [InlineKeyboardButton(t(lang, "menu"), callback_data="menu_back")]
    ])
    
    await bot.send_message(
        chat_id=player.uid,
        text=text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


# ═══════════════════════════════════════════════════════════════
# QUEST DETAIL
# ═══════════════════════════════════════════════════════════════

async def callback_quest_detail(update, context):
    """Показать подробности квеста — HTML mode"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    if len(parts) < 3:
        return
    
    player = await Player.objects.get_or_none(uid=query.from_user.id)
    if not player:
        return
    lang = player.lang or "ru"
    
    quest_key = "_".join(parts[2:])
    quest = await PlayerQuest.objects.filter(quest_key=quest_key).get_or_none()
    
    if not quest:
        await safe_edit(query, "❌ Quest not found" if lang == "en" else "❌ Квест не найден")
        return
    
    if quest.player_uid != player.uid:
        return
    
    bar = quest_bar(quest.progress, quest.target_count)
    
    deadline = ""
    penalty = ""
    if quest.expires_at:
        left = quest.expires_at - int(time.time())
        if left > 0:
            hours = left // 3600
            minutes = (left % 3600) // 60
            if lang != "en":
                deadline = f"⏰ Осталось: {hours}ч {minutes}мин"
                penalties = {"explore": quest.reward_xp // 10, "kill": 50, "boss": 200, "duel": 25}
                p = penalties.get(quest.quest_type, 10)
                penalty = f"❌ Штраф: -{p} XP"
            else:
                deadline = f"⏰ Left: {hours}h {minutes}m"
                penalties = {"explore": quest.reward_xp // 10, "kill": 50, "boss": 200, "duel": 25}
                p = penalties.get(quest.quest_type, 10)
                penalty = f"❌ Penalty: -{p} XP"
        else:
            deadline = "⛔ Просрочен" if lang != "en" else "⛔ Expired"
    
    text = f"🎯 <b>{quest.title}</b> ({quest.status})\n\n"
    
    if quest.location_id:
        text += f"{'📍 Локация: ' if lang != 'en' else '📍 Location: '}{quest.location_id}\n"
    
    text += f"{'⏳ Прогресс: ' if lang != 'en' else '⏳ Progress: '}{bar} {quest.progress}/{quest.target_count}\n"
    
    if deadline:
        text += f"{deadline}\n\n"
    
    text += f"{'🎁 Награда: ' if lang != 'en' else '🎁 Reward: '}+{quest.reward_xp} XP, +{quest.reward_gold} Gold"
    
    if penalty:
        text += f"\n{penalty}"
    
    if quest.status == "active":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "🚫 Отменить" if lang != "en" else "🚫 Abandon",
                callback_data=f"quest_abandon_{quest.quest_key}"
            )],
            [InlineKeyboardButton(t(lang, "back"), callback_data="menu_quest")]
        ])
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t(lang, "back"), callback_data="menu_quest")]
        ])
    
    await safe_edit(query, text, parse_mode="HTML", reply_markup=keyboard)


# ═══════════════════════════════════════════════════════════════
# NEW SYSTEM CALLBACKS
# ═══════════════════════════════════════════════════════════════

async def accept_quest_callback_new(update, context):
    """Принять квест (новая система с UUID) — HTML mode."""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    if len(parts) < 3:
        return
    
    player = await Player.objects.get_or_none(uid=query.from_user.id)
    if not player:
        return
    lang = player.lang or "ru"
    
    quest_key = "_".join(parts[2:])
    quest = await PlayerQuest.objects.filter(quest_key=quest_key).get_or_none()
    
    if not quest:
        await safe_edit(query, "❌ Quest not found" if lang == "en" else "❌ Квест не найден")
        return
    
    if quest.player_uid != player.uid:
        return
    
    if quest.status != "offered":
        await safe_edit(query, "⏰ Квест уже принят или неактивен" if lang != "en" else "⏰ Quest already accepted or inactive")
        return
    
    deadline = ""
    if quest.expires_at:
        left = quest.expires_at - int(time.time())
        if left > 0:
            hours = left // 3600
            minutes = (left % 3600) // 60
            if lang != "en":
                deadline = f"\n⏰ Срок: {hours}ч {minutes}мин"
            else:
                deadline = f"\n⏰ Deadline: {hours}h {minutes}m"
        else:
            deadline = "\n⛔ Просрочен" if lang != "en" else "\n⛔ Expired"
    
    _offer_messages.pop(quest_key, None)
    quest.status = "active"
    quest.accepted_at = int(time.time())
    await quest.update()
    
    goal_label = "🎯 Цель: " if lang != "en" else "🎯 Goal: "
    reward_label = "🎁 Награда: " if lang != "en" else "🎁 Reward: "
    auto_label = "<i>Квест выполняется автоматически!</i>" if lang != "en" else "<i>Quest runs automatically!</i>"
    text = (
        f"{t(lang, 'quest_accepted')}\n\n"
        f"<b>{quest.title}</b>\n\n"
        f"{quest.description}\n\n"
        f"{goal_label}{quest.target_id} ({quest.progress}/{quest.target_count})\n"
        f"{reward_label}+{quest.reward_xp} XP, +{quest.reward_gold} Gold"
        f"{deadline}\n\n"
        f"{auto_label}"
    )
    await safe_edit(query, text, parse_mode="HTML")


async def decline_quest_callback_new(update, context):
    """Отклонить квест (новая система с UUID) — HTML mode."""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    if len(parts) < 3:
        return
    
    player = await Player.objects.get_or_none(uid=query.from_user.id)
    if not player:
        return
    lang = player.lang or "ru"
    
    quest_key = "_".join(parts[2:])
    quest = await PlayerQuest.objects.filter(quest_key=quest_key).get_or_none()
    
    if not quest:
        msg_info = _offer_messages.pop(quest_key, None)
        if msg_info:
            try:
                await query.message.delete()
            except Exception:
                await safe_edit(query, "❌ Quest not found" if lang == "en" else "❌ Квест не найден")
        else:
            await safe_edit(query, "❌ Quest not found" if lang == "en" else "❌ Квест не найден")
        return
    
    if quest.player_uid != player.uid:
        return
    
    _offer_messages.pop(quest_key, None)
    quest.status = "declined"
    quest.completed_at = int(time.time())
    await quest.update()
    
    try:
        await query.message.delete()
    except Exception:
        await safe_edit(query, t(lang, "location_quest_decline"))


async def abandon_quest_callback(update, context):
    """Отменить квест — HTML mode."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    if len(parts) < 3:
        return

    player = await Player.objects.get_or_none(uid=query.from_user.id)
    if not player:
        return
    lang = player.lang or "ru"

    quest_key = "_".join(parts[2:])
    quest = await PlayerQuest.objects.filter(quest_key=quest_key).get_or_none()

    if not quest:
        await safe_edit(query, "❌ Quest not found" if lang == "en" else "❌ Квест не найден")
        return

    if quest.player_uid != player.uid:
        return
    if quest.status != "active":
        await safe_edit(query, "⏰ Квест неактивен" if lang != "en" else "⏰ Quest inactive")
        return

    quest.status = "abandoned"
    quest.cooldown_until = int(time.time()) + 600
    quest.location_locked = False
    quest.target_location_id = ""
    await quest.update()

    abandon_msg = "🚫 Квест отменён\n\n⏱️ 10 минут кулдаун" if lang != "en" else "🚫 Quest cancelled\n\n⏱️ 10 min cooldown"
    await safe_edit(query, abandon_msg)


async def cmd_quest_new(update, context):
    """Показать выбор типа нового квеста — HTML mode."""
    query = update.callback_query
    await query.answer()
    player = await Player.objects.get_or_none(uid=query.from_user.id)
    lang = (player.lang or "ru") if player else "ru"
    
    from game.quests import get_available_quest_types
    available = await get_available_quest_types(player)
    
    TYPE_ICONS = {
        "kill": "🗡️", "explore": "📍", "xp": "💰", "duel": "🤺",
        "boss": "🐉", "survive": "💀", "streak": "🔥", "rare": "💎",
    }
    TYPE_NAMES_RU = {
        "kill": "Убить монстров", "explore": "Исследовать", "xp": "Заработать XP",
        "duel": "Победа в дуэли", "boss": "Убить босса",
        "survive": "Выживание", "streak": "Серия побед", "rare": "Редкий предмет",
    }
    TYPE_NAMES_EN = {
        "kill": "Kill monsters", "explore": "Explore", "xp": "Earn XP",
        "duel": "Win duel", "boss": "Kill boss",
        "survive": "Survive", "streak": "Win streak", "rare": "Rare item",
    }
    
    type_names = TYPE_NAMES_RU if lang == "ru" else TYPE_NAMES_EN
    
    rows = []
    for qt in available:
        icon = TYPE_ICONS.get(qt, "📋")
        name = type_names.get(qt, qt)
        rows.append([InlineKeyboardButton(f"{icon} {name}",
                     callback_data=f"quest_take_{qt}")])
    
    rows.append([InlineKeyboardButton(t(lang, "back"), callback_data="menu_quest")])
    
    text = "🎯 <b>Новый квест</b>\n\nВыбери тип:" if lang != "en" else "🎯 <b>New quest</b>\n\nChoose type:"
    await safe_edit(query, text, parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(rows))


async def take_quest_callback(update, context):
    """Взять квест выбранного типа — HTML mode."""
    query = update.callback_query
    await query.answer()
    player = await Player.objects.get_or_none(uid=query.from_user.id)
    if not player:
        return

    lang = player.lang or "ru"
    parts = query.data.split("_")
    if len(parts) < 3:
        return
    quest_take_type = parts[2]

    from data.quests import generate_quest
    from data.quest_config import get_max_slots_for_player
    from game.quests import get_quest_slots_available, can_offer_new_quests

    if not await can_offer_new_quests(player):
        await safe_edit(query, "❌ Нет свободных слотов для квестов" if lang != "en" else "❌ No free quest slots")
        return

    quest_data = generate_quest(player, quest_take_type, location=None, lang=lang)
    if not quest_data:
        await safe_edit(query, "❌ Не удалось создать квест" if lang != "en" else "❌ Failed to create quest")
        return

    quest = await PlayerQuest.objects.create(
        player_uid=player.uid,
        quest_id=0,
        quest_id_str="",
        location_name="",
        location_x=0,
        location_y=0,
        quest_key=quest_data["quest_key"],
        quest_type=quest_data["quest_type"],
        category=quest_data["category"],
        title=quest_data["title"],
        description=quest_data["description"],
        location_id=quest_data.get("location_id", ""),
        target_type=quest_data.get("target_type", ""),
        target_id=quest_data.get("target_id", ""),
        target_count=quest_data["target_count"],
        progress=0,
        reward_xp=quest_data["reward_xp"],
        reward_gold=quest_data.get("reward_gold", 0),
        reward_item=quest_data.get("reward_item", ""),
        status="active",
        expires_at=quest_data.get("expires_at", 0),
        created_at=int(time.time()),
    )

    text = (
        f"{t(lang, 'quest_accepted')}\n\n"
        f"<b>{quest.title}</b>\n\n"
        f"{quest.description}\n\n"
        f"🎯 {quest.progress}/{quest.target_count}\n"
        f"🎁 +{quest.reward_xp} XP, +{quest.reward_gold} Gold"
    )
    await safe_edit(query, text, parse_mode="HTML")


def register_handlers(app):
    """Регистрация обработчиков квестов."""
    app.add_handler(CommandHandler("myquests", cmd_myquests))
    app.add_handler(CommandHandler("quests", cmd_myquests))
    app.add_handler(CallbackQueryHandler(accept_quest_callback, pattern="^quest_accept_"))
    app.add_handler(CallbackQueryHandler(accept_quest_callback_new, pattern="^quest_accept_new_"))
    app.add_handler(CallbackQueryHandler(decline_quest_callback, pattern="^quest_decline_"))
    app.add_handler(CallbackQueryHandler(abandon_quest_callback, pattern="^quest_abandon_"))
    app.add_handler(CallbackQueryHandler(cmd_quest_new, pattern="^quest_new$"))
    app.add_handler(CallbackQueryHandler(take_quest_callback, pattern="^quest_take_"))
    logging.info("Quest handlers registered")
