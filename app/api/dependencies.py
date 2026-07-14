"""Explicit dependency container for the Flask app.

`create_app` (app_factory.py) requires an AppDependencies instance rather
than constructing adapters from environment variables internally: tests
build one from fakes, `wsgi.py` builds one from real adapters. Keeping
construction outside the factory means the HTTP layer can be tested
without a live PostgreSQL, GROBID, or embedding model.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.indexing.document_deleter import DocumentDeleter
from app.application.indexing.indexing_pipeline import IndexingPipeline
from app.application.ranking.plagiarism_scorer import PlagiarismScorer
from app.application.ranking.reranker import Reranker
from app.application.search.search_pipeline import SearchPipeline
from app.domain.ports.chunk_repository import ChunkRepository
from app.domain.ports.document_repository import DocumentRepository
from app.domain.ports.language_detector import LanguageDetector
from app.domain.ports.topic_classifier import TopicClassifier
from app.domain.ports.vector_index_repository import VectorIndexRepository


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
