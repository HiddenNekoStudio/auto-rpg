"""
game/nemesis.py — Досье на виды монстров (PQ3 nemesis).

Каждая встреча пишется в player_nemesis (переживает рестарт, в отличие от
in-memory счётчиков). После DOSSIER_ENCOUNTERS встреч с видом открывается
досье с процентом побед. Наград не даёт, только информация.
"""
import logging
import time

logger = logging.getLogger(__name__)

DOSSIER_ENCOUNTERS = 25
NEMESIS_TOP = 10


def win_rate(wins: int, encounters: int) -> float:
    """Доля побед 0..1 (0 при отсутствии встреч)."""
    if encounters <= 0:
        return 0.0
    return min(1.0, wins / encounters)


def dossier_unlocked(encounters: int) -> bool:
    return encounters >= DOSSIER_ENCOUNTERS


async def record_encounter(player_uid: int, monster_id: str, won: bool) -> None:
    """Атомарно учесть встречу; строка создаётся при первой встрече."""
    if not monster_id:
        return
    from db import PlayerNemesis, database

    now = int(time.time())
    params = {
        "uid": player_uid, "mid": monster_id, "now": now,
        "w": 1 if won else 0, "d": 0 if won else 1,
    }
    updated = await database.fetch_val(
        "UPDATE player_nemesis SET encounters = encounters + 1, "
        "wins = wins + :w, deaths = deaths + :d, last_seen = :now "
        "WHERE player_uid = :uid AND monster_id = :mid RETURNING 1",
        params,
    )
    if updated:
        return
    await PlayerNemesis.objects.create(
        player_uid=player_uid, monster_id=monster_id,
        encounters=1, wins=params["w"], deaths=params["d"], last_seen=now,
    )


async def get_dossiers(player_uid: int) -> list:
    """Виды, по которым открыто досье, по убыванию числа встреч."""
    from db import PlayerNemesis

    rows = await PlayerNemesis.objects.filter(
        player_uid=player_uid, encounters__gte=DOSSIER_ENCOUNTERS,
    ).order_by("-encounters").limit(NEMESIS_TOP).all()
    return rows
