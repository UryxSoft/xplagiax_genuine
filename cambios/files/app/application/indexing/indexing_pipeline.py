"""Plain-text indexing use case (RF-01/RF-11 ingestion side, ADR sect 10).

Write ordering: vectors first, metadata second. If the vector add succeeds
and the metadata write fails, the orphan vectors are harmless -- search
skips hits whose chunk_id has no metadata row (ResultAggregator's defensive
skip) and background compaction reclaims them. The opposite order would
strand a metadata row whose content_hash blocks any retry (dedup would
report "duplicate" for a document that never reached the index).

Dedup scope: exact SHA256 within tenant. The ADR's full cascade
(Bloom/SimHash/MinHash near-dup) needs an LSH store over the corpus;
until that exists this pipeline does not pretend to near-dedup.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from app.application.indexing.chunk_id_factory import chunk_id_for
from app.domain.entities.chunk import Chunk
from app.domain.entities.document import Document
from app.domain.entities.document_status import DocumentStatus
from app.domain.ports.chunk_repository import ChunkRepository
from app.domain.ports.document_repository import DocumentRepository
from app.domain.ports.embedding_model import EmbeddingModel
from app.domain.ports.language_detector import LanguageDetector
from app.domain.ports.topic_classifier import TopicClassifier
from app.domain.ports.vector_index_repository import VectorIndexRepository
from app.domain.value_objects.bibliographic_metadata import BibliographicMetadata
from app.domain.value_objects.language import Language
from app.domain.value_objects.pdf_source import PLAIN_TEXT_PATH, PdfSource
from app.domain.value_objects.sha256_hash import Sha256Hash
from app.domain.value_objects.topic import Topic
from app.infrastructure.chunking.hybrid_chunker import HybridChunker
from app.infrastructure.parsers.plain_text_normalizer import normalize_plain_text

PROVIDED_METADATA_CONFIDENCE = 1.0


class EmptyDocumentError(ValueError):
    """Raised when the submitted text contains nothing indexable."""


@dataclass(frozen=True)
class IndexCommand:
    text: str
    tenant_id: str
    filename: str | None = None
    language_code: str | None = None
    topic_domain: str | None = None
    bibliography: BibliographicMetadata = BibliographicMetadata()


@dataclass(frozen=True)
class IndexResult:
    document_id: str
    chunks_indexed: int
    duplicate: bool
    language_code: str
    topic_domain: str


class IndexingPipeline:
    def __init__(
        self,
        chunker: HybridChunker,
        embedding_model: EmbeddingModel,
        language_detector: LanguageDetector,
        topic_classifier: TopicClassifier,
        vector_index: VectorIndexRepository,
        document_repository: DocumentRepository,
        chunk_repository: ChunkRepository,
        snapshot_after_write: bool = True,
    ) -> None:
        self._chunker = chunker
        self._embedding_model = embedding_model
        self._language_detector = language_detector
        self._topic_classifier = topic_classifier
        self._vector_index = vector_index
        self._documents = document_repository
        self._chunks = chunk_repository
        self._snapshot_after_write = snapshot_after_write

    def index(self, command: IndexCommand) -> IndexResult:
        normalized = normalize_plain_text(command.text)
        if not normalized:
            raise EmptyDocumentError("document text is empty after normalization")

        content_hash = Sha256Hash.of(normalized)
        existing = self._documents.by_hash(command.tenant_id, content_hash)
        if existing is not None:
            return IndexResult(
                document_id=existing.id,
                chunks_indexed=0,
                duplicate=True,
                language_code=existing.language.code if existing.language else "",
                topic_domain=existing.topic.domain if existing.topic else "",
            )

        language = (
            Language(code=command.language_code, confidence=PROVIDED_METADATA_CONFIDENCE)
            if command.language_code is not None
            else self._language_detector.detect(normalized)
        )
        topic = (
            Topic(domain=command.topic_domain, confidence=PROVIDED_METADATA_CONFIDENCE)
            if command.topic_domain is not None
            else self._topic_classifier.classify(normalized)
        )

        segments = self._chunker.chunk(normalized)
        if not segments:
            raise EmptyDocumentError("document text produced no indexable segments")

        document_id = str(uuid.uuid4())
        chunks = [
            Chunk(
                id=chunk_id_for(document_id, segment.order),
                document_id=document_id,
                text=segment.text,
                span=segment.span,
                order=segment.order,
            )
            for segment in segments
        ]

        vectors = self._embedding_model.embed_passages([c.text for c in chunks])
        self._vector_index.add([c.id for c in chunks], vectors)

        self._chunks.save_all(chunks)
        self._documents.save(
            Document(
                id=document_id,
                tenant_id=command.tenant_id,
                source=PdfSource(
                    filename=command.filename or f"{document_id}.txt",
                    path=PLAIN_TEXT_PATH,
                    pages=0,
                    mime="text/plain",
                    size_bytes=len(normalized.encode("utf-8")),
                ),
                content_hash=content_hash,
                bibliography=command.bibliography,
                language=language,
                topic=topic,
                status=DocumentStatus.INDEXED,
                indexed_at=datetime.now(timezone.utc),
            )
        )

        if self._snapshot_after_write:
            self._vector_index.snapshot()

        return IndexResult(
            document_id=document_id,
            chunks_indexed=len(chunks),
            duplicate=False,
            language_code=language.code,
            topic_domain=topic.domain,
        )
