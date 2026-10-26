"""
game/progress_blob.py — безопасное изменение JSON-блоба Player.achievement_progress.

Блоб делят достижения, бестиарий и акты, поэтому запись идёт через CAS
(UPDATE ... WHERE achievement_progress = :old), чтобы параллельные писатели
не затирали друг друга.
"""
import json
import logging
from typing import Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
CAS_RETRIES = 3


def load_progress(raw) -> dict:
    """Разобрать блоб; битый JSON даёт пустой словарь."""
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return {}


async def mutate_progress(
    player, mutator: Callable[[dict], tuple[dict, T]]
) -> Optional[T]:
    """Применить mutator(progress) -> (new_progress, result) через CAS.

    Возвращает result либо None, если CAS не удался за CAS_RETRIES попыток.
    mutator должен быть чистым: он может вызываться повторно.
    """
    from db import database

    for _ in range(CAS_RETRIES):
        old = player.achievement_progress
        new_progress, result = mutator(load_progress(old))
        new_raw = json.dumps(new_progress)
        updated = await database.fetch_val(
            "UPDATE users SET achievement_progress = :p "
            "WHERE uid = :uid AND achievement_progress = :old RETURNING 1",
            {"p": new_raw, "uid": player.uid, "old": old},
        )
        if updated:
            player.achievement_progress = new_raw
            return result
        player.achievement_progress = await database.fetch_val(
            "SELECT achievement_progress FROM users WHERE uid = :uid",
            {"uid": player.uid},
        )

    logger.warning("progress blob: CAS не удался uid=%s", player.uid)
    return None
