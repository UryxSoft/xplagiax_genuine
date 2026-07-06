from app.application.search.result_aggregator import ResultAggregator
from app.domain.entities.chunk import Chunk
from app.domain.value_objects.search_hit import SearchHit
from app.domain.value_objects.token_span import TokenSpan


class _FakeChunkRepository:
    def __init__(self, chunks: list[Chunk]) -> None:
        self._by_id = {c.id: c for c in chunks}

    def by_ids(self, chunk_ids: list[int]) -> list[Chunk]:
        return [self._by_id[i] for i in chunk_ids if i in self._by_id]


def _chunk(chunk_id: int, document_id: str) -> Chunk:
    return Chunk(id=chunk_id, document_id=document_id, text="x", span=TokenSpan(start=0, end=10), order=0)


def test_empty_hits_returns_empty_list() -> None:
    aggregator = ResultAggregator(_FakeChunkRepository([]))
    assert aggregator.aggregate([]) == []


def test_groups_hits_by_document() -> None:
    chunks = [_chunk(1, "doc-a"), _chunk(2, "doc-a"), _chunk(3, "doc-b")]
    aggregator = ResultAggregator(_FakeChunkRepository(chunks))

    hits = [
        SearchHit(chunk_id=1, score=0.9),
        SearchHit(chunk_id=2, score=0.7),
        SearchHit(chunk_id=3, score=0.95),
    ]
    results = aggregator.aggregate(hits)

    by_doc = {r.document_id: r for r in results}
    assert by_doc["doc-a"].chunk_count == 2
    assert by_doc["doc-a"].max_score == 0.9
    assert by_doc["doc-a"].average_score == 0.8
    assert by_doc["doc-b"].chunk_count == 1


def test_results_sorted_by_max_score_descending() -> None:
    chunks = [_chunk(1, "doc-a"), _chunk(2, "doc-b")]
    aggregator = ResultAggregator(_FakeChunkRepository(chunks))

    hits = [SearchHit(chunk_id=1, score=0.5), SearchHit(chunk_id=2, score=0.99)]
    results = aggregator.aggregate(hits)

    assert [r.document_id for r in results] == ["doc-b", "doc-a"]


def test_deduplicates_repeated_chunk_hits_keeping_best_score() -> None:
    chunks = [_chunk(1, "doc-a")]
    aggregator = ResultAggregator(_FakeChunkRepository(chunks))

    # same chunk hit twice (e.g. two overlapping query segments both matched it)
    hits = [SearchHit(chunk_id=1, score=0.6), SearchHit(chunk_id=1, score=0.85)]
    results = aggregator.aggregate(hits)

    assert len(results) == 1
    assert results[0].chunk_count == 1
    assert results[0].best_hit.score == 0.85


def test_best_hit_is_the_highest_scoring_chunk_in_document() -> None:
    chunks = [_chunk(1, "doc-a"), _chunk(2, "doc-a")]
    aggregator = ResultAggregator(_FakeChunkRepository(chunks))

    hits = [SearchHit(chunk_id=1, score=0.3), SearchHit(chunk_id=2, score=0.99)]
    results = aggregator.aggregate(hits)

    assert results[0].best_hit.chunk_id == 2


def test_unknown_chunk_id_is_skipped_defensively() -> None:
    aggregator = ResultAggregator(_FakeChunkRepository([_chunk(1, "doc-a")]))

    hits = [SearchHit(chunk_id=1, score=0.5), SearchHit(chunk_id=999, score=0.99)]
    results = aggregator.aggregate(hits)

    assert len(results) == 1
    assert results[0].document_id == "doc-a"
