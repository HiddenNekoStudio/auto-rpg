"""Драгоценные камни: дроп, вставка в гнёзда, суммирование бонусов."""
import json
import random
from functools import lru_cache

try:
    from config import GEM_SOCKET_CHANCE, GEM_DROP_CHANCE  # noqa: F401
except ImportError:
    GEM_SOCKET_CHANCE = 0.25
    GEM_DROP_CHANCE = 0.08


@lru_cache(maxsize=1)
def _load_gems():
    from data.quest_config import DATA_DIR
    with open(DATA_DIR / "gems.json", encoding="utf-8") as f:
        return json.load(f)["gems"]


def get_gem_config(gem_id: str) -> dict | None:
    return _load_gems().get(gem_id)


def random_gem() -> str | None:
    """Случайный камень с учётом весов. None если выпал пустышка."""
    gems = _load_gems()
    if not gems:
        return None
    r = random.uniform(0, 1)
    total = sum(g.get("drop_weight", 1) for g in gems.values())
    roll = r * total
    for gid, g in gems.items():
        roll -= g.get("drop_weight", 1)
        if roll <= 0:
            return gid
    return list(gems)[-1]


def parse_gem_ids(raw: str) -> list:
    try:
        data = json.loads(raw) if raw else []
    except (json.JSONDecodeError, TypeError):
        data = []
    return [g for g in data if isinstance(g, str)]


async def apply_gem(owner, slot: str) -> tuple[bool, str]:
    """Вставить камень в первое свободное гнездо предмета."""
    item = getattr(owner, slot, None)
    if not item or not isinstance(item, dict):
        return False, "no_item"
    sockets = item.get("sockets", 0) or 0
    socketed = item.get("socketed") or []
    if sockets == 0:
        return False, "no_socket"
    if all(socketed):
        return False, "full"
    from db import PlayerGem
    gem = await PlayerGem.objects.filter(
        player_uid=owner.uid, equipped=False
    ).order_by("-id").get_or_none()
    if not gem:
        return False, "no_gem"
    idx = socketed.index(None)
    socketed[idx] = gem.gem_id
    item["socketed"] = socketed
    setattr(owner, slot, json.dumps(item))
    gem.equipped = True
    await gem.update(_columns=["equipped"])
    await owner.update(_columns=[slot])
    return True, "ok"


async def extract_gem(owner, slot: str, idx: int) -> tuple[bool, str]:
    """Извлечь камень из гнезда обратно в инвентарь."""
    item = getattr(owner, slot, None)
    if not item or not isinstance(item, dict):
        return False, "no_item"
    socketed = item.get("socketed") or []
    if idx < 0 or idx >= len(socketed) or not socketed[idx]:
        return False, "empty"
    gem_id = socketed[idx]
    socketed[idx] = None
    item["socketed"] = socketed
    setattr(owner, slot, json.dumps(item))
    from db import PlayerGem
    await PlayerGem.objects.create(player_uid=owner.uid, gem_id=gem_id)
    await owner.update(_columns=[slot])
    return True, "ok"


async def socketed_gems(owner, slot: str) -> list[str]:
    """Список gem_id, вставленных в предмет в слоте."""
    item = getattr(owner, slot, None)
    if not item or not isinstance(item, dict):
        return []
    return [g for g in (item.get("socketed") or []) if g]


_ALL_SLOTS = ("weapon", "shield", "helmet", "chest", "gloves", "boots", "ring", "amulet")


def get_socket_bonuses_sync(owner) -> dict:
    """Суммарные бонусы от всех вставленных камней (синхронно, из JSON предметов)."""
    total = {"dps_pct": 0, "hp_pct": 0, "def": 0, "mp": 0}
    for slot in _ALL_SLOTS:
        item = getattr(owner, slot, None)
        if isinstance(item, str):
            try:
                item = json.loads(item)
            except json.JSONDecodeError:
                item = None
        if not isinstance(item, dict):
            continue
        for gid in (item.get("socketed") or []):
            conf = get_gem_config(gid)
            if not conf:
                continue
            for key in total:
                total[key] += conf.get(key, 0)
    return total


async def get_socket_bonuses(owner) -> dict:
    """Суммарные бонусы от всех вставленных камней во всех слотах."""
    return get_socket_bonuses_sync(owner)


async def add_gem_to_inventory(player_uid: int, gem_id: str) -> None:
    from db import PlayerGem
    await PlayerGem.objects.create(player_uid=player_uid, gem_id=gem_id)
