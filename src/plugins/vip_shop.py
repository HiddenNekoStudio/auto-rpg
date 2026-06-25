"""
plugins/vip_shop.py — Token Магазин за токены

Плагин для покупки бустов и prestige за токены.
Цены настраиваются в config.py (VIP_SHOP_ITEMS).
"""
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from db import Player

logger = logging.getLogger(__name__)


def default_vip_items() -> dict:
    """Дефолтные товары VIP магазина."""
    return {
        "xp_boost": {"price": 1, "duration": 3600, "emoji": "⚡", "name": "XP Boost"},
        "speed_boost": {"price": 1, "duration": 1800, "emoji": "🏃", "name": "Speed Boost"},
        "protect": {"price": 2, "duration": 3600, "emoji": "🛡️", "name": "Protect"},
        "prestige": {"price": 5, "emoji": "✨", "name": "Prestige"},
        "auto_quest": {"price": 5, "emoji": "🤖", "name": "Auto Quests"},
    }


def get_vip_items() -> dict:
    """Получить конфигурацию VIP магазина из config."""
    import config as cfg
    return getattr(cfg, 'VIP_SHOP_ITEMS', default_vip_items())


def get_prestige_bonus() -> tuple:
    """Получить настройки бонуса prestige."""
    import config as cfg
    per_level = getattr(cfg, 'PRESTIGE_BONUS_PER_LEVEL', 2)
    max_bonus = getattr(cfg, 'PRESTIGE_MAX_BONUS', 1000)
    return per_level, max_bonus


def vip_t(lang: str, key: str, **kwargs) -> str:
    """Получить перевод для VIP магазина."""
    from i18n import t
    return t(lang, key, **kwargs)


def build_vip_keyboard(lang: str, player: Player = None) -> InlineKeyboardMarkup:
    """Построить клавиатуру VIP магазина."""
    items = get_vip_items()
    buttons = []

    for item_id, item_data in items.items():
        name = vip_t(lang, f"vip_item_{item_id}")
        price = item_data['price']
        emoji = item_data.get('emoji', '📦')
        btn_text = f"{emoji} {name} ({price}🪙)"
        buttons.append(InlineKeyboardButton(btn_text, callback_data=f"vip_buy_{item_id}"))

    rows = []
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            rows.append([buttons[i], buttons[i + 1]])
        else:
            rows.append([buttons[i]])

    if player and player.prestige_count > 0:
        rows.append([InlineKeyboardButton("⭐ Prestige" if lang == "en" else "⭐ Престиж", callback_data="vip_prestige_change")])

    rows.append([InlineKeyboardButton(vip_t(lang, "menu"), callback_data="menu_back")])

    return InlineKeyboardMarkup(rows)


def build_prestige_choose_keyboard(lang: str, player: Player) -> InlineKeyboardMarkup:
    """Построить клавиатуру выбора бонуса prestige."""
    per_level, max_bonus = get_prestige_bonus()
    
    xp_level = player.prestige_xp_level or 0
    gold_level = player.prestige_gold_level or 0
    
    xp_percent = min(xp_level * per_level, max_bonus)
    gold_percent = min(gold_level * per_level, max_bonus)
    
    xp_text = f"⚡ XP +{xp_percent}% (Lv.{xp_level})"
    gold_text = f"💰 Gold +{gold_percent}% (Lv.{gold_level})"
    
    rows = [[
        InlineKeyboardButton(xp_text, callback_data="vip_bonus_xp"),
        InlineKeyboardButton(gold_text, callback_data="vip_bonus_gold"),
    ]]
    
    rows.append([InlineKeyboardButton("🔙 Menu" if lang == "en" else "🔙 Меню", callback_data="menu_back")])
    
    return InlineKeyboardMarkup(rows)


def build_prestige_change_keyboard(lang: str, player: Player) -> InlineKeyboardMarkup:
    """Построить клавиатуру смены бонуса prestige."""
    per_level, max_bonus = get_prestige_bonus()
    
    xp_level = player.prestige_xp_level or 0
    gold_level = player.prestige_gold_level or 0
    
    xp_percent = min(xp_level * per_level, max_bonus)
    gold_percent = min(gold_level * per_level, max_bonus)
    
    xp_text = f"⚡ XP +{xp_percent}% (Lv.{xp_level})"
    gold_text = f"💰 Gold +{gold_percent}% (Lv.{gold_level})"
    
    rows = [[
        InlineKeyboardButton(xp_text, callback_data="vip_bonus_xp"),
        InlineKeyboardButton(gold_text, callback_data="vip_bonus_gold"),
    ]]
    
    rows.append([InlineKeyboardButton(vip_t(lang, "menu"), callback_data="menu_back")])
    
    return InlineKeyboardMarkup(rows)


async def handle_vip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback VIP магазина."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    from handlers.user import safe_edit

    if not player:
        await safe_edit(query, vip_t(lang, "not_registered"))
        return

    data = query.data

    # === МЕНЮ VIP МАГАЗИНА ===
    if data == "vip_menu":
        text = vip_t(lang, "vip_title", tokens=player.tokens)
        keyboard = build_vip_keyboard(lang, player)
        await safe_edit(query, text, parse_mode="Markdown", reply_markup=keyboard)
        return

    # === ПОКУПКА ТОВАРОВ ===
    if data.startswith("vip_buy_"):
        item_type = data.replace("vip_buy_", "")
        items = get_vip_items()

        if item_type not in items:
            await query.answer("Unknown item" if lang == "en" else "Неизвестный предмет", show_alert=True)
            return

        item_data = items[item_type]
        price = max(0, item_data.get('price', 0))

        if player.tokens < price:
            await query.answer(vip_t(lang, "vip_not_enough_tokens"), show_alert=True)
            return

        # Списание токенов
        player.tokens -= price
        await player.update(_columns=["tokens"])

        # === XP BOOST ===
        if item_type == "xp_boost":
            duration = item_data.get('duration', 3600)
            import time as time_module
            player.xp_boost_until = int(time_module.time()) + duration
            await player.update(_columns=["xp_boost_until"])
            text = vip_t(lang, "vip_bought_xp_boost", name=player.name, duration=duration // 60)

        # === SPEED BOOST ===
        elif item_type == "speed_boost":
            duration = item_data.get('duration', 1800)
            import time as time_module
            player.speed_boost_until = int(time_module.time()) + duration
            await player.update(_columns=["speed_boost_until"])
            text = vip_t(lang, "vip_bought_speed_boost", name=player.name, duration=duration // 60)

        # === PROTECT ===
        elif item_type == "protect":
            duration = item_data.get('duration', 3600)
            import time as time_module
            player.protect_until = int(time_module.time()) + duration
            await player.update(_columns=["protect_until"])
            text = vip_t(lang, "vip_bought_protect", name=player.name, duration=duration // 60)

        # === AUTO QUEST UNLOCK ===
        elif item_type == "auto_quest":
            if player.auto_quest_unlocked:
                await query.answer("🤖 Already bought!" if lang == "en" else "🤖 Уже куплено!", show_alert=True)
                return
            player.auto_quest_unlocked = True
            await player.update(_columns=["auto_quest_unlocked"])
            await query.answer("✅ Purchased!" if lang == "en" else "✅ Куплено!", show_alert=True)
            # Redirect to auto-quest settings
            from i18n import t as i18n_t
            current = player.auto_accept_quests or "off"
            opts = [("off", "autoquest_off"), ("silent", "autoquest_silent"), ("notify", "autoquest_notify")]
            kb_rows = []
            row = []
            for val, label_key in opts:
                label = i18n_t(lang, label_key)
                if val == current:
                    label = f"✅ {label}"
                row.append(InlineKeyboardButton(label, callback_data=f"autoquest_set_{val}"))
            kb_rows.append(row)
            kb_rows.append([InlineKeyboardButton(i18n_t(lang, "back"), callback_data="menu_settings")])
            await safe_edit(query, i18n_t(lang, "autoquest_title"),
                            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb_rows))
            return

        # === PRESTIGE ===
        elif item_type == "prestige":
            try:
                # Выполняем сброс
                old_level = player.level
                old_job = player.job
                
                # Сбрасываем уровень и XP
                player.level = 1
                player.currentxp = 0
                player.nextxp = 600
                
                # Сбрасываем золото
                player.gold = 0
                
                # Сбрасываем инвентарь (8 слотов) - выдаём рандомное базовое снаряжение
                from core.loot import generate_item_data
                
                new_level = 1  # level после сброса
                for slot in ['weapon', 'shield', 'helmet', 'chest', 'gloves', 'boots', 'ring', 'amulet']:
                    item = generate_item_data(slot, new_level)
                    setattr(player, slot, item)
                
                # Увеличиваем prestige счётчик
                player.prestige_count += 1
                
                # Увеличиваем prestige level для бонусов
                if player.prestige_level is None or player.prestige_level == 0:
                    player.prestige_level = 1
                else:
                    player.prestige_level += 1
                
                # Уровни бонусов НЕ сбрасываются — они накапливаются
                
                player.sync_max_hp_mp()
                await player.update(_columns=[
                    "level", "currentxp", "nextxp", "gold",
                    "weapon", "shield", "helmet", "chest", "gloves", "boots", "ring", "amulet",
                    "prestige_count", "prestige_level", "max_hp", "max_mp"
                ])
                
                # Показываем меню выбора бонуса
                per_level, max_bonus = get_prestige_bonus()
                
                xp_level = player.prestige_xp_level or 0
                gold_level = player.prestige_gold_level or 0
                xp_percent = min(xp_level * per_level, max_bonus)
                gold_percent = min(gold_level * per_level, max_bonus)
                
                # Plain text without Markdown formatting
                text = (f"✨ PRESTIGE!\n\n"
                        f"{player.name} {'starts anew!' if lang == 'en' else 'начинает заново!'}\n\n"
                        f"{'Old level:' if lang == 'en' else 'Старый уровень:'} {old_level}\n"
                        f"{'Total prestige:' if lang == 'en' else 'Всего prestige:'} x{player.prestige_count}\n"
                        f"Prestige level: {player.prestige_level}\n\n"
                        f"⚡ XP: Lv.{xp_level} (+{xp_percent}%)\n"
                        f"💰 Gold: Lv.{gold_level} (+{gold_percent}%)\n\n"
                        f"{'Choose a bonus:' if lang == 'en' else 'Выбери бонус:'}")
                
                logging.info(f"PRESTIGE: player={player.name}, level={player.prestige_level}, xp={xp_percent}%, gold={gold_percent}%, building keyboard...")
                
                keyboard = build_prestige_choose_keyboard(lang, player)
                logging.info(f"PRESTIGE: keyboard built, buttons count={len(keyboard.inline_keyboard)}")
                
                try:
                    await query.edit_message_text(text=text, reply_markup=keyboard)
                    logging.info(f"PRESTIGE: message sent to user {player.uid}")
                except Exception as e:
                    logging.error(f"PRESTIGE edit_message_text error: {e}")
                    # Пробуем без parse_mode
                    try:
                        await query.edit_message_text(text=text, parse_mode=None, reply_markup=keyboard)
                    except Exception as e2:
                        logging.error(f"PRESTIGE edit_message_text error (no parse_mode): {e2}")
                return
            except Exception as e:
                logging.error(f"PRESTIGE error: {e}")
                await query.answer(f"{'An error occurred. Try again later.' if lang == 'en' else 'Произошла ошибка. Попробуйте позже.'}", show_alert=True)
                return

        # Кнопки после покупки
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(vip_t(lang, "vip_again"), callback_data=f"vip_buy_{item_type}"),
            ],
            [
                InlineKeyboardButton(vip_t(lang, "vip_menu"), callback_data="vip_menu"),
            ],
            [
                InlineKeyboardButton(vip_t(lang, "menu"), callback_data="menu_back"),
            ],
        ])

        await safe_edit(query, text, parse_mode="Markdown", reply_markup=keyboard)
        return

    # === ВЫБОР БОНУСА PRESTIGЕ ===
    if data == "vip_bonus_xp":
        allocated = (player.prestige_xp_level or 0) + (player.prestige_gold_level or 0)
        if allocated >= player.prestige_count:
            await query.answer(f"{'No points available' if lang == 'en' else 'Нет доступных очков'}", show_alert=True)
            return
        player.prestige_xp_level = (player.prestige_xp_level or 0) + 1
        await player.update(_columns=["prestige_xp_level"])
        per_level, max_bonus = get_prestige_bonus()
        bonus_percent = min(player.prestige_xp_level * per_level, max_bonus)
        text = f"{'✅ XP bonus increased!' if lang == 'en' else '✅ XP бонус повышен!'}\n\n⚡ XP: Lv.{player.prestige_xp_level} (+{bonus_percent}%)\n💰 Gold: Lv.{player.prestige_gold_level or 0} (+{min((player.prestige_gold_level or 0) * per_level, max_bonus)}%)\nPrestige: x{player.prestige_count}"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(vip_t(lang, "menu"), callback_data="menu_back")]])
        try:
            await query.edit_message_text(text=text, reply_markup=keyboard)
        except Exception:
            await query.answer(f"{'✅ XP: Lv.' if lang == 'en' else '✅ XP: Lv.'}{player.prestige_xp_level}!", show_alert=False)
        return

    if data == "vip_bonus_gold":
        allocated = (player.prestige_xp_level or 0) + (player.prestige_gold_level or 0)
        if allocated >= player.prestige_count:
            await query.answer(f"{'No points available' if lang == 'en' else 'Нет доступных очков'}", show_alert=True)
            return
        player.prestige_gold_level = (player.prestige_gold_level or 0) + 1
        await player.update(_columns=["prestige_gold_level"])
        per_level, max_bonus = get_prestige_bonus()
        bonus_percent = min(player.prestige_gold_level * per_level, max_bonus)
        text = f"{'✅ Gold bonus increased!' if lang == 'en' else '✅ Gold бонус повышен!'}\n\n⚡ XP: Lv.{player.prestige_xp_level or 0} (+{min((player.prestige_xp_level or 0) * per_level, max_bonus)}%)\n💰 Gold: Lv.{player.prestige_gold_level} (+{bonus_percent}%)\nPrestige: x{player.prestige_count}"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(vip_t(lang, "menu"), callback_data="menu_back")]])
        try:
            await query.edit_message_text(text=text, reply_markup=keyboard)
        except Exception:
            await query.answer(f"{'✅ Gold: Lv.' if lang == 'en' else '✅ Gold: Lv.'}{player.prestige_gold_level}!", show_alert=False)
        return

    # === CHANGE PRESTIGE BONUS ===
    if data == "vip_prestige_change":
        per_level, max_bonus = get_prestige_bonus()
        xp_level = player.prestige_xp_level or 0
        gold_level = player.prestige_gold_level or 0
        allocated = xp_level + gold_level
        unallocated = max(0, player.prestige_count - allocated)
        xp_percent = min(xp_level * per_level, max_bonus)
        gold_percent = min(gold_level * per_level, max_bonus)

        if unallocated <= 0:
            text = (f"🔄 {'Prestige bonuses' if lang == 'en' else 'Бонусы престижа'}\n\n"
                    f"⚡ XP: Lv.{xp_level} (+{xp_percent}%)\n"
                    f"💰 Gold: Lv.{gold_level} (+{gold_percent}%)\n\n"
                    f"{'All points allocated' if lang == 'en' else 'Все очки распределены'}")
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(vip_t(lang, "menu"), callback_data="menu_back")]])
            await safe_edit(query, text, parse_mode="Markdown", reply_markup=keyboard)
            return

        text = (f"🔄 {'Prestige bonuses' if lang == 'en' else 'Бонусы престижа'}\n\n"
                f"⚡ XP: Lv.{xp_level} (+{xp_percent}%)\n"
                f"💰 Gold: Lv.{gold_level} (+{gold_percent}%)\n\n"
                f"{'Available:' if lang == 'en' else 'Доступно:'} {unallocated}\n\n"
                f"{'Choose a bonus:' if lang == 'en' else 'Выбери бонус:'}")
        keyboard = build_prestige_change_keyboard(lang, player)
        await safe_edit(query, text, parse_mode="Markdown", reply_markup=keyboard)
        return


def show_vip_menu(query, player, lang: str):
    """Показать меню VIP магазина."""
    from handlers.user import safe_edit
    text = vip_t(lang, "vip_title", tokens=player.tokens)
    keyboard = build_vip_keyboard(lang, player)
    return safe_edit(query, text, parse_mode="Markdown", reply_markup=keyboard)


def register_vip_handlers(app: Application):
    """Зарегистрировать обработчики VIP магазина."""
    app.add_handler(CallbackQueryHandler(handle_vip_callback, pattern="^vip_"))


# ============================================================
# Утилиты для проверки активных бустов и бонусов
# ============================================================

def has_active_xp_boost(player: Player) -> bool:
    """Проверить есть ли активный XP буст."""
    if player.xp_boost_until <= 0:
        return False
    import time as time_module
    return int(time_module.time()) < player.xp_boost_until


def has_active_speed_boost(player: Player) -> bool:
    """Проверить есть ли активный Speed буст."""
    if player.speed_boost_until <= 0:
        return False
    import time as time_module
    return int(time_module.time()) < player.speed_boost_until


def has_active_protect(player: Player) -> bool:
    """Проверить есть ли активная защита."""
    if player.protect_until <= 0:
        return False
    import time as time_module
    return int(time_module.time()) < player.protect_until


def get_xp_multiplier(player: Player) -> int:
    """Получить множитель XP (1 или 2 с бустом)."""
    if has_active_xp_boost(player):
        return 2
    return 1


def get_speed_multiplier(player: Player) -> int:
    """Получить множитель скорости (1 или 2 с бустом)."""
    if has_active_speed_boost(player):
        return 2
    return 1


def get_prestige_xp_multiplier(player: Player) -> float:
    """Получить множитель XP бонуса от prestige (1.0 + X%)."""
    level = player.prestige_xp_level or 0
    if level <= 0:
        return 1.0
    
    import config as cfg
    per_level = getattr(cfg, 'PRESTIGE_BONUS_PER_LEVEL', 2)
    max_bonus = getattr(cfg, 'PRESTIGE_MAX_BONUS', 1000)
    
    bonus_percent = min(level * per_level, max_bonus)
    return 1.0 + (bonus_percent / 100.0)


def get_prestige_gold_multiplier(player: Player) -> float:
    """Получить множитель Gold бонуса от prestige (1.0 + X%)."""
    level = player.prestige_gold_level or 0
    if level <= 0:
        return 1.0
    
    import config as cfg
    per_level = getattr(cfg, 'PRESTIGE_BONUS_PER_LEVEL', 2)
    max_bonus = getattr(cfg, 'PRESTIGE_MAX_BONUS', 1000)
    
    bonus_percent = min(level * per_level, max_bonus)
    return 1.0 + (bonus_percent / 100.0)


def has_prestige_xp_bonus(player: Player) -> bool:
    """Проверить есть ли XP бонус от prestige (уровень > 0)."""
    return (player.prestige_xp_level or 0) > 0


def has_prestige_gold_bonus(player: Player) -> bool:
    """Проверить есть ли Gold бонус от prestige (уровень > 0)."""
    return (player.prestige_gold_level or 0) > 0


__all__ = [
    "register_vip_handlers",
    "show_vip_menu",
    "get_vip_items",
    "default_vip_items",
    "vip_t",
    "build_vip_keyboard",
    "has_active_xp_boost",
    "has_active_speed_boost",
    "has_active_protect",
    "get_xp_multiplier",
    "get_speed_multiplier",
    "get_prestige_xp_multiplier",
    "get_prestige_gold_multiplier",
    "has_prestige_xp_bonus",
    "has_prestige_gold_bonus",
]