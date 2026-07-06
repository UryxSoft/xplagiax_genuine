"""Groups, deduplicates and fuses chunk-level hits into per-document matches
(docs/ARCHITECTURE.md sect 11: "Agrupar + deduplicar por documento").

Chunk overlap (RF-05, 20%) and multiple query segments both can produce the
same chunk_id more than once across the hit list; only the best score per
chunk is kept before grouping (docs/RESEARCH.md #4).
"""

from __future__ import annotations

from app.domain.ports.chunk_repository import ChunkRepository
from app.domain.value_objects.match_result import MatchResult
from app.domain.value_objects.search_hit import SearchHit


class ResultAggregator:
    def __init__(self, chunk_repository: ChunkRepository) -> None:
        self._chunks = chunk_repository

    def aggregate(self, hits: list[SearchHit]) -> list[MatchResult]:
        if not hits:
            return []

        best_by_chunk = self._dedupe_best_per_chunk(hits)
        doc_id_by_chunk = self._resolve_document_ids(list(best_by_chunk.keys()))

        grouped: dict[str, list[SearchHit]] = {}
        for chunk_id, hit in best_by_chunk.items():
            document_id = doc_id_by_chunk.get(chunk_id)
            if document_id is None:
                continue  # chunk id absent from metadata store: skip defensively
            grouped.setdefault(document_id, []).append(hit)

        results = [self._build_match_result(doc_id, doc_hits) for doc_id, doc_hits in grouped.items()]
        results.sort(key=lambda r: r.max_score, reverse=True)
        return results

    @staticmethod
    def _dedupe_best_per_chunk(hits: list[SearchHit]) -> dict[int, SearchHit]:
        best: dict[int, SearchHit] = {}
        for hit in hits:
            current = best.get(hit.chunk_id)
            if current is None or hit.score > current.score:
                best[hit.chunk_id] = hit
        return best

    def _resolve_document_ids(self, chunk_ids: list[int]) -> dict[int, str]:
        chunks = self._chunks.by_ids(chunk_ids)
        return {chunk.id: chunk.document_id for chunk in chunks}

    @staticmethod
    def _build_match_result(document_id: str, hits: list[SearchHit]) -> MatchResult:
        ordered = tuple(sorted(hits, key=lambda h: h.score, reverse=True))
        scores = [h.score for h in ordered]
        return MatchResult(
            document_id=document_id,
            chunk_hits=ordered,
            average_score=sum(scores) / len(scores),
            max_score=max(scores),
            best_hit=ordered[0],
        )
