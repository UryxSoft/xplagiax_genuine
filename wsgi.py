"""Gunicorn entrypoint: wires real adapters and exposes the Flask app.

Not exercised by the test suite (needs a live PostgreSQL, a downloaded
embedding model, a TurboVec index file, and optionally a running GROBID
service) -- tests build AppDependencies from fakes instead
(tests/integration/test_search_api.py). This module is the actual
production wiring.

Sessions are request-scoped: repositories hold a scoped_session proxy and
Flask's teardown_appcontext calls remove() after every request, so a
multi-threaded or multi-request worker never leaks one request's identity
map or failed transaction into the next.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from app.api.app_factory import create_app
from app.api.dependencies import AppDependencies
from app.application.indexing.document_deleter import DocumentDeleter
from app.application.indexing.indexing_pipeline import IndexingPipeline
from app.application.ranking.plagiarism_scorer import PlagiarismScorer
from app.application.ranking.reranker import Reranker
from app.application.search.candidate_filter import CandidateFilter
from app.application.search.result_aggregator import ResultAggregator
from app.application.search.search_pipeline import SearchPipeline
from app.config.app_settings import AppSettings
from app.infrastructure.chunking.hybrid_chunker import HybridChunker
from app.infrastructure.chunking.word_token_counter import WordTokenCounter
from app.infrastructure.embeddings.e5_large_adapter import E5LargeAdapter
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


def _build_embedding_model(settings: AppSettings):
    if settings.embedding_backend == "onnx":
        from app.infrastructure.embeddings.onnx_embedding_adapter import OnnxEmbeddingAdapter

        return OnnxEmbeddingAdapter(
            model_dir=settings.onnx_model_dir,
            model_filename=settings.onnx_model_filename,
            batch_size=settings.embedding_batch_size,
        )
    return E5LargeAdapter(
        model_name=settings.embedding_model_name,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
    )


def _build_search_cache(settings: AppSettings):
    if settings.redis_url:
        import redis

        from app.infrastructure.cache.redis_search_cache import RedisSearchCache

        return RedisSearchCache(
            redis.Redis.from_url(settings.redis_url),
            ttl_seconds=settings.search_cache_ttl_seconds,
        )
    from app.infrastructure.cache.in_memory_search_cache import InMemorySearchCache

    return InMemorySearchCache(
        max_entries=settings.search_cache_max_entries,
        ttl_seconds=float(settings.search_cache_ttl_seconds),
    )


def build_dependencies(
    settings: AppSettings | None = None,
) -> tuple[AppDependencies, scoped_session]:
    settings = settings or AppSettings()

    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    session = scoped_session(sessionmaker(bind=engine))

    document_repository = SqlAlchemyDocumentRepository(session)
    chunk_repository = SqlAlchemyChunkRepository(session)

    embedding_model = _build_embedding_model(settings)

    vector_index = TurboVecRepository(
        dimension=embedding_model.dimension,
        bit_width=settings.turbovec_bit_width,
        index_path=settings.turbovec_index_path,
    )

    language_detector = LangDetectAdapter()
    topic_classifier = EmbeddingCentroidTopicClassifier.from_seed_texts(embedding_model, _TOPIC_SEED_TEXTS)

    chunker = HybridChunker(
        WordTokenCounter(),
        min_tokens=settings.chunk_min_tokens,
        max_tokens=settings.chunk_max_tokens,
        overlap_ratio=settings.chunk_overlap_ratio,
    )
    candidate_filter = CandidateFilter(
        document_repository, chunk_repository, settings.topic_confidence_threshold
    )
    result_aggregator = ResultAggregator(chunk_repository)

    search_pipeline = SearchPipeline(
        chunker=chunker,
        embedding_model=embedding_model,
        language_detector=language_detector,
        topic_classifier=topic_classifier,
        candidate_filter=candidate_filter,
        vector_index=vector_index,
        result_aggregator=result_aggregator,
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
        search_cache=_build_search_cache(settings),
    )
    return dependencies, session


_dependencies, _session_scope = build_dependencies()
app = create_app(_dependencies)


@app.teardown_appcontext
def _remove_request_session(_exc: BaseException | None) -> None:
    _session_scope.remove()
