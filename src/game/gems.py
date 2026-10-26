"""Драгоценные камни: дроп, вставка в гнёзда, суммирование бонусов.

Источник правды о том, где лежит камень, один: таблица player_gems.
  equipped=False                 — камень в инвентаре;
  equipped=True, slot, socket_idx — камень вставлен в гнездо предмета.
JSON предмета (item["socketed"]) хранит только gem_id для быстрого расчёта
бонусов; он меняется вместе со строкой player_gems в одном месте (здесь).
"""
import json
import random
from functools import lru_cache

try:
    from config import GEM_SOCKET_CHANCE, GEM_DROP_CHANCE  # noqa: F401
except ImportError:
    GEM_SOCKET_CHANCE = 0.25
    GEM_DROP_CHANCE = 0.08

_ALL_SLOTS = ("weapon", "shield", "helmet", "chest", "gloves", "boots", "ring", "amulet")

# Суммарный бонус камней по каждой характеристике не выше этого потолка
GEM_BONUS_CAP = {"dps_pct": 25, "hp_pct": 25}


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


def _item_of(owner, slot: str) -> dict | None:
    """Предмет слота как dict (ormar уже десериализует JSON-колонку)."""
    item = getattr(owner, slot, None)
    if isinstance(item, str):
        try:
            item = json.loads(item)
        except json.JSONDecodeError:
            return None
    return item if isinstance(item, dict) else None


def _refresh_caches(owner) -> None:
    owner.sync_max_hp_mp()
    from core.dps import invalidate_dps_cache
    invalidate_dps_cache(owner.uid)


def free_sockets(item: dict) -> int:
    """Сколько пустых гнёзд у предмета."""
    sockets = item.get("sockets", 0) or 0
    socketed = item.get("socketed") or []
    return sum(1 for i in range(sockets) if i >= len(socketed) or not socketed[i])


async def list_inventory(player_uid: int) -> list:
    """Камни в инвентаре (не вставленные), новые первыми."""
    from db import PlayerGem
    return await PlayerGem.objects.filter(
        player_uid=player_uid, equipped=False
    ).order_by("-id").all()


async def apply_gem(owner, slot: str, gem_row_id: int | None = None) -> tuple[bool, str]:
    """Вставить камень в первое свободное гнездо. gem_row_id — выбранный камень
    (по умолчанию самый новый из инвентаря)."""
    item = _item_of(owner, slot)
    if item is None:
        return False, "no_item"
    if not (item.get("sockets", 0) or 0):
        return False, "no_socket"
    if free_sockets(item) == 0:
        return False, "full"

    from db import PlayerGem, database
    if gem_row_id is None:
        gem = (await list_inventory(owner.uid) or [None])[0]
        if gem is None:
            return False, "no_gem"
        gem_row_id = gem.id

    sockets = item["sockets"]
    socketed = list(item.get("socketed") or [])
    socketed += [None] * (sockets - len(socketed))
    idx = next(i for i in range(sockets) if not socketed[i])

    # Атомарно «забираем» камень: двойное нажатие вставит его только один раз
    claimed = await database.fetch_val(
        "UPDATE player_gems SET equipped = TRUE, slot = :slot, socket_idx = :idx "
        "WHERE id = :id AND player_uid = :uid AND equipped = FALSE RETURNING 1",
        {"slot": slot, "idx": idx, "id": gem_row_id, "uid": owner.uid},
    )
    if not claimed:
        return False, "no_gem"

    gem = await PlayerGem.objects.get(id=gem_row_id)
    socketed[idx] = gem.gem_id
    setattr(owner, slot, {**item, "socketed": socketed})
    await owner.update(_columns=[slot])
    _refresh_caches(owner)
    return True, "ok"


async def extract_gem(owner, slot: str, idx: int) -> tuple[bool, str]:
    """Вернуть камень из гнезда в инвентарь (та же строка player_gems)."""
    item = _item_of(owner, slot)
    if item is None:
        return False, "no_item"
    socketed = list(item.get("socketed") or [])
    if idx < 0 or idx >= len(socketed) or not socketed[idx]:
        return False, "empty"

    from db import database
    released = await database.fetch_val(
        "UPDATE player_gems SET equipped = FALSE, slot = '', socket_idx = -1 "
        "WHERE player_uid = :uid AND equipped = TRUE AND slot = :slot AND socket_idx = :idx "
        "RETURNING 1",
        {"uid": owner.uid, "slot": slot, "idx": idx},
    )
    socketed[idx] = None
    setattr(owner, slot, {**item, "socketed": socketed})
    await owner.update(_columns=[slot])
    _refresh_caches(owner)
    return (True, "ok") if released else (True, "ok_orphan")


async def release_slot_gems(player_uid: int, slot: str) -> int:
    """Вернуть в инвентарь все камни слота (при замене предмета). Возвращает число."""
    from db import database
    rows = await database.fetch_all(
        "SELECT id FROM player_gems WHERE player_uid = :uid AND equipped = TRUE AND slot = :slot",
        {"uid": player_uid, "slot": slot},
    )
    if not rows:
        return 0
    await database.execute(
        "UPDATE player_gems SET equipped = FALSE, slot = '', socket_idx = -1 "
        "WHERE player_uid = :uid AND equipped = TRUE AND slot = :slot",
        {"uid": player_uid, "slot": slot},
    )
    return len(rows)


async def replace_item(owner, slot: str, new_item: dict) -> int:
    """Заменить предмет в слоте, вернув камни старого в инвентарь.

    Единая точка замены: лут, охота, престиж и т.п. вызывают её вместо
    setattr(), иначе камни остаются «вставленными» в предмет, которого нет.
    Возвращает число возвращённых камней.
    """
    returned = await release_slot_gems(owner.uid, slot)
    setattr(owner, slot, new_item)
    return returned


async def socketed_gems(owner, slot: str) -> list[str]:
    """Список gem_id, вставленных в предмет в слоте."""
    item = _item_of(owner, slot)
    return [g for g in ((item or {}).get("socketed") or []) if g]


def get_socket_bonuses_sync(owner) -> dict:
    """Суммарные бонусы от вставленных камней (из JSON предметов), с потолком."""
    total = {"dps_pct": 0, "hp_pct": 0, "def": 0, "mp": 0}
    for slot in _ALL_SLOTS:
        item = _item_of(owner, slot)
        if item is None:
            continue
        for gid in (item.get("socketed") or []):
            conf = get_gem_config(gid) if gid else None
            if not conf:
                continue
            for key in total:
                total[key] += conf.get(key, 0)
    for key, cap in GEM_BONUS_CAP.items():
        total[key] = min(total[key], cap)
    return total


async def get_socket_bonuses(owner) -> dict:
    """Суммарные бонусы от всех вставленных камней во всех слотах."""
    return get_socket_bonuses_sync(owner)


async def add_gem_to_inventory(player_uid: int, gem_id: str) -> None:
    from db import PlayerGem
    await PlayerGem.objects.create(player_uid=player_uid, gem_id=gem_id)
