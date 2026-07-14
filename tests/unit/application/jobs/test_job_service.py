"""JobService over the inline backend and in-memory fakes: full submit ->
execute -> poll lifecycle for the three job kinds, plus failure recording."""

from __future__ import annotations

import pytest

from app.application.indexing.document_deleter import DocumentDeleter
from app.application.indexing.indexing_pipeline import IndexCommand, IndexingPipeline
from app.application.jobs.job_service import JobService, UnknownJobError
from app.application.ranking.plagiarism_scorer import PlagiarismScorer
from app.application.ranking.reranker import Reranker
from app.application.search.candidate_filter import CandidateFilter
from app.application.search.result_aggregator import ResultAggregator
from app.application.search.search_pipeline import SearchPipeline
from app.application.search.search_service import SearchService
from app.domain.entities.job import JobStatus
from app.infrastructure.cache.in_memory_search_cache import InMemorySearchCache
from app.infrastructure.chunking.hybrid_chunker import HybridChunker
from app.infrastructure.chunking.word_token_counter import WordTokenCounter
from app.infrastructure.jobs.in_memory import InlineJobQueue, InMemoryJobRepository
from tests.integration.inmemory import (
    HashingEmbeddingModel,
    InMemoryChunkRepository,
    InMemoryDocumentRepository,
    InMemoryVectorIndex,
    StaticLanguageDetector,
    StaticTopicClassifier,
)

_TEXT = "Texto academico suficientemente largo para producir un segmento indexable."


@pytest.fixture()
def service() -> JobService:
    documents = InMemoryDocumentRepository()
    chunks = InMemoryChunkRepository()
    chunks.bind_documents(documents)
    vector_index = InMemoryVectorIndex(dimension=8)
    embeddings = HashingEmbeddingModel(dimension=8)
    chunker = HybridChunker(WordTokenCounter(), min_tokens=2, max_tokens=30, overlap_ratio=0.0)

    indexing_pipeline = IndexingPipeline(
        chunker=chunker,
        embedding_model=embeddings,
        language_detector=StaticLanguageDetector(),
        topic_classifier=StaticTopicClassifier(),
        vector_index=vector_index,
        document_repository=documents,
        chunk_repository=chunks,
    )
    search_service = SearchService(
        search_pipeline=SearchPipeline(
            chunker=chunker,
            embedding_model=embeddings,
            language_detector=StaticLanguageDetector(),
            topic_classifier=StaticTopicClassifier(),
            candidate_filter=CandidateFilter(documents, chunks),
            vector_index=vector_index,
            result_aggregator=ResultAggregator(chunks),
        ),
        language_detector=StaticLanguageDetector(),
        topic_classifier=StaticTopicClassifier(),
        document_repository=documents,
        chunk_repository=chunks,
        reranker=Reranker(chunks),
        plagiarism_scorer=PlagiarismScorer(),
    )

    queue = InlineJobQueue()
    job_service = JobService(
        job_repository=InMemoryJobRepository(),
        job_queue=queue,
        indexing_pipeline=indexing_pipeline,
        search_service=search_service,
        document_deleter=DocumentDeleter(documents, chunks, vector_index),
        search_cache=InMemorySearchCache(),
    )
    queue.bind(job_service.execute)
    return job_service


def test_index_job_completes_with_result(service: JobService) -> None:
    job_id = service.submit_index(IndexCommand(text=_TEXT, tenant_id="tenant-a"))

    job = service.get(job_id, "tenant-a")
    assert job is not None
    assert job.status == JobStatus.DONE
    assert job.result["chunks_indexed"] > 0
    assert job.result["duplicate"] is False


def test_search_job_returns_search_body(service: JobService) -> None:
    service.submit_index(IndexCommand(text=_TEXT, tenant_id="tenant-a"))
    job_id = service.submit_search(_TEXT, "tenant-a")

    job = service.get(job_id, "tenant-a")
    assert job.status == JobStatus.DONE
    assert len(job.result["documents"]) == 1


def test_delete_job_removes_document(service: JobService) -> None:
    index_job = service.get(
        service.submit_index(IndexCommand(text=_TEXT, tenant_id="tenant-a")), "tenant-a"
    )
    document_id = index_job.result["document_id"]

    job = service.get(service.submit_delete(document_id, "tenant-a"), "tenant-a")

    assert job.status == JobStatus.DONE
    assert job.result == {"deleted": True, "document_id": document_id}


def test_failing_job_is_recorded_as_failed(service: JobService) -> None:
    job_id = service.submit_index(IndexCommand(text="   ", tenant_id="tenant-a"))

    job = service.get(job_id, "tenant-a")
    assert job.status == JobStatus.FAILED
    assert "EmptyDocumentError" in job.error


def test_get_is_tenant_scoped(service: JobService) -> None:
    job_id = service.submit_search(_TEXT, "tenant-a")
    assert service.get(job_id, "tenant-b") is None
    assert service.get("missing", "tenant-a") is None


def test_execute_unknown_job_raises(service: JobService) -> None:
    with pytest.raises(UnknownJobError):
        service.execute("no-such-job")
