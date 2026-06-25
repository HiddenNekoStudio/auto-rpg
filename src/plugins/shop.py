"""
plugins/shop.py — Магазин сундуков

Плагин для покупки сундуков с случайными предметами за золото.
Цены настраиваются в config.py (SHOP_CHESTS).

Конфигурация SHOP_CHESTS в config.py:
    SHOP_CHESTS = {
        "small": {"price": 10, "items": 1, "emoji": "🎒"},
        "medium": {"price": 50, "items": 3, "emoji": "📦"},
        "big": {"price": 100, "items": 5, "emoji": "🏴"},
        "legendary": {"price": 500, "items": 3, "emoji": "✨", "guaranteed_rare": True},
    }
"""
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from db import Player
from loot import get_item
from bot import item_string

logger = logging.getLogger(__name__)


def default_shop_chests() -> dict:
    """Дефолтные сундуки."""
    return {
        "small": {"price": 10, "items": 1, "emoji": "🎒"},
        "medium": {"price": 50, "items": 3, "emoji": "📦"},
        "big": {"price": 100, "items": 5, "emoji": "🏴"},
        "legendary": {"price": 500, "items": 3, "emoji": "✨", "guaranteed_rare": True},
    }


def get_shop_chests() -> dict:
    """Получить конфигурацию магазина из config."""
    import config as cfg
    return getattr(cfg, 'SHOP_CHESTS', default_shop_chests())


def shop_t(lang: str, key: str, **kwargs) -> str:
    """Получить перевод для магазина."""
    from i18n import t
    return t(lang, key, **kwargs)


def build_shop_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Построить клавиатуру магазина."""
    chests = get_shop_chests()
    buttons = []

    for chest_id, chest_data in chests.items():
        name = shop_t(lang, f"shop_chest_{chest_id}")
        price = chest_data['price']
        emoji = chest_data.get('emoji', '📦')
        btn_text = f"{emoji} {name} ({price}{'g' if lang == 'en' else 'з'})"
        buttons.append(InlineKeyboardButton(btn_text, callback_data=f"shop_buy_{chest_id}"))

    rows = []
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            rows.append([buttons[i], buttons[i + 1]])
        else:
            rows.append([buttons[i]])

    rows.append([InlineKeyboardButton(shop_t(lang, "menu"), callback_data="menu_back")])

    return InlineKeyboardMarkup(rows)


async def handle_shop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback магазина."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    from handlers.user import safe_edit

    if not player:
        await safe_edit(query, shop_t(lang, "not_registered"))
        return

    data = query.data

    if data == "shop_menu":
        text = shop_t(lang, "shop_title", gold=player.gold)
        keyboard = build_shop_keyboard(lang)
        await safe_edit(query, text, parse_mode="Markdown", reply_markup=keyboard)
        return

    if data.startswith("shop_buy_"):
        chest_type = data.replace("shop_buy_", "")
        chests = get_shop_chests()

        if chest_type not in chests:
            chest_type = "small"

        chest = chests[chest_type]
        price = max(0, chest.get('price', 0))
        items_count = chest.get('items', 1)

        if player.gold < price:
            await query.answer(shop_t(lang, "shop_not_enough_gold"), show_alert=True)
            return

        player.gold -= price
        await player.update(_columns=["gold"])

        chest_name = shop_t(lang, f"shop_chest_{chest_type}")
        text = shop_t(lang, "shop_bought", name=player.name, chest=chest_name, price=price) + "\n\n"

        for _ in range(items_count):
            item, slot, replaced = await get_item(player)
            item_str = item_string(item, lang)
            text += f"• {item_str}"
            if replaced:
                text += f" {shop_t(lang, 'loot_upgrade')}\n"
            else:
                text += "\n"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(shop_t(lang, "shop_again"), callback_data=f"shop_buy_{chest_type}"),
            ],
            [
                InlineKeyboardButton(shop_t(lang, "shop_menu"), callback_data="shop_menu"),
            ],
            [
                InlineKeyboardButton(shop_t(lang, "menu"), callback_data="menu_back"),
            ],
        ])

        await safe_edit(query, text, parse_mode="Markdown", reply_markup=keyboard)


def show_shop_menu(query, player, lang: str):
    """Показать меню магазина."""
    from handlers.user import safe_edit
    text = shop_t(lang, "shop_title", gold=player.gold)
    keyboard = build_shop_keyboard(lang)
    return safe_edit(query, text, parse_mode="Markdown", reply_markup=keyboard)


def register_shop_handlers(app: Application):
    """Зарегистрировать обработчики магазина."""
    app.add_handler(CallbackQueryHandler(handle_shop_callback, pattern="^shop_"))
