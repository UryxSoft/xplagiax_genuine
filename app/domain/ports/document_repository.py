"""Port for Document persistence (docs/DOMAIN_MODEL.md sect 8)."""

from __future__ import annotations

from typing import Protocol

from app.domain.entities.document import Document
from app.domain.value_objects.sha256_hash import Sha256Hash


class DocumentRepository(Protocol):
    def save(self, document: Document) -> None:
        ...

    def by_id(self, document_id: str) -> Document | None:
        ...

    def by_hash(self, tenant_id: str, content_hash: Sha256Hash) -> Document | None:
        ...

    def list(
        self, tenant_id: str, language: str | None = None, topic: str | None = None, page: int = 1
    ) -> list[Document]:
        ...

    def ids_matching(
        self, tenant_id: str, language: str | None = None, topic: str | None = None
    ) -> list[str]:
        """Returns matching document ids only, unpaginated.

        Used by CandidateFilter (ADR-004, filter-first search) to build an
        allowlist over a tenant's full matching corpus: loading paginated
        full Document aggregates (`list`, 20/page) for that purpose would
        be prohibitively wasteful at the scale this system targets.
        """
        ...

    def delete(self, document_id: str) -> None:
        ...
