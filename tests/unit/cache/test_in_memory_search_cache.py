from __future__ import annotations

import pytest

from app.infrastructure.cache.in_memory_search_cache import InMemorySearchCache


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_put_then_get_hits() -> None:
    cache = InMemorySearchCache()
    cache.put("tenant-a", "k1", {"documents": []})
    assert cache.get("tenant-a", "k1") == {"documents": []}


def test_miss_on_unknown_key_and_tenant() -> None:
    cache = InMemorySearchCache()
    cache.put("tenant-a", "k1", {"x": 1})
    assert cache.get("tenant-a", "other") is None
    assert cache.get("tenant-b", "k1") is None


def test_ttl_expires_entries() -> None:
    clock = _Clock()
    cache = InMemorySearchCache(ttl_seconds=10.0, clock=clock)
    cache.put("tenant-a", "k1", {"x": 1})

    clock.now = 9.9
    assert cache.get("tenant-a", "k1") is not None

    clock.now = 10.0
    assert cache.get("tenant-a", "k1") is None


def test_invalidate_tenant_hides_only_that_tenant(v_key: str = "k1") -> None:
    cache = InMemorySearchCache()
    cache.put("tenant-a", v_key, {"a": 1})
    cache.put("tenant-b", v_key, {"b": 2})

    cache.invalidate_tenant("tenant-a")

    assert cache.get("tenant-a", v_key) is None
    assert cache.get("tenant-b", v_key) == {"b": 2}


def test_put_after_invalidation_uses_new_namespace() -> None:
    cache = InMemorySearchCache()
    cache.put("tenant-a", "k1", {"old": True})
    cache.invalidate_tenant("tenant-a")
    cache.put("tenant-a", "k1", {"new": True})

    assert cache.get("tenant-a", "k1") == {"new": True}


def test_lru_evicts_oldest_entry() -> None:
    cache = InMemorySearchCache(max_entries=2)
    cache.put("t", "k1", {"n": 1})
    cache.put("t", "k2", {"n": 2})
    cache.get("t", "k1")  # refresh k1: k2 becomes the eviction candidate
    cache.put("t", "k3", {"n": 3})

    assert cache.get("t", "k1") is not None
    assert cache.get("t", "k2") is None
    assert cache.get("t", "k3") is not None


def test_invalid_construction_rejected() -> None:
    with pytest.raises(ValueError):
        InMemorySearchCache(max_entries=0)
    with pytest.raises(ValueError):
        InMemorySearchCache(ttl_seconds=0)
