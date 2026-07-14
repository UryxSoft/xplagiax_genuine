from __future__ import annotations

import pytest

from app.application.indexing.document_deleter import DocumentDeleter
from app.application.indexing.indexing_pipeline import IndexCommand, IndexingPipeline
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

_TEXT = "Contenido academico de prueba con palabras suficientes para un segmento."


@pytest.fixture()
def stack():
    documents = InMemoryDocumentRepository()
    chunks = InMemoryChunkRepository()
    chunks.bind_documents(documents)
    vector_index = InMemoryVectorIndex(dimension=8)
    pipeline = IndexingPipeline(
        chunker=HybridChunker(WordTokenCounter(), min_tokens=2, max_tokens=30, overlap_ratio=0.0),
        embedding_model=HashingEmbeddingModel(dimension=8),
        language_detector=StaticLanguageDetector(),
        topic_classifier=StaticTopicClassifier(),
        vector_index=vector_index,
        document_repository=documents,
        chunk_repository=chunks,
    )
    deleter = DocumentDeleter(documents, chunks, vector_index)
    return pipeline, deleter, documents, chunks, vector_index


def test_delete_removes_document_chunks_and_vectors(stack) -> None:
    pipeline, deleter, documents, chunks, vector_index = stack
    result = pipeline.index(IndexCommand(text=_TEXT, tenant_id="tenant-a"))

    assert deleter.delete(result.document_id, "tenant-a") is True

    assert documents.by_id(result.document_id) is None
    assert chunks.by_document(result.document_id) == []
    assert len(vector_index) == 0


def test_delete_wrong_tenant_refused(stack) -> None:
    pipeline, deleter, documents, _chunks, vector_index = stack
    result = pipeline.index(IndexCommand(text=_TEXT, tenant_id="tenant-a"))

    assert deleter.delete(result.document_id, "tenant-b") is False

    assert documents.by_id(result.document_id) is not None
    assert len(vector_index) > 0


def test_delete_missing_document_returns_false(stack) -> None:
    _pipeline, deleter, _d, _c, _v = stack
    assert deleter.delete("missing-id", "tenant-a") is False
