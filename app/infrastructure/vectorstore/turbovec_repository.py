"""Adapter around turbovec.IdMapIndex (ADR-002, ADR-007).

Default bit_width=4 per docs/RESEARCH.md #1: the ICLR 2026 TurboQuant
paper and the repo's own benchmarks show 2-bit losing recall in the
regimes closest to our setup (low-dim / adversarial coordinates), and
being the config where FAISS's AVX-512 kernel actually wins on x86. 2-bit
remains available as an explicit low-memory opt-in, not the default.

The index file is opened for on-disk persistence and reloaded via mmap
semantics (ADR-007): TurboVec's own `.write()`/`.load()` handle this: the
adapter does not hold the whole index in a Python-side structure.
"""

from __future__ import annotations

from pathlib import Path

from app.domain.value_objects.embedding_vector import EmbeddingVector
from app.domain.value_objects.search_hit import SearchHit

DEFAULT_BIT_WIDTH = 4


class DimensionMismatchError(ValueError):
    """Raised when a vector's dimension does not match the index's dimension."""


class TurboVecRepository:
    """Implements VectorIndexRepository on top of turbovec.IdMapIndex."""

    def __init__(
        self,
        dimension: int,
        bit_width: int = DEFAULT_BIT_WIDTH,
        index_path: Path | None = None,
    ) -> None:
        from turbovec import IdMapIndex  # deferred: native extension, optional at import time

        self._dimension = dimension
        self._bit_width = bit_width
        self._index_path = index_path
        self._version = 0

        if index_path is not None and index_path.exists():
            self._index = IdMapIndex.load(str(index_path))
        else:
            self._index = IdMapIndex(dim=dimension, bit_width=bit_width)

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def version(self) -> int:
        return self._version

    def add(self, chunk_ids: list[int], vectors: list[EmbeddingVector]) -> None:
        if len(chunk_ids) != len(vectors):
            raise ValueError("chunk_ids and vectors must have the same length")
        if not chunk_ids:
            return

        import numpy as np

        self._validate_dimensions(vectors)
        np_vectors = np.array([v.values for v in vectors], dtype=np.float32)
        np_ids = np.array(chunk_ids, dtype=np.uint64)
        self._index.add_with_ids(np_vectors, np_ids)

    def search(
        self, query: EmbeddingVector, k: int, allowlist: set[int] | None = None
    ) -> list[SearchHit]:
        if k <= 0:
            raise ValueError("k must be positive")
        self._validate_dimensions([query])

        import numpy as np

        np_query = np.array(query.values, dtype=np.float32)

        search_kwargs = {}
        if allowlist is not None:
            # empty allowlist is a valid, deliberate "match nothing" filter --
            # distinct from allowlist=None (unrestricted search).
            search_kwargs["allowlist"] = np.array(sorted(allowlist), dtype=np.uint64)

        scores, ids = self._index.search(np_query, k=k, **search_kwargs)
        return [SearchHit(chunk_id=int(chunk_id), score=float(score)) for score, chunk_id in zip(scores, ids)]

    def remove(self, chunk_id: int) -> None:
        self._index.remove(chunk_id)

    def snapshot(self) -> None:
        if self._index_path is None:
            raise ValueError("snapshot() requires an index_path")
        self._index.write(str(self._index_path))
        self._version += 1

    def _validate_dimensions(self, vectors: list[EmbeddingVector]) -> None:
        for vector in vectors:
            if vector.dimension != self._dimension:
                raise DimensionMismatchError(
                    f"expected dimension {self._dimension}, got {vector.dimension}"
                )
