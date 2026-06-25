"""
core/redis_cache.py — Redis integration для кэширования
Используется опционально для снижения нагрузки на основную БД.

Установка Redis: redis-server
 pip install redis aioredis

В .env:
  REDIS_URL=redis://localhost:6379/0
  USE_REDIS=true
"""
import json
import logging
from typing import Optional, Any
from functools import wraps

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

logger = logging.getLogger(__name__)


class RedisCache:
    """
    Асинхронный Redis кэш с TTL.
    
    Что можно кэшировать в Redis:
    - Leaderboard (топ 10) — обновлять каждые 5 мин
    - Статистика (онлайн, всего игроков)
    - Частые запросы игроков (но не sensitive данные!)
    """
    
    _instance: Optional['RedisCache'] = None
    _client: Optional[redis.Redis] = None
    
    def __init__(self):
        self._connected = False
    
    @classmethod
    async def get_instance(cls) -> 'RedisCache':
        if cls._instance is None:
            cls._instance = RedisCache()
            await cls._instance.connect()
        return cls._instance
    
    async def connect(self):
        """Подключиться к Redis."""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available (pip install redis aioredis)")
            return
        
        import os
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        
        try:
            self._client = redis.from_url(
                redis_url,
                decode_responses=True,
            )
            await self._client.ping()
            self._connected = True
            logger.info("Redis connected: %s", redis_url)
        except Exception as e:
            logger.warning("Redis connection failed: %s", e)
            self._connected = False
    
    async def disconnect(self):
        """Отключиться от Redis."""
        if self._client:
            await self._client.close()
            self._connected = False
    
    async def get(self, key: str) -> Optional[Any]:
        """Получить значение из кэша."""
        if not self._connected:
            return None
        
        try:
            value = await self._client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.debug("Redis get error: %s", e)
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Установить значение в кэш с TTL (секунды)."""
        if not self._connected:
            return False
        
        try:
            await self._client.setex(key, ttl, json.dumps(value))
            return True
        except Exception as e:
            logger.debug("Redis set error: %s", e)
            return False
    
    async def delete(self, key: str) -> bool:
        """Удалить ключ."""
        if not self._connected:
            return False
        
        try:
            await self._client.delete(key)
            return True
        except Exception as e:
            logger.debug("Redis delete error: %s", e)
            return False
    
    async def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """Инкремент счётчика."""
        if not self._connected:
            return None
        
        try:
            return await self._client.incrby(key, amount)
        except Exception as e:
            logger.debug("Redis incr error: %s", e)
            return None


# ── Cache decorators ───────────────────────────

def cached(key_prefix: str, ttl: int = 60):
    """
    Декоратор для кэширования результатов функций в Redis.
    
    Usage:
        @cached("player_stats", ttl=300)
        async def get_player_stats(uid: int):
            return await Player.objects.get(uid=uid)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Формируем ключ
            cache_key = f"{key_prefix}:{':'.join(str(a) for a in args[1:])}"
            
            # Пробуем получить из кэша
            cache = await RedisCache.get_instance()
            cached_value = await cache.get(cache_key)
            
            if cached_value is not None:
                return cached_value
            
            # Выполняем функцию
            result = await func(*args, **kwargs)
            
            # Кэшируем результат
            if result is not None:
                await cache.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator


# ── Usage Examples ─────────────────────────────

async def cache_leaderboard():
    """Кэшировать топ 10 игроков."""
    from db import Player
    
    cache = await RedisCache.get_instance()
    
    # Получаем топ 10
    players = await Player.objects.all()
    import heapq
    top = heapq.nlargest(10, players, key=lambda p: (p.level, p.totalxp))
    
    # Сериализуем только нужные поля
    data = [
        {
            "uid": p.uid,
            "name": p.name,
            "level": p.level,
            "totalxp": p.totalxp,
            "job": p.job,
            "online": p.online,
        }
        for p in top
    ]
    
    # Кэшируем на 5 минут
    await cache.set("leaderboard:top10", data, ttl=300)
    return data


async def get_cached_leaderboard():
    """Получить кэшированный топ 10."""
    cache = await RedisCache.get_instance()
    return await cache.get("leaderboard:top10") or []


async def invalidate_leaderboard():
    """Инвалидировать кэш топа."""
    cache = await RedisCache.get_instance()
    await cache.delete("leaderboard:top10")


# ── PlayerState для быстрых операций с игроками ───

LUA_ADD_IDLE_XP = """
local key = KEYS[1]
local amount = tonumber(ARGV[1])
local elf_bonus = tonumber(ARGV[2])
local race = redis.call('HGET', key, 'race') or ''

local multiplier = 1.0
if race == 'elf' then
    multiplier = elf_bonus
end

local current_xp = tonumber(redis.call('HGET', key, 'idle_xp') or '0')
local new_xp = current_xp + (amount * multiplier)
redis.call('HSET', key, 'idle_xp', new_xp)

return new_xp
"""

LUA_SYNC_TO_DB = """
local key = KEYS[1]
local fields = cjson.decode(ARGV[1])
for field, value in pairs(fields) do
    redis.call('HSET', key, field, value)
end
return 'OK'
"""


class PlayerState:
    """
    Управление состоянием игрока в Redis для быстрых операций.
    Использует Lua-скрипты для атомарности.
    """

    _instance: Optional['PlayerState'] = None
    _client: Optional[redis.Redis] = None

    @classmethod
    async def get_instance(cls) -> 'PlayerState':
        if cls._instance is None:
            cls._instance = PlayerState()
            await cls._instance.connect()
        return cls._instance

    async def connect(self):
        """Подключиться к Redis."""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available for PlayerState")
            return

        import os
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        try:
            self._client = redis.from_url(
                redis_url,
                decode_responses=True,
            )
            await self._client.ping()
            logger.info("PlayerState: Redis connected")
        except Exception as e:
            logger.warning("PlayerState connection failed: %s", e)
            self._client = None

    def _get_key(self, uid: int) -> str:
        """Получить ключ для игрока."""
        return f"player:state:{uid}"

    async def get_state(self, uid: int) -> Optional[dict]:
        """Получить состояние игрока из Redis."""
        if not self._client:
            return None

        try:
            state = await self._client.hgetall(self._get_key(uid))
            return state if state else None
        except Exception as e:
            logger.debug("PlayerState get error: %s", e)
            return None

    async def set_state(self, uid: int, **kwargs) -> bool:
        """Установить состояние игрока."""
        if not self._client:
            return False

        try:
            await self._client.hset(self._get_key(uid), mapping=kwargs)
            return True
        except Exception as e:
            logger.debug("PlayerState set error: %s", e)
            return False

    async def add_idle_xp(self, uid: int, amount: int, elf_bonus: float = 1.1) -> Optional[int]:
        """
        Атомарно добавить idle XP с учетом бонуса расы.
        Использует Lua-скрипт для избежания race conditions.
        """
        if not self._client:
            return None

        try:
            result = await self._client.eval(
                LUA_ADD_IDLE_XP,
                1,
                self._get_key(uid),
                amount,
                elf_bonus
            )
            return int(result)
        except Exception as e:
            logger.debug("PlayerState add_idle_xp error: %s", e)
            return None

    async def sync_to_db(self, uid: int, **fields) -> bool:
        """Синхронизировать поля в Redis с БД."""
        if not self._client:
            return False

        try:
            import json
            await self._client.eval(
                LUA_SYNC_TO_DB,
                1,
                self._get_key(uid),
                json.dumps(fields)
            )
            return True
        except Exception as e:
            logger.debug("PlayerState sync_to_db error: %s", e)
            return False

    async def delete_state(self, uid: int) -> bool:
        """Удалить состояние игрока (при выходе из idle)."""
        if not self._client:
            return False

        try:
            await self._client.delete(self._get_key(uid))
            return True
        except Exception as e:
            logger.debug("PlayerState delete error: %s", e)
            return False

    async def init_from_player(self, player) -> bool:
        """Инициализировать состояние из объекта Player."""
        return await self.set_state(
            player.uid,
            uid=player.uid,
            name=player.name,
            race=player.race or "",
            level=player.level,
            idle_since=player.idle_since,
            idle_xp=player.idle_xp,
            online=str(player.online).lower(),
        )

    async def get_idle_xp(self, uid: int) -> int:
        """Получить накопленный idle XP."""
        if not self._client:
            return 0

        try:
            xp = await self._client.hget(self._get_key(uid), "idle_xp")
            return int(xp) if xp else 0
        except Exception:
            return 0

    async def set_idle(self, uid: int, idle_since: int) -> bool:
        """Перевести игрока в idle режим."""
        return await self.set_state(
            uid,
            idle_since=idle_since,
            idle_xp=0,
            online="false"
        )

    async def set_idle_state(self, uid: int, idle_since: int, idle_xp: int) -> bool:
        """Сохранить idle состояние в Redis."""
        if not self._client:
            return False
        try:
            await self._client.hset(self._get_key(uid), mapping={
                "idle_since": idle_since,
                "idle_xp": idle_xp
            })
            return True
        except Exception as e:
            logger.debug("set_idle_state error: %s", e)
            return False

    async def sync_idle_to_db(self, uid: int) -> bool:
        """Синхронизировать idle состояние из Redis в БД."""
        if not self._client:
            return False
        try:
            state = await self._client.hgetall(self._get_key(uid))
            if not state or not state.get("idle_xp"):
                return False

            from db import Player
            player = await Player.objects.get(uid=uid)
            player.idle_since = int(state.get("idle_since", 0))
            player.idle_xp = int(state.get("idle_xp", 0))
            await player.update(_columns=["idle_since", "idle_xp"])
            return True
        except Exception as e:
            logger.error("sync_idle_to_db failed: %s", e)
            return False
