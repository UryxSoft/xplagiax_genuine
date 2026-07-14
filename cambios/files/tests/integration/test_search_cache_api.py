"""L2 cache behavior through the HTTP layer: repeated searches skip the
pipeline, indexing/deleting invalidates the tenant's namespace."""

from __future__ import annotations

import pytest

from app.api.app_factory import create_app
from app.api.dependencies import AppDependencies
from app.application.indexing.document_deleter import DocumentDeleter
from app.application.indexing.indexing_pipeline import IndexingPipeline
from app.application.ranking.plagiarism_scorer import PlagiarismScorer
from app.application.ranking.reranker import Reranker
from app.application.search.candidate_filter import CandidateFilter
from app.application.search.result_aggregator import ResultAggregator
from app.application.search.search_pipeline import SearchPipeline
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
    "La ingenieria de software estudia el diseno de sistemas complejos "
    "usando algoritmos y estructuras de datos bien conocidas."
)


class _CountingEmbeddingModel(HashingEmbeddingModel):
    def __init__(self) -> None:
        super().__init__(dimension=8)
        self.query_calls = 0

    def embed_query(self, text: str):
        self.query_calls += 1
        return super().embed_query(text)


@pytest.fixture()
def stack():
    documents = InMemoryDocumentRepository()
    chunks = InMemoryChunkRepository()
    chunks.bind_documents(documents)
    vector_index = InMemoryVectorIndex(dimension=8)
    embeddings = _CountingEmbeddingModel()
    chunker = HybridChunker(WordTokenCounter(), min_tokens=5, max_tokens=30, overlap_ratio=0.0)

    dependencies = AppDependencies(
        document_repository=documents,
        chunk_repository=chunks,
        language_detector=StaticLanguageDetector(),
        topic_classifier=StaticTopicClassifier(),
        search_pipeline=SearchPipeline(
            chunker=chunker,
            embedding_model=embeddings,
            language_detector=StaticLanguageDetector(),
            topic_classifier=StaticTopicClassifier(),
            candidate_filter=CandidateFilter(documents, chunks),
            vector_index=vector_index,
            result_aggregator=ResultAggregator(chunks),
        ),
        reranker=Reranker(chunks),
        plagiarism_scorer=PlagiarismScorer(),
        indexing_pipeline=IndexingPipeline(
            chunker=chunker,
            embedding_model=embeddings,
            language_detector=StaticLanguageDetector(),
            topic_classifier=StaticTopicClassifier(),
            vector_index=vector_index,
            document_repository=documents,
            chunk_repository=chunks,
        ),
        document_deleter=DocumentDeleter(documents, chunks, vector_index),
        vector_index=vector_index,
    )

    app = create_app(dependencies)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client, embeddings


def _search(client, tenant_id: str = "tenant-a"):
    return client.post("/search", json={"text": _TEXT, "tenant_id": tenant_id})


def test_repeated_search_is_served_from_cache(stack) -> None:
    client, embeddings = stack
    client.post("/index", json={"text": _TEXT, "tenant_id": "tenant-a"})

    first = _search(client)
    calls_after_first = embeddings.query_calls
    assert calls_after_first > 0

    second = _search(client)

    assert second.get_json() == first.get_json()
    assert embeddings.query_calls == calls_after_first  # pipeline never ran


def test_indexing_invalidates_tenant_cache(stack) -> None:
    client, embeddings = stack
    client.post("/index", json={"text": _TEXT, "tenant_id": "tenant-a"})
    _search(client)
    calls_after_first = embeddings.query_calls

    client.post("/index", json={"text": _TEXT + " Nuevo contenido.", "tenant_id": "tenant-a"})
    second = _search(client)

    assert embeddings.query_calls > calls_after_first  # recomputed
    assert second.status_code == 200


def test_delete_invalidates_tenant_cache(stack) -> None:
    client, embeddings = stack
    document_id = client.post(
        "/index", json={"text": _TEXT, "tenant_id": "tenant-a"}
    ).get_json()["document_id"]

    assert len(_search(client).get_json()["documents"]) == 1
    client.delete(f"/documents/{document_id}?tenant_id=tenant-a")

    assert _search(client).get_json()["documents"] == []


def test_cache_does_not_leak_across_tenants(stack) -> None:
    client, _embeddings = stack
    client.post("/index", json={"text": _TEXT, "tenant_id": "tenant-a"})

    assert len(_search(client, "tenant-a").get_json()["documents"]) == 1
    assert _search(client, "tenant-b").get_json()["documents"] == []
