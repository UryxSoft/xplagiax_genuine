"""Composition root shared by the web entrypoint (wsgi.py) and the indexer
worker (app/workers/indexer_worker.py).

Not exercised by the test suite (needs a live PostgreSQL, a downloaded
embedding model and, in worker mode, Redis) -- tests build AppDependencies
from fakes instead. This module is the actual production wiring.

Topology (ADR-010 single-writer):

- index_write_mode=local (default): the web process owns the TurboVec file
  and writes synchronously; jobs run inline unless Redis is configured.
- index_write_mode=worker: web replicas hold a read-only
  HotReloadingVectorIndex over index_data_dir and every write becomes a
  Redis Streams job; the ONE indexer worker owns a VersionedIndexWriter
  (WAL + versioned snapshots) over the same directory.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from app.api.dependencies import AppDependencies
from app.application.indexing.document_deleter import DocumentDeleter
from app.application.indexing.indexing_pipeline import IndexingPipeline
from app.application.jobs.job_service import JobService
from app.application.ranking.plagiarism_scorer import PlagiarismScorer
from app.application.ranking.reranker import Reranker
from app.application.search.candidate_filter import CandidateFilter
from app.application.search.result_aggregator import ResultAggregator
from app.application.search.search_pipeline import SearchPipeline
from app.application.search.search_service import SearchService
from app.config.app_settings import AppSettings
from app.infrastructure.chunking.hybrid_chunker import HybridChunker
from app.infrastructure.chunking.word_token_counter import WordTokenCounter
from app.infrastructure.language.langdetect_adapter import LangDetectAdapter
from app.infrastructure.metadata.institution_normalizer import InstitutionNormalizer
from app.infrastructure.metadata.orm import Base
from app.infrastructure.metadata.sqlalchemy_chunk_repository import SqlAlchemyChunkRepository
from app.infrastructure.metadata.sqlalchemy_document_repository import SqlAlchemyDocumentRepository
from app.infrastructure.topic.embedding_centroid_topic_classifier import (
    EmbeddingCentroidTopicClassifier,
)
from app.infrastructure.vectorstore.turbovec_repository import TurboVecRepository

# Starter centroid seed texts. Production must replace these with
# centroids trained on a real labeled corpus per academic domain
# (docs/RESEARCH.md #4 note on EmbeddingCentroidTopicClassifier).
_TOPIC_SEED_TEXTS = {
    "Ingenieria": ["diseno de sistemas", "algoritmos y estructuras de datos", "ingenieria de software"],
    "Medicina": ["diagnostico clinico", "tratamiento farmacologico", "anatomia humana"],
    "Derecho": ["derecho civil", "jurisprudencia constitucional", "codigo penal"],
    "Economia": ["politica monetaria", "mercados financieros", "microeconomia"],
}


def build_embedding_model(settings: AppSettings):
    if settings.embedding_backend == "onnx":
        from app.infrastructure.embeddings.onnx_embedding_adapter import OnnxEmbeddingAdapter

        return OnnxEmbeddingAdapter(
            model_dir=settings.onnx_model_dir,
            model_filename=settings.onnx_model_filename,
            batch_size=settings.embedding_batch_size,
        )
    from app.infrastructure.embeddings.e5_large_adapter import E5LargeAdapter

    return E5LargeAdapter(
        model_name=settings.embedding_model_name,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
    )


def build_search_cache(settings: AppSettings):
    if settings.redis_url:
        from app.infrastructure.cache.redis_search_cache import RedisSearchCache

        return RedisSearchCache(
            _redis_client(settings), ttl_seconds=settings.search_cache_ttl_seconds
        )
    from app.infrastructure.cache.in_memory_search_cache import InMemorySearchCache

    return InMemorySearchCache(
        max_entries=settings.search_cache_max_entries,
        ttl_seconds=float(settings.search_cache_ttl_seconds),
    )


def _redis_client(settings: AppSettings):
    import redis

    return redis.Redis.from_url(settings.redis_url)


def _turbovec_factory(settings: AppSettings, dimension: int):
    def factory(path: Path | None) -> TurboVecRepository:
        return TurboVecRepository(
            dimension=dimension,
            bit_width=settings.turbovec_bit_width,
            index_path=path,
        )

    return factory


def _build_session(settings: AppSettings) -> scoped_session:
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    return scoped_session(sessionmaker(bind=engine))


def build_web_dependencies(
    settings: AppSettings | None = None,
) -> tuple[AppDependencies, scoped_session]:
    settings = settings or AppSettings()
    session = _build_session(settings)

    document_repository = SqlAlchemyDocumentRepository(session)
    chunk_repository = SqlAlchemyChunkRepository(session)
    embedding_model = build_embedding_model(settings)

    worker_mode = settings.index_write_mode == "worker"
    if worker_mode:
        if not settings.redis_url:
            raise ValueError("index_write_mode=worker requires redis_url")
        from app.infrastructure.persistence.hot_reloading_index import HotReloadingVectorIndex

        vector_index = HotReloadingVectorIndex(
            _turbovec_factory(settings, embedding_model.dimension), settings.index_data_dir
        )
    else:
        vector_index = TurboVecRepository(
            dimension=embedding_model.dimension,
            bit_width=settings.turbovec_bit_width,
            index_path=settings.turbovec_index_path,
        )

    language_detector = LangDetectAdapter()
    topic_classifier = EmbeddingCentroidTopicClassifier.from_seed_texts(
        embedding_model, _TOPIC_SEED_TEXTS
    )
    chunker = HybridChunker(
        WordTokenCounter(),
        min_tokens=settings.chunk_min_tokens,
        max_tokens=settings.chunk_max_tokens,
        overlap_ratio=settings.chunk_overlap_ratio,
    )
    search_pipeline = SearchPipeline(
        chunker=chunker,
        embedding_model=embedding_model,
        language_detector=language_detector,
        topic_classifier=topic_classifier,
        candidate_filter=CandidateFilter(
            document_repository, chunk_repository, settings.topic_confidence_threshold
        ),
        vector_index=vector_index,
        result_aggregator=ResultAggregator(chunk_repository),
        top_k_per_segment=settings.search_top_k_per_segment,
    )
    reranker = Reranker(chunk_repository, InstitutionNormalizer())
    plagiarism_scorer = PlagiarismScorer()

    indexing_pipeline = IndexingPipeline(
        chunker=chunker,
        embedding_model=embedding_model,
        language_detector=language_detector,
        topic_classifier=topic_classifier,
        vector_index=vector_index,
        document_repository=document_repository,
        chunk_repository=chunk_repository,
    )
    document_deleter = DocumentDeleter(document_repository, chunk_repository, vector_index)
    search_cache = build_search_cache(settings)

    job_service = None
    if settings.redis_url:
        from app.infrastructure.jobs.redis_jobs import RedisJobRepository, RedisStreamJobQueue

        search_service = SearchService(
            search_pipeline=search_pipeline,
            language_detector=language_detector,
            topic_classifier=topic_classifier,
            document_repository=document_repository,
            chunk_repository=chunk_repository,
            reranker=reranker,
            plagiarism_scorer=plagiarism_scorer,
        )
        client = _redis_client(settings)
        job_service = JobService(
            job_repository=RedisJobRepository(client, ttl_seconds=settings.job_ttl_seconds),
            job_queue=RedisStreamJobQueue(client, stream_key=settings.jobs_stream_key),
            indexing_pipeline=indexing_pipeline,
            search_service=search_service,
            document_deleter=document_deleter,
            search_cache=search_cache,
        )

    dependencies = AppDependencies(
        document_repository=document_repository,
        chunk_repository=chunk_repository,
        language_detector=language_detector,
        topic_classifier=topic_classifier,
        search_pipeline=search_pipeline,
        reranker=reranker,
        plagiarism_scorer=plagiarism_scorer,
        indexing_pipeline=indexing_pipeline,
        document_deleter=document_deleter,
        vector_index=vector_index,
        search_cache=search_cache,
        job_service=job_service,
        worker_mode=worker_mode,
    )
    return dependencies, session


def build_worker(settings: AppSettings | None = None):
    """Wires the single-writer indexer worker: returns (job_service, consumer)."""
    settings = settings or AppSettings()
    if not settings.redis_url:
        raise ValueError("the indexer worker requires redis_url")

    from app.infrastructure.jobs.redis_jobs import (
        RedisJobRepository,
        RedisStreamJobConsumer,
        RedisStreamJobQueue,
    )
    from app.infrastructure.persistence.versioned_index_writer import VersionedIndexWriter

    session = _build_session(settings)
    document_repository = SqlAlchemyDocumentRepository(session)
    chunk_repository = SqlAlchemyChunkRepository(session)
    embedding_model = build_embedding_model(settings)

    vector_index = VersionedIndexWriter(
        _turbovec_factory(settings, embedding_model.dimension),
        settings.index_data_dir,
        checkpoint_every_ops=settings.index_checkpoint_every_ops,
    )

    language_detector = LangDetectAdapter()
    topic_classifier = EmbeddingCentroidTopicClassifier.from_seed_texts(
        embedding_model, _TOPIC_SEED_TEXTS
    )
    chunker = HybridChunker(
        WordTokenCounter(),
        min_tokens=settings.chunk_min_tokens,
        max_tokens=settings.chunk_max_tokens,
        overlap_ratio=settings.chunk_overlap_ratio,
    )
    indexing_pipeline = IndexingPipeline(
        chunker=chunker,
        embedding_model=embedding_model,
        language_detector=language_detector,
        topic_classifier=topic_classifier,
        vector_index=vector_index,
        document_repository=document_repository,
        chunk_repository=chunk_repository,
        # the writer checkpoints by ops count; snapshot-per-document would
        # rewrite the whole index file on every job
        snapshot_after_write=False,
    )
    search_pipeline = SearchPipeline(
        chunker=chunker,
        embedding_model=embedding_model,
        language_detector=language_detector,
        topic_classifier=topic_classifier,
        candidate_filter=CandidateFilter(
            document_repository, chunk_repository, settings.topic_confidence_threshold
        ),
        vector_index=vector_index,
        result_aggregator=ResultAggregator(chunk_repository),
        top_k_per_segment=settings.search_top_k_per_segment,
    )
    search_service = SearchService(
        search_pipeline=search_pipeline,
        language_detector=language_detector,
        topic_classifier=topic_classifier,
        document_repository=document_repository,
        chunk_repository=chunk_repository,
        reranker=Reranker(chunk_repository, InstitutionNormalizer()),
        plagiarism_scorer=PlagiarismScorer(),
    )
    document_deleter = DocumentDeleter(
        document_repository, chunk_repository, vector_index, snapshot_after_write=False
    )

    client = _redis_client(settings)
    job_service = JobService(
        job_repository=RedisJobRepository(client, ttl_seconds=settings.job_ttl_seconds),
        job_queue=RedisStreamJobQueue(client, stream_key=settings.jobs_stream_key),
        indexing_pipeline=indexing_pipeline,
        search_service=search_service,
        document_deleter=document_deleter,
        search_cache=build_search_cache(settings),
    )
    consumer = RedisStreamJobConsumer(
        client,
        stream_key=settings.jobs_stream_key,
        group=settings.jobs_consumer_group,
        consumer_name=settings.jobs_consumer_name,
    )
    return job_service, consumer
