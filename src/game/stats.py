"""
game/stats.py — Основные характеристики STR/CON/DEX/INT/WIS/CHA (PQ3 prime stats).

На каждом уровне героя +1 очко, вероятность стата пропорциональна его
квадрату (как в PQ3). Бонусы идут множителями поверх существующих формул
и ограничены потолком STAT_BONUS_CAP, чтобы не ломать баланс:
  STR -> DPS, CON -> макс. HP, INT -> макс. MP.
DEX, WIS и CHA пока только копятся (задел под будущие механики).
"""
import random
from typing import Mapping

PRIME_STATS: tuple[str, ...] = ("str", "con", "dex", "int", "wis", "cha")
BASE_STAT = 10

# +0.3% за очко сверх базы, потолок +25% (как COMBO_STREAK_MAX_MULT)
STAT_BONUS_PER_POINT = 0.003
STAT_BONUS_CAP = 0.25

# Цена сброса характеристик в токенах
RESPEC_TOKEN_COST = 5

STAT_ICONS = {"str": "💪", "con": "🫀", "dex": "🏹", "int": "🧠", "wis": "🔮", "cha": "🎭"}


def column(stat: str) -> str:
    """Имя колонки users для стата."""
    return f"stat_{stat}"


def read_stats(player) -> dict[str, int]:
    """Текущие значения статов игрока (отсутствующие = BASE_STAT)."""
    return {s: int(getattr(player, column(s), BASE_STAT) or BASE_STAT) for s in PRIME_STATS}


def pick_stat(stats: Mapping[str, int], rng: random.Random) -> str:
    """Выбрать стат для очка: вес = значение² (PQ3)."""
    weights = [max(1, stats.get(s, BASE_STAT)) ** 2 for s in PRIME_STATS]
    return rng.choices(PRIME_STATS, weights=weights, k=1)[0]


def stat_bonus(value: int) -> float:
    """Доля бонуса стата: 0..STAT_BONUS_CAP."""
    return min(STAT_BONUS_CAP, max(0, value - BASE_STAT) * STAT_BONUS_PER_POINT)


def default_stats(level: int) -> dict[str, int]:
    """Детерминированная раскладка по уровню: очки поровну (используется
    в миграции-бэкфилле и при сбросе). Остаток очков отбрасывается."""
    per_stat = max(0, level - 1) // len(PRIME_STATS)
    return {s: BASE_STAT + per_stat for s in PRIME_STATS}


def dps_mult(player) -> float:
    return 1 + stat_bonus(read_stats(player)["str"])


def hp_mult(player) -> float:
    return 1 + stat_bonus(read_stats(player)["con"])


def mp_mult(player) -> float:
    return 1 + stat_bonus(read_stats(player)["int"])


async def grant_level_point(player, rng: random.Random | None = None) -> str:
    """Начислить очко за уровень выбранному стату (атомарный инкремент)."""
    from db import database

    stat = pick_stat(read_stats(player), rng or random.Random())
    col = column(stat)
    await database.execute(
        f"UPDATE users SET {col} = {col} + 1 WHERE uid = :uid",  # col из белого списка
        {"uid": player.uid},
    )
    setattr(player, col, getattr(player, col, BASE_STAT) + 1)
    return stat


async def respec(player) -> bool:
    """Сбросить характеристики к раскладке по уровню за RESPEC_TOKEN_COST токенов."""
    from db import database

    stats = default_stats(player.level)
    sets = ", ".join(f"{column(s)} = :{s}" for s in PRIME_STATS)
    paid = await database.fetch_val(
        f"UPDATE users SET tokens = tokens - :cost, {sets} "
        "WHERE uid = :uid AND tokens >= :cost RETURNING 1",
        {"cost": RESPEC_TOKEN_COST, "uid": player.uid, **stats},
    )
    if not paid:
        return False
    player.tokens = (player.tokens or 0) - RESPEC_TOKEN_COST
    for s, value in stats.items():
        setattr(player, column(s), value)
    return True
