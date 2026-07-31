"""
plugins/vip_shop.py — Token Магазин за токены

Плагин для покупки бустов и prestige за токены.
Цены настраиваются в config.py (VIP_SHOP_ITEMS).
"""
import logging
import time as time_module

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from db import Player
from ui.icons import SEP
from core.telegram_utils import safe_edit
import config as cfg
from core.loot import generate_item_data

logger = logging.getLogger(__name__)

# ── VIP item descriptions ──
VIP_ITEM_INFO = {
    "xp_boost": {
        "desc_ru": "Удваивает получаемый XP на 1 час",
        "desc_en": "Doubles XP gained for 1 hour",
        "duration_ru": "1 час",
        "duration_en": "1 hour",
    },
    "speed_boost": {
        "desc_ru": "Удваивает скорость передвижения на 30 минут",
        "desc_en": "Doubles movement speed for 30 minutes",
        "duration_ru": "30 минут",
        "duration_en": "30 minutes",
    },
    "protect": {
        "desc_ru": "Защита от штрафов за смерть на 1 час",
        "desc_en": "Death penalty protection for 1 hour",
        "duration_ru": "1 час",
        "duration_en": "1 hour",
    },
    "prestige": {
        "desc_ru": "Сброс уровня, получение престиж-баллов\n⭐ Бонусы XP и Gold",
        "desc_en": "Reset level, gain prestige points\n⭐ XP and Gold bonuses",
        "duration_ru": "",
        "duration_en": "",
    },
    "auto_quest": {
        "desc_ru": "Авто-приём заданий в настройках\n🤖 Один раз покупается навсегда",
        "desc_en": "Auto-accept quests in settings\n🤖 One-time permanent unlock",
        "duration_ru": "",
        "duration_en": "",
    },
}


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


async def buy_prestige(player: Player, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    """Купить престиж: сброс уровня, обнуление, генерация стартового шмота.
    Возвращает (текст, клавиатура) для показа игроку."""
    from ui.icons import SEP
    
    old_level = player.level
    
    player.level = 1
    player.currentxp = 0
    player.nextxp = 600
    player.gold = 0
    
    for slot in cfg.WEAPON_SLOTS:
        setattr(player, slot, generate_item_data(slot, 1))
    
    player.prestige_count += 1
    player.sync_max_hp_mp()
    await player.update(_columns=[
        "level", "currentxp", "nextxp", "gold",
        *cfg.WEAPON_SLOTS,
        "prestige_count", "max_hp", "max_mp"
    ])
    
    per_level, max_bonus = get_prestige_bonus()
    
    xp_level    = player.prestige_xp_level or 0
    gold_level  = player.prestige_gold_level or 0
    xp_percent  = min(xp_level * per_level, max_bonus)
    gold_percent = min(gold_level * per_level, max_bonus)
    
    text = (
        f"✨ <b>PRESTIGE!</b>\n\n"
        f"{player.name} {'starts anew!' if lang == 'en' else 'начинает заново!'}\n\n"
        f"{'Old level:' if lang == 'en' else 'Старый уровень:'} <b>{old_level}</b>\n"
        f"{'Total prestige:' if lang == 'en' else 'Всего prestige:'} <b>x{player.prestige_count}</b>\n"
        f"Prestige level: <b>{player.prestige_count}</b>\n\n"
        f"⚡ XP: Lv.<b>{xp_level}</b> (+{xp_percent}%)\n"
        f"💰 Gold: Lv.<b>{gold_level}</b> (+{gold_percent}%)\n\n"
        f"{'Choose a bonus:' if lang == 'en' else 'Выбери бонус:'}"
    )
    
    keyboard = build_prestige_choose_keyboard(lang, player)
    return text, keyboard


def vip_t(lang: str, key: str, **kwargs) -> str:
    """Получить перевод для VIP магазина."""
    from i18n import t
    return t(lang, key, **kwargs)


def build_vip_text(player, lang: str) -> str:
    """Построить текст VIP магазина с карточками."""
    items = get_vip_items()
    
    lines = [
        "💎 <b>ТОКЕНЫ</b>" if lang != "en" else "💎 <b>TOKENS</b>",
        f"🪙 Твои токены: <b>{player.tokens}</b>" if lang != "en" else f"🪙 Your tokens: <b>{player.tokens}</b>",
        SEP,
        "🛒 <b>ТОВАРЫ</b>" if lang != "en" else "🛒 <b>SHOP</b>",
    ]
    
    for item_id, item_data in items.items():
        name = vip_t(lang, f"vip_item_{item_id}")
        price = item_data['price']
        emoji = item_data.get('emoji', '📦')
        info = VIP_ITEM_INFO.get(item_id, {})
        desc = info.get(f"desc_{lang}", info.get("desc_ru", ""))
        
        affordable = "✅" if player.tokens >= price else "❌"
        
        lines.append(f"{emoji} <b>{name}</b> — {price}🪙 {affordable}")
        if desc:
            lines.append(f"   {desc}")
        lines.append("")
    
    return "\n".join(lines)


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

    rows.append([InlineKeyboardButton(vip_t(lang, "menu"), callback_data="menu_back")])

    return InlineKeyboardMarkup(rows)


def build_prestige_choose_keyboard(lang: str, player: Player) -> InlineKeyboardMarkup:
    """Построить клавиатуру выбора бонуса prestige (после покупки)."""
    per_level, max_bonus = get_prestige_bonus()
    
    xp_level = player.prestige_xp_level or 0
    gold_level = player.prestige_gold_level or 0
    
    xp_percent = min(xp_level * per_level, max_bonus)
    gold_percent = min(gold_level * per_level, max_bonus)
    
    xp_text = f"⚡ XP +{xp_percent}% (Lv.{xp_level})"
    gold_text = f"💰 Gold +{gold_percent}% (Lv.{gold_level})"
    
    rows = [[
        InlineKeyboardButton(xp_text, callback_data="prestige_bonus_xp"),
        InlineKeyboardButton(gold_text, callback_data="prestige_bonus_gold"),
    ]]
    
    rows.append([InlineKeyboardButton("⭐ Престиж" if lang != "en" else "⭐ Prestige", callback_data="prestige_manage")])
    
    return InlineKeyboardMarkup(rows)


async def handle_vip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback VIP магазина — HTML mode."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"

    if not player:
        await safe_edit(query, vip_t(lang, "not_registered"))
        return

    data = query.data

    # === МЕНЮ VIP МАГАЗИНА ===
    if data == "vip_menu":
        text = build_vip_text(player, lang)
        keyboard = build_vip_keyboard(lang, player)
        await safe_edit(query, text, parse_mode="HTML", reply_markup=keyboard)
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

        # === AUTO QUEST UNLOCK (check before token deduction) ===
        if item_type == "auto_quest" and player.auto_quest_unlocked:
            await query.answer("🤖 Already bought!" if lang == "en" else "🤖 Уже куплено!", show_alert=True)
            return

        # Списание токенов
        player.tokens -= price
        await player.update(_columns=["tokens"])

        # === XP BOOST ===
        if item_type == "xp_boost":
            duration = item_data.get('duration', 3600)
            player.xp_boost_until = int(time_module.time()) + duration
            await player.update(_columns=["xp_boost_until"])
            name_ru = player.name or ""
            name_en = player.name_en or name_ru
            display_name = name_en if lang == "en" else name_ru
            text = vip_t(lang, "vip_bought_xp_boost", name=display_name, duration=duration // 60)

        # === SPEED BOOST ===
        elif item_type == "speed_boost":
            duration = item_data.get('duration', 1800)
            player.speed_boost_until = int(time_module.time()) + duration
            await player.update(_columns=["speed_boost_until"])
            name_ru = player.name or ""
            name_en = player.name_en or name_ru
            display_name = name_en if lang == "en" else name_ru
            text = vip_t(lang, "vip_bought_speed_boost", name=display_name, duration=duration // 60)

        # === PROTECT ===
        elif item_type == "protect":
            duration = item_data.get('duration', 3600)
            player.protect_until = int(time_module.time()) + duration
            await player.update(_columns=["protect_until"])
            name_ru = player.name or ""
            name_en = player.name_en or name_ru
            display_name = name_en if lang == "en" else name_ru
            text = vip_t(lang, "vip_bought_protect", name=display_name, duration=duration // 60)

        # === AUTO QUEST UNLOCK ===
        elif item_type == "auto_quest":
            player.auto_quest_unlocked = True
            await player.update(_columns=["auto_quest_unlocked"])
            await query.answer("✅ Purchased!" if lang == "en" else "✅ Куплено!", show_alert=True)
            # Redirect to auto-quest settings
            current = player.auto_accept_quests or "off"
            opts = [("off", "autoquest_off"), ("silent", "autoquest_silent"), ("notify", "autoquest_notify")]
            kb_rows = []
            row = []
            for val, label_key in opts:
                label = vip_t(lang, label_key)
                if val == current:
                    label = f"✅ {label}"
                row.append(InlineKeyboardButton(label, callback_data=f"autoquest_set_{val}"))
            kb_rows.append(row)
            kb_rows.append([InlineKeyboardButton(vip_t(lang, "back"), callback_data="menu_settings")])
            await safe_edit(query, vip_t(lang, "autoquest_title"),
                            parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb_rows))
            return

        # === PRESTIGE ===
        elif item_type == "prestige":
            text, keyboard = await buy_prestige(player, lang)
            await safe_edit(query, text, parse_mode="HTML", reply_markup=keyboard)
            return

        # Кнопки после покупки
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(vip_t(lang, "vip_again"), callback_data=f"vip_buy_{item_type}"),
            ],
            [
                InlineKeyboardButton(vip_t(lang, "vip_menu"), callback_data="shop_boosts"),
            ],
            [
                InlineKeyboardButton(vip_t(lang, "menu"), callback_data="menu_shop"),
            ],
        ])

        await safe_edit(query, text, parse_mode="HTML", reply_markup=keyboard)
        return


def show_vip_menu(query, player, lang: str):
    """Показать меню VIP магазина."""
    text = build_vip_text(player, lang)
    keyboard = build_vip_keyboard(lang, player)
    return safe_edit(query, text, parse_mode="HTML", reply_markup=keyboard)


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
    return int(time_module.time()) < player.xp_boost_until


def has_active_speed_boost(player: Player) -> bool:
    """Проверить есть ли активный Speed буст."""
    if player.speed_boost_until <= 0:
        return False
    return int(time_module.time()) < player.speed_boost_until


def has_active_protect(player: Player) -> bool:
    """Проверить есть ли активная защита."""
    if player.protect_until <= 0:
        return False
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
    "buy_prestige",
    "get_prestige_bonus",
    "build_prestige_choose_keyboard",
]
