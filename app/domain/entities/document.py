"""Document aggregate root -- persistence-oriented fields (docs/DOMAIN_MODEL.md sect 2.1).

State-machine transition methods (attach_extraction, split_into, etc.) are
introduced alongside the IndexingPipeline that invokes them; this sprint's
scope is persistence (Metadata), so only the shape and the invariants that
matter for storage/retrieval are enforced here.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.domain.entities.document_status import DocumentStatus
from app.domain.value_objects.bibliographic_metadata import BibliographicMetadata
from app.domain.value_objects.language import Language
from app.domain.value_objects.pdf_source import PdfSource
from app.domain.value_objects.sha256_hash import Sha256Hash
from app.domain.value_objects.topic import Topic


class Document(BaseModel):
    model_config = {"frozen": True}

    id: str
    tenant_id: str
    source: PdfSource
    content_hash: Sha256Hash
    bibliography: BibliographicMetadata = BibliographicMetadata()
    language: Language | None = None
    topic: Topic | None = None
    keywords: tuple[str, ...] = ()
    status: DocumentStatus = DocumentStatus.RECEIVED
    indexed_at: datetime | None = None

    def with_status(self, status: DocumentStatus) -> "Document":
        return self.model_copy(update={"status": status})
