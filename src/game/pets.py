"""
game/pets.py — питомцы
- покупка за токены и дроп с боссов/редкого лута
- прокачка XP за тик и за убийства
- бонусы (dps/hp/def/gold/xp) активного пета через in-memory кэш
"""
import json
import random
import time
from pathlib import Path

import config as cfg
from db import PlayerPet, Player, database

PETS_JSON = Path(__file__).parent.parent / "data" / "pets.json"

# Кэш бонусов активного пета: uid -> {dps_pct, hp_pct, def, gold_pct, xp_pct}
# Заполняется из БД (async) — синхронные геттеры Player читают его на лету.
_bonus_cache: dict[int, dict] = {}


def _load_pets_config() -> dict:
    if not hasattr(_load_pets_config, "_cache"):
        try:
            _load_pets_config._cache = json.loads(PETS_JSON.read_text()).get("pets", {})
        except Exception:
            _load_pets_config._cache = {}
    return _load_pets_config._cache


def all_pets() -> dict:
    return _load_pets_config()


def get_pet_config(pet_id: str) -> dict | None:
    return _load_pets_config().get(pet_id)


def _level_mult(level: int) -> float:
    return 1.0 + (level - 1) * cfg.PET_LEVEL_GROWTH


def get_bonus(uid: int, key: str) -> float:
    return _bonus_cache.get(uid, {}).get(key, 0.0)


def pet_dps_mult(uid: int) -> float:
    return 1.0 + get_bonus(uid, "dps_pct") / 100


def pet_hp_mult(uid: int) -> float:
    return 1.0 + get_bonus(uid, "hp_pct") / 100


def pet_def_add(uid: int) -> int:
    return int(get_bonus(uid, "def"))


def pet_gold_mult(uid: int) -> float:
    return 1.0 + get_bonus(uid, "gold_pct") / 100


def pet_xp_mult(uid: int) -> float:
    return 1.0 + get_bonus(uid, "xp_pct") / 100


async def refresh_cache(player) -> None:
    """Пересчитать бонусы активного пета игрока в кэш."""
    pet = await PlayerPet.objects.filter(
        player_uid=player.uid, equipped=True
    ).get_or_none()
    if not pet:
        _bonus_cache[player.uid] = {}
        return
    conf = get_pet_config(pet.pet_id) or {}
    mult = _level_mult(pet.level)
    _bonus_cache[player.uid] = {
        k: v * mult for k, v in conf.get("bonuses", {}).items()
    }


async def get_owned(player_uid: int) -> list[PlayerPet]:
    return await PlayerPet.objects.filter(player_uid=player_uid).all()


async def get_equipped(player_uid: int) -> PlayerPet | None:
    return await PlayerPet.objects.filter(
        player_uid=player_uid, equipped=True
    ).get_or_none()


async def buy_pet(player: Player, pet_id: str) -> tuple[bool, str]:
    """Купить питомца за токены."""
    lang = player.lang or "ru"
    conf = get_pet_config(pet_id)
    if not conf:
        return False, "Питомец не найден" if lang != "en" else "Pet not found"

    own = await PlayerPet.objects.filter(
        player_uid=player.uid, pet_id=pet_id
    ).get_or_none()
    if own:
        return False, "Этот питомец уже у тебя!" if lang != "en" else "You already own this pet!"

    price = conf.get("price_tokens", 5)
    if (player.tokens or 0) < price:
        return False, (
            f"Нужно {price}🪙 токенов, у тебя {player.tokens or 0}"
            if lang != "en"
            else f"Need {price}🪙 tokens, you have {player.tokens or 0}"
        )

    player.tokens = (player.tokens or 0) - price
    res = await database.fetch_val(
        "UPDATE users SET tokens = tokens - :price WHERE uid = :uid AND tokens >= :price RETURNING 1",
        {"price": price, "uid": player.uid},
    )
    if not res:
        return False, (
            f"Нужно {price}🪙 токенов" if lang != "en" else f"Need {price}🪙 tokens"
        )
    await PlayerPet(
        player_uid=player.uid, pet_id=pet_id, level=1, xp=0,
        equipped=False, source="shop", acquired_at=int(time.time()),
    ).save()
    name = conf["name_ru"] if lang != "en" else conf["name_en"]
    return True, f"{conf['icon']} {name} куплен!" if lang != "en" else f"{conf['icon']} {name} purchased!"


async def equip_pet(player: Player, pet_id: str) -> tuple[bool, str]:
    """Экипировать питомца (активен только один)."""
    lang = player.lang or "ru"
    pet = await PlayerPet.objects.filter(
        player_uid=player.uid, pet_id=pet_id
    ).get_or_none()
    if not pet:
        return False, "Нет такого питомца" if lang != "en" else "Pet not found"

    equipped = await get_equipped(player.uid)
    if equipped:
        if equipped.pet_id == pet_id:
            return False, "Уже экипирован" if lang != "en" else "Already equipped"
        equipped.equipped = False
        await equipped.update(_columns=["equipped"])

    pet.equipped = True
    await pet.update(_columns=["equipped"])
    await refresh_cache(player)
    conf = get_pet_config(pet_id) or {}
    name = conf.get("name_ru", pet_id) if lang != "en" else conf.get("name_en", pet_id)
    return True, f"⚔️ Экипирован: {conf.get('icon', '✨')} {name}"


def can_evolve(pet, player) -> bool:
    """Можно ли эволюционировать питомца."""
    conf = get_pet_config(pet.pet_id) or {}
    target = conf.get("evolves_to")
    if not target or conf.get("evolution"):
        return False
    if (player.tokens or 0) < cfg.PET_EVOLVE_TOKENS:
        return False
    return pet.level >= cfg.PET_EVOLVE_LEVEL


async def evolve_pet(player, pet_id: str) -> tuple[bool, str]:
    """Эволюция питомца: требует уровень и токены. Возвращает новый pet_id."""
    lang = player.lang or "ru"
    conf = get_pet_config(pet_id) or {}
    target = conf.get("evolves_to")
    if not target or conf.get("evolution"):
        return False, "Нельзя эволюционировать" if lang != "en" else "Cannot evolve"
    pet = await PlayerPet.objects.filter(player_uid=player.uid, pet_id=pet_id).get_or_none()
    if not pet:
        return False, "Нет такого питомца" if lang != "en" else "Pet not found"
    if pet.level < cfg.PET_EVOLVE_LEVEL:
        return False, f"Нужен {cfg.PET_EVOLVE_LEVEL} уровень" if lang != "en" else f"Need level {cfg.PET_EVOLVE_LEVEL}"
    if (player.tokens or 0) < cfg.PET_EVOLVE_TOKENS:
        return False, f"Нужно {cfg.PET_EVOLVE_TOKENS} 🪙" if lang != "en" else f"Need {cfg.PET_EVOLVE_TOKENS} 🪙"

    was_equipped = pet.equipped
    res = await database.fetch_val(
        "UPDATE users SET tokens = tokens - :price WHERE uid = :uid AND tokens >= :price RETURNING 1",
        {"price": cfg.PET_EVOLVE_TOKENS, "uid": player.uid},
    )
    if not res:
        return False, f"Нужно {cfg.PET_EVOLVE_TOKENS} 🪙" if lang != "en" else f"Need {cfg.PET_EVOLVE_TOKENS} 🪙"
    player.tokens = (player.tokens or 0) - cfg.PET_EVOLVE_TOKENS
    await pet.delete()
    new_pet = await PlayerPet.objects.create(
        player_uid=player.uid, pet_id=target, level=1, xp=0,
        equipped=was_equipped, source="evolution",
    )
    await refresh_cache(player)
    tconf = get_pet_config(target) or {}
    name = tconf.get("name_ru", target) if lang != "en" else tconf.get("name_en", target)
    return True, f"✨ Эволюция: {conf.get('icon', '')} → {tconf.get('icon', '')} {name}"


async def add_pet_xp(player, amount: int) -> tuple[int, int]:
    """
    Начислить XP активному питомцу.
    Возвращает (level_after, levels_gained).
    """
    pet = await get_equipped(player.uid)
    if not pet or pet.level >= cfg.PET_MAX_LEVEL or amount <= 0:
        return (pet.level if pet else 1), 0

    pet.xp += amount
    levels = 0
    while pet.level < cfg.PET_MAX_LEVEL and pet.xp >= pet.level * cfg.PET_XP_THRESHOLD_BASE:
        pet.xp -= pet.level * cfg.PET_XP_THRESHOLD_BASE
        pet.level += 1
        levels += 1
    if pet.level >= cfg.PET_MAX_LEVEL:
        pet.xp = 0
    await pet.update(_columns=["level", "xp"])
    if levels:
        await refresh_cache(player)
    return pet.level, levels


async def maybe_pet_combat(player) -> tuple[int, str]:
    """
    Боевой призыв пета: шансовый бонусный урон в бою.
    Возвращает (dmg, display_name). dmg=0 если нет активного боевого пета/не сработал.
    """
    pet = await get_equipped(player.uid)
    if not pet:
        return 0, ""
    conf = get_pet_config(pet.pet_id) or {}
    combat_cfg = conf.get("combat") or {}
    if not combat_cfg:
        return 0, ""
    if random.random() > combat_cfg.get("trigger_chance", 0.0):
        return 0, ""
    base = (player.get_dps() or 100)
    dmg = int(base * combat_cfg.get("dmg_pct", 10) / 100 * _level_mult(pet.level))
    lang = player.lang or "ru"
    name = conf.get("name_ru", pet.pet_id) if lang != "en" else conf.get("name_en", pet.pet_id)
    return max(1, dmg), f"{conf.get('icon', '✨')} {name}"


async def maybe_drop_pet(player, source: str) -> str | None:
    """Случайный дроп пета из недоступных игроку. Возвращает pet_id или None."""
    if not player or not source:
        return None
    owned = {p.pet_id for p in await get_owned(player.uid)}
    candidates = [
        (pid, conf) for pid, conf in all_pets().items()
        if pid not in owned and source in conf.get("drop_sources", [])
    ]
    if not candidates:
        return None
    if random.random() > max(conf.get("drop_chance", 0) for _, conf in candidates):
        return None
    pet_id, conf = random.choice(candidates)
    await PlayerPet(
        player_uid=player.uid, pet_id=pet_id, level=1, xp=0,
        equipped=False, source=source, acquired_at=int(time.time()),
    ).save()
    return pet_id
