"""RF-13 through HTTP: mode=async returns 202 + job_id, GET /jobs/{id}
polls the outcome; worker_mode replicas force every write through jobs."""

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


def _build_client(worker_mode: bool):
    documents = InMemoryDocumentRepository()
    chunks = InMemoryChunkRepository()
    chunks.bind_documents(documents)
    vector_index = InMemoryVectorIndex(dimension=8)
    embeddings = HashingEmbeddingModel(dimension=8)
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
        worker_mode=worker_mode,
    )

    app = create_app(dependencies)
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture()
def client():
    with _build_client(worker_mode=False) as c:
        yield c


@pytest.fixture()
def worker_client():
    with _build_client(worker_mode=True) as c:
        yield c


def test_async_index_returns_202_and_job_completes(client) -> None:
    response = client.post(
        "/index", json={"text": _TEXT, "tenant_id": "tenant-a", "mode": "async"}
    )

    assert response.status_code == 202
    job_id = response.get_json()["job_id"]

    poll = client.get(f"/jobs/{job_id}?tenant_id=tenant-a")
    assert poll.status_code == 200
    body = poll.get_json()
    assert body["status"] == "DONE"
    assert body["kind"] == "index"
    assert body["result"]["chunks_indexed"] > 0


def test_async_search_returns_result_via_polling(client) -> None:
    client.post("/index", json={"text": _TEXT, "tenant_id": "tenant-a"})

    job_id = client.post(
        "/search", json={"text": _TEXT, "tenant_id": "tenant-a", "mode": "async"}
    ).get_json()["job_id"]

    body = client.get(f"/jobs/{job_id}?tenant_id=tenant-a").get_json()
    assert body["status"] == "DONE"
    assert len(body["result"]["documents"]) == 1


def test_failed_async_job_reports_error(client) -> None:
    job_id = client.post(
        "/index", json={"text": "   \n ", "tenant_id": "tenant-a", "mode": "async"}
    ).get_json()["job_id"]

    body = client.get(f"/jobs/{job_id}?tenant_id=tenant-a").get_json()
    assert body["status"] == "FAILED"
    assert "EmptyDocumentError" in body["error"]


def test_job_polling_is_tenant_scoped(client) -> None:
    job_id = client.post(
        "/search", json={"text": _TEXT, "tenant_id": "tenant-a", "mode": "async"}
    ).get_json()["job_id"]

    assert client.get(f"/jobs/{job_id}?tenant_id=tenant-b").status_code == 404
    assert client.get(f"/jobs/{job_id}").status_code == 400
    assert client.get("/jobs/no-such-job?tenant_id=tenant-a").status_code == 404


def test_worker_mode_forces_index_through_jobs(worker_client) -> None:
    response = worker_client.post("/index", json={"text": _TEXT, "tenant_id": "tenant-a"})

    assert response.status_code == 202  # sync requested, job enforced
    job_id = response.get_json()["job_id"]
    body = worker_client.get(f"/jobs/{job_id}?tenant_id=tenant-a").get_json()
    assert body["status"] == "DONE"


def test_worker_mode_forces_delete_through_jobs(worker_client) -> None:
    index_job = worker_client.post(
        "/index", json={"text": _TEXT, "tenant_id": "tenant-a"}
    ).get_json()["job_id"]
    document_id = worker_client.get(
        f"/jobs/{index_job}?tenant_id=tenant-a"
    ).get_json()["result"]["document_id"]

    response = worker_client.delete(f"/documents/{document_id}?tenant_id=tenant-a")

    assert response.status_code == 202
    job_id = response.get_json()["job_id"]
    body = worker_client.get(f"/jobs/{job_id}?tenant_id=tenant-a").get_json()
    assert body["status"] == "DONE"
    assert body["result"] == {"deleted": True, "document_id": document_id}
