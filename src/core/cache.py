"""
core/cache.py — TTL Cache для управления памятью
Заменяет бесконечно растущие dict'ы на автоматически очищаемые кэши
"""
import asyncio
import time
from typing import TypeVar, Generic, Optional, Callable
from collections import OrderedDict
from functools import wraps

T = TypeVar('T')


class TTLCache(Generic[T]):
    """
    Кэш с автоматическим TTL (Time-To-Live).
    Автоматически очищает просроченные записи.
    
    Usage:
        cache = TTLCache[str](ttl=60, maxsize=1000)
        cache.set("key", "value")
        cache.get("key")  # returns "value" or None if expired
    """
    
    def __init__(self, ttl: float = 60.0, maxsize: int = 10000, cleanup_interval: float = 30.0):
        self._ttl = ttl
        self._maxsize = maxsize
        self._cleanup_interval = cleanup_interval
        self._cache: OrderedDict[str, tuple[float, T]] = OrderedDict()
        self._last_cleanup = time.monotonic()
        self._lock = asyncio.Lock()
    
    def _cleanup(self) -> int:
        """Удалить просроченные записи. Возвращает количество удалённых."""
        now = time.monotonic()
        expired = []
        
        for key, (timestamp, _) in self._cache.items():
            if now - timestamp > self._ttl:
                expired.append(key)
        
        for key in expired:
            self._cache.pop(key, None)
        
        # Также удаляем старые записи если превысили maxsize
        while len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)
        
        return len(expired)
    
    def get(self, key: str) -> Optional[T]:
        """Получить значение из кэша. None если не найдено или истекло."""
        now = time.monotonic()
        
        if key not in self._cache:
            return None
        
        timestamp, value = self._cache[key]
        if now - timestamp > self._ttl:
            self._cache.pop(key, None)
            return None
        
        # Перемещаем в конец (LRU)
        self._cache.move_to_end(key)
        return value
    
    def set(self, key: str, value: T) -> None:
        """Установить значение в кэш."""
        now = time.monotonic()
        
        # Cleanup при необходимости
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup()
            self._last_cleanup = now
        
        # Удаляем если достигли maxsize (LRU)
        if len(self._cache) >= self._maxsize and key not in self._cache:
            self._cache.popitem(last=False)
        
        self._cache[key] = (now, value)
        self._cache.move_to_end(key)
    
    def delete(self, key: str) -> bool:
        """Удалить ключ из кэша."""
        return self._cache.pop(key, None) is not None
    
    def clear(self) -> None:
        """Очистить весь кэш."""
        self._cache.clear()
    
    def __len__(self) -> int:
        return len(self._cache)
    
    def stats(self) -> dict:
        """Статистика кэша."""
        return {
            "size": len(self._cache),
            "maxsize": self._maxsize,
            "ttl": self._ttl,
        }


class RateLimiter:
    """
    Rate limiter с TTL. Автоматически очищает старые записи.
    
    Usage:
        limiter = RateLimiter(max_calls=5, window=60)
        if limiter.check(uid):
            # allow
        else:
            # rate limited
    """
    
    def __init__(self, max_calls: int = 1, window: float = 1.0, maxsize: int = 10000):
        self._cache = TTLCache[list](ttl=window, maxsize=maxsize)
        self._max_calls = max_calls
    
    def check(self, key: str) -> bool:
        """
        Проверить и отметить вызов.
        Returns True если вызов разрешён, False если rate limited.
        """
        now = time.monotonic()
        calls = self._cache.get(key) or []
        
        if len(calls) >= self._max_calls:
            return False
        
        calls.append(now)
        self._cache.set(key, calls)
        return True
    
    def reset(self, key: str) -> None:
        """Сбросить rate limit для ключа."""
        self._cache.delete(key)


def cached_property(ttl: float = 60.0):
    """
    Декоратор для кэширования свойств объекта.
    Кэш привязан к объекту и очищается при его удалении.
    """
    def decorator(func: Callable):
        cache_attr = f"_cached_{func.__name__}"
        time_attr = f"_cached_time_{func.__name__}"
        
        @wraps(func)
        def wrapper(self):
            now = time.monotonic()
            cached = getattr(self, cache_attr, None)
            cached_time = getattr(self, time_attr, 0)
            
            if cached is not None and (now - cached_time) < ttl:
                return cached
            
            value = func(self)
            setattr(self, cache_attr, value)
            setattr(self, time_attr, now)
            return value
        
        return wrapper
    return decorator
