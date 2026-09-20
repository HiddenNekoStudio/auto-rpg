"""
plugins/shop.py — Магазин сундуков (карточный формат)

Плагин для покупки сундуков с случайными предметами за золото.
Каждый сундук — карточка с описанием, ценой и содержимым.
"""
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from db import Player, database
from loot import get_item
from bot import item_string

logger = logging.getLogger(__name__)

# ── Chest descriptions ──
CHEST_INFO = {
    "small": {
        "desc_ru": "Обычный рюкзак с одним предметом",
        "desc_en": "A common backpack with one item",
        "items_ru": "1 предмет",
        "items_en": "1 item",
        "quality_ru": "Любое качество",
        "quality_en": "Any quality",
    },
    "medium": {
        "desc_ru": "Крепкий ящик с тремя предметами",
        "desc_en": "A sturdy box with three items",
        "items_ru": "3 предмета",
        "items_en": "3 items",
        "quality_ru": "Любое качество",
        "quality_en": "Any quality",
    },
    "big": {
        "desc_ru": "Огромный сундук с пятью предметами",
        "desc_en": "A huge chest with five items",
        "items_ru": "5 предметов",
        "items_en": "5 items",
        "quality_ru": "Любое качество",
        "quality_en": "Any quality",
    },
    "legendary": {
        "desc_ru": "Легендарный сундук с тремя предметами\n✨ Гарантирован Rare+",
        "desc_en": "A legendary chest with three items\n✨ Guaranteed Rare+",
        "items_ru": "3 предмета (Rare+)",
        "items_en": "3 items (Rare+)",
        "quality_ru": "Rare+ гарантировано",
        "quality_en": "Rare+ guaranteed",
    },
}


def default_shop_chests() -> dict:
    return {
        "small": {"price": 10, "items": 1, "emoji": "🎒"},
        "medium": {"price": 50, "items": 3, "emoji": "📦"},
        "big": {"price": 100, "items": 5, "emoji": "🏴"},
        "legendary": {"price": 500, "items": 3, "emoji": "✨", "guaranteed_rare": True},
    }


def get_shop_chests() -> dict:
    import config as cfg
    return getattr(cfg, 'SHOP_CHESTS', default_shop_chests())


def shop_t(lang: str, key: str, **kwargs) -> str:
    from i18n import t
    return t(lang, key, **kwargs)


def build_shop_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Построить клавиатуру магазина с карточками."""
    chests = get_shop_chests()
    buttons = []

    for chest_id, chest_data in chests.items():
        name = shop_t(lang, f"shop_chest_{chest_id}")
        price = chest_data['price']
        emoji = chest_data.get('emoji', '📦')
        btn_text = f"{emoji} {name} — {price}💰"
        buttons.append(InlineKeyboardButton(btn_text, callback_data=f"shop_buy_{chest_id}"))

    rows = []
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            rows.append([buttons[i], buttons[i + 1]])
        else:
            rows.append([buttons[i]])

    rows.append([InlineKeyboardButton(shop_t(lang, "menu"), callback_data="menu_back")])

    return InlineKeyboardMarkup(rows)


def build_shop_text(player, lang: str) -> str:
    """Построить текст магазина с карточками сундуков."""
    from ui.icons import SEP
    chests = get_shop_chests()
    
    lines = [
        "🏪 <b>МАГАЗИН</b>" if lang != "en" else "🏪 <b>SHOP</b>",
        f"💰 Твоё золото: <b>{player.gold}</b>" if lang != "en" else f"💰 Your gold: <b>{player.gold}</b>",
        SEP,
    ]
    
    for chest_id, chest_data in chests.items():
        name = shop_t(lang, f"shop_chest_{chest_id}")
        price = chest_data['price']
        emoji = chest_data.get('emoji', '📦')
        info = CHEST_INFO.get(chest_id, {})
        desc = info.get(f"desc_{lang}", info.get("desc_ru", ""))
        items_count = chest_data.get('items', 1)
        
        affordable = "✅" if player.gold >= price else "❌"
        
        lines.append(f"{emoji} <b>{name}</b> — {price}💰 {affordable}")
        lines.append(f"   {desc}")
        lines.append("")
    
    return "\n".join(lines)


async def handle_shop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback магазина — HTML mode."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    from handlers.user import check_callback_rate
    if not check_callback_rate(user.id):
        return
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    from core.telegram_utils import safe_edit

    if not player:
        await safe_edit(query, shop_t(lang, "not_registered"))
        return

    data = query.data

    if data == "shop_menu":
        text = build_shop_text(player, lang)
        keyboard = build_shop_keyboard(lang)
        await safe_edit(query, text, parse_mode="HTML", reply_markup=keyboard)
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

        res = await database.fetch_val(
            "UPDATE users SET gold = gold - :price WHERE uid = :uid AND gold >= :price RETURNING 1",
            {"price": price, "uid": player.uid},
        )
        if not res:
            await query.answer(shop_t(lang, "shop_not_enough_gold"), show_alert=True)
            return
        player.gold -= price

        chest_name = shop_t(lang, f"shop_chest_{chest_type}")
        emoji = chest.get('emoji', '📦')
        
        from ui.icons import SEP
        lines = [
            f"{emoji} <b>{chest_name}</b>",
            f"💰 Потрачено: {price} золота" if lang != "en" else f"💰 Spent: {price} gold",
            SEP,
            "🎁 <b>Получено:</b>" if lang != "en" else "🎁 <b>Received:</b>",
        ]

        for _ in range(items_count):
            item, slot, replaced = await get_item(player)
            item_str = item_string(item, lang)
            upgrade = f" ⬆️ <b>УЛУЧШЕНИЕ!</b>" if lang != "en" else f" ⬆️ <b>UPGRADE!</b>" if replaced else ""
            lines.append(f"• {item_str}{upgrade}")

        text = "\n".join(lines)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(shop_t(lang, "shop_again"), callback_data=f"shop_buy_{chest_type}"),
            ],
            [
                InlineKeyboardButton(shop_t(lang, "shop_menu"), callback_data="shop_chests"),
            ],
            [
                InlineKeyboardButton(shop_t(lang, "menu"), callback_data="menu_shop"),
            ],
        ])

        await safe_edit(query, text, parse_mode="HTML", reply_markup=keyboard)


def show_shop_menu(query, player, lang: str):
    """Показать меню магазина."""
    from core.telegram_utils import safe_edit
    text = build_shop_text(player, lang)
    keyboard = build_shop_keyboard(lang)
    return safe_edit(query, text, parse_mode="HTML", reply_markup=keyboard)


def register_shop_handlers(app: Application):
    """Зарегистрировать обработчики магазина."""
    app.add_handler(CallbackQueryHandler(handle_shop_callback, pattern="^shop_"))
