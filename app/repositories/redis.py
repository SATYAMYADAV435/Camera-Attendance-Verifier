from __future__ import annotations
import json
import time
from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.core.logging import logger

try:
    import redis.asyncio as aioredis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

class RedisRepository:
    def __init__(self):
        self.host = settings.redis.host
        self.port = settings.redis.port
        self.db = settings.redis.db
        self.client: Optional[Any] = None
        self.is_connected = False
        
        # In-memory dictionary fallback with TTL tracking
        self._memory_cache: Dict[str, Any] = {}
        self._memory_expiry: Dict[str, float] = {}

    async def connect(self):
        if not HAS_REDIS:
            logger.warning("Redis package not available. Using in-memory cache fallback.")
            self.is_connected = False
            return

        try:
            self.client = aioredis.Redis(host=self.host, port=self.port, db=self.db, decode_responses=True)
            pong = await self.client.ping()
            if pong:
                self.is_connected = True
                logger.info("Connected to Redis server successfully.", host=self.host, port=self.port)
            else:
                self.is_connected = False
        except Exception as exc:
            self.is_connected = False
            logger.warning("Redis connection failed; operating on in-memory fallback cache.", error=str(exc))

    async def set(self, key: str, value: Any, expire_seconds: Optional[int] = None):
        serialized = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        if self.is_connected and self.client:
            try:
                await self.client.set(key, serialized, ex=expire_seconds)
                return
            except Exception:
                pass
        
        # Fallback cache
        self._memory_cache[key] = serialized
        if expire_seconds:
            self._memory_expiry[key] = time.time() + expire_seconds
        elif key in self._memory_expiry:
            del self._memory_expiry[key]

    async def get(self, key: str) -> Optional[Any]:
        if self.is_connected and self.client:
            try:
                val = await self.client.get(key)
                if val is not None:
                    try:
                        return json.loads(val)
                    except Exception:
                        return val
            except Exception:
                pass

        # Check in-memory
        if key in self._memory_cache:
            if key in self._memory_expiry and time.time() > self._memory_expiry[key]:
                del self._memory_cache[key]
                del self._memory_expiry[key]
                return None
            val = self._memory_cache[key]
            try:
                return json.loads(val)
            except Exception:
                return val
        return None

    async def delete(self, key: str):
        if self.is_connected and self.client:
            try:
                await self.client.delete(key)
            except Exception:
                pass
        self._memory_cache.pop(key, None)
        self._memory_expiry.pop(key, None)

    async def close(self):
        if self.client:
            await self.client.close()

redis_repo = RedisRepository()
