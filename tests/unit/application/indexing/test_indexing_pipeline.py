"""IndexingPipeline behavior over in-memory fakes: dedup short-circuit,
metadata overrides, chunk/vector consistency, idempotent chunk ids."""

from __future__ import annotations

import pytest

from app.application.indexing.document_deleter import DocumentDeleter
from app.application.indexing.indexing_pipeline import (
    EmptyDocumentError,
    IndexCommand,
    IndexingPipeline,
)
from app.domain.entities.document_status import DocumentStatus
from app.domain.value_objects.bibliographic_metadata import BibliographicMetadata
from app.infrastructure.chunking.hybrid_chunker import HybridChunker
from app.infrastructure.chunking.word_token_counter import WordTokenCounter
from tests.integration.inmemory import (
    HashingEmbeddingModel,
    InMemoryChunkRepository,
    InMemoryDocumentRepository,
    InMemoryVectorIndex,
    StaticLanguageDetector,
    StaticTopicClassifier,
)

_TEXT = (
    "Primer parrafo con contenido academico suficiente para un segmento completo.\n\n"
    "Segundo parrafo con mas contenido tecnico y otras palabras distintas."
)


@pytest.fixture()
def stack():
    documents = InMemoryDocumentRepository()
    chunks = InMemoryChunkRepository()
    chunks.bind_documents(documents)
    vector_index = InMemoryVectorIndex(dimension=8)
    pipeline = IndexingPipeline(
        chunker=HybridChunker(WordTokenCounter(), min_tokens=5, max_tokens=30, overlap_ratio=0.0),
        embedding_model=HashingEmbeddingModel(dimension=8),
        language_detector=StaticLanguageDetector(),
        topic_classifier=StaticTopicClassifier(),
        vector_index=vector_index,
        document_repository=documents,
        chunk_repository=chunks,
    )
    return pipeline, documents, chunks, vector_index


def test_index_persists_document_chunks_and_vectors(stack) -> None:
    pipeline, documents, chunks, vector_index = stack

    result = pipeline.index(IndexCommand(text=_TEXT, tenant_id="tenant-a"))

    assert result.duplicate is False
    assert result.chunks_indexed > 0

    document = documents.by_id(result.document_id)
    assert document is not None
    assert document.status == DocumentStatus.INDEXED
    assert document.indexed_at is not None
    assert document.source.mime == "text/plain"

    stored_chunks = chunks.by_document(result.document_id)
    assert len(stored_chunks) == result.chunks_indexed
    assert len(vector_index) == result.chunks_indexed


def test_duplicate_short_circuits_before_touching_index(stack) -> None:
    pipeline, _documents, _chunks, vector_index = stack

    first = pipeline.index(IndexCommand(text=_TEXT, tenant_id="tenant-a"))
    vectors_after_first = len(vector_index)

    second = pipeline.index(IndexCommand(text=_TEXT, tenant_id="tenant-a"))

    assert second.duplicate is True
    assert second.document_id == first.document_id
    assert second.chunks_indexed == 0
    assert len(vector_index) == vectors_after_first


def test_whitespace_variations_hash_to_same_document(stack) -> None:
    pipeline, _d, _c, _v = stack

    first = pipeline.index(IndexCommand(text=_TEXT, tenant_id="tenant-a"))
    second = pipeline.index(
        IndexCommand(text=_TEXT.replace("\n\n", "\n\n\n\n") + "\n  \n", tenant_id="tenant-a")
    )

    assert second.duplicate is True
    assert second.document_id == first.document_id


def test_provided_metadata_overrides_detection(stack) -> None:
    pipeline, documents, _c, _v = stack

    result = pipeline.index(
        IndexCommand(
            text=_TEXT,
            tenant_id="tenant-a",
            language_code="en",
            topic_domain="Derecho",
            bibliography=BibliographicMetadata(institution="Universidad X", country="Bolivia"),
        )
    )

    assert result.language_code == "en"
    assert result.topic_domain == "Derecho"
    document = documents.by_id(result.document_id)
    assert document.language.code == "en"
    assert document.topic.domain == "Derecho"
    assert document.bibliography.country == "Bolivia"


def test_empty_text_raises(stack) -> None:
    pipeline, _d, _c, _v = stack
    with pytest.raises(EmptyDocumentError):
        pipeline.index(IndexCommand(text="  \n \n ", tenant_id="tenant-a"))


def test_delete_then_reindex_same_text_succeeds(stack) -> None:
    """Deterministic chunk ids must not collide with a deleted document's
    leftovers: delete removes vectors, reindex mints a new document uuid."""
    pipeline, documents, chunks, vector_index = stack
    deleter = DocumentDeleter(documents, chunks, vector_index)

    first = pipeline.index(IndexCommand(text=_TEXT, tenant_id="tenant-a"))
    assert deleter.delete(first.document_id, "tenant-a") is True
    assert len(vector_index) == 0

    second = pipeline.index(IndexCommand(text=_TEXT, tenant_id="tenant-a"))

    assert second.duplicate is False
    assert second.document_id != first.document_id
    assert len(vector_index) == second.chunks_indexed
