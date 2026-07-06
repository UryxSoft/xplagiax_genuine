"""Integration test for the HTTP layer: Flask test client + fake adapters.

No live PostgreSQL/TurboVec/embedding model involved -- this proves
routing, request validation, response shape and error handling, which is
what the API layer itself is responsible for. wsgi.py's real wiring is
exercised only in a deployed environment.
"""

from __future__ import annotations

import pytest

from app.api.app_factory import create_app
from app.api.dependencies import AppDependencies
from app.application.ranking.plagiarism_scorer import PlagiarismScorer
from app.application.ranking.reranker import Reranker
from app.application.search.candidate_filter import CandidateFilter
from app.application.search.result_aggregator import ResultAggregator
from app.application.search.search_pipeline import SearchPipeline
from app.domain.entities.chunk import Chunk
from app.domain.entities.document import Document
from app.domain.value_objects.bibliographic_metadata import BibliographicMetadata
from app.domain.value_objects.embedding_vector import EmbeddingVector
from app.domain.value_objects.language import Language
from app.domain.value_objects.pdf_source import PdfSource
from app.domain.value_objects.search_hit import SearchHit
from app.domain.value_objects.sha256_hash import Sha256Hash
from app.domain.value_objects.token_span import TokenSpan
from app.domain.value_objects.topic import Topic
from app.infrastructure.chunking.hybrid_chunker import HybridChunker
from app.infrastructure.chunking.word_token_counter import WordTokenCounter


class _FakeEmbeddingModel:
    def embed_query(self, text: str) -> EmbeddingVector:
        return EmbeddingVector(values=(float(len(text)), 0.0))


class _FakeLanguageDetector:
    def detect(self, text: str) -> Language:
        return Language(code="es", confidence=0.95)


class _FakeTopicClassifier:
    def classify(self, text: str) -> Topic:
        return Topic(domain="Ingenieria", confidence=0.9)


class _FakeDocumentRepository:
    def __init__(self, documents: list[Document]) -> None:
        self._by_id = {d.id: d for d in documents}

    def ids_matching(self, tenant_id, language=None, topic=None) -> list[str]:
        return [
            d.id
            for d in self._by_id.values()
            if d.tenant_id == tenant_id
            and (language is None or (d.language and d.language.code == language))
            and (topic is None or (d.topic and d.topic.domain == topic))
        ]

    def by_id(self, document_id: str) -> Document | None:
        return self._by_id.get(document_id)


class _FakeChunkRepository:
    def __init__(self, chunk_map: dict[str, list[int]], chunks: list[Chunk]) -> None:
        self._chunk_map = chunk_map
        self._by_id = {c.id: c for c in chunks}

    def ids_for_documents(self, document_ids: list[str]) -> list[int]:
        ids: list[int] = []
        for doc_id in document_ids:
            ids.extend(self._chunk_map.get(doc_id, []))
        return ids

    def by_ids(self, chunk_ids: list[int]) -> list[Chunk]:
        return [self._by_id[i] for i in chunk_ids if i in self._by_id]


class _FakeVectorIndex:
    def __init__(self, hits_by_allowlist: dict) -> None:
        self._hits = hits_by_allowlist

    def search(self, query, k, allowlist=None):
        key = frozenset(allowlist) if allowlist is not None else None
        return self._hits.get(key, [])[:k]


def _document() -> Document:
    return Document(
        id="doc-1",
        tenant_id="tenant-a",
        source=PdfSource(filename="tesis.pdf", path="/data/tesis.pdf", pages=50, mime="application/pdf", size_bytes=1000),
        content_hash=Sha256Hash.of("contenido de la tesis"),
        bibliography=BibliographicMetadata(title="Tesis X", authors=("Juan Perez",), institution="Universidad Nacional de Ingenieria"),
        language=Language(code="es", confidence=0.95),
        topic=Topic(domain="Ingenieria", confidence=0.9),
    )


@pytest.fixture()
def client():
    document = _document()
    chunks = [
        Chunk(id=1, document_id="doc-1", text="contenido academico de ejemplo copiado", span=TokenSpan(start=0, end=10), order=0),
    ]
    chunk_map = {"doc-1": [1]}
    allowlist_key = frozenset({1})
    vector_index = _FakeVectorIndex({allowlist_key: [SearchHit(chunk_id=1, score=0.92)]})

    document_repository = _FakeDocumentRepository([document])
    chunk_repository = _FakeChunkRepository(chunk_map, chunks)

    pipeline = SearchPipeline(
        chunker=HybridChunker(WordTokenCounter(), min_tokens=3, max_tokens=20, overlap_ratio=0.0),
        embedding_model=_FakeEmbeddingModel(),
        language_detector=_FakeLanguageDetector(),
        topic_classifier=_FakeTopicClassifier(),
        candidate_filter=CandidateFilter(document_repository, chunk_repository),
        vector_index=vector_index,
        result_aggregator=ResultAggregator(chunk_repository),
    )

    dependencies = AppDependencies(
        document_repository=document_repository,
        chunk_repository=chunk_repository,
        language_detector=_FakeLanguageDetector(),
        topic_classifier=_FakeTopicClassifier(),
        search_pipeline=pipeline,
        reranker=Reranker(chunk_repository),
        plagiarism_scorer=PlagiarismScorer(),
    )

    app = create_app(dependencies)
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def test_health_endpoint(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_ready_endpoint(client) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ready"


def test_search_returns_ranked_document_match(client) -> None:
    response = client.post(
        "/search",
        json={"text": "un texto extenso sobre ingenieria de software y algoritmos", "tenant_id": "tenant-a"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["query_language"] == "es"
    assert body["query_topic"] == "Ingenieria"
    assert len(body["documents"]) == 1

    match = body["documents"][0]
    assert match["documento"] == "tesis.pdf"
    assert match["universidad"] == "Universidad Nacional de Ingenieria"
    assert match["autores"] == ["Juan Perez"]
    assert match["chunks"] == 1
    assert 0.0 <= match["similaridad"] <= 100.0
    assert match["chunk_mas_parecido"]["texto"] == "contenido academico de ejemplo copiado"


def test_search_missing_text_returns_400(client) -> None:
    response = client.post("/search", json={"tenant_id": "tenant-a"})

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_request"


def test_search_missing_tenant_id_returns_400(client) -> None:
    response = client.post("/search", json={"text": "algun texto"})

    assert response.status_code == 400


def test_search_malformed_json_returns_400_not_500(client) -> None:
    response = client.post("/search", data="not json at all", content_type="application/json")

    assert response.status_code == 400


def test_search_no_matches_returns_empty_documents(client) -> None:
    response = client.post(
        "/search", json={"text": "texto que no coincide con nada indexado", "tenant_id": "tenant-b"}
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["documents"] == []
    assert body["global_plagiarism_percent"] == 0.0


def test_unknown_route_returns_404_json() -> None:
    from app.api.app_factory import create_app as factory

    dependencies = AppDependencies(
        document_repository=_FakeDocumentRepository([]),
        chunk_repository=_FakeChunkRepository({}, []),
        language_detector=_FakeLanguageDetector(),
        topic_classifier=_FakeTopicClassifier(),
        search_pipeline=SearchPipeline(
            chunker=HybridChunker(WordTokenCounter(), min_tokens=3, max_tokens=20, overlap_ratio=0.0),
            embedding_model=_FakeEmbeddingModel(),
            language_detector=_FakeLanguageDetector(),
            topic_classifier=_FakeTopicClassifier(),
            candidate_filter=CandidateFilter(_FakeDocumentRepository([]), _FakeChunkRepository({}, [])),
            vector_index=_FakeVectorIndex({}),
            result_aggregator=ResultAggregator(_FakeChunkRepository({}, [])),
        ),
        reranker=Reranker(_FakeChunkRepository({}, [])),
        plagiarism_scorer=PlagiarismScorer(),
    )
    app = factory(dependencies)
    with app.test_client() as test_client:
        response = test_client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.get_json()["error"] == "Not Found"
