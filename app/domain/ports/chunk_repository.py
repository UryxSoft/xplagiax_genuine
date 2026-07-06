"""Port for Chunk persistence (docs/DOMAIN_MODEL.md sect 8)."""

from __future__ import annotations

from typing import Protocol

from app.domain.entities.chunk import Chunk


class ChunkRepository(Protocol):
    def save_all(self, chunks: list[Chunk]) -> None:
        ...

    def by_ids(self, chunk_ids: list[int]) -> list[Chunk]:
        ...

    def by_document(self, document_id: str) -> list[Chunk]:
        ...

    def ids_for_documents(self, document_ids: list[str]) -> list[int]:
        """Returns chunk ids only, across possibly many documents, in one query.

        Used by CandidateFilter to build TurboVec allowlists without an
        N+1 fetch-full-Chunk-per-document pattern.
        """
        ...
