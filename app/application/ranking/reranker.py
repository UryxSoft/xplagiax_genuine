"""Computes the raw rerank signals for one document match (ADR sect 12).

embedding_similarity reuses MatchResult.max_score directly: it is already
the best chunk-level cosine similarity TurboVec returned for this
document (e5 output is L2-normalized, so inner product is cosine), so
recomputing it here would be redundant work over the same vectors.
"""

from __future__ import annotations

from app.domain.entities.document import Document
from app.domain.ports.chunk_repository import ChunkRepository
from app.domain.value_objects.language import Language
from app.domain.value_objects.match_result import MatchResult
from app.domain.value_objects.rerank_signals import RerankSignals
from app.domain.value_objects.topic import Topic
from app.infrastructure.dedup.exact_match import exact_ngram_overlap
from app.infrastructure.dedup.minhash_similarity import minhash_similarity
from app.infrastructure.dedup.simhash_similarity import simhash_similarity
from app.infrastructure.metadata.institution_normalizer import InstitutionNormalizer
from app.infrastructure.parsers.institution_fallback import guess_institution


class Reranker:
    def __init__(
        self,
        chunk_repository: ChunkRepository,
        institution_normalizer: InstitutionNormalizer | None = None,
    ) -> None:
        self._chunks = chunk_repository
        self._institution_normalizer = institution_normalizer or InstitutionNormalizer()

    def compute_signals(
        self,
        match: MatchResult,
        query_text: str,
        query_language: Language | None,
        query_topic: Topic | None,
        document: Document,
    ) -> RerankSignals:
        matched_chunks = self._chunks.by_ids([hit.chunk_id for hit in match.chunk_hits])
        candidate_text = " ".join(chunk.text for chunk in matched_chunks)

        return RerankSignals(
            embedding=match.max_score,
            topic=self._categorical_match(query_topic.domain if query_topic else None, document.topic.domain if document.topic else None),
            language=self._categorical_match(query_language.code if query_language else None, document.language.code if document.language else None),
            minhash=minhash_similarity(query_text, candidate_text) if candidate_text else None,
            simhash=simhash_similarity(query_text, candidate_text) if candidate_text else None,
            entity=self._entity_match(query_text, document),
            exact=exact_ngram_overlap(query_text, candidate_text) if candidate_text else None,
        )

    @staticmethod
    def _categorical_match(query_value: str | None, document_value: str | None) -> float | None:
        if query_value is None or document_value is None:
            return None
        return 1.0 if query_value == document_value else 0.0

    def _entity_match(self, query_text: str, document: Document) -> float | None:
        if document.bibliography.institution is None:
            return None

        raw_query_institution = guess_institution(query_text)
        if raw_query_institution is None:
            return None

        normalized_query_institution = self._institution_normalizer.normalize(raw_query_institution)
        return 1.0 if normalized_query_institution == document.bibliography.institution else 0.0
