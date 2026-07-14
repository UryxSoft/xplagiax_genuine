"""End-to-end API tests for the Fase 1 CRUD surface: POST /index,
GET /documents (dynamic filters), GET/DELETE /documents/{id}, GET /stats.

Real application services (IndexingPipeline, DocumentDeleter,
SearchPipeline) run over complete in-memory fakes (tests/integration/
inmemory.py), so these tests prove the whole loop: index -> catalog ->
search -> delete -> gone.
"""

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
    "La ingenieria de software estudia el diseno de sistemas complejos. "
    "Los algoritmos y las estructuras de datos son la base de todo programa.\n\n"
    "Un segundo parrafo habla de arquitectura hexagonal y puertos. "
    "Los adaptadores conectan el dominio con la infraestructura externa."
)


@pytest.fixture()
def client():
    documents = InMemoryDocumentRepository()
    chunks = InMemoryChunkRepository()
    chunks.bind_documents(documents)
    vector_index = InMemoryVectorIndex(dimension=8)
    embeddings = HashingEmbeddingModel(dimension=8)
    language_detector = StaticLanguageDetector()
    topic_classifier = StaticTopicClassifier()
    chunker = HybridChunker(WordTokenCounter(), min_tokens=5, max_tokens=30, overlap_ratio=0.0)

    indexing_pipeline = IndexingPipeline(
        chunker=chunker,
        embedding_model=embeddings,
        language_detector=language_detector,
        topic_classifier=topic_classifier,
        vector_index=vector_index,
        document_repository=documents,
        chunk_repository=chunks,
    )
    search_pipeline = SearchPipeline(
        chunker=chunker,
        embedding_model=embeddings,
        language_detector=language_detector,
        topic_classifier=topic_classifier,
        candidate_filter=CandidateFilter(documents, chunks),
        vector_index=vector_index,
        result_aggregator=ResultAggregator(chunks),
    )

    dependencies = AppDependencies(
        document_repository=documents,
        chunk_repository=chunks,
        language_detector=language_detector,
        topic_classifier=topic_classifier,
        search_pipeline=search_pipeline,
        reranker=Reranker(chunks),
        plagiarism_scorer=PlagiarismScorer(),
        indexing_pipeline=indexing_pipeline,
        document_deleter=DocumentDeleter(documents, chunks, vector_index),
        vector_index=vector_index,
    )

    app = create_app(dependencies)
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def _index(client, **overrides):
    payload = {
        "text": _TEXT,
        "tenant_id": "tenant-a",
        "filename": "tesis.txt",
        "titulo": "Tesis X",
        "autores": ["Ana Ruiz"],
        "institucion": "Universidad Nacional",
        "pais": "Peru",
    }
    payload.update(overrides)
    return client.post("/index", json=payload)


def test_index_returns_201_with_chunk_count(client) -> None:
    response = _index(client)

    assert response.status_code == 201
    body = response.get_json()
    assert body["chunks_indexed"] > 0
    assert body["duplicate"] is False
    assert body["idioma"] == "es"
    assert body["tema"] == "Ingenieria"
    assert body["document_id"]


def test_index_same_text_twice_reports_duplicate(client) -> None:
    first = _index(client).get_json()
    response = _index(client)

    assert response.status_code == 200
    body = response.get_json()
    assert body["duplicate"] is True
    assert body["document_id"] == first["document_id"]
    assert body["chunks_indexed"] == 0


def test_index_same_text_other_tenant_is_not_duplicate(client) -> None:
    _index(client)
    response = _index(client, tenant_id="tenant-b")

    assert response.status_code == 201
    assert response.get_json()["duplicate"] is False


def test_index_empty_text_returns_400(client) -> None:
    response = _index(client, text="   \n\n  ")
    assert response.status_code == 400
    assert response.get_json()["error"] == "empty_document"


def test_index_explicit_language_overrides_detection(client) -> None:
    response = _index(client, idioma="en")
    assert response.status_code == 201
    assert response.get_json()["idioma"] == "en"


def test_list_documents_with_dynamic_filters(client) -> None:
    _index(client)
    _index(
        client,
        text=_TEXT + " Texto adicional distinto.",
        institucion="Universidad de Chile",
        pais="Chile",
    )

    everything = client.get("/documents?tenant_id=tenant-a").get_json()
    assert len(everything["documents"]) == 2

    by_country = client.get("/documents?tenant_id=tenant-a&pais=peru").get_json()
    assert len(by_country["documents"]) == 1
    assert by_country["documents"][0]["pais"] == "Peru"

    by_institution = client.get(
        "/documents?tenant_id=tenant-a&institucion=Universidad%20de%20Chile"
    ).get_json()
    assert len(by_institution["documents"]) == 1

    combined = client.get(
        "/documents?tenant_id=tenant-a&idioma=es&tema=Ingenieria&pais=Chile"
    ).get_json()
    assert len(combined["documents"]) == 1

    nothing = client.get("/documents?tenant_id=tenant-a&pais=Argentina").get_json()
    assert nothing["documents"] == []


def test_list_documents_requires_tenant(client) -> None:
    assert client.get("/documents").status_code == 400


def test_get_document_detail_includes_chunk_count(client) -> None:
    document_id = _index(client).get_json()["document_id"]

    response = client.get(f"/documents/{document_id}?tenant_id=tenant-a")

    assert response.status_code == 200
    body = response.get_json()
    assert body["id"] == document_id
    assert body["documento"] == "tesis.txt"
    assert body["chunks"] > 0
    assert body["estado"] == "INDEXED"


def test_get_document_cross_tenant_is_404(client) -> None:
    document_id = _index(client).get_json()["document_id"]
    response = client.get(f"/documents/{document_id}?tenant_id=tenant-b")
    assert response.status_code == 404


def test_indexed_text_is_found_by_search(client) -> None:
    _index(client)

    response = client.post(
        "/search",
        json={"text": _TEXT, "tenant_id": "tenant-a"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert len(body["documents"]) == 1
    assert body["documents"][0]["documento"] == "tesis.txt"
    assert body["documents"][0]["similaridad"] > 50.0


def test_delete_document_removes_everything(client) -> None:
    document_id = _index(client).get_json()["document_id"]

    response = client.delete(f"/documents/{document_id}?tenant_id=tenant-a")
    assert response.status_code == 200
    assert response.get_json() == {"deleted": True, "document_id": document_id}

    assert client.get(f"/documents/{document_id}?tenant_id=tenant-a").status_code == 404

    search = client.post("/search", json={"text": _TEXT, "tenant_id": "tenant-a"}).get_json()
    assert search["documents"] == []

    stats = client.get("/stats?tenant_id=tenant-a").get_json()
    assert stats["documents"] == 0
    assert stats["chunks"] == 0


def test_delete_cross_tenant_is_404_and_keeps_document(client) -> None:
    document_id = _index(client).get_json()["document_id"]

    assert client.delete(f"/documents/{document_id}?tenant_id=tenant-b").status_code == 404
    assert client.get(f"/documents/{document_id}?tenant_id=tenant-a").status_code == 200


def test_delete_missing_document_is_404(client) -> None:
    assert client.delete("/documents/no-such-id?tenant_id=tenant-a").status_code == 404


def test_stats_reports_corpus_size(client) -> None:
    _index(client)
    _index(client, text=_TEXT + " Mas contenido unico.", tenant_id="tenant-a")
    _index(client, tenant_id="tenant-b")

    response = client.get("/stats?tenant_id=tenant-a")

    assert response.status_code == 200
    body = response.get_json()
    assert body["documents"] == 2
    assert body["chunks"] > 0
    assert body["index_dimension"] == 8
