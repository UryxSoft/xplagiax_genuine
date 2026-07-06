"""End-to-end search orchestration (docs/ARCHITECTURE.md sect 11), up to
per-document aggregation. Reranking and the composite plagiarism score
(minhash/simhash/entities/exact-match) are the Ranking sprint's concern and
are not part of this pipeline.
"""

from __future__ import annotations

from app.application.search.candidate_filter import CandidateFilter
from app.application.search.result_aggregator import ResultAggregator
from app.domain.ports.embedding_model import EmbeddingModel
from app.domain.ports.language_detector import LanguageDetector
from app.domain.ports.topic_classifier import TopicClassifier
from app.domain.ports.vector_index_repository import VectorIndexRepository
from app.domain.value_objects.match_result import MatchResult
from app.infrastructure.chunking.hybrid_chunker import HybridChunker

DEFAULT_TOP_K_PER_SEGMENT = 10


class SearchPipeline:
    def __init__(
        self,
        chunker: HybridChunker,
        embedding_model: EmbeddingModel,
        language_detector: LanguageDetector,
        topic_classifier: TopicClassifier,
        candidate_filter: CandidateFilter,
        vector_index: VectorIndexRepository,
        result_aggregator: ResultAggregator,
        top_k_per_segment: int = DEFAULT_TOP_K_PER_SEGMENT,
    ) -> None:
        self._chunker = chunker
        self._embedding_model = embedding_model
        self._language_detector = language_detector
        self._topic_classifier = topic_classifier
        self._candidate_filter = candidate_filter
        self._vector_index = vector_index
        self._aggregator = result_aggregator
        self._top_k_per_segment = top_k_per_segment

    def search(self, text: str, tenant_id: str) -> list[MatchResult]:
        segments = self._chunker.chunk(text)
        if not segments:
            return []

        language = self._language_detector.detect(text)
        topic = self._topic_classifier.classify(text)
        allowlist = self._candidate_filter.build_allowlist(tenant_id, language, topic)

        if allowlist is not None and len(allowlist) == 0:
            return []  # filter matched no candidates: nothing to search

        all_hits = []
        for segment in segments:
            query_vector = self._embedding_model.embed_query(segment.text)
            hits = self._vector_index.search(
                query_vector, k=self._top_k_per_segment, allowlist=allowlist
            )
            all_hits.extend(hits)

        return self._aggregator.aggregate(all_hits)
