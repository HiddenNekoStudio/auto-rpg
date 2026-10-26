"""
handlers/gems.py — /gems: инвентарь камней, выбор камня и гнезда, извлечение.

Экраны (callback):
  gems_menu                 — инвентарь + предметы с гнёздами
  gem_pick_<id>             — выбран камень → в какой предмет вставить
  gem_put_<id>_<slot>       — вставить камень <id> в предмет слота
  gem_pull_<slot>_<idx>     — достать камень из гнезда обратно в инвентарь
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from core.telegram_utils import safe_edit
from db import Player
from game import gems as gems_api
from i18n import t
from ui.format import esc
from ui.icons import SLOT

CB_MENU = "gems_menu"
GEMS_PER_PAGE = 8


def _tr(lang: str, ru: str, en: str) -> str:
    return en if lang == "en" else ru


def _gem_label(gem_id: str, lang: str) -> str:
    conf = gems_api.get_gem_config(gem_id) or {}
    name = conf.get("name_en" if lang == "en" else "name_ru", gem_id)
    return f"{conf.get('icon', '💎')} {name}"


def _gem_effect(gem_id: str, lang: str) -> str:
    conf = gems_api.get_gem_config(gem_id) or {}
    parts = []
    if conf.get("dps_pct"):
        parts.append(f"DPS +{conf['dps_pct']}%")
    if conf.get("hp_pct"):
        parts.append(f"HP +{conf['hp_pct']}%")
    if conf.get("def"):
        parts.append(f"{_tr(lang, 'Защ', 'Def')} +{conf['def']}")
    if conf.get("mp"):
        parts.append(f"MP +{conf['mp']}")
    return ", ".join(parts)


def _socketed_slots(player) -> list[tuple[str, dict]]:
    """Предметы игрока, у которых есть гнёзда."""
    result = []
    for slot in gems_api._ALL_SLOTS:
        item = gems_api._item_of(player, slot)
        if item and (item.get("sockets", 0) or 0) > 0:
            result.append((slot, item))
    return result


def _item_title(item: dict, lang: str) -> str:
    return item.get("name_en" if lang == "en" else "name", "?") or "?"


def menu_text(player, inventory: list, lang: str) -> str:
    lines = [_tr(lang, "💎 <b>Камни</b>", "💎 <b>Gems</b>"), ""]

    lines.append(_tr(lang, "<b>В инвентаре:</b>", "<b>In inventory:</b>"))
    if inventory:
        counts: dict[str, int] = {}
        for gem in inventory:
            counts[gem.gem_id] = counts.get(gem.gem_id, 0) + 1
        for gem_id, count in counts.items():
            lines.append(f"• {_gem_label(gem_id, lang)} ×{count} — {_gem_effect(gem_id, lang)}")
    else:
        lines.append(_tr(lang, "• пока пусто", "• nothing yet"))

    lines += ["", _tr(lang, "<b>Гнёзда в снаряжении:</b>", "<b>Sockets in gear:</b>")]
    slots = _socketed_slots(player)
    if not slots:
        lines.append(_tr(lang, "• у предметов нет гнёзд", "• no gear has sockets"))
    for slot, item in slots:
        cells = [(_gem_label(g, lang) if g else "▫️")
                 for g in (item.get("socketed") or [None] * item["sockets"])]
        lines.append(f"{SLOT.get(slot, '📦')} {esc(_item_title(item, lang))}: {' '.join(cells)}")

    bonuses = gems_api.get_socket_bonuses_sync(player)
    totals = [f"DPS +{bonuses['dps_pct']}%" if bonuses["dps_pct"] else "",
              f"HP +{bonuses['hp_pct']}%" if bonuses["hp_pct"] else "",
              f"{_tr(lang, 'Защ', 'Def')} +{bonuses['def']}" if bonuses["def"] else "",
              f"MP +{bonuses['mp']}" if bonuses["mp"] else ""]
    totals = [x for x in totals if x]
    if totals:
        lines += ["", _tr(lang, "Итого от камней: ", "Total from gems: ") + ", ".join(totals)]
    return "\n".join(lines)


def menu_keyboard(player, inventory: list, lang: str) -> InlineKeyboardMarkup:
    rows = []
    seen = set()
    for gem in inventory:
        if gem.gem_id in seen or len(seen) >= GEMS_PER_PAGE:
            continue
        seen.add(gem.gem_id)
        rows.append([InlineKeyboardButton(
            _tr(lang, f"Вставить: {_gem_label(gem.gem_id, lang)}",
                f"Socket: {_gem_label(gem.gem_id, lang)}"),
            callback_data=f"gem_pick_{gem.id}")])
    for slot, item in _socketed_slots(player):
        for idx, gem_id in enumerate(item.get("socketed") or []):
            if gem_id:
                rows.append([InlineKeyboardButton(
                    _tr(lang, f"Достать: {_gem_label(gem_id, lang)} ({slot})",
                        f"Remove: {_gem_label(gem_id, lang)} ({slot})"),
                    callback_data=f"gem_pull_{slot}_{idx}")])
    rows.append([InlineKeyboardButton(t(lang, "btn_profile"), callback_data="menu_profile")])
    return InlineKeyboardMarkup(rows)


def pick_screen(player, gem, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    """Куда вставить выбранный камень: только предметы со свободными гнёздами."""
    title = _tr(lang, f"Куда вставить {_gem_label(gem.gem_id, lang)}?",
                f"Where to socket {_gem_label(gem.gem_id, lang)}?")
    rows = []
    for slot, item in _socketed_slots(player):
        free = gems_api.free_sockets(item)
        if free:
            rows.append([InlineKeyboardButton(
                f"{SLOT.get(slot, '📦')} {_item_title(item, lang)} ({free} "
                f"{_tr(lang, 'своб.', 'free')})",
                callback_data=f"gem_put_{gem.id}_{slot}")])
    if not rows:
        title += "\n\n" + _tr(lang, "Нет предметов со свободными гнёздами.",
                              "No gear with a free socket.")
    rows.append([InlineKeyboardButton(_tr(lang, "🔙 Камни", "🔙 Gems"), callback_data=CB_MENU)])
    return title, InlineKeyboardMarkup(rows)


_STATUS_RU = {
    "no_item": "Предмет не найден", "no_socket": "У предмета нет гнёзд",
    "full": "Гнёзда заняты", "no_gem": "Камень недоступен", "empty": "Гнездо пусто",
}
_STATUS_EN = {
    "no_item": "Item not found", "no_socket": "Item has no sockets",
    "full": "Sockets full", "no_gem": "Gem unavailable", "empty": "Socket is empty",
}


def status_message(status: str, lang: str) -> str:
    table = _STATUS_EN if lang == "en" else _STATUS_RU
    return table.get(status, status)


async def _render_menu(player, lang: str):
    inventory = await gems_api.list_inventory(player.uid)
    return menu_text(player, inventory, lang), menu_keyboard(player, inventory, lang)


async def cmd_gems(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player = await Player.objects.get_or_none(uid=update.effective_user.id)
    if not player:
        return
    lang = player.lang or "ru"
    text, keyboard = await _render_menu(player, lang)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def _handle_pick(query, player, lang: str, gem_row_id: int) -> bool:
    """Показать выбор гнезда. False, если камня уже нет (тогда ответ дан алертом)."""
    inventory = await gems_api.list_inventory(player.uid)
    gem = next((g for g in inventory if g.id == gem_row_id), None)
    if gem is None:
        await query.answer(status_message("no_gem", lang), show_alert=True)
        return False
    await query.answer()
    text, keyboard = pick_screen(player, gem, lang)
    await safe_edit(query, text, parse_mode="HTML", reply_markup=keyboard)
    return True


async def callback_gems(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    player = await Player.objects.get_or_none(uid=query.from_user.id)
    lang = (player.lang or "ru") if player else "ru"
    if not player:
        await query.answer()
        await safe_edit(query, t(lang, "not_registered"))
        return
    data = query.data

    # На каждый callback — ровно один query.answer()
    if data.startswith("gem_pick_"):
        if await _handle_pick(query, player, lang, int(data[len("gem_pick_"):])):
            return
    elif data.startswith("gem_put_"):
        gem_id, slot = data[len("gem_put_"):].split("_", 1)
        ok, status = await gems_api.apply_gem(player, slot, int(gem_id))
        await query.answer(_tr(lang, "Камень вставлен!", "Gem socketed!") if ok
                           else status_message(status, lang), show_alert=not ok)
    elif data.startswith("gem_pull_"):
        slot, idx = data[len("gem_pull_"):].rsplit("_", 1)
        ok, status = await gems_api.extract_gem(player, slot, int(idx))
        await query.answer(_tr(lang, "Камень в инвентаре", "Gem returned to inventory") if ok
                           else status_message(status, lang), show_alert=not ok)
    else:
        await query.answer()

    text, keyboard = await _render_menu(player, lang)
    await safe_edit(query, text, parse_mode="HTML", reply_markup=keyboard)


async def show_gems_menu(query, player, lang: str):
    """Совместимость: вход из других меню (profile → gems_menu)."""
    text, keyboard = await _render_menu(player, lang)
    await safe_edit(query, text, parse_mode="HTML", reply_markup=keyboard)


def register(app: Application):
    app.add_handler(CommandHandler("gems", cmd_gems))
    app.add_handler(CallbackQueryHandler(callback_gems, pattern="^(gem_pick_|gem_put_|gem_pull_|gems_menu)"))
