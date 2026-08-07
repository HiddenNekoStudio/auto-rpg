"""
services/event_handlers.py — Обработчики событий EventBus для Telegram уведомлений

Подписывается на события из game модулей и отправляет уведомления игрокам.
"""
import logging
from telegram import Bot

from core.event_bus import GameEvent, EventType, event_bus
from bot import send_to_players, item_string, format_short
from db import Player

logger = logging.getLogger(__name__)

_bot: Bot = None


def init_event_handlers(bot: Bot):
    """Инициализировать обработчики событий с экземпляром бота."""
    global _bot
    _bot = bot

    event_bus.subscribe(EventType.PLAYER_IDLE_EXIT, handle_idle_exit)
    event_bus.subscribe(EventType.PLAYER_ITEM_GAINED, handle_item_gained)
    event_bus.subscribe(EventType.PLAYER_MONSTER_DEFEATED, handle_monster_defeated)
    event_bus.subscribe(EventType.PLAYER_GOLD_CHANGED, handle_gold_changed)
    event_bus.subscribe(EventType.GLOBAL_EVENT, handle_global_event)

    logger.info("Event handlers initialized")


async def handle_idle_exit(event: GameEvent) -> None:
    """Обработка выхода из idle режима."""
    if not _bot:
        return

    data = event.data
    player_uid = event.player_uid
    xp_gained = data.get("xp_gained", 0)

    try:
        player = await Player.objects.get(uid=player_uid)
    except Exception:
        player = None
    lang = player.lang if player and player.lang else "ru"

    if xp_gained > 0:
        text = f"💤 You're back from idle mode!\n\n🎁 Gained: *{format_short(xp_gained)}* XP" if lang == "en" else f"💤 Ты вернулся из idle режима!\n\n🎁 Получено: *{format_short(xp_gained)}* XP"
        await send_to_players(_bot, text, player_uids=[player_uid])


async def handle_item_gained(event: GameEvent) -> None:
    """Обработка получения предмета."""
    if not _bot:
        return

    data = event.data
    player_uid = event.player_uid

    try:
        player = await Player.objects.get(uid=player_uid)
    except Exception:
        player = None
    lang = player.lang if player and player.lang else "ru"

    item = data.get("item", {})
    slot = data.get("slot", "")
    replaced = data.get("replaced", False)

    text = f"🎒 Item received in slot *{slot}*:\n{item_string(item, lang)}" if lang == "en" else f"🎒 Получен предмет в слот *{slot}*:\n{item_string(item, lang)}"
    if replaced:
        text += "\n✨ *Upgrade!*" if lang == "en" else "\n✨ *Улучшение!*"

    await send_to_players(_bot, text, player_uids=[player_uid])


async def handle_monster_defeated(event: GameEvent) -> None:
    """Обработка победы над монстром."""
    if not _bot:
        return

    data = event.data
    player_uid = event.player_uid

    try:
        player = await Player.objects.get(uid=player_uid)
    except Exception:
        player = None
    lang = player.lang if player and player.lang else "ru"

    xp = data.get("xp_gained", 0)
    gold = data.get("gold_gained", 0)

    text = f"⚔️ Monster level {data.get('monster_level', 1)} defeated!\n\n" if lang == "en" else f"⚔️ Побеждён монстр уровня {data.get('monster_level', 1)}!\n\n"
    text += f"🎁 +{format_short(xp)} XP\n"
    text += f"💰 +{format_short(gold)} Gold"

    await send_to_players(_bot, text, player_uids=[player_uid])


async def handle_gold_changed(event: GameEvent) -> None:
    """Обработка изменения золота."""
    try:
        from game.achievements import on_gold_changed
        await on_gold_changed(event.player_uid, event.data.get("amount", 0))
    except Exception:
        import logging
        logging.exception("achievements on gold error")

    if not _bot:
        return

    data = event.data
    player_uid = event.player_uid
    amount = data.get("amount", 0)

    try:
        player = await Player.objects.get(uid=player_uid)
    except Exception:
        player = None
    lang = player.lang if player and player.lang else "ru"

    if amount > 0:
        text = f"💰 +{format_short(amount)} Gold\n(reason: {data.get('reason', 'unknown')})" if lang == "en" else f"💰 +{format_short(amount)} Gold\n(причина: {data.get('reason', 'unknown')})"
        await send_to_players(_bot, text, player_uids=[player_uid])


async def handle_global_event(event: GameEvent) -> None:
    """Обработка глобального события."""
    if not _bot:
        return

    data = event.data
    message = data.get("message", "")
    affected = data.get("affected_uids", [])

    if affected:
        await send_to_players(_bot, message, player_uids=affected)
    else:
        await send_to_players(_bot, message)