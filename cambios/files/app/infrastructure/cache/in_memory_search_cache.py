"""In-process L2 search-result cache: LRU + TTL + per-tenant namespace.

Single-process fallback when no Redis is configured. Namespace versioning
(the standard generation-counter pattern) makes invalidate_tenant O(1):
entries of older generations simply stop being addressable and age out of
the LRU. Note the per-process limitation: with N gunicorn workers each
process has its own cache and its own invalidation -- correctness is
preserved (a worker that indexed also bumped its own namespace) only under
Redis; here a *different* worker may serve a stale hit until TTL expiry.
That trade-off is why the TTL default is short and Redis is the production
choice (redis_search_cache.py).
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any, Callable

DEFAULT_MAX_ENTRIES = 1_000
DEFAULT_TTL_SECONDS = 300.0


class InMemorySearchCache:
    def __init__(
        self,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._max_entries = max_entries
        self._ttl = ttl_seconds
        self._clock = clock
        self._store: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
        self._generations: dict[str, int] = {}

    def get(self, tenant_id: str, key: str) -> dict[str, Any] | None:
        full_key = self._full_key(tenant_id, key)
        entry = self._store.get(full_key)
        if entry is None:
            return None
        expires_at, value = entry
        if self._clock() >= expires_at:
            del self._store[full_key]
            return None
        self._store.move_to_end(full_key)
        return value

    def put(self, tenant_id: str, key: str, value: dict[str, Any]) -> None:
        full_key = self._full_key(tenant_id, key)
        self._store[full_key] = (self._clock() + self._ttl, value)
        self._store.move_to_end(full_key)
        if len(self._store) > self._max_entries:
            self._store.popitem(last=False)

    def invalidate_tenant(self, tenant_id: str) -> None:
        self._generations[tenant_id] = self._generations.get(tenant_id, 0) + 1

    def _full_key(self, tenant_id: str, key: str) -> str:
        generation = self._generations.get(tenant_id, 0)
        return f"{tenant_id}:{generation}:{key}"
