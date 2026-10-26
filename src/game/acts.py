"""
game/acts.py — Акты: главы прогресса по уровню (PQ3 acts).

Вход в новый акт даёт одноразовую награду токенами и титульную строку в
уведомлении. XP и золото не выдаются, чтобы не ломать кривую TIME_BASE/TIME_EXP.
Отметки о полученных актах лежат в achievement_progress["acts_claimed"].
"""
import logging
from typing import NamedTuple

from game.progress_blob import mutate_progress

logger = logging.getLogger(__name__)

_KEY_CLAIMED = "acts_claimed"


class Act(NamedTuple):
    number: int
    min_level: int
    name_ru: str
    name_en: str
    tokens: int


ACTS: tuple[Act, ...] = (
    Act(1, 1, "Пролог", "Prologue", 0),
    Act(2, 10, "Дорога героя", "The Hero's Road", 1),
    Act(3, 25, "Тёмные земли", "Darklands", 2),
    Act(4, 50, "Осада бездны", "Siege of the Abyss", 3),
    Act(5, 80, "Закат эпохи", "Twilight of an Age", 5),
    Act(6, 120, "Эпилог", "Epilogue", 8),
)


def act_for_level(level: int) -> Act:
    """Текущий акт для уровня (последний, чей порог достигнут)."""
    current = ACTS[0]
    for act in ACTS:
        if level >= act.min_level:
            current = act
    return current


def unlocked_acts(level: int) -> list[Act]:
    return [a for a in ACTS if level >= a.min_level]


def act_name(act: Act, lang: str = "ru") -> str:
    return act.name_en if lang == "en" else act.name_ru


def claim_new_acts(progress: dict, level: int) -> tuple[dict, list[Act]]:
    """Чистая функция: вернуть новый прогресс и впервые открытые акты."""
    claimed = list(progress.get(_KEY_CLAIMED, []))
    fresh = [a for a in unlocked_acts(level) if a.number not in claimed]
    if not fresh:
        return progress, []
    claimed.extend(a.number for a in fresh)
    return {**progress, _KEY_CLAIMED: claimed}, fresh


async def check_act_progress(player) -> list[Act]:
    """Отметить новые акты и начислить токены. Возвращает открытые акты."""
    fresh = await mutate_progress(
        player, lambda progress: claim_new_acts(progress, player.level)
    )
    if not fresh:
        return []

    tokens = sum(a.tokens for a in fresh)
    if tokens:
        from db import database
        await database.execute(
            "UPDATE users SET tokens = tokens + :t WHERE uid = :uid",
            {"t": tokens, "uid": player.uid},
        )
        player.tokens = (player.tokens or 0) + tokens
    return fresh
