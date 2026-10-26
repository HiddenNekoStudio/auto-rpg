"""
game/home.py — Главный экран (/start, «Меню»): живая сводка и кнопки по ситуации.

Текст и клавиатура строятся из HomeSnapshot (чистые функции, легко тестировать),
данные для снимка собирает load_snapshot. Кнопка действия меняется с контекстом:
готова ежедневная награда, идёт охота, есть активные квесты.
"""
import time
from dataclasses import dataclass

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from game.absence import DAY_SECONDS
from ui.bars import skill_bar
from ui.format import esc

XP_BAR_WIDTH = 10

# Разделы, спрятанные с главного экрана. Всё это доступно из профиля
# (см. handlers/user.py:_profile_keyboard). Чтобы вернуть кнопки, очистите
# набор или поставьте SHOW_ALL_NAV = True.
HIDDEN_NAV: frozenset[str] = frozenset({
    "menu_quest",
    "battle_menu",
    "menu_hunt",
    "menu_shop",
    "clan_menu",
    "codex_menu",
    "pets_menu",
})
SHOW_ALL_NAV = False


@dataclass(frozen=True)
class HomeSnapshot:
    name: str
    level: int
    xp_pct: int
    xp_left: str          # время до следующего уровня, уже отформатированное
    hp: int
    max_hp: int
    gold: str
    tokens: int
    active_quests: int
    daily_ready: bool
    hunting_left: str     # пусто, если игрок не на охоте


def _tr(lang: str, ru: str, en: str) -> str:
    return en if lang == "en" else ru


def _button(lang: str, ru: str, en: str, callback: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(_tr(lang, ru, en), callback_data=callback)


def build_home_text(s: HomeSnapshot, lang: str = "ru") -> str:
    lines = [
        _tr(lang, f"⚔️ <b>{esc(s.name)}</b> — главное меню",
            f"⚔️ <b>{esc(s.name)}</b> — main menu"),
        "",
        f"🎖️ {_tr(lang, 'Ур.', 'Lv.')} <b>{s.level}</b>  {skill_bar(s.xp_pct, 100, XP_BAR_WIDTH)} {s.xp_pct}%",
        _tr(lang, f"⏱️ До следующего уровня: <b>{s.xp_left}</b>",
            f"⏱️ Next level in: <b>{s.xp_left}</b>"),
        f"❤️ <b>{s.hp}/{s.max_hp}</b>   💰 <b>{s.gold}</b>   🪙 <b>{s.tokens}</b>",
    ]
    status = []
    if s.hunting_left:
        status.append(_tr(lang, f"🗡️ На охоте, осталось: <b>{s.hunting_left}</b>",
                          f"🗡️ Hunting, time left: <b>{s.hunting_left}</b>"))
    if s.daily_ready:
        status.append(_tr(lang, "📅 Ежедневная награда <b>готова</b>!",
                          "📅 Daily reward is <b>ready</b>!"))
    if s.active_quests:
        status.append(_tr(lang, f"🎯 Активных квестов: <b>{s.active_quests}</b>",
                          f"🎯 Active quests: <b>{s.active_quests}</b>"))
    if status:
        lines += ["", *status]
    return "\n".join(lines)


def build_home_keyboard(s: HomeSnapshot, lang: str = "ru") -> InlineKeyboardMarkup:
    """Верхний ряд — самое актуальное действие; ниже — постоянная навигация."""
    action_row = []
    if s.daily_ready:
        action_row.append(_button(lang, "📅 Забрать награду", "📅 Claim reward", "daily_menu"))
    if s.hunting_left:
        action_row.append(_button(lang, "🗡️ Состояние охоты", "🗡️ Hunt status", "hunt_status"))
    elif s.active_quests:
        action_row.append(_button(lang, f"🎯 Квесты ({s.active_quests})",
                                  f"🎯 Quests ({s.active_quests})", "menu_quest"))
    rows = [action_row] if action_row else []
    rows += _navigation_rows(lang)
    return InlineKeyboardMarkup(rows)


def _navigation_rows(lang: str) -> list[list[InlineKeyboardButton]]:
    """Навигация главного экрана. Скрытые разделы живут в профиле (см. HIDDEN_NAV)."""
    rows = [
        [_button(lang, "👤 Профиль", "👤 Profile", "menu_profile"),
         _button(lang, "🎯 Квесты", "🎯 Quests", "menu_quest")],
        [_button(lang, "⚔️ Бой", "⚔️ Battle", "battle_menu"),
         _button(lang, "🗡️ Охота", "🗡️ Hunt", "menu_hunt")],
        [_button(lang, "🏪 Магазин", "🏪 Shop", "menu_shop"),
         _button(lang, "🏰 Клан", "🏰 Clan", "clan_menu")],
        [_button(lang, "📔 Дневник", "📔 Journal", "codex_menu"),
         _button(lang, "🐾 Питомцы", "🐾 Pets", "pets_menu")],
        [_button(lang, "📊 Статистика", "📊 Statistics", "menu_stats"),
         _button(lang, "⚙️ Настройки", "⚙️ Settings", "menu_settings")],
        [_button(lang, "ℹ️ О игре", "ℹ️ About", "menu_info"),
         _button(lang, "🔄 Обновить", "🔄 Refresh", "menu_back")],
    ]
    if SHOW_ALL_NAV:
        return rows
    visible = []
    for row in rows:
        kept = [b for b in row if b.callback_data not in HIDDEN_NAV]
        if kept:
            visible.append(kept)
    return visible


def static_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Меню без данных игрока (онбординг, смена языка): только навигация."""
    return InlineKeyboardMarkup(_navigation_rows(lang))


def daily_is_ready(last_daily_claim: int, now: int) -> bool:
    return (last_daily_claim or 0) // DAY_SECONDS != now // DAY_SECONDS


async def load_snapshot(player, lang: str) -> HomeSnapshot:
    from bot import ctime, format_short
    from db import PlayerQuest
    from game.hunting import is_hunting

    now = int(time.time())
    active = await PlayerQuest.objects.filter(
        player_uid=player.uid, status="active"
    ).count()
    next_xp = max(1, player.nextxp or 1)
    xp_pct = max(0, min(100, int(100 * (player.currentxp or 0) / next_xp)))
    hunting_left = (
        ctime(max(0, player.hunting_expires_at - now), lang) if is_hunting(player) else ""
    )
    return HomeSnapshot(
        name=player.name,
        level=player.level,
        xp_pct=xp_pct,
        xp_left=ctime(max(0, next_xp - (player.currentxp or 0)), lang),
        hp=player.hp,
        max_hp=player.max_hp,
        gold=format_short(player.gold or 0),
        tokens=player.tokens or 0,
        active_quests=active,
        daily_ready=daily_is_ready(player.last_daily_claim, now),
        hunting_left=hunting_left,
    )


async def home_keyboard_for(player, lang: str) -> InlineKeyboardMarkup:
    """Клавиатура главного экрана для текста, который уже собран вызывающим кодом."""
    return build_home_keyboard(await load_snapshot(player, lang), lang)


async def home_screen(player, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    snapshot = await load_snapshot(player, lang)
    return build_home_text(snapshot, lang), build_home_keyboard(snapshot, lang)
