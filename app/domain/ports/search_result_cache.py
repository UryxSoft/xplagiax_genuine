"""Port for the L2 search-result cache (ADR sect 14).

Values are opaque JSON-serializable dicts (the /search response body).
Invalidation is namespace-based per tenant: indexing or deleting any
document of a tenant must make every cached result of that tenant
unreachable at once (ADR sect 14, "invalidacion por namespace"), without
enumerating keys.
"""

from __future__ import annotations

from typing import Any, Protocol


class SearchResultCache(Protocol):
    def get(self, tenant_id: str, key: str) -> dict[str, Any] | None:
        ...

    def put(self, tenant_id: str, key: str, value: dict[str, Any]) -> None:
        ...

    def invalidate_tenant(self, tenant_id: str) -> None:
        ...
