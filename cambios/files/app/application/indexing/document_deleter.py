"""Delete use case (RF-14): removes a document's vectors and metadata.

Tenant-scoped: a document belonging to another tenant is reported as
not-found, never as forbidden -- revealing existence across tenants is
itself a leak (ADR-011).

Delete ordering mirrors the indexing pipeline's rationale inverted:
vectors go first so a failure midway leaves metadata pointing at missing
vectors (search returns nothing for them) rather than live vectors with no
metadata owner to delete them through.
"""

from __future__ import annotations

from app.domain.ports.chunk_repository import ChunkRepository
from app.domain.ports.document_repository import DocumentRepository
from app.domain.ports.vector_index_repository import VectorIndexRepository


class DocumentDeleter:
    def __init__(
        self,
        document_repository: DocumentRepository,
        chunk_repository: ChunkRepository,
        vector_index: VectorIndexRepository,
        snapshot_after_write: bool = True,
    ) -> None:
        self._documents = document_repository
        self._chunks = chunk_repository
        self._vector_index = vector_index
        self._snapshot_after_write = snapshot_after_write

    def delete(self, document_id: str, tenant_id: str) -> bool:
        document = self._documents.by_id(document_id)
        if document is None or document.tenant_id != tenant_id:
            return False

        for chunk_id in self._chunks.ids_for_documents([document_id]):
            self._vector_index.remove(chunk_id)

        self._chunks.delete_by_document(document_id)
        self._documents.delete(document_id)

        if self._snapshot_after_write:
            self._vector_index.snapshot()
        return True
