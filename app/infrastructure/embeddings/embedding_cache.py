"""In-process LRU cache for embeddings (ADR sect 14, L1 cache).

Keyed by a content hash so identical passages (e.g. duplicated boilerplate
across theses) are only embedded once per process, and repeated query
segments during a single search hit the cache instead of the model.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict

from app.domain.value_objects.embedding_vector import EmbeddingVector


class EmbeddingCache:
    """Fixed-capacity LRU cache mapping text -> EmbeddingVector."""

    def __init__(self, max_size: int = 10_000) -> None:
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        self._max_size = max_size
        self._store: OrderedDict[str, EmbeddingVector] = OrderedDict()

    def get(self, text: str, namespace: str = "") -> EmbeddingVector | None:
        key = self._key(text, namespace)
        if key not in self._store:
            return None
        self._store.move_to_end(key)
        return self._store[key]

    def put(self, text: str, vector: EmbeddingVector, namespace: str = "") -> None:
        key = self._key(text, namespace)
        self._store[key] = vector
        self._store.move_to_end(key)
        if len(self._store) > self._max_size:
            self._store.popitem(last=False)

    def __len__(self) -> int:
        return len(self._store)

    @staticmethod
    def _key(text: str, namespace: str) -> str:
        # namespace separates e.g. "query" vs "passage" caches: asymmetric
        # embedding models (e5) produce different vectors for the same raw
        # text depending on which prefix was applied, so the two must never
        # collide in the same cache slot.
        return hashlib.sha256(f"{namespace}\x00{text}".encode("utf-8")).hexdigest()
