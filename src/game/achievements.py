"""Достижения: проверка прогресса, разблокировка, награда токенами."""
import json
from functools import lru_cache

from core.event_bus import emit_global_event


@lru_cache(maxsize=1)
def _load_achievements():
    from data.quest_config import DATA_DIR
    with open(DATA_DIR / "achievements.json", encoding="utf-8") as f:
        return json.load(f)["achievements"]


def all_achievements() -> dict:
    return _load_achievements()


def get_achievement_config(aid: str) -> dict | None:
    return _load_achievements().get(aid)


def _progress(player) -> dict:
    raw = getattr(player, "achievement_progress", None)
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _current_value(player, atype: str) -> int:
    """Текущее значение счётчика для типа достижения."""
    if atype == "monsters_killed":
        return player.monster_kills or 0
    if atype == "xp_total":
        return player.totalxp or 0
    if atype == "win_streak":
        return player.fight_streak or 0
    if atype == "gold_earned":
        return player.gold or 0
    return _progress(player).get(atype, 0)


async def _inc_progress(player, atype: str, amount: int = 1):
    progress = _progress(player)
    progress[atype] = progress.get(atype, 0) + amount
    player.achievement_progress = json.dumps(progress)
    await player.update(_columns=["achievement_progress"])


async def check_achievements(player, atype: str, current: int | None = None):
    """Проверить все достижения типа atype, разблокировать выполнившиеся."""
    try:
        from game.titles import check_titles
        await check_titles(player)
    except Exception:
        pass
    if current is None:
        current = _current_value(player, atype)
    from db import PlayerAchievement
    unlocked = {
        a.achievement_id for a in await PlayerAchievement.objects.filter(
            player_uid=player.uid, achievement_id__in=list(_load_achievements().keys())
        ).all()
    }
    for aid, conf in _load_achievements().items():
        if conf.get("type") != atype or aid in unlocked:
            continue
        if current >= conf.get("target", 1):
            await PlayerAchievement.objects.create(
                player_uid=player.uid, achievement_id=aid, unlocked_at=int(__import__("time").time())
            )
            reward = conf.get("reward_tokens", 0)
            if reward:
                player.tokens = (player.tokens or 0) + reward
                await player.update(_columns=["tokens"])
            lang = getattr(player, "lang", None) or "ru"
            name = conf.get("name_ru", aid) if lang != "en" else conf.get("name_en", aid)
            await emit_global_event(
                "achievement_unlocked",
                f"🏆 {conf.get('icon', '')} {name}" + (f" +{reward}🪙" if reward else ""),
                [player.uid],
            )


async def on_monster_defeated(player):
    await check_achievements(player, "monsters_killed")


async def on_xp_gained(player):
    await check_achievements(player, "xp_total")


async def on_duel_win(player):
    await _inc_progress(player, "duel_wins")
    await check_achievements(player, "duel_wins")


async def on_boss_defeated(player):
    await _inc_progress(player, "bosses_killed")
    await check_achievements(player, "bosses_killed")


async def on_win_streak(player):
    await check_achievements(player, "win_streak")


async def on_rare_drop(player):
    await _inc_progress(player, "rare_drops")
    await check_achievements(player, "rare_drops")


async def on_gold_changed(player_uid: int, amount: int):
    """Подсчёт суммарного заработанного золота (только положительные поступления)."""
    if amount <= 0:
        return
    from db import Player
    player = await Player.objects.get_or_none(uid=player_uid)
    if not player:
        return
    await _inc_progress(player, "gold_earned", amount)
    await check_achievements(player, "gold_earned")
