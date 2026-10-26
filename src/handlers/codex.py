"""
handlers/codex.py — «Дневник героя»: бестиарий, досье врагов, книга заклинаний
и характеристики. Один хаб с inline-кнопками + те же экраны по командам
/journal, /bestiary, /nemesis, /spellbook, /mystats и /respec.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from core.telegram_utils import safe_edit
from db import Player
from i18n import t
from ui.format import esc

BESTIARY_TOP = 15

CB_MENU = "codex_menu"
CB_BESTIARY = "codex_bestiary"
CB_NEMESIS = "codex_nemesis"
CB_SPELLBOOK = "codex_spellbook"
CB_STATS = "codex_stats"
CB_RESPEC_ASK = "codex_respec_ask"
CB_RESPEC_YES = "codex_respec_yes"

_STAT_LABELS = {
    "str": ("Сила", "Strength", "DPS"),
    "con": ("Телосложение", "Constitution", "HP"),
    "dex": ("Ловкость", "Dexterity", None),
    "int": ("Интеллект", "Intellect", "MP"),
    "wis": ("Мудрость", "Wisdom", None),
    "cha": ("Харизма", "Charisma", None),
}


def _tr(lang: str, ru: str, en: str) -> str:
    return en if lang == "en" else ru


def _button(lang: str, ru: str, en: str, callback: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(_tr(lang, ru, en), callback_data=callback)


def hub_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_button(lang, "📖 Бестиарий", "📖 Bestiary", CB_BESTIARY),
         _button(lang, "🗡️ Досье врагов", "🗡️ Nemesis", CB_NEMESIS)],
        [_button(lang, "📕 Заклинания", "📕 Spellbook", CB_SPELLBOOK)],
        [_button(lang, "🔙 Профиль", "🔙 Profile", "menu_profile")],
    ])


def _back_keyboard(lang: str, *extra_rows: list) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([*extra_rows, [_button(lang, "🔙 Дневник", "🔙 Journal", CB_MENU)]])


def hub_text(lang: str) -> str:
    return _tr(
        lang,
        "📔 <b>Дневник героя</b>\n\nВсё, что ты накопил в приключениях:",
        "📔 <b>Hero's journal</b>\n\nEverything you've collected on your adventures:",
    )


def _monster_names(lang: str) -> dict[str, str]:
    from game.factories import MonsterFactory
    return {
        m["id"]: (m["name_en"] if lang == "en" else m["name_ru"])
        for m in MonsterFactory.get_config()._data
    }


def bestiary_text(player, lang: str) -> str:
    from game.bestiary import BESTIARY_MILESTONES, bestiary_entries

    title = _tr(lang, "📖 <b>Бестиарий</b>", "📖 <b>Bestiary</b>")
    entries = bestiary_entries(player)[:BESTIARY_TOP]
    if not entries:
        return f"{title}\n\n" + _tr(lang, "Пока нет убитых монстров.", "No kills recorded yet.")

    names = _monster_names(lang)
    lines = [title, ""]
    for monster_id, kills in entries:
        next_goal = next((m for m in BESTIARY_MILESTONES if kills < m), None)
        goal = f" → {next_goal}" if next_goal else " ✅"
        lines.append(f"• {esc(names.get(monster_id, monster_id))}: <b>{kills}</b>{goal}")
    return "\n".join(lines)


async def nemesis_text(player, lang: str) -> str:
    from game.nemesis import DOSSIER_ENCOUNTERS, get_dossiers, win_rate

    title = _tr(lang, "🗡️ <b>Досье врагов</b>", "🗡️ <b>Nemesis dossier</b>")
    rows = await get_dossiers(player.uid)
    if not rows:
        return f"{title}\n\n" + _tr(
            lang,
            f"Досье открывается после {DOSSIER_ENCOUNTERS} встреч с видом.",
            f"A dossier opens after {DOSSIER_ENCOUNTERS} encounters with a species.",
        )

    names = _monster_names(lang)
    lines = [title, ""]
    for row in rows:
        pct = int(win_rate(row.wins, row.encounters) * 100)
        label = esc(names.get(row.monster_id, row.monster_id))
        lines.append(f"• {label}: {row.encounters} / ✅ {pct}% / 💀 {row.deaths}")
    return "\n".join(lines)


def spellbook_text(player, lang: str) -> str:
    from game.acts import act_for_level, act_name
    from game.spellbook import SPELLS, learned_ids, spell_name

    known = set(learned_ids(player.achievement_progress))
    act = act_for_level(player.level)
    lines = [
        _tr(lang, "📕 <b>Книга заклинаний</b>", "📕 <b>Spellbook</b>"),
        f"📜 {_tr(lang, 'Акт', 'Act')} {act.number}: {esc(act_name(act, lang))}",
        "",
    ]
    for spell in SPELLS:
        lines.append(f"✨ {esc(spell_name(spell, lang))}" if spell.id in known else "▫️ ???")
    lines += ["", f"{len(known)}/{len(SPELLS)}"]
    return "\n".join(lines)


def stats_text(player, lang: str) -> str:
    from game.stats import STAT_ICONS, read_stats, stat_bonus

    lines = [_tr(lang, "💪 <b>Характеристики</b>", "💪 <b>Stats</b>"), ""]
    for stat, value in read_stats(player).items():
        ru, en, effect = _STAT_LABELS[stat]
        bonus = int(round(stat_bonus(value) * 100))
        suffix = f" — {effect} +{bonus}%" if effect else _tr(lang, " — копится", " — accumulating")
        lines.append(f"{STAT_ICONS[stat]} {_tr(lang, ru, en)}: <b>{value}</b>{suffix}")
    lines += ["", _tr(lang, "+1 очко за каждый уровень.", "+1 point per level.")]
    return "\n".join(lines)


def _stats_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Характеристики открываются из профиля, поэтому «Назад» ведёт туда же."""
    from game.stats import RESPEC_TOKEN_COST
    return InlineKeyboardMarkup([
        [_button(lang, f"♻️ Сброс ({RESPEC_TOKEN_COST}🪙)", f"♻️ Respec ({RESPEC_TOKEN_COST}🪙)", CB_RESPEC_ASK)],
        [_button(lang, "🔙 Профиль", "🔙 Profile", "menu_profile")],
    ])


async def _screen(player, lang: str, kind: str) -> tuple[str, InlineKeyboardMarkup]:
    if kind == CB_BESTIARY:
        return bestiary_text(player, lang), _back_keyboard(lang)
    if kind == CB_NEMESIS:
        return await nemesis_text(player, lang), _back_keyboard(lang)
    if kind == CB_SPELLBOOK:
        return spellbook_text(player, lang), _back_keyboard(lang)
    if kind == CB_STATS:
        return stats_text(player, lang), _stats_keyboard(lang)
    return hub_text(lang), hub_keyboard(lang)


async def _respec_screen(player, lang: str, confirmed: bool) -> tuple[str, InlineKeyboardMarkup]:
    from game.stats import RESPEC_TOKEN_COST, respec

    if not confirmed:
        text = _tr(
            lang,
            f"♻️ Сбросить характеристики к ровной раскладке за {RESPEC_TOKEN_COST} 🪙?\n"
            f"У тебя: {player.tokens or 0} 🪙",
            f"♻️ Reset stats to an even layout for {RESPEC_TOKEN_COST} 🪙?\n"
            f"You have: {player.tokens or 0} 🪙",
        )
        return text, InlineKeyboardMarkup([[
            _button(lang, "✅ Да", "✅ Yes", CB_RESPEC_YES),
            _button(lang, "❌ Нет", "❌ No", CB_STATS),
        ]])

    if not await respec(player):
        text = _tr(lang, "Не хватает токенов.", "Not enough tokens.")
        return text, _stats_keyboard(lang)

    from core.dps import invalidate_dps_cache
    player.sync_max_hp_mp()
    invalidate_dps_cache(player.uid)
    return stats_text(player, lang), _stats_keyboard(lang)


async def _load_player(uid: int):
    player = await Player.objects.get_or_none(uid=uid)
    return (player, player.lang or "ru") if player and player.lang else (None, "ru")


async def callback_codex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from handlers.user import check_callback_rate

    query = update.callback_query
    player, lang = await _load_player(query.from_user.id)
    if not check_callback_rate(query.from_user.id):
        await query.answer(_tr(lang, "Подожди секунду!", "Wait a second!"), show_alert=True)
        return
    await query.answer()
    if not player:
        await safe_edit(query, t("ru", "not_registered"))
        return

    if query.data in (CB_RESPEC_ASK, CB_RESPEC_YES):
        text, keyboard = await _respec_screen(player, lang, query.data == CB_RESPEC_YES)
    else:
        text, keyboard = await _screen(player, lang, query.data)
    await safe_edit(query, text, parse_mode="HTML", reply_markup=keyboard)


def _command(kind: str):
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        player, lang = await _load_player(update.effective_user.id)
        if not player:
            await update.message.reply_text(t("ru", "not_registered"))
            return
        text, keyboard = await _screen(player, lang, kind)
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
    return handler


async def cmd_respec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/respec — тот же экран подтверждения, что и кнопка в характеристиках."""
    player, lang = await _load_player(update.effective_user.id)
    if not player:
        await update.message.reply_text(t("ru", "not_registered"))
        return
    text, keyboard = await _respec_screen(player, lang, confirmed=False)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


def register(app: Application):
    app.add_handler(CommandHandler("journal", _command(CB_MENU)))
    app.add_handler(CommandHandler("bestiary", _command(CB_BESTIARY)))
    app.add_handler(CommandHandler("nemesis", _command(CB_NEMESIS)))
    app.add_handler(CommandHandler("spellbook", _command(CB_SPELLBOOK)))
    app.add_handler(CommandHandler("mystats", _command(CB_STATS)))
    app.add_handler(CommandHandler("respec", cmd_respec))
    app.add_handler(CallbackQueryHandler(callback_codex, pattern="^codex_"))
