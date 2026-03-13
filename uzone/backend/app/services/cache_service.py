"""Simple cache service with local-memory and optional Redis backends."""

from __future__ import annotations

import json
import logging
import time
from threading import Lock
from typing import Any

from app.core.config import settings

try:
    from redis import Redis
except ImportError:  # pragma: no cover - exercised only when dependency is missing
    Redis = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)
_CACHE_MISS = object()


class LocalCacheBackend:
    def __init__(self) -> None:
        self._lock = Lock()
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any:
        with self._lock:
            cached = self._store.get(key)
            if cached is None:
                return _CACHE_MISS
            expires_at, value = cached
            if expires_at < time.time():
                self._store.pop(key, None)
                return _CACHE_MISS
            return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        with self._lock:
            self._store[key] = (time.time() + ttl_seconds, value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def delete_prefix(self, prefix: str) -> None:
        with self._lock:
            keys = [key for key in self._store if key.startswith(prefix)]
            for key in keys:
                self._store.pop(key, None)


class RedisCacheBackend:
    def __init__(self, url: str) -> None:
        if Redis is None:  # pragma: no cover - depends on environment packaging
            raise RuntimeError("redis package is not installed")
        self._client = Redis.from_url(url, decode_responses=True)

    def get(self, key: str) -> Any:
        payload = self._client.get(key)
        if payload is None:
            return _CACHE_MISS
        return json.loads(payload)

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._client.set(key, json.dumps(value), ex=ttl_seconds)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def delete_prefix(self, prefix: str) -> None:
        cursor = 0
        pattern = f"{prefix}*"
        while True:
            cursor, keys = self._client.scan(cursor=cursor, match=pattern, count=200)
            if keys:
                self._client.delete(*keys)
            if cursor == 0:
                break


class CacheService:
    def __init__(self) -> None:
        backend_name = settings.cache_backend.strip().lower()
        redis_url = settings.cache_redis_url.strip() if settings.cache_redis_url else ""

        if backend_name == "redis" and redis_url:
            try:
                self._backend: LocalCacheBackend | RedisCacheBackend = RedisCacheBackend(redis_url)
            except Exception as exc:  # pragma: no cover - redis availability is env-specific
                logger.warning("Falling back to local cache backend: %s", exc)
                self._backend = LocalCacheBackend()
        else:
            self._backend = LocalCacheBackend()

    @property
    def cache_miss(self) -> object:
        return _CACHE_MISS

    def get_json(self, key: str) -> Any:
        return self._backend.get(key)

    def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else settings.cache_default_ttl_seconds
        self._backend.set(key, value, ttl)

    def delete(self, key: str) -> None:
        self._backend.delete(key)

    def delete_prefix(self, prefix: str) -> None:
        self._backend.delete_prefix(prefix)


_cache_service: CacheService | None = None


def get_cache_service() -> CacheService:
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service
