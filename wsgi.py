"""Gunicorn entrypoint: wires real adapters and exposes the Flask app.

Not exercised by the test suite (needs a live PostgreSQL, a downloaded
e5-large model, a TurboVec index file, and optionally a running GROBID
service) -- tests build AppDependencies from fakes instead
(tests/integration/test_search_api.py). This module is the actual
production wiring.

Simplification: repositories share one long-lived SQLAlchemy Session per
worker process rather than a request-scoped session (Flask
teardown_appcontext). Acceptable for a single gunicorn worker handling
requests sequentially; a multi-threaded worker class would need proper
per-request session scoping before this is production-hardened.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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


def build_dependencies(settings: AppSettings | None = None) -> AppDependencies:
    settings = settings or AppSettings()

    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    document_repository = SqlAlchemyDocumentRepository(session)
    chunk_repository = SqlAlchemyChunkRepository(session)

    embedding_model = E5LargeAdapter(
        model_name=settings.embedding_model_name,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
    )

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

    return AppDependencies(
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
    )


app = create_app(build_dependencies())
