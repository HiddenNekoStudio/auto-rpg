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
                encoding="utf-8",
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
