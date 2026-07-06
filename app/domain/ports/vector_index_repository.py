"""Port for the vector index (ADR-002: TurboVec IdMapIndex, exclusively).

`allowlist=None` means unrestricted search; `allowlist=set()` (empty but
not None) means restrict to nothing -- these are semantically different
and both must be preserved by every adapter (docs/ARCHITECTURE.md sect 6,
"filter-first" search: CandidateFilter can legitimately produce an empty
candidate set when no document matches language+topic).
"""

from __future__ import annotations

from typing import Protocol

from app.domain.value_objects.embedding_vector import EmbeddingVector
from app.domain.value_objects.search_hit import SearchHit


class VectorIndexRepository(Protocol):
    @property
    def dimension(self) -> int:
        ...

    @property
    def version(self) -> int:
        ...

    def add(self, chunk_ids: list[int], vectors: list[EmbeddingVector]) -> None:
        ...

    def search(
        self, query: EmbeddingVector, k: int, allowlist: set[int] | None = None
    ) -> list[SearchHit]:
        ...

    def remove(self, chunk_id: int) -> None:
        ...

    def snapshot(self) -> None:
        ...
