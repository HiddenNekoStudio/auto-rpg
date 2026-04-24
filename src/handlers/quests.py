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
from data.locations import find_location, format_location


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


async def cmd_myquests(update, context):
    """Показать мои квесты через меню."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    player = await Player.objects.get_or_none(uid=update.effective_user.id)
    if not player:
        await update.message.reply_text(t("not_registered", "ru"))
        return

    lang = player.lang or "ru"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Мои квесты", callback_data="menu_quest")],
        [InlineKeyboardButton("🏠 Меню", callback_data="menu_back")]
    ])
    
    await update.message.reply_text(
        "🎯 *Мои квесты*\n\nНажми кнопку ниже чтобы открыть меню квестов!",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


async def accept_quest_callback(update, context):
    """Принять квест."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    if len(parts) < 3:
        return

    #quest_accept_quest_town_1234 -> parts = ["quest", "accept", "quest", "town", "1234"]
    quest_id = "_".join(parts[2:])
    player = await Player.objects.get_or_none(uid=query.from_user.id)
    if not player:
        return

    lang = player.lang or "ru"

    try:
        logging.error(f"DEBUG: accept quest_id={quest_id}, player_uid={player.uid}")
        
        quest = await PlayerQuest.objects.filter(
            quest_key=quest_id,
            player_uid=player.uid
        ).get_or_none()
        
        if quest:
            quest.status = "active"
            await quest.update(_columns=["status"])
            text = t("location_quest_accept", lang)
            await query.message.edit_text(text)
            logging.error(f"DEBUG: quest accepted: {quest.id}, status={quest.status}")
        else:
            logging.error(f"DEBUG: quest NOT FOUND by quest_key - fallback to legacy fields")
            # Fallback: ищем по quest_id_str или quest_id
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
                logging.error(f"DEBUG: found by legacy field! id={quest.id}")
                quest.status = "active"
                await quest.update(_columns=["status"])
                text = t("location_quest_accept", lang)
                await query.message.edit_text(text)
            else:
                logging.error(f"DEBUG: quest still not found")
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

    #quest_decline_quest_town_1234 -> parts = ["quest", "decline", "quest", "town", "1234"]
    quest_id = "_".join(parts[2:])
    player = await Player.objects.get_or_none(uid=query.from_user.id)
    if not player:
        return

    lang = player.lang or "ru"

    try:
        # Ищем по quest_key (UUID), fallback на legacy поля
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
        await query.message.edit_text(text)
    except Exception as e:
        logging.error(f"Decline quest error: {e}")
        pass


QUEST_OFFER_COOLDOWN = 300  # 5 minutes between quest offers
QUEST_LOCATION_COOLDOWN = 180  # 3 minutes before offering quest on same location


async def offer_quest(bot, player, quest_type, location=None):
    """Предложить квест игроку - создаёт и отправляет уведомление"""
    from data.quests import generate_quest
    from data.quest_config import MAX_TOTAL_ACTIVE_QUESTS
    from game.quests import get_quest_slots_available, can_offer_new_quests
    
    player_lang = player.lang or "ru"
    
    if not await can_offer_new_quests(player):
        slots = await get_quest_slots_available(player)
        if slots <= 0:
            await bot.send_message(
                chat_id=player.uid,
                text=f"🎯 *Квесты недоступны*\n\nУ тебя уже {MAX_TOTAL_ACTIVE_QUESTS} активных квестов. Заверши хотя бы один, чтобы получить новый!",
                parse_mode="Markdown"
            )
        return None
    
    quest_data = generate_quest(player, quest_type, location, player_lang)
    if not quest_data:
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
            text = f"🎯 *{quest.title}*\n\nПринятие через 1 сек..."
        elif auto_mode == "silent":
            text = f"🎯 *{quest.title}*\n\nПринятие через 1 сек..."
            await bot.send_message(
                chat_id=player.uid,
                text=text,
                parse_mode="Markdown"
            )
        return quest
    else:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Принять", callback_data=f"quest_accept_{quest.quest_key}"),
                InlineKeyboardButton("❌ Отказаться", callback_data=f"quest_decline_{quest.quest_key}"),
            ]
        ])
        
        text = (
            f"🎯 *Новый квест!*\n\n"
            f"*{quest.title}*\n\n"
            f"{quest.description}\n\n"
            f"🎁 Награда: +{quest.reward_xp} XP, +{quest.reward_gold} Gold"
        )
        
        await bot.send_message(
            chat_id=player.uid,
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    return quest


async def check_location_quests(bot, player):
    """Проверить квесты при входе на локацию (новая система)."""
    if not player:
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
        status__in=["active", "offered"]
    ).all()

    if recent:
        return

    recent_offers = await PlayerQuest.objects.filter(
        player_uid=player.uid,
        status__in=["active", "offered"]
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

    await offer_quest(bot, player, quest_type="location", location=loc)


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
                
                # Снять блокировку локации при выполнении квеста
                if quest.location_locked:
                    quest.location_locked = False
                    quest.target_location_id = ""
                    await quest.update()
                    await query.message.edit_text(
                        f"❌ Квест *{quest.title}* отменён\n\n⏱️ Доступен через 10 мин.",
                        parse_mode="Markdown"
                    )
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
        
        text = f"✅ {t(lang, 'quest_accepted')} {quest.title}\n\n🎁 XP: +{xp} 💰 +{gold}"
        await send_to_players(bot, text, player_uids=[player_uid], parse_mode="Markdown")
    elif mode == "silent":
        await bot.send_message(
            chat_id=player_uid,
            text=f"🎯 {quest.title} — принят",
            parse_mode="Markdown"
        )
    
    quest_data = generate_quest(player, quest_type, location, player_lang)
    if not quest_data:
        return None
    
    # Записываем в БД
    quest = await PlayerQuest.objects.create(
        player_uid=player.uid,
        quest_id=0,  # Legacy field - set to 0 for new system
        quest_id_str="",  # Legacy field
        location_name="",  # Legacy field
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
            text = f"🎯 *{quest.title}*\n\nПринятие через 1 сек..."
        elif auto_mode == "silent":
            text = f"🎯 *{quest.title}*\n\nПринятие через 1 сек..."
            await bot.send_message(
                chat_id=player.uid,
                text=text,
                parse_mode="Markdown"
            )
        return quest
    else:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Принять", callback_data=f"quest_accept_{quest.quest_key}"),
                InlineKeyboardButton("❌ Отказаться", callback_data=f"quest_decline_{quest.quest_key}"),
            ]
        ])
        
        text = (
            f"🎯 *Новый квест!*\n\n"
            f"*{quest.title}*\n\n"
            f"{quest.description}\n\n"
            f"🎁 Награда: +{quest.reward_xp} XP, +{quest.reward_gold} Gold"
        )
        
        await bot.send_message(
            chat_id=player.uid,
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    return quest


# ═══════════════════════════════════════════════════════════════
# SHOW PLAYER QUESTS - Показать список принятых квестов
# ═══════════════════════════════════════════════════════════════

async def show_player_quests(bot, player):
    """Показать список активных принятых квестов игрока"""
    import time
    lang = player.lang or "ru"
    
    quests = await PlayerQuest.objects.filter(
        player_uid=player.uid,
        status="active"
    ).all()
    
    if not quests:
        text = "🎯 *Мои квесты*\n\nНет активных квестов"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Меню", callback_data="menu_back")]
        ])
        await bot.send_message(
            chat_id=player.uid,
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        return
    
    lines = ["🎯 *Мои квесты*", ""]
    
    for i, q in enumerate(quests, 1):
        # Дедлайн
        deadline = ""
        if q.expires_at:
            left = q.expires_at - int(time.time())
            if left > 0:
                hours = left // 3600
                minutes = (left % 3600) // 60
                deadline = f" ⏰ {hours}ч {minutes}мин"
            else:
                deadline = " ⛔ Просрочен"
        
        lines.append(f"{i}. {q.title}")
        lines.append(f"   ⏳ Прогресс: {q.progress}/{q.target_count}{deadline}")
        lines.append(f"   🎁 +{q.reward_xp} XP, +{q.reward_gold} Gold")
        lines.append("")
    
    text = "\n".join(lines)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Обновить", callback_data="menu_quest")],
        [InlineKeyboardButton("🏠 Меню", callback_data="menu_back")]
    ])
    
    await bot.send_message(
        chat_id=player.uid,
        text=text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )


# ═══════════════════════════════════════════════════════════════
# QUEST DETAIL - Подробности квеста
# ═══════════════════════════════════════════════════════════════

async def callback_quest_detail(update, context):
    """Показать подробности квеста"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    if len(parts) < 3:
        return
    
    quest_key = "_".join(parts[2:])
    quest = await PlayerQuest.objects.filter(quest_key=quest_key).get_or_none()
    
    if not quest:
        await query.message.edit_text("❌ Квест не найден")
        return
    
    player = await Player.objects.get_or_none(uid=query.from_user.id)
    if not player or quest.player_uid != player.uid:
        return
    
    import time
    lang = player.lang or "ru"
    
    # Дедлайн
    deadline = ""
    penalty = ""
    if quest.expires_at:
        left = quest.expires_at - int(time.time())
        if left > 0:
            hours = left // 3600
            minutes = (left % 3600) // 60
            deadline = f"⏰ Осталось: {hours}ч {minutes}мин"
            # Штраф
            penalties = {"location": quest.reward_xp // 10, "daily": 50, "story": 200, "periodic": 25}
            p = penalties.get(quest.quest_type, 10)
            penalty = f"❌ Штраф: -{p} XP"
        else:
            deadline = "⛔ Просрочен"
    
    text = f"🎯 *{quest.title}* ({quest.status})\n\n"
    
    if quest.location_id:
        text += f"📍 Локация: {quest.location_id}\n"
    
    text += f"⏳ Прогресс: {quest.progress}/{quest.target_count}\n"
    
    if deadline:
        text += f"{deadline}\n\n"
    
    text += f"🎁 Награда: +{quest.reward_xp} XP, +{quest.reward_gold} Gold"
    
    if penalty:
        text += f"\n{penalty}"
    
    # Кнопки
    if quest.status == "active":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚫 Отменить", callback_data=f"quest_abandon_{quest.quest_key}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_quest")]
        ])
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_quest")]
        ])
    
    await query.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )


# ═══════════════════════════════════════════════════════════════
# NEW SYSTEM CALLBACKS - UUID based
# ═══════════════════════════════════════════════════════════════

async def accept_quest_callback_new(update, context):
    """Принять квест (новая система с UUID)."""
    query = update.callback_query
    await query.answer()
    
    # Извлечь quest_key из callback_data
    # format: quest_accept_UUID36
    parts = query.data.split("_")
    if len(parts) < 3:
        return
    
    quest_key = "_".join(parts[2:])  # UUID
    
    quest = await PlayerQuest.objects.filter(quest_key=quest_key).get_or_none()
    if not quest:
        await query.message.edit_text("❌ Квест не найден")
        return
    
    player = await Player.objects.get_or_none(uid=query.from_user.id)
    if not player or quest.player_uid != player.uid:
        return
    
    lang = player.lang or "ru"
    
    if quest.status != "offered":
        await query.message.edit_text("⏰ Квест уже принят или неактивен")
        return
    
    import time
    
    deadline = ""
    if quest.expires_at:
        left = quest.expires_at - int(time.time())
        if left > 0:
            hours = left // 3600
            minutes = (left % 3600) // 60
            deadline = f"\n⏰ Срок: {hours}ч {minutes}мин"
        else:
            deadline = "\n⛔ Просрочен"
    
    quest.status = "active"
    quest.accepted_at = int(time.time())
    await quest.update()
    
    text = (
        f"✅ *Квест принят!*\n\n"
        f"*{quest.title}*\n\n"
        f"{quest.description}\n\n"
        f"🎯 Цель: {quest.target_id} ({quest.progress}/{quest.target_count})\n"
        f"🎁 Награда: +{quest.reward_xp} XP, +{quest.reward_gold} Gold"
        f"{deadline}\n\n"
        f"_Квест выполняется автоматически!_"
    )
    await query.message.edit_text(text, parse_mode="Markdown")


async def decline_quest_callback_new(update, context):
    """Отклонить квест (новая система с UUID)."""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    if len(parts) < 3:
        return
    
    quest_key = "_".join(parts[2:])
    
    quest = await PlayerQuest.objects.filter(quest_key=quest_key).get_or_none()
    if not quest:
        await query.message.edit_text("❌ Квест не найден")
        return
    
    player = await Player.objects.get_or_none(uid=query.from_user.id)
    if not player or quest.player_uid != player.uid:
        return
    
    # Удалить квест
    await quest.delete()
    
    # Очистить location_locked если нет других location_locked квестов
    remaining_locked = await PlayerQuest.objects.filter(
        player_uid=player.uid,
        status="active",
        location_locked=True
    ).count()
    
    if remaining_locked == 0:
        pass  # Нет заблокированных - всё ок
    
    await query.message.edit_text("❌ Квест отклонён")


async def abandon_quest_callback(update, context):
    """Отменить квест."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    if len(parts) < 3:
        return

    quest_key = "_".join(parts[2:])

    quest = await PlayerQuest.objects.filter(quest_key=quest_key).get_or_none()
    if not quest:
        await query.message.edit_text("❌ Квест не найден")
        return

    player = await Player.objects.get_or_none(uid=query.from_user.id)
    if not player or quest.player_uid != player.uid:
        return

    if quest.status != "active":
        await query.message.edit_text("⏰ Квест неактивен")
        return

    # Снять блокировку локации при отмене
    was_locked = quest.location_locked
    import time
    quest.status = "abandoned"
    quest.cooldown_until = int(time.time()) + 600  # 10 минут
    quest.location_locked = False
    quest.target_location_id = ""
    await quest.update()

    await query.message.edit_text("🚫 Квест отменён\n\n⏱️ 10 минут кулдаун")


def register_handlers(app):
    """Регистрация обработчиков квестов."""
    from telegram.ext import CommandHandler, CallbackQueryHandler
    app.add_handler(CommandHandler("myquests", cmd_myquests))
    app.add_handler(CommandHandler("quests", cmd_myquests))
    app.add_handler(CallbackQueryHandler(accept_quest_callback, pattern="^quest_accept_"))
    app.add_handler(CallbackQueryHandler(accept_quest_callback_new, pattern="^quest_accept_new_"))
    app.add_handler(CallbackQueryHandler(decline_quest_callback, pattern="^quest_decline_"))
    app.add_handler(CallbackQueryHandler(abandon_quest_callback, pattern="^quest_abandon_"))
    logging.info("Quest handlers registered")