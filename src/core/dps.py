"""
core/dps.py — единый источник расчёта DPS игрока.

До этого DPS считался в трёх местах (db.Player.get_dps, game/monsters,
plugins/monsters) с двумя независимыми кэшами и расхождением: вариант в
game/monsters не учитывал множитель питомца. Здесь один расчёт и один кэш.

Расчёт: Player.get_dps() (экипировка × раса × пет × сет × камни)
        × классовый бонус (dps_pct).
"""
from core.cache import TTLCache

# Кэш DPS: uid (int) -> итоговый DPS. TTL 5 мин, защита от утечки памяти.
DPS_CACHE_TTL = 300
DPS_CACHE_MAXSIZE = 10000

_dps_cache: TTLCache = TTLCache(ttl=DPS_CACHE_TTL, maxsize=DPS_CACHE_MAXSIZE)


def get_total_dps(player, use_cache: bool = True) -> int:
    """Итоговый DPS игрока со всеми множителями. Кэшируется по uid."""
    cache_key = int(player.uid)

    if use_cache:
        cached = _dps_cache.get(cache_key)
        if cached is not None:
            return cached

    total = player.get_dps()

    from game.classes import get_class_bonus
    cls_bonus = get_class_bonus(player.job)
    if cls_bonus.get("dps_pct"):
        total = int(total * (1 + cls_bonus["dps_pct"] / 100))

    _dps_cache.set(cache_key, total)
    return total


def invalidate_dps_cache(uid: int) -> None:
    """Сбросить кэш DPS игрока — вызывать при смене снаряжения/пета/камней."""
    _dps_cache.delete(int(uid))
