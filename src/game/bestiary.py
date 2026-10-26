"""
game/bestiary.py — Бестиарий: счётчики убийств по видам монстров.

Идея из Progress Quest III (журнал образцов). Счётчики лежат в JSON-блобе
Player.achievement_progress под ключом "bestiary", новые колонки не нужны.
Награды за вехи одноразовые (по виду и порогу), чтобы не раздувать экономику.
"""
import json
import logging

logger = logging.getLogger(__name__)

# Пороги убийств одного вида и множитель золота от уровня игрока
BESTIARY_MILESTONES: tuple[int, ...] = (10, 50, 200)
BESTIARY_GOLD_PER_LEVEL = 25

_KEY_KILLS = "bestiary"
_KEY_CLAIMED = "bestiary_claimed"
_CAS_RETRIES = 3


def apply_kill(progress: dict, monster_id: str) -> tuple[dict, list[int]]:
    """Вернуть новый прогресс и список впервые достигнутых вех (без мутации входа)."""
    kills = dict(progress.get(_KEY_KILLS, {}))
    claimed = list(progress.get(_KEY_CLAIMED, []))

    kills[monster_id] = kills.get(monster_id, 0) + 1
    reached = []
    for milestone in BESTIARY_MILESTONES:
        tag = f"{monster_id}:{milestone}"
        if kills[monster_id] >= milestone and tag not in claimed:
            claimed.append(tag)
            reached.append(milestone)

    new_progress = {**progress, _KEY_KILLS: kills, _KEY_CLAIMED: claimed}
    return new_progress, reached


def milestone_gold(player_level: int, milestone: int) -> int:
    """Золото за веху: растёт с порогом и уровнем игрока."""
    return max(1, player_level) * BESTIARY_GOLD_PER_LEVEL * (milestone // BESTIARY_MILESTONES[0])


def _load(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return {}


async def record_kill(player, monster_id: str) -> list[int]:
    """Записать убийство. Возвращает новые вехи; золото начисляется атомарно."""
    if not monster_id:
        return []
    from db import database

    for _ in range(_CAS_RETRIES):
        old = player.achievement_progress
        new_progress, reached = apply_kill(_load(old), monster_id)
        new_raw = json.dumps(new_progress)
        updated = await database.fetch_val(
            "UPDATE users SET achievement_progress = :p "
            "WHERE uid = :uid AND achievement_progress = :old RETURNING 1",
            {"p": new_raw, "uid": player.uid, "old": old},
        )
        if not updated:
            # Конкурентная запись (например, достижения) — перечитываем и пробуем снова
            fresh = await database.fetch_val(
                "SELECT achievement_progress FROM users WHERE uid = :uid",
                {"uid": player.uid},
            )
            player.achievement_progress = fresh
            continue

        player.achievement_progress = new_raw
        gold = sum(milestone_gold(player.level, m) for m in reached)
        if gold:
            await database.execute(
                "UPDATE users SET gold = gold + :g WHERE uid = :uid",
                {"g": gold, "uid": player.uid},
            )
            player.gold = (player.gold or 0) + gold
        return reached

    logger.warning("bestiary: CAS не удался uid=%s monster=%s", player.uid, monster_id)
    return []


def bestiary_entries(player) -> list[tuple[str, int]]:
    """Список (monster_id, kills), по убыванию убийств."""
    kills = _load(player.achievement_progress).get(_KEY_KILLS, {})
    return sorted(kills.items(), key=lambda kv: kv[1], reverse=True)
