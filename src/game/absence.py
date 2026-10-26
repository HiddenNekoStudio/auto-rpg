"""
game/absence.py — Сводка «пока тебя не было» при возврате из оффлайна.

Показывает только то, что реально происходит с оффлайн-игроком: накопленный
опыт (idle_xp), полученные уровни, восстановленные HP/MP. Бои, охота и квесты
офлайн не идут (циклы фильтруют по online=True), поэтому убийств и золота
в сводке нет. Вместо них подсказки, что можно сделать прямо сейчас.
"""
import time
from dataclasses import dataclass

from ui.format import esc

DAY_SECONDS = 86400


@dataclass(frozen=True)
class AbsenceDigest:
    name: str
    away: str            # отформатированная длительность, например «5ч 20м»
    xp: str              # отформатированный опыт, например «12.3K»
    levels_gained: int
    level: int
    next_in: str         # время до следующего уровня
    hp: int
    max_hp: int
    mp: int
    max_mp: int
    daily_ready: bool
    active_quests: int
    slow_xp: bool        # отсутствие дольше суток: опыт копился медленнее


def _tr(lang: str, ru: str, en: str) -> str:
    return en if lang == "en" else ru


def build_digest(d: AbsenceDigest, lang: str = "ru") -> str:
    """Собрать HTML-сообщение из готовых данных (чистая функция)."""
    lines = [
        _tr(lang, f"🌙 <b>С возвращением, {esc(d.name)}!</b>",
            f"🌙 <b>Welcome back, {esc(d.name)}!</b>"),
        "",
        _tr(lang, f"💤 Тебя не было: <b>{d.away}</b>", f"💤 You were away: <b>{d.away}</b>"),
        f"⚡ XP: <b>+{d.xp}</b>",
    ]
    if d.levels_gained:
        lines.append(_tr(lang, f"🆙 Уровней: <b>+{d.levels_gained}</b>",
                         f"🆙 Levels: <b>+{d.levels_gained}</b>"))
    lines.append(_tr(lang, f"🎖️ Уровень <b>{d.level}</b>, до следующего: <b>{d.next_in}</b>",
                     f"🎖️ Level <b>{d.level}</b>, next level in: <b>{d.next_in}</b>"))
    lines.append(f"❤️ HP <b>{d.hp}/{d.max_hp}</b>   💧 MP <b>{d.mp}/{d.max_mp}</b>")
    if d.slow_xp:
        lines.append(_tr(lang, "🐢 После суток отсутствия опыт копится медленнее.",
                         "🐢 After a day away, XP accrues more slowly."))

    todo = []
    if d.daily_ready:
        todo.append(_tr(lang, "📅 Ждёт ежедневная награда: /daily",
                        "📅 Daily reward is waiting: /daily"))
    if d.active_quests:
        todo.append(_tr(lang, f"🎯 Активных квестов: {d.active_quests}: /quest",
                        f"🎯 Active quests: {d.active_quests}: /quest"))
    if todo:
        lines += ["", _tr(lang, "<b>Что дальше:</b>", "<b>What's next:</b>"), *todo]
    return "\n".join(lines)


async def absence_text(player, lang: str, away_seconds: int, xp: int, levels_gained: int) -> str:
    """Собрать сводку для игрока: добрать из БД число активных квестов."""
    from bot import ctime, format_short
    from db import PlayerQuest

    now = int(time.time())
    active_quests = await PlayerQuest.objects.filter(
        player_uid=player.uid, status="active"
    ).count()
    digest = AbsenceDigest(
        name=player.name,
        away=ctime(away_seconds, lang),
        xp=format_short(xp),
        levels_gained=levels_gained,
        level=player.level,
        next_in=ctime(max(0, player.nextxp - player.currentxp), lang),
        hp=player.hp,
        max_hp=player.max_hp,
        mp=player.mp,
        max_mp=player.max_mp,
        daily_ready=(player.last_daily_claim or 0) // DAY_SECONDS != now // DAY_SECONDS,
        active_quests=active_quests,
        slow_xp=away_seconds > DAY_SECONDS,
    )
    return build_digest(digest, lang)
