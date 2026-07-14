"""Redis-backed L2 search-result cache: shared across workers and nodes.

Same generation-counter invalidation as the in-memory variant, but the
generation lives in Redis so ANY worker bumping it invalidates for ALL
workers -- the property the in-process cache cannot give. Values expire by
Redis TTL; generations never expire (a single small integer per tenant).

The client is injected (any object honoring get/set/incr with the redis-py
signatures) so tests run against a dict-backed stub and production wires
redis.Redis.from_url(settings.redis_url).
"""

from __future__ import annotations

import json
from typing import Any

DEFAULT_TTL_SECONDS = 300


class RedisSearchCache:
    def __init__(self, client: Any, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._redis = client
        self._ttl = ttl_seconds

    def get(self, tenant_id: str, key: str) -> dict[str, Any] | None:
        raw = self._redis.get(self._full_key(tenant_id, key))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        loaded = json.loads(raw)
        return loaded if isinstance(loaded, dict) else None

    def put(self, tenant_id: str, key: str, value: dict[str, Any]) -> None:
        self._redis.set(self._full_key(tenant_id, key), json.dumps(value), ex=self._ttl)

    def invalidate_tenant(self, tenant_id: str) -> None:
        self._redis.incr(self._generation_key(tenant_id))

    def _generation_key(self, tenant_id: str) -> str:
        return f"xplagiax:cache:gen:{tenant_id}"

    def _generation(self, tenant_id: str) -> int:
        raw = self._redis.get(self._generation_key(tenant_id))
        if raw is None:
            return 0
        return int(raw)

    def _full_key(self, tenant_id: str, key: str) -> str:
        return f"xplagiax:cache:{tenant_id}:{self._generation(tenant_id)}:{key}"
