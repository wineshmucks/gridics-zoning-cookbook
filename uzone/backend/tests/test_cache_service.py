"""Unit tests for cache service backends."""

from app.services.cache_service import LocalCacheBackend


def test_local_cache_backend_supports_set_get_and_prefix_delete() -> None:
    cache = LocalCacheBackend()

    cache.set("tenant-public:one", {"value": 1}, ttl_seconds=30)
    cache.set("tenant-public:two", {"value": 2}, ttl_seconds=30)
    cache.set("admin:fee:one", {"value": 3}, ttl_seconds=30)

    assert cache.get("tenant-public:one") == {"value": 1}
    assert cache.get("tenant-public:two") == {"value": 2}
    assert cache.get("admin:fee:one") == {"value": 3}

    cache.delete_prefix("tenant-public:")

    miss = cache.get("tenant-public:one")
    assert miss is not None
    assert cache.get("tenant-public:two") is miss
    assert cache.get("admin:fee:one") == {"value": 3}
