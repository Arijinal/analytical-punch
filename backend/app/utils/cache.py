import json
import hashlib
from typing import Any, Optional, Dict, Callable
from functools import wraps
import asyncio
import redis.asyncio as aioredis
from datetime import timedelta

from app.config import get_config
from app.utils.logger import setup_logger

config = get_config()
logger = setup_logger(__name__)


class CacheManager:
    """Redis-based cache manager with TTL support"""
    
    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
        self._connected = False
    
    async def connect(self):
        """Connect to Redis"""
        if not self._connected:
            try:
                self._redis = await aioredis.from_url(
                    config.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True
                )
                await self._redis.ping()
                self._connected = True
                logger.info("Connected to Redis cache")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self._connected = False
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self._redis:
            await self._redis.close()
            self._connected = False
    
    def _generate_key(self, prefix: str, params: Dict[str, Any]) -> str:
        """Generate cache key from prefix and parameters"""
        # Sort params for consistent keys
        sorted_params = sorted(params.items())
        param_str = json.dumps(sorted_params, sort_keys=True)
        
        # Create hash for long keys
        if len(param_str) > 200:
            param_hash = hashlib.md5(param_str.encode()).hexdigest()
            return f"{prefix}:{param_hash}"
        
        return f"{prefix}:{param_str}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self._connected:
            await self.connect()
        
        if not self._connected:
            return None
        
        try:
            value = await self._redis.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.error(f"Cache get error: {e}")
        
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache with optional TTL"""
        if not self._connected:
            await self.connect()
        
        if not self._connected:
            return
        
        try:
            ttl = ttl or config.CACHE_TTL
            serialized = json.dumps(value)
            await self._redis.setex(key, ttl, serialized)
        except Exception as e:
            logger.error(f"Cache set error: {e}")
    
    async def delete(self, pattern: str):
        """Delete keys matching pattern"""
        if not self._connected:
            return
        
        try:
            keys = await self._redis.keys(pattern)
            if keys:
                await self._redis.delete(*keys)
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
    
    async def clear_all(self):
        """Clear all cache entries"""
        if not self._connected:
            return
        
        try:
            await self._redis.flushdb()
        except Exception as e:
            logger.error(f"Cache clear error: {e}")


# Global cache instance
cache_manager = CacheManager()


def cached(prefix: str, ttl: Optional[int] = None):
    """Decorator for caching function results"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_params = {
                "args": args,
                "kwargs": kwargs
            }
            cache_key = cache_manager._generate_key(prefix, cache_params)
            
            # Try to get from cache
            cached_value = await cache_manager.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {cache_key}")
                return cached_value
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Store in cache
            await cache_manager.set(cache_key, result, ttl)
            logger.debug(f"Cache miss for {cache_key}, stored result")
            
            return result
        
        return wrapper
    return decorator


class UsageTracker:
    """Track feature usage in personal mode"""
    
    def __init__(self):
        self.enabled = config.ENABLE_USAGE_TRACKING
    
    async def track_indicator(self, indicator: str, params: Dict[str, Any]):
        """Track indicator usage"""
        if not self.enabled:
            return
        
        key = f"usage:indicator:{indicator}"
        await cache_manager.set(
            key,
            {
                "count": await self._increment_count(key),
                "last_params": params,
                "timestamp": asyncio.get_event_loop().time()
            },
            ttl=86400 * 30  # 30 days
        )
    
    async def track_api_call(self, endpoint: str, params: Dict[str, Any]):
        """Track API endpoint usage"""
        if not self.enabled:
            return
        
        key = f"usage:api:{endpoint}"
        await cache_manager.set(
            key,
            {
                "count": await self._increment_count(key),
                "last_params": params,
                "timestamp": asyncio.get_event_loop().time()
            },
            ttl=86400 * 30  # 30 days
        )
    
    async def _increment_count(self, key: str) -> int:
        """Increment usage counter"""
        current = await cache_manager.get(key)
        count = 1
        if current and isinstance(current, dict):
            count = current.get("count", 0) + 1
        return count
    
    async def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        if not self.enabled:
            return {}
        
        # This would aggregate all usage data
        # Implementation depends on specific tracking needs
        return {
            "indicators": {},
            "endpoints": {},
            "timeframes": {}
        }


# Global usage tracker
usage_tracker = UsageTracker()