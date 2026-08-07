"""Титулы: проверка разблокировки, экипировка, показ."""
import json
from functools import lru_cache


@lru_cache(maxsize=1)
def _load_titles():
    from data.quest_config import DATA_DIR
    with open(DATA_DIR / "titles.json", encoding="utf-8") as f:
        return json.load(f)["titles"]


def all_titles() -> dict:
    return _load_titles()


def get_title_config(title_id: str) -> dict | None:
    return _load_titles().get(title_id)


def _progress(player) -> dict:
    raw = getattr(player, "achievement_progress", None)
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _current_value(player, req_type: str) -> int:
    if req_type == "level":
        return player.level or 0
    if req_type == "monsters_killed":
        return player.monster_kills or 0
    if req_type == "win_streak":
        return player.fight_streak or 0
    if req_type == "prestige_count":
        return player.prestige_count or 0
    return _progress(player).get(req_type, 0)


def is_unlocked(player, title_id: str) -> bool:
    conf = get_title_config(title_id)
    if not conf:
        return False
    req = conf.get("requirement", {})
    return _current_value(player, req.get("type", "level")) >= req.get("target", 1)


async def unlocked_titles(player) -> list[str]:
    """Список title_id, доступных игроку по требованиям."""
    return [tid for tid in all_titles() if is_unlocked(player, tid)]


async def title_name(title_id: str, lang: str) -> str:
    conf = get_title_config(title_id)
    if not conf:
        return title_id
    return conf.get("name_ru", title_id) if lang != "en" else conf.get("name_en", title_id)


def format_title(player, lang: str) -> str:
    """Оформление титула для строки профиля."""
    tid = getattr(player, "title_id", "") or ""
    if not tid:
        return ""
    conf = get_title_config(tid)
    if not conf:
        return ""
    return conf.get("name_ru", tid) if lang != "en" else conf.get("name_en", tid)


async def check_titles(player):
    """Разблокировать все доступные титулы."""
    from db import PlayerTitle
    owned = {
        a.title_id for a in await PlayerTitle.objects.filter(
            player_uid=player.uid, title_id__in=list(all_titles().keys())
        ).all()
    }
    for tid, conf in all_titles().items():
        if tid in owned:
            continue
        req = conf.get("requirement", {})
        if _current_value(player, req.get("type", "level")) >= req.get("target", 1):
            await PlayerTitle.objects.create(
                player_uid=player.uid, title_id=tid, unlocked_at=int(__import__("time").time())
            )
