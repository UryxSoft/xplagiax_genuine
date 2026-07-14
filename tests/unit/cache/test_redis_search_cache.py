"""RedisSearchCache against a dict-backed stub honoring the redis-py
get/set/incr signatures -- proves key layout, JSON round-trip and
generation-based invalidation without a live Redis."""

from __future__ import annotations

from app.infrastructure.cache.redis_search_cache import RedisSearchCache


class _StubRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def get(self, key: str) -> str | None:
        return self.store.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value
        if ex is not None:
            self.ttls[key] = ex

    def incr(self, key: str) -> int:
        current = int(self.store.get(key, "0")) + 1
        self.store[key] = str(current)
        return current


def test_round_trip_with_ttl() -> None:
    stub = _StubRedis()
    cache = RedisSearchCache(stub, ttl_seconds=60)

    cache.put("tenant-a", "k1", {"documents": [1, 2]})

    assert cache.get("tenant-a", "k1") == {"documents": [1, 2]}
    assert all(ttl == 60 for ttl in stub.ttls.values())


def test_miss_returns_none() -> None:
    cache = RedisSearchCache(_StubRedis(), ttl_seconds=60)
    assert cache.get("tenant-a", "missing") is None


def test_invalidate_tenant_changes_generation() -> None:
    stub = _StubRedis()
    cache = RedisSearchCache(stub, ttl_seconds=60)
    cache.put("tenant-a", "k1", {"v": 1})
    cache.put("tenant-b", "k1", {"v": 2})

    cache.invalidate_tenant("tenant-a")

    assert cache.get("tenant-a", "k1") is None
    assert cache.get("tenant-b", "k1") == {"v": 2}

    cache.put("tenant-a", "k1", {"v": 3})
    assert cache.get("tenant-a", "k1") == {"v": 3}


def test_bytes_payload_from_real_redis_decoded() -> None:
    stub = _StubRedis()
    cache = RedisSearchCache(stub, ttl_seconds=60)
    cache.put("tenant-a", "k1", {"v": 1})
    # redis-py without decode_responses returns bytes
    key = next(k for k in stub.store if k.endswith(":k1"))
    stub.store[key] = stub.store[key].encode("utf-8")  # type: ignore[assignment]

    assert cache.get("tenant-a", "k1") == {"v": 1}
