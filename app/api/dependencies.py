"""Explicit dependency container for the Flask app.

`create_app` (app_factory.py) requires an AppDependencies instance rather
than constructing adapters from environment variables internally: tests
build one from fakes, `wsgi.py` builds one from real adapters. Keeping
construction outside the factory means the HTTP layer can be tested
without a live PostgreSQL, GROBID, or embedding model.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.indexing.document_deleter import DocumentDeleter
from app.application.indexing.indexing_pipeline import IndexingPipeline
from app.application.jobs.job_service import JobService
from app.application.ranking.plagiarism_scorer import PlagiarismScorer
from app.application.ranking.reranker import Reranker
from app.application.search.search_pipeline import SearchPipeline
from app.application.search.search_service import SearchService
from app.domain.ports.chunk_repository import ChunkRepository
from app.domain.ports.document_repository import DocumentRepository
from app.domain.ports.language_detector import LanguageDetector
from app.domain.ports.search_result_cache import SearchResultCache
from app.domain.ports.topic_classifier import TopicClassifier
from app.domain.ports.vector_index_repository import VectorIndexRepository
from app.infrastructure.cache.in_memory_search_cache import InMemorySearchCache


@dataclass(frozen=True)
class AppDependencies:
    document_repository: DocumentRepository
    chunk_repository: ChunkRepository
    language_detector: LanguageDetector
    topic_classifier: TopicClassifier
    search_pipeline: SearchPipeline
    reranker: Reranker
    plagiarism_scorer: PlagiarismScorer
    indexing_pipeline: IndexingPipeline
    document_deleter: DocumentDeleter
    vector_index: VectorIndexRepository
    # In-process default keeps tests and single-node setups zero-config;
    # wsgi.py swaps in RedisSearchCache when redis_url is configured.
    search_cache: SearchResultCache = field(default_factory=InMemorySearchCache)
    # Built in __post_init__ from the other fields when not provided.
    search_service: SearchService | None = None
    # Inline (execute-on-enqueue) by default; the bootstrap swaps in the
    # Redis Streams backend when configured. Same API contract either way.
    job_service: JobService | None = None
    # True when this replica holds a read-only index view: index/delete
    # must go through jobs (see HotReloadingVectorIndex).
    worker_mode: bool = False

    def __post_init__(self) -> None:
        if self.search_service is None:
            object.__setattr__(
                self,
                "search_service",
                SearchService(
                    search_pipeline=self.search_pipeline,
                    language_detector=self.language_detector,
                    topic_classifier=self.topic_classifier,
                    document_repository=self.document_repository,
                    chunk_repository=self.chunk_repository,
                    reranker=self.reranker,
                    plagiarism_scorer=self.plagiarism_scorer,
                ),
            )
        if self.job_service is None:
            from app.infrastructure.jobs.in_memory import InlineJobQueue, InMemoryJobRepository

            queue = InlineJobQueue()
            job_service = JobService(
                job_repository=InMemoryJobRepository(),
                job_queue=queue,
                indexing_pipeline=self.indexing_pipeline,
                search_service=self.search_service,
                document_deleter=self.document_deleter,
                search_cache=self.search_cache,
            )
            queue.bind(job_service.execute)
            object.__setattr__(self, "job_service", job_service)
